"""盤後公司行動同步、unified_collection 接線與全 Owner 自動掃描測試。"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date
import json
from uuid import uuid4

from ingestion_core import corporate_actions_sync, unified_collection
from services.api.repository import PostgresWorkspaceRepository


class _FakeControlCursor:
    def __init__(self, *, schema_ready: bool) -> None:
        self.schema_ready = schema_ready
        self.statements: list[str] = []
        self.upserted: list[tuple] = []
        self._last = ""

    def execute(self, sql: str, params=None) -> None:
        self._last = " ".join(sql.split())
        self.statements.append(self._last)
        if self._last.startswith("INSERT INTO control.corporate_actions"):
            self.upserted.append(tuple(params or ()))

    def fetchone(self):
        if "to_regclass('control.corporate_actions')" in self._last:
            return ("control.corporate_actions",) if self.schema_ready else (None,)
        return None


class _FakeControl:
    def __init__(self, *, schema_ready: bool = True) -> None:
        self.cursor = _FakeControlCursor(schema_ready=schema_ready)
        self.closed = False

    @contextmanager
    def _tx(self):
        yield self.cursor

    def close(self) -> None:
        self.closed = True


def _sample_transport(*, fail_twse: bool = False, fail_tpex: bool = False):
    def transport(url: str) -> bytes:
        if "twse.com.tw" in url:
            if fail_twse:
                raise RuntimeError("twse timeout")
            if "TWT49UDetail" in url:
                return json.dumps({"stat": "ok", "fields": [], "data": []}).encode("utf-8")
            if "TWT49U" in url:
                return json.dumps({"stat": "OK", "fields": [], "data": []}).encode("utf-8")
            return json.dumps({
                "fields": ["除權息日期", "股票代號", "名稱", "現金股利", "無償配股率", "發放日"],
                "data": [["115年08月01日", "2884", "玉山金", "1.2", "0.10", "115/08/28"]],
            }).encode("utf-8")
        if "tpex.org.tw" in url:
            if fail_tpex:
                raise RuntimeError("tpex timeout")
            if "exDailyQ_result" in url:
                return json.dumps({"stat": "ok", "tables": [{"fields": [], "data": []}]}).encode("utf-8")
            return json.dumps([
                {
                    "SecuritiesCompanyCode": "6488",
                    "CompanyName": "環球晶",
                    "ExdividendDate": "115/06/10",
                    "CashDividend": "8.0",
                    "StockDividendRatio": "0.05",
                    "PaymentDate": "115/07/10",
                }
            ]).encode("utf-8")
        raise AssertionError(f"unexpected url: {url}")

    return transport


def test_corporate_actions_sync_handles_success_partial_unavailable_and_missing_schema():
    missing = _FakeControl(schema_ready=False)
    res_missing = corporate_actions_sync.run_daily(transport=_sample_transport(), control=missing)
    assert res_missing == {"status": "skipped", "reason": "schema_not_installed", "upserted_count": 0}

    ctrl = _FakeControl(schema_ready=True)
    res_ok = corporate_actions_sync.run_daily(transport=_sample_transport(), control=ctrl)
    assert res_ok == {"status": "succeeded", "upserted_count": 4, "source_errors": {}}
    assert len(ctrl.cursor.upserted) == 4

    ctrl_partial = _FakeControl(schema_ready=True)
    res_partial = corporate_actions_sync.run_daily(
        transport=_sample_transport(fail_tpex=True), control=ctrl_partial
    )
    assert res_partial["status"] == "partial"
    assert res_partial["upserted_count"] == 2
    assert res_partial["source_errors"] == {"tpex_preview": "RuntimeError", "tpex_history": "RuntimeError"}

    ctrl_down = _FakeControl(schema_ready=True)
    res_down = corporate_actions_sync.run_daily(
        transport=_sample_transport(fail_twse=True, fail_tpex=True), control=ctrl_down
    )
    assert res_down["status"] == "unavailable"
    assert res_down["upserted_count"] == 0
    assert set(res_down["source_errors"]) == {"twse_preview", "tpex_preview", "twse_history", "tpex_history"}
    assert len(ctrl_down.cursor.upserted) == 0


def test_unified_collection_wires_corporate_actions_without_blocking_main_collection(monkeypatch):
    from ingestion_core import __main__ as entry

    monkeypatch.setenv("JANUS_STOCK_SUPPLEMENT_ENABLED", "false")
    monkeypatch.setenv("JANUS_ETF_CATALOG_SYNC_ENABLED", "false")
    monkeypatch.setenv("JANUS_CORPORATE_ACTIONS_SYNC_ENABLED", "true")
    monkeypatch.setattr(entry, "run_scheduled_collection", lambda: {"status": "succeeded"})
    monkeypatch.setattr(
        corporate_actions_sync,
        "run_daily",
        lambda: (_ for _ in ()).throw(RuntimeError("upstream down")),
    )

    out = unified_collection.run()
    assert out["status"] == "succeeded"
    assert out["corporate_actions"] == {"status": "unavailable", "error_code": "RuntimeError"}

    monkeypatch.setenv("JANUS_CORPORATE_ACTIONS_SYNC_ENABLED", "false")
    out_disabled = unified_collection.run()
    assert out_disabled["corporate_actions"] == {"status": "disabled"}


def test_scan_all_owners_dividends_respects_flag_and_aggregates(monkeypatch):
    class _StubRepo(PostgresWorkspaceRepository):
        def __init__(self) -> None:
            super().__init__("postgresql://unused")
            self.owners = [uuid4(), uuid4()]
            self.called: list = []

        @contextmanager
        def _connection(self):
            owners = self.owners

            class _Conn:
                def execute(self, sql: str, params=()):
                    class _Res:
                        def __init__(self, one=None, many=None):
                            self._one = one
                            self._many = many or []

                        def fetchone(self):
                            return self._one

                        def fetchall(self):
                            return self._many

                    if "to_regclass" in sql:
                        return _Res(one={"drafts": "private.pending_dividend_events", "actions": "control.corporate_actions"})
                    return _Res(many=[{"user_id": u} for u in owners])

            yield _Conn()

        def scan_dividends(self, user_id, *, from_date=None, symbols=None):
            self.called.append((user_id, from_date))
            if user_id == self.owners[1]:
                raise RuntimeError("simulated single owner error")
            return {"newly_created": 2, "recalculated": 1, "already_recorded": 0}

    repo = _StubRepo()
    monkeypatch.setenv("DIVIDEND_AUTO_SCAN_ENABLED", "false")
    disabled = repo.scan_all_owners_dividends(from_date=date(2026, 11, 1))
    assert disabled["status"] == "disabled"
    assert repo.called == []

    monkeypatch.setenv("DIVIDEND_AUTO_SCAN_ENABLED", "true")
    summary = repo.scan_all_owners_dividends(from_date=date(2026, 11, 1))
    assert summary == {
        "status": "partial",
        "owners_scanned": 1,
        "newly_created": 2,
        "recalculated": 1,
        "already_recorded": 0,
        "errors": 1,
    }
