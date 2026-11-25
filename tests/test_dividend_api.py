"""股利自動推算與一鍵入帳 API、原子入帳與 Migration 契約測試（TC-07、TC-08）。"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from services.api.app import create_app
from services.api.dividend_engine import compute_dividend_draft
from services.api.repository import ConflictError, NotFoundError, PostgresWorkspaceRepository

OWNER_A = UUID("00000000-0000-0000-0000-0000000000a1")
OWNER_B = UUID("00000000-0000-0000-0000-0000000000b2")
ROOT = Path(__file__).parents[1]


class _FakeCursor:
    def __init__(self, rows=None):
        self._rows = list(rows or [])

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)


class _InMemoryLedgerDB:
    """記憶體交易式模擬 DB，讓真實 PostgresWorkspaceRepository 邏輯可於無外部 PG 環境執行驗證。"""

    def __init__(self) -> None:
        self.users = {
            OWNER_A: {"user_id": OWNER_A, "ledger_version": 1, "change_version": 1},
            OWNER_B: {"user_id": OWNER_B, "ledger_version": 0, "change_version": 0},
        }
        self.ledger_events: list[dict] = [
            {
                "event_id": uuid4(),
                "user_id": OWNER_A,
                "ledger_version": 1,
                "event_action": "ORIGINAL",
                "event_type": "BUY",
                "trade_date": date(2026, 7, 1),
                "symbol": "2884",
                "shares": Decimal("2000"),
                "price": Decimal("25"),
                "cash_amount": None,
                "fee": Decimal("0"),
                "tax": Decimal("0"),
                "currency": "TWD",
                "memo": None,
            }
        ]
        self.corporate_actions: list[dict] = [
            {
                "action_id": uuid4(),
                "symbol": "2884",
                "market": "TWSE",
                "security_type": "financial",
                "ex_date": date(2026, 8, 1),
                "payment_date": date(2026, 8, 28),
                "action_type": "CASH_DIVIDEND",
                "cash_dividend_per_share": Decimal("1.2"),
                "stock_dividend_ratio": Decimal("0"),
                "par_value": Decimal("10"),
                "source_name": "TWSE_TWT48U",
                "source_updated_at": datetime(2026, 7, 20, tzinfo=timezone.utc),
            },
            {
                "action_id": uuid4(),
                "symbol": "2884",
                "market": "TWSE",
                "security_type": "financial",
                "ex_date": date(2026, 8, 1),
                "payment_date": date(2026, 8, 28),
                "action_type": "STOCK_DIVIDEND",
                "cash_dividend_per_share": Decimal("0"),
                "stock_dividend_ratio": Decimal("0.1"),
                "par_value": Decimal("10"),
                "source_name": "TWSE_TWT48U",
                "source_updated_at": datetime(2026, 7, 20, tzinfo=timezone.utc),
            },
        ]
        self.drafts: dict[UUID, dict] = {}
        self.changes: list[dict] = []
        self.refreshed_users: list[UUID] = []
        self.supplement_synced = 0

    def snapshot(self):
        return (
            deepcopy(self.users),
            deepcopy(self.ledger_events),
            deepcopy(self.drafts),
            deepcopy(self.changes),
            list(self.refreshed_users),
            self.supplement_synced,
        )

    def restore(self, snap):
        (
            self.users,
            self.ledger_events,
            self.drafts,
            self.changes,
            self.refreshed_users,
            self.supplement_synced,
        ) = snap

    def execute(self, sql: str, params=()):
        q = " ".join(sql.split())
        if q.startswith("SELECT pg_advisory_xact_lock"):
            return _FakeCursor([{"ok": 1}])
        if q.startswith("SELECT to_regclass('private.pending_dividend_events')"):
            return _FakeCursor([{"rel": "private.pending_dividend_events"}])
        if q.startswith("SELECT COALESCE(MAX(ledger_version),0) AS version FROM private.ledger_events"):
            uid = params[0]
            ver = max((r["ledger_version"] for r in self.ledger_events if r["user_id"] == uid), default=0)
            return _FakeCursor([{"version": ver}])
        if q.startswith("UPDATE private.users SET ledger_version=ledger_version+1"):
            uid = params[0]
            self.users[uid]["ledger_version"] += 1
            return _FakeCursor([{"ledger_version": self.users[uid]["ledger_version"]}])
        if q.startswith("UPDATE private.users SET change_version=change_version+1"):
            uid = params[0]
            self.users[uid]["change_version"] += 1
            return _FakeCursor([{"change_version": self.users[uid]["change_version"]}])
        if q.startswith("INSERT INTO private.change_log"):
            self.changes.append({"user_id": params[0], "change_version": params[1], "kind": params[2], "entity_id": params[3]})
            return _FakeCursor()
        if q.startswith("SELECT private.refresh_current_positions"):
            self.refreshed_users.append(params[0])
            return _FakeCursor()
        if q.startswith("SELECT control.sync_stock_supplement_demand"):
            self.supplement_synced += 1
            return _FakeCursor()
        if q.startswith("SELECT event_id, user_id, ledger_version, event_action, event_type"):
            uid = params[0]
            rows = [r for r in self.ledger_events if r["user_id"] == uid]
            return _FakeCursor(sorted(rows, key=lambda r: (r["trade_date"], r["ledger_version"])))
        if q.startswith("SELECT * FROM control.corporate_actions WHERE symbol = ANY(%s) AND ex_date >= %s"):
            symbols, from_d = set(params[0]), params[1]
            rows = [r for r in self.corporate_actions if r["symbol"] in symbols and r["ex_date"] >= from_d]
            return _FakeCursor(rows)
        if q.startswith("SELECT * FROM control.corporate_actions WHERE symbol = ANY(%s)"):
            symbols = set(params[0])
            return _FakeCursor([r for r in self.corporate_actions if r["symbol"] in symbols])
        if q.startswith("SELECT * FROM private.pending_dividend_events WHERE user_id = %s AND status = 'STALE'"):
            uid = params[0]
            return _FakeCursor([r for r in self.drafts.values() if r["user_id"] == uid and r["status"] == "STALE"])
        if q.startswith("SELECT * FROM private.pending_dividend_events WHERE user_id = %s AND symbol = ANY(%s)"):
            uid, symbols = params[0], set(params[1])
            return _FakeCursor([r for r in self.drafts.values() if r["user_id"] == uid and r["symbol"] in symbols])
        if q.startswith("SELECT * FROM private.pending_dividend_events WHERE user_id = %s AND status = %s"):
            uid, status_val = params[0], params[1]
            rows = [r for r in self.drafts.values() if r["user_id"] == uid and r["status"] == status_val]
            if len(params) > 2:
                rows = [r for r in rows if r["symbol"] == params[2]]
            return _FakeCursor(sorted(rows, key=lambda r: (r["ex_date"], r["symbol"], r["action_type"]), reverse=True))
        if q.startswith("SELECT COUNT(*) AS cnt FROM private.pending_dividend_events WHERE user_id = %s AND status = 'PENDING'"):
            uid = params[0]
            return _FakeCursor([{"cnt": sum(1 for r in self.drafts.values() if r["user_id"] == uid and r["status"] == "PENDING")}])
        if q.startswith("INSERT INTO private.pending_dividend_events"):
            import json as _json
            draft_id = UUID(str(params[0]))
            row = {
                "draft_id": draft_id,
                "user_id": params[1],
                "symbol": params[2],
                "company_name": params[3],
                "security_type": params[4],
                "action_type": params[5],
                "ex_date": params[6],
                "payment_date": params[7],
                "eligible_shares": params[8],
                "rate_per_share": params[9],
                "gross_cash_amount": params[10],
                "estimated_remit_fee": params[11],
                "estimated_nhi_fee": params[12],
                "net_cash_amount": params[13],
                "estimated_stock_shares": params[14],
                "fractional_shares": params[15],
                "confirmed_stock_shares": params[16],
                "status": params[17],
                "warnings": _json.loads(params[18]),
                "ledger_version_at_calc": params[19],
                "confirmed_trade_id": params[20],
                "user_note": params[21],
            }
            existing = next(
                (
                    d for d in self.drafts.values()
                    if d["user_id"] == row["user_id"]
                    and d["symbol"] == row["symbol"]
                    and d["ex_date"] == row["ex_date"]
                    and d["action_type"] == row["action_type"]
                ),
                None,
            )
            if existing is None:
                self.drafts[draft_id] = row
            elif existing["status"] not in {"CONFIRMED", "DISMISSED"}:
                row["draft_id"] = existing["draft_id"]
                self.drafts[existing["draft_id"]] = row
            return _FakeCursor()
        if q.startswith("SELECT * FROM private.pending_dividend_events WHERE user_id = %s AND draft_id = %s"):
            uid, did = params[0], UUID(str(params[1]))
            row = self.drafts.get(did)
            return _FakeCursor([row] if row and row["user_id"] == uid else [])
        if q.startswith("UPDATE private.pending_dividend_events SET estimated_remit_fee = %s"):
            remit, nhi, net_cash, note, uid, did = params
            row = self.drafts[UUID(str(did))]
            assert row["user_id"] == uid
            row.update(
                estimated_remit_fee=remit,
                estimated_nhi_fee=nhi,
                net_cash_amount=net_cash,
                user_note=note if note is not None else row.get("user_note"),
            )
            return _FakeCursor([row])
        if q.startswith("UPDATE private.pending_dividend_events SET confirmed_stock_shares = %s"):
            shares, note, uid, did = params
            row = self.drafts[UUID(str(did))]
            assert row["user_id"] == uid
            row.update(
                confirmed_stock_shares=shares,
                user_note=note if note is not None else row.get("user_note"),
            )
            return _FakeCursor([row])
        if q.startswith("SELECT * FROM private.pending_dividend_events WHERE user_id = %s AND draft_id = ANY(%s)"):
            uid, dids = params[0], {UUID(str(x)) for x in params[1]}
            rows = [r for r in self.drafts.values() if r["user_id"] == uid and r["draft_id"] in dids]
            return _FakeCursor(sorted(rows, key=lambda r: (r["ex_date"], r["symbol"], r["action_type"])))
        if q.startswith("SELECT draft_id, status FROM private.pending_dividend_events WHERE user_id = %s AND draft_id = ANY(%s)"):
            uid, dids = params[0], {UUID(str(x)) for x in params[1]}
            return _FakeCursor([{"draft_id": r["draft_id"], "status": r["status"]} for r in self.drafts.values() if r["user_id"] == uid and r["draft_id"] in dids])
        if q.startswith("UPDATE private.pending_dividend_events SET status='STALE'"):
            uid, did = params[0], UUID(str(params[1]))
            self.drafts[did]["status"] = "STALE"
            return _FakeCursor()
        if q.startswith("INSERT INTO private.ledger_events"):
            if "'CASH_DIV'" in q:
                row = {
                    "event_id": params[0],
                    "user_id": params[1],
                    "ledger_version": params[2],
                    "event_action": "ORIGINAL",
                    "event_type": "CASH_DIV",
                    "trade_date": params[3],
                    "symbol": params[4],
                    "shares": None,
                    "price": None,
                    "cash_amount": params[5],
                    "fee": params[6],
                    "tax": params[7],
                    "currency": "TWD",
                    "memo": params[8],
                    "idempotency_key": params[9],
                }
            else:
                row = {
                    "event_id": params[0],
                    "user_id": params[1],
                    "ledger_version": params[2],
                    "event_action": "ORIGINAL",
                    "event_type": "STOCK_DIV",
                    "trade_date": params[3],
                    "symbol": params[4],
                    "shares": params[5],
                    "price": None,
                    "cash_amount": None,
                    "fee": Decimal("0"),
                    "tax": Decimal("0"),
                    "currency": "TWD",
                    "memo": params[6],
                    "idempotency_key": params[7],
                }
            self.ledger_events.append(row)
            return _FakeCursor([row])
        if q.startswith("UPDATE private.pending_dividend_events SET status = 'CONFIRMED'"):
            eid, uid, did = params
            row = self.drafts[UUID(str(did))]
            assert row["user_id"] == uid
            row["status"] = "CONFIRMED"
            row["confirmed_trade_id"] = eid
            return _FakeCursor()
        if q.startswith("UPDATE private.pending_dividend_events SET status = 'DISMISSED'"):
            reason, uid, dids = params[0], params[1], {UUID(str(x)) for x in params[2]}
            for did in dids:
                if self.drafts[did]["user_id"] == uid:
                    self.drafts[did]["status"] = "DISMISSED"
                    if reason is not None:
                        self.drafts[did]["user_note"] = reason
            return _FakeCursor()
        raise AssertionError(f"Unexpected SQL in test harness: {q}")


class _TestableRepository(PostgresWorkspaceRepository):
    def __init__(self) -> None:
        super().__init__("postgresql://unused")
        self.db = _InMemoryLedgerDB()

    @contextmanager
    def _connection(self):
        snap = self.db.snapshot()
        try:
            yield self.db
        except Exception:
            self.db.restore(snap)
            raise

    def resolve_user(self, sub: str, email: str) -> UUID:
        return OWNER_B if sub == "owner-b" else OWNER_A

    def stock_identities(self, symbols: set[str]) -> dict[str, dict]:
        return {
            symbol: {"symbol": symbol, "name": "玉山金", "market": "TWSE", "enabled": True, "instrument_kind": "EQUITY"}
            for symbol in symbols
        }


def _client_for(repo: _TestableRepository, sub: str = "owner-a") -> TestClient:
    claims = {
        "iss": "https://accounts.google.com",
        "aud": "user-client",
        "sub": sub,
        "email": f"{sub}@example.com",
        "email_verified": True,
        "exp": 1900000000,
    }
    app = create_app(
        repo,
        SimpleNamespace(),
        lambda _token, _audience: claims,
        audience="user-client",
        private_recalculator=SimpleNamespace(run_user=lambda *_args, **_kw: {}),
    )
    return TestClient(app, raise_server_exceptions=False)


def test_dividend_api_end_to_end_tc07_and_tc08(monkeypatch):
    monkeypatch.setenv("JANUS_STOCK_SUPPLEMENT_ENABLED", "false")
    repo = _TestableRepository()
    client_a = _client_for(repo, "owner-a")
    client_b = _client_for(repo, "owner-b")
    auth = {"Authorization": "Bearer valid"}

    # 未登入不可存取
    assert client_a.get("/api/v1/me/dividends/pending").status_code == 401

    # 1. 手動掃描產生現金與股票股利兩筆草稿
    scan_res = client_a.post("/api/v1/me/dividends/scan", json={}, headers=auth)
    assert scan_res.status_code == 200
    assert scan_res.json() == {"newly_created": 2, "recalculated": 0, "already_recorded": 0}

    pending_res = client_a.get("/api/v1/me/dividends/pending", headers=auth)
    assert pending_res.status_code == 200
    body = pending_res.json()
    assert body["pending_count"] == 2
    assert body["ledger_version"] == 1
    cash_draft = next(i for i in body["items"] if i["action_type"] == "CASH_DIVIDEND")
    stock_draft = next(i for i in body["items"] if i["action_type"] == "STOCK_DIVIDEND")

    # 2. TC-08：跨 Owner B 嘗試微調、確認或忽略 Owner A 之草稿均遭拒絕
    assert client_b.patch(
        f"/api/v1/me/dividends/pending/{cash_draft['draft_id']}",
        json={"estimated_remit_fee": "0"},
        headers=auth,
    ).status_code == 404
    assert client_b.post(
        "/api/v1/me/dividends/pending/confirm",
        json={"draft_ids": [cash_draft["draft_id"]], "expected_ledger_version": 0},
        headers=auth,
    ).status_code == 404
    assert client_b.post(
        "/api/v1/me/dividends/pending/dismiss",
        json={"draft_ids": [cash_draft["draft_id"]]},
        headers=auth,
    ).status_code == 404

    # 3. 逐筆微調：改為免匯費 0 元
    patch_res = client_a.patch(
        f"/api/v1/me/dividends/pending/{cash_draft['draft_id']}",
        json={"estimated_remit_fee": "0", "user_note": "同銀行入帳"},
        headers=auth,
    )
    assert patch_res.status_code == 200
    assert Decimal(str(patch_res.json()["net_cash_amount"])) == Decimal("2400")

    # 4. TC-07：樂觀鎖版本衝突（帶錯 expected_ledger_version=0）回傳 409 且不寫入帳本
    conflict_res = client_a.post(
        "/api/v1/me/dividends/pending/confirm",
        json={
            "draft_ids": [cash_draft["draft_id"], stock_draft["draft_id"]],
            "expected_ledger_version": 0,
        },
        headers=auth,
    )
    assert conflict_res.status_code == 409
    assert len(repo.db.ledger_events) == 1

    # 5. 正確版本一鍵批次確認入帳（現金 + 股票）
    confirm_res = client_a.post(
        "/api/v1/me/dividends/pending/confirm",
        json={
            "draft_ids": [cash_draft["draft_id"], stock_draft["draft_id"]],
            "expected_ledger_version": 1,
        },
        headers=auth,
    )
    assert confirm_res.status_code == 200
    confirm_data = confirm_res.json()
    assert confirm_data["confirmed_count"] == 2
    assert confirm_data["ledger_version"] == 3
    assert len(repo.db.ledger_events) == 3
    assert repo.db.refreshed_users == [OWNER_A]

    cash_event = next(e for e in repo.db.ledger_events if e["event_type"] == "CASH_DIV")
    stock_event = next(e for e in repo.db.ledger_events if e["event_type"] == "STOCK_DIV")
    assert cash_event["cash_amount"] == Decimal("2400")
    assert cash_event["fee"] == Decimal("0")
    assert stock_event["shares"] == Decimal("200")

    # 確認後待確認數歸零
    after = client_a.get("/api/v1/me/dividends/pending", headers=auth).json()
    assert after["pending_count"] == 0


def test_migration_080_and_allowlists_are_properly_wired():
    sql_080 = (ROOT / "infra/postgres/migrations/080_dividend_auto_ledger.sql").read_text(encoding="utf-8")
    sql_down = (ROOT / "infra/postgres/migrations/rollback/080_dividend_auto_ledger_down.sql").read_text(encoding="utf-8")
    bootstrap = (ROOT / "scripts/gcp/analysis_schema_bootstrap.py").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/serving-schema-migration-dev.yml").read_text(encoding="utf-8")
    repo_src = (ROOT / "services/api/repository.py").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS control.corporate_actions" in sql_080
    assert "stock_dividend_ratio numeric(18,8)" in sql_080
    assert "CREATE TABLE IF NOT EXISTS private.pending_dividend_events" in sql_080
    assert "UNIQUE (user_id, symbol, ex_date, action_type)" in sql_080
    assert "NOT has_table_privilege('janus_public_api', 'private.pending_dividend_events', 'SELECT')" in sql_080
    assert "INSERT INTO control.schema_migrations(version)\nVALUES ('080_dividend_auto_ledger')" in sql_080
    assert "DROP TABLE IF EXISTS private.pending_dividend_events" in sql_down
    assert "080_dividend_auto_ledger" in bootstrap
    assert "080_dividend_auto_ledger" in workflow
    assert '"pending_dividend_events"' in repo_src


def test_load_owner_ledger_events_includes_reversal_and_correction_fields():
    """回歸測試：_load_owner_ledger_events 須選取 reverses_event_id／replaces_event_id，避免 REVERSAL 帳本報 KeyError。"""
    from services.api.dividend_engine import compute_dividend_draft
    from services.api.repository import PostgresWorkspaceRepository

    captured_sql: list[str] = []

    class _StubConn:
        def execute(self, sql, params=None):
            captured_sql.append(" ".join(sql.split()))
            return _FakeCursor([])

    PostgresWorkspaceRepository._load_owner_ledger_events(_StubConn(), OWNER_A)
    assert captured_sql
    assert "reverses_event_id" in captured_sql[0]
    assert "replaces_event_id" in captured_sql[0]

    buy_1 = uuid4()
    buy_2 = uuid4()
    buy_2_corr = uuid4()
    events = [
        {
            "event_id": buy_1,
            "user_id": OWNER_A,
            "ledger_version": 1,
            "event_action": "ORIGINAL",
            "event_type": "BUY",
            "reverses_event_id": None,
            "replaces_event_id": None,
            "trade_date": date(2025, 1, 10),
            "symbol": "2330",
            "shares": Decimal("1000"),
            "price": Decimal("1000"),
            "cash_amount": Decimal("1000000"),
            "fee": Decimal("0"),
            "tax": Decimal("0"),
            "currency": "TWD",
        },
        {
            "event_id": uuid4(),
            "user_id": OWNER_A,
            "ledger_version": 2,
            "event_action": "REVERSAL",
            "event_type": "BUY",
            "reverses_event_id": buy_1,
            "replaces_event_id": None,
            "trade_date": date(2025, 1, 10),
            "symbol": "2330",
            "shares": Decimal("1000"),
            "price": Decimal("1000"),
            "cash_amount": Decimal("1000000"),
            "fee": Decimal("0"),
            "tax": Decimal("0"),
            "currency": "TWD",
        },
        {
            "event_id": buy_2,
            "user_id": OWNER_A,
            "ledger_version": 3,
            "event_action": "ORIGINAL",
            "event_type": "BUY",
            "reverses_event_id": None,
            "replaces_event_id": None,
            "trade_date": date(2025, 2, 10),
            "symbol": "2330",
            "shares": Decimal("500"),
            "price": Decimal("1000"),
            "cash_amount": Decimal("500000"),
            "fee": Decimal("0"),
            "tax": Decimal("0"),
            "currency": "TWD",
        },
        {
            "event_id": uuid4(),
            "user_id": OWNER_A,
            "ledger_version": 4,
            "event_action": "REVERSAL",
            "event_type": "BUY",
            "reverses_event_id": buy_2,
            "replaces_event_id": None,
            "trade_date": date(2025, 2, 10),
            "symbol": "2330",
            "shares": Decimal("500"),
            "price": Decimal("1000"),
            "cash_amount": Decimal("500000"),
            "fee": Decimal("0"),
            "tax": Decimal("0"),
            "currency": "TWD",
        },
        {
            "event_id": buy_2_corr,
            "user_id": OWNER_A,
            "ledger_version": 5,
            "event_action": "CORRECTION",
            "event_type": "BUY",
            "reverses_event_id": None,
            "replaces_event_id": buy_2,
            "trade_date": date(2025, 2, 10),
            "symbol": "2330",
            "shares": Decimal("2000"),
            "price": Decimal("1000"),
            "cash_amount": Decimal("2000000"),
            "fee": Decimal("0"),
            "tax": Decimal("0"),
            "currency": "TWD",
        },
    ]
    action = {
        "symbol": "2330",
        "ex_date": date(2025, 6, 12),
        "payment_date": date(2025, 7, 10),
        "action_type": "CASH_DIVIDEND",
        "cash_dividend_per_share": Decimal("4.5"),
        "stock_dividend_ratio": Decimal("0"),
        "security_type": "common_stock",
    }
    draft = compute_dividend_draft(
        user_id=OWNER_A,
        action=action,
        events=events,
        ledger_version=5,
        identity={"name": "台積電"},
    )
    assert draft is not None
    assert draft["eligible_shares"] == Decimal("2000")
    assert draft["gross_cash_amount"] == Decimal("9000")


def test_list_pending_dividends_includes_prev_and_next_month_ledger_compare():
    """驗證待確認股利清單回傳除權息日前後一個月帳本對照（且嚴格隔離不同 Owner）。"""
    repo = _TestableRepository()
    repo.db.ledger_events.extend(
        [
            {
                "event_id": uuid4(),
                "user_id": OWNER_A,
                "ledger_version": 1,
                "event_action": "ORIGINAL",
                "event_type": "BUY",
                "reverses_event_id": None,
                "replaces_event_id": None,
                "trade_date": date(2026, 7, 1),
                "symbol": "00719B",
                "shares": Decimal("30000"),
                "price": Decimal("31"),
                "cash_amount": Decimal("930000"),
                "fee": Decimal("0"),
                "tax": Decimal("0"),
                "currency": "TWD",
            },
            # 前一個月（2026-09）
            {
                "event_id": uuid4(),
                "user_id": OWNER_A,
                "ledger_version": 2,
                "event_action": "ORIGINAL",
                "event_type": "CASH_DIV",
                "reverses_event_id": None,
                "replaces_event_id": None,
                "trade_date": date(2026, 9, 25),
                "symbol": "00719B",
                "shares": None,
                "price": None,
                "cash_amount": Decimal("8090"),
                "fee": Decimal("10"),
                "tax": Decimal("0"),
                "currency": "TWD",
            },
            # 後一個月（2026-11，刻意設不同金額以免觸發自動 ALREADY_RECORDED）
            {
                "event_id": uuid4(),
                "user_id": OWNER_A,
                "ledger_version": 3,
                "event_action": "ORIGINAL",
                "event_type": "CASH_DIV",
                "reverses_event_id": None,
                "replaces_event_id": None,
                "trade_date": date(2026, 11, 18),
                "symbol": "00719B",
                "shares": None,
                "price": None,
                "cash_amount": Decimal("6000"),
                "fee": Decimal("0"),
                "tax": Decimal("0"),
                "currency": "TWD",
            },
            # 超出窗口（2026-08）不應列入
            {
                "event_id": uuid4(),
                "user_id": OWNER_A,
                "ledger_version": 4,
                "event_action": "ORIGINAL",
                "event_type": "CASH_DIV",
                "reverses_event_id": None,
                "replaces_event_id": None,
                "trade_date": date(2026, 8, 20),
                "symbol": "00719B",
                "shares": None,
                "price": None,
                "cash_amount": Decimal("7500"),
                "fee": Decimal("0"),
                "tax": Decimal("0"),
                "currency": "TWD",
            },
            # 其他 Owner（2026-10）不應洩漏
            {
                "event_id": uuid4(),
                "user_id": OWNER_B,
                "ledger_version": 1,
                "event_action": "ORIGINAL",
                "event_type": "CASH_DIV",
                "reverses_event_id": None,
                "replaces_event_id": None,
                "trade_date": date(2026, 10, 28),
                "symbol": "00719B",
                "shares": None,
                "price": None,
                "cash_amount": Decimal("99999"),
                "fee": Decimal("0"),
                "tax": Decimal("0"),
                "currency": "TWD",
            },
        ]
    )
    repo.db.corporate_actions.extend(
        [
            {
                "action_id": uuid4(),
                "symbol": "00719B",
                "market": "TWSE",
                "security_type": "etf",
                "ex_date": date(2026, 10, 22),
                "payment_date": None,
                "action_type": "CASH_DIVIDEND",
                "cash_dividend_per_share": Decimal("0.27"),
                "stock_dividend_ratio": Decimal("0"),
                "par_value": Decimal("10"),
                "source_name": "TWSE_TWT49U",
            }
        ]
    )

    repo.scan_dividends(OWNER_A)
    listed = repo.list_pending_dividends(OWNER_A, symbol="00719B")
    assert len(listed["items"]) == 1
    item = listed["items"][0]
    assert item["compare_window_label"] == "2026-09～2026-11"
    nearby = item["nearby_ledger_dividends"]
    assert [m["trade_date"] for m in nearby] == ["2026-11-18", "2026-09-25"]
    assert [m["cash_amount"] for m in nearby] == [Decimal("6000"), Decimal("8090")]
