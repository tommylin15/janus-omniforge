"""Unit and boundary tests for scoped OAuth watchlist mirror synchronization."""

from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal
import re
from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest

import services.api.app as app_module
from services.api.app import create_app
from services.api.mcp_oauth import InMemoryOAuthCodeStore, MCP_READ_SCOPES, McpOAuth, OAuthSettings
from services.api.models import WatchlistSyncIn
from services.api.repository import ConflictError, PostgresWorkspaceRepository


OWNER_A = UUID("00000000-0000-0000-0000-000000000001")
OWNER_B = UUID("00000000-0000-0000-0000-000000000002")


class _StubCursor:
    def __init__(self, rows: list[dict] | None = None):
        self._rows = list(rows or [])

    def fetchall(self):
        return list(self._rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _InMemoryWatchlistDb:
    """In-memory PostgreSQL connection double covering private.watchlist SQL contracts."""

    def __init__(self, *, eligible: set[str], etfs: set[str] | None = None, b_capacity: int | None = None):
        self.eligible = set(eligible)
        self.etfs = set(etfs or set())
        self.b_capacity = b_capacity
        self.users = {
            OWNER_A: {"user_id": OWNER_A, "change_version": 0},
            OWNER_B: {"user_id": OWNER_B, "change_version": 0},
        }
        self.watchlist: dict[tuple[UUID, str], dict] = {}
        self.mutations: dict[tuple[UUID, str], dict] = {}
        self.change_log: list[dict] = []
        self.demand_calls: list[str] = []
        self.supplement_sync_calls = 0

    def execute(self, sql: str, params=()):
        normalized = " ".join(sql.split())
        if normalized.startswith("SELECT pg_advisory_xact_lock"):
            return _StubCursor()
        if normalized.startswith("SELECT user_id FROM private.users"):
            uid = params[0]
            return _StubCursor([self.users[uid]] if uid in self.users else [])
        if normalized.startswith("SELECT kind,entity_id FROM private.mutation_keys"):
            uid, key = params
            row = self.mutations.get((uid, key))
            return _StubCursor([row] if row else [])
        if normalized.startswith("INSERT INTO private.mutation_keys"):
            uid, key, kind, entity = params
            self.mutations[(uid, key)] = {"kind": kind, "entity_id": entity}
            return _StubCursor()
        if normalized.startswith("SELECT * FROM private.watchlist WHERE user_id=%s"):
            uid = params[0]
            rows = [dict(r) for (u, _), r in self.watchlist.items() if u == uid]
            return _StubCursor(rows)
        if normalized.startswith("SELECT symbol, tier, tier_confirmed, sync_locked, target_price, sort_order, version FROM private.watchlist"):
            uid = params[0]
            rows = [
                {
                    "symbol": r["symbol"],
                    "tier": r["tier"],
                    "tier_confirmed": r["tier_confirmed"],
                    "sync_locked": r["sync_locked"],
                    "target_price": r["target_price"],
                    "sort_order": r["sort_order"],
                    "version": r["version"],
                }
                for (u, _), r in self.watchlist.items()
                if u == uid and r["active"]
            ]
            rows.sort(key=lambda r: (r["sort_order"], r["symbol"]))
            return _StubCursor(rows)
        if normalized.startswith("SELECT s.symbol,"):
            symbols = params[0]
            rows = [
                {"symbol": sym, "is_etf": sym in self.etfs}
                for sym in symbols
                if sym in self.eligible
            ]
            return _StubCursor(rows)
        if normalized.startswith("SELECT DISTINCT symbol FROM private.watchlist WHERE active AND user_id<>%s"):
            uid = params[0]
            syms = sorted({r["symbol"] for (u, _), r in self.watchlist.items() if u != uid and r["active"]})
            return _StubCursor([{"symbol": sym} for sym in syms])
        if normalized.startswith("SELECT p.rules FROM private.personal_strategy_state"):
            if self.b_capacity is None:
                return _StubCursor([])
            return _StubCursor([{"rules": {"b_capacity": self.b_capacity}}])
        if normalized.startswith("UPDATE private.watchlist SET active=false"):
            key, uid, sym = params
            row = self.watchlist.get((uid, sym))
            if row and row["active"]:
                row["active"] = False
                row["version"] += 1
                row["idempotency_key"] = key
            return _StubCursor()
        if normalized.startswith("INSERT INTO private.watchlist"):
            uid, sym, target_price, sort_order, key, tier = params
            existing = self.watchlist.get((uid, sym))
            if existing:
                existing["active"] = True
                existing["tier"] = tier
                existing["tier_confirmed"] = True
                existing["sort_order"] = sort_order
                existing["target_price"] = target_price
                existing["version"] += 1
                existing["idempotency_key"] = key
            else:
                self.watchlist[(uid, sym)] = {
                    "user_id": uid,
                    "symbol": sym,
                    "target_price": target_price,
                    "sort_order": sort_order,
                    "active": True,
                    "version": 1,
                    "idempotency_key": key,
                    "tier": tier,
                    "tier_confirmed": True,
                    "sync_locked": False,
                }
            return _StubCursor()
        if normalized.startswith("UPDATE private.watchlist SET tier=%s"):
            tier, sort_order, target_price, key, uid, sym = params
            row = self.watchlist.get((uid, sym))
            if row and row["active"]:
                row["tier"] = tier
                row["tier_confirmed"] = True
                row["sort_order"] = sort_order
                row["target_price"] = target_price
                row["version"] += 1
                row["idempotency_key"] = key
            return _StubCursor()
        if normalized.startswith("SELECT control.record_deep_tracking_demand"):
            self.demand_calls.append(params[0])
            return _StubCursor()
        if normalized.startswith("UPDATE private.users SET change_version=change_version+1"):
            uid = params[0]
            self.users[uid]["change_version"] += 1
            return _StubCursor([{"change_version": self.users[uid]["change_version"]}])
        if normalized.startswith("INSERT INTO private.change_log"):
            uid, version, kind, entity_id, artifact = params
            self.change_log.append(
                {"user_id": uid, "change_version": version, "kind": kind, "entity_id": entity_id}
            )
            return _StubCursor()
        if normalized.startswith("SELECT control.sync_stock_supplement_demand()"):
            self.supplement_sync_calls += 1
            return _StubCursor()
        raise AssertionError(f"Unexpected SQL: {normalized}")


class _FakeRepo(PostgresWorkspaceRepository):
    def __init__(self, db: _InMemoryWatchlistDb):
        super().__init__("postgresql://test/test")
        self.db = db

    @contextmanager
    def _connection(self):
        yield self.db


def _build_oauth() -> McpOAuth:
    settings = OAuthSettings(
        issuer="https://api.example.test",
        resource="https://api.example.test/mcp",
        google_client_id="google-client",
        google_client_secret="google-secret",
        signing_key=b"k" * 32,
        allowed_emails=frozenset({"owner@example.com"}),
    )
    return McpOAuth(
        settings,
        InMemoryOAuthCodeStore(),
        lambda _sub, _email: OWNER_A,
        clock=lambda: 1_700_000_000,
    )


def _mint_oauth_token(oauth: McpOAuth, scope: str, owner: UUID = OWNER_A) -> str:
    return oauth._sign({
        "iss": oauth.settings.issuer,
        "sub": str(owner),
        "aud": oauth.settings.resource,
        "scope": scope,
        "iat": 1_700_000_000,
        "exp": 1_700_000_900,
        "jti": "jti-test",
    })


def _make_api(repo, oauth=None, *, google_audience: str = "google-audience", google_verifier=None):
    recalc = SimpleNamespace(calls=[])
    recalc.run_user = lambda uid, *_args: recalc.calls.append(uid) or {"status": "updated"}
    supplement_calls: list[str] = []

    class _Pipeline:
        pass

    return TestClient(
        create_app(
            repository=repo,
            store=SimpleNamespace(),
            core=SimpleNamespace(),
            oauth_facade=oauth,
            audience=google_audience,
            verifier=google_verifier,
            private_recalculator=recalc,
            pipeline_service=_Pipeline(),
        )
    ), recalc, supplement_calls


def test_sync_auth_boundaries_and_zero_ledger_blast_radius(monkeypatch):
    oauth = _build_oauth()
    sync_calls: list[tuple] = []

    class _StubRepo:
        def resolve_user(self, _sub, _email):
            return OWNER_A

        def sync_watchlist(self, owner_id, value, key):
            sync_calls.append((owner_id, value, key))
            return {
                "dry_run": value.dry_run,
                "applied": not value.dry_run,
                "replayed": False,
                "changed_count": 0 if value.dry_run else 1,
                "items": [],
            }

    supplement_calls: list[str] = []
    monkeypatch.setattr("services.api.stock_supplement.wake_stock_supplement", lambda *_: supplement_calls.append("wake"))

    api, recalc, _ = _make_api(
        _StubRepo(),
        oauth=oauth,
        google_verifier=lambda token, _aud: {
            "iss": "https://accounts.google.com",
            "aud": "google-audience",
            "sub": "google-sub",
            "email": "owner@example.com",
            "email_verified": True,
            "exp": 9_999_999_999,
        } if token == "google-id-token" else (_ for _ in ()).throw(ValueError("bad google token")),
    )

    payload = {"items": [{"symbol": "3711", "tier": "A", "target_price": "555"}], "dry_run": True}

    # 1. Anonymous rejected
    assert api.post("/api/v1/me/watchlist/sync", json=payload).status_code == 401

    # 2. Read-only MCP token rejected (no janus.watchlist.write)
    ro_token = _mint_oauth_token(oauth, " ".join(sorted(MCP_READ_SCOPES)))
    assert api.post(
        "/api/v1/me/watchlist/sync",
        json=payload,
        headers={"Authorization": f"Bearer {ro_token}"},
    ).status_code == 401

    # 3. Scoped OAuth token succeeds on watchlist/sync, rejected on all ledger/cash/private-data routes
    rw_token = _mint_oauth_token(oauth, "janus.private.read janus.watchlist.write")
    rw_headers = {"Authorization": f"Bearer {rw_token}"}
    res = api.post("/api/v1/me/watchlist/sync", json=payload, headers=rw_headers)
    assert res.status_code == 200
    assert res.json()["dry_run"] is True
    assert recalc.calls == []
    assert supplement_calls == []

    for method, path, body in (
        ("GET", "/api/v1/me/journal/positions", None),
        ("POST", "/api/v1/me/journal/events", {"event_type": "BUY", "trade_date": "2026-11-28", "symbol": "2330", "shares": "1", "price": "100"}),
        ("PUT", "/api/v1/me/cash-position", {"amount": "100", "expected_version": 0}),
        ("POST", "/api/v1/me/dividends/pending/confirm", {"draft_ids": [str(uuid4())], "expected_ledger_version": 0}),
        ("DELETE", "/api/v1/me/private-data", None),
    ):
        denied = api.request(method, path, json=body, headers={**rw_headers, "Idempotency-Key": "test-deny-1234"})
        assert denied.status_code == 401

    # 4. dry_run=False requires Idempotency-Key
    assert api.post(
        "/api/v1/me/watchlist/sync",
        json={"items": [{"symbol": "3711", "tier": "A"}], "dry_run": False},
        headers=rw_headers,
    ).status_code == 422

    # 5. dry_run=False with Idempotency-Key succeeds and schedules background tasks
    applied = api.post(
        "/api/v1/me/watchlist/sync",
        json={"items": [{"symbol": "3711", "tier": "A"}], "dry_run": False},
        headers={**rw_headers, "Idempotency-Key": "sync-key-0001"},
    )
    assert applied.status_code == 200
    assert applied.json()["applied"] is True
    assert recalc.calls == [OWNER_A]
    assert supplement_calls == ["wake"]

    # 6. Google OIDC ID Token also accepted on /api/v1/me/watchlist/sync
    oidc_res = api.post(
        "/api/v1/me/watchlist/sync",
        json=payload,
        headers={"Authorization": "Bearer google-id-token"},
    )
    assert oidc_res.status_code == 200

    # 7. /mcp tools/list remains strictly 3 read-only tools
    tools = api.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}).json()["result"]["tools"]
    assert {tool["name"] for tool in tools} == {"janus_sources", "janus_market_context", "janus_private_context"}
    assert all(tool["annotations"]["readOnlyHint"] is True for tool in tools)


def test_sync_skips_background_tasks_on_replay_or_zero_changes(monkeypatch):
    oauth = _build_oauth()
    rw_token = _mint_oauth_token(oauth, "janus.watchlist.write")
    supplement_calls: list[str] = []
    monkeypatch.setattr("services.api.stock_supplement.wake_stock_supplement", lambda *_: supplement_calls.append("wake"))

    class _NoopRepo:
        def __init__(self, response):
            self.response = response

        def sync_watchlist(self, _owner_id, _value, _key):
            return self.response

    for resp in (
        {"dry_run": False, "applied": False, "replayed": True, "changed_count": 0, "items": []},
        {"dry_run": False, "applied": True, "replayed": False, "changed_count": 0, "items": []},
    ):
        api, recalc, _ = _make_api(_NoopRepo(resp), oauth=oauth, google_audience="")
        r = api.post(
            "/api/v1/me/watchlist/sync",
            json={"items": [{"symbol": "3711", "tier": "A"}], "dry_run": False},
            headers={"Authorization": f"Bearer {rw_token}", "Idempotency-Key": "sync-noop-0001"},
        )
        assert r.status_code == 200
        assert recalc.calls == []
        assert supplement_calls == []


def test_oauth_401_does_not_turn_into_503_when_google_audience_unset():
    oauth = _build_oauth()
    ro_token = _mint_oauth_token(oauth, "janus.private.read")
    api, _, _ = _make_api(SimpleNamespace(), oauth=oauth, google_audience="")
    r = api.post(
        "/api/v1/me/watchlist/sync",
        json={"items": [], "dry_run": True},
        headers={"Authorization": f"Bearer {ro_token}"},
    )
    assert r.status_code == 401


def test_repository_mirror_sync_17_stocks_locked_targets_and_replay():
    seventeen = [
        ("3711", "A", "555"),
        ("3037", "A", "700"),
        ("3665", "B", "3100"),
        ("3017", "B", "4815"),
        ("2345", "B", "2250"),
        ("6669", "B", "3777"),
        ("2308", "B", "2300"),
        ("2383", "B", "8800"),
        ("3533", "B", "2500"),
        ("4958", "B", "1070"),
        ("2413", "C", None),
        ("3491", "C", "1780"),
        ("8227", "C", None),
        ("2344", "C", "120"),
        ("3363", "C", None),
        ("2481", "C", None),
        ("2492", "C", None),
    ]
    all_symbols = {s for s, _, _ in seventeen} | {"6451", "6224", "6426", "2493", "2330", "2882"}
    db = _InMemoryWatchlistDb(eligible=all_symbols, b_capacity=8)
    # Seed existing watchlist for OWNER_A: 4 retired, 3 downgraded B->C, 1 locked custom symbol, 1 with existing target_price
    for idx, (sym, tier, tp, locked) in enumerate([
        ("3711", "A", "500", False),
        ("3037", "A", None, False),
        ("6451", "C", None, False),
        ("6224", "C", None, False),
        ("6426", "C", None, False),
        ("2493", "C", None, False),
        ("3363", "B", "310", False),
        ("2481", "B", None, False),
        ("2492", "B", None, False),
        ("2330", "A", "1200", True),  # Locked by user in Janus, absent from 17-stock sheet -> preserved!
    ]):
        db.watchlist[(OWNER_A, sym)] = {
            "user_id": OWNER_A, "symbol": sym,
            "target_price": Decimal(tp) if tp else None,
            "sort_order": idx, "active": True, "version": 3,
            "idempotency_key": f"seed-{idx}", "tier": tier,
            "tier_confirmed": True, "sync_locked": locked,
        }
    # OWNER_B also has a symbol — must stay untouched
    db.watchlist[(OWNER_B, "2882")] = {
        "user_id": OWNER_B, "symbol": "2882", "target_price": Decimal("80"),
        "sort_order": 0, "active": True, "version": 1, "idempotency_key": "other",
        "tier": "C", "tier_confirmed": True, "sync_locked": False,
    }

    repo = _FakeRepo(db)
    sync_req = WatchlistSyncIn.model_validate({
        "items": [{"symbol": sym, "tier": tier, "target_price": tp} for sym, tier, tp in seventeen],
        "mode": "mirror",
        "preserve_locked": True,
        "update_target_price": True,
        "dry_run": True,
        "source": "股市/03_候選股與觀察池",
    })

    preview = repo.sync_watchlist(OWNER_A, sync_req, None)
    assert preview["dry_run"] is True
    assert preview["before_count"] == 10
    assert preview["after_count"] == 18  # 17 synced + 1 locked 2330
    assert {x["symbol"] for x in preview["removed"]} == {"6451", "6224", "6426", "2493"}
    assert [x["symbol"] for x in preview["preserved_locked"]] == ["2330"]
    assert db.change_log == []  # dry_run made zero mutations

    # Now apply
    apply_req = sync_req.model_copy(update={"dry_run": False, "expected_version": 3})
    result = repo.sync_watchlist(OWNER_A, apply_req, "sync-2026-11-28-01")
    assert result["applied"] is True
    assert result["replayed"] is False
    assert result["after_count"] == 18
    assert db.users[OWNER_A]["change_version"] == 1
    assert db.supplement_sync_calls == 1

    active_a = {r["symbol"]: r for r in result["items"]}
    assert set(active_a) == {s for s, _, _ in seventeen} | {"2330"}
    assert active_a["3711"]["target_price"] == Decimal("555")
    assert active_a["3037"]["target_price"] == Decimal("700")
    assert active_a["3665"]["target_price"] == Decimal("3100")
    # 3363 had target_price=310 before and incoming target_price=None -> preserved!
    assert active_a["3363"]["tier"] == "C"
    assert active_a["3363"]["target_price"] == Decimal("310")
    # Locked 2330 survived mirror deletion untouched
    assert active_a["2330"]["sync_locked"] is True
    assert active_a["2330"]["target_price"] == Decimal("1200")
    # Retired symbols soft-deleted & demand recorded
    for retired in ("6451", "6224", "6426", "2493"):
        assert db.watchlist[(OWNER_A, retired)]["active"] is False
        assert retired in db.demand_calls
    # OWNER_B untouched
    assert db.watchlist[(OWNER_B, "2882")]["active"] is True

    # Replay with same Idempotency-Key is safe & no-op
    replay = repo.sync_watchlist(OWNER_A, apply_req, "sync-2026-11-28-01")
    assert replay["replayed"] is True
    assert replay["changed_count"] == 0
    assert db.users[OWNER_A]["change_version"] == 1

    # clear_missing_target_price=True clears 3363's old 310 when incoming is None
    clear_req = WatchlistSyncIn.model_validate({
        "items": [{"symbol": sym, "tier": tier, "target_price": tp} for sym, tier, tp in seventeen],
        "mode": "mirror",
        "clear_missing_target_price": True,
        "dry_run": False,
    })
    cleared = repo.sync_watchlist(OWNER_A, clear_req, "sync-2026-11-28-02")
    assert {r["symbol"]: r for r in cleared["items"]}["3363"]["target_price"] is None


def test_repository_sync_enforces_locked_in_incoming_capacity_version_and_eligibility():
    all_syms = {f"{1100 + i}" for i in range(60)}
    db = _InMemoryWatchlistDb(eligible=all_syms - {"9999"}, b_capacity=8)
    db.watchlist[(OWNER_A, "1100")] = {
        "user_id": OWNER_A, "symbol": "1100", "target_price": Decimal("99"),
        "sort_order": 5, "active": True, "version": 2, "idempotency_key": "k0",
        "tier": "A", "tier_confirmed": True, "sync_locked": True,
    }
    repo = _FakeRepo(db)

    # Locked stock in incoming must NOT be overwritten
    res = repo.sync_watchlist(
        OWNER_A,
        WatchlistSyncIn.model_validate({
            "items": [{"symbol": "1100", "tier": "C", "target_price": "10", "sort_order": 0}],
            "dry_run": False,
        }),
        "lock-keep-01",
    )
    assert res["preserved_locked"][0]["in_incoming"] is True
    assert db.watchlist[(OWNER_A, "1100")]["tier"] == "A"
    assert db.watchlist[(OWNER_A, "1100")]["target_price"] == Decimal("99")

    # Wrong expected_version -> ConflictError
    with pytest.raises(ConflictError, match="watchlist version changed"):
        repo.sync_watchlist(
            OWNER_A,
            WatchlistSyncIn.model_validate({"items": [], "expected_version": 99, "dry_run": False}),
            "bad-ver-01",
        )

    # Ineligible symbol -> ConflictError
    with pytest.raises(ConflictError, match="not in the current listed/OTC universe"):
        repo.sync_watchlist(
            OWNER_A,
            WatchlistSyncIn.model_validate({"items": [{"symbol": "9999", "tier": "C"}], "dry_run": False}),
            "bad-sym-01",
        )

    # B-tier capacity > 8 -> ConflictError
    too_many_b = [{"symbol": f"{1101 + i}", "tier": "B"} for i in range(9)]
    with pytest.raises(ConflictError, match="B池已達策略容量"):
        repo.sync_watchlist(
            OWNER_A,
            WatchlistSyncIn.model_validate({"items": too_many_b, "dry_run": False}),
            "bad-bcap-01",
        )

    # Global distinct limit > 50 -> ConflictError
    for i in range(45):
        db.watchlist[(OWNER_B, f"{1110 + i}")] = {
            "user_id": OWNER_B, "symbol": f"{1110 + i}", "target_price": None,
            "sort_order": i, "active": True, "version": 1, "idempotency_key": "ob",
            "tier": "C", "tier_confirmed": True, "sync_locked": False,
        }
    with pytest.raises(ConflictError, match="deep-tracking symbol limit reached"):
        repo.sync_watchlist(
            OWNER_A,
            WatchlistSyncIn.model_validate({
                "items": [{"symbol": f"{1101 + i}", "tier": "C"} for i in range(7)],
                "dry_run": False,
            }),
            "bad-global-01",
        )
