from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock
import runpy
from pathlib import Path
import pytest
from ingestion_core import batch_controller as controller


def test_controlled_chain_keeps_clock_real_and_dependencies_stable():
    now = datetime(2026, 10, 29, 1, tzinfo=timezone.utc)
    rows = controller.controlled_rows(now, "eod", "2026-10-28")
    assert {row[1].name for row in rows} == {"ingestion", "market-screening", "private", "serving-prune"}
    assert all(row[0].startswith("controlled/") for row in rows)
    assert all(dep.startswith("controlled/") for row in rows for dep in row[3])
    ingestion = next(row for row in rows if row[1].name == "ingestion")
    assert dict(controller.occurrence_env(ingestion[1], ingestion[2]))["INGESTION_DATE"] == "2026-10-28"
    assert rows == controller.controlled_rows(now, "eod", "2026-10-28")
    for group, day in [("eod", "2026-10-31"), ("maintenance", "2026-10-28"), ("bogus", "2026-10-28")]:
        with pytest.raises(ValueError):
            controller.controlled_rows(now, group, day)


def test_chain_reconciles_without_holding_writer_lock_during_wait(monkeypatch):
    from ingestion_core import __main__ as worker
    calls = []
    control = MagicMock()
    cursor = control.__enter__.return_value.connection.cursor.return_value.__enter__.return_value
    cursor.fetchall.side_effect = [[("ingestion/day/18", "running")], [("ingestion/day/18", "succeeded")]]
    monkeypatch.setattr(worker, "_control_plane", lambda: control)
    monkeypatch.setattr(controller, "run", lambda **kwargs: calls.append("tick") or
        {"status": "tick_completed", "chain_keys": ["ingestion/day/18"]})
    def sleep(seconds):
        assert control.__exit__.call_count == 1
        calls.append("wait")
    monkeypatch.setattr(controller, "sleep", sleep)
    assert controller.run_chain()["chain_status"] == "settled"
    assert calls == ["tick", "wait", "tick"]


@pytest.mark.parametrize("status", ["failed", "ambiguous"])
def test_chain_never_retries_failed_or_unknown_dispatch(monkeypatch, status):
    from ingestion_core import __main__ as worker
    control = MagicMock()
    control.__enter__.return_value.connection.cursor.return_value.__enter__.return_value.fetchall.return_value = [("key", status)]
    tick = Mock(return_value={"status": "tick_completed", "chain_keys": ["key"]})
    monkeypatch.setattr(worker, "_control_plane", lambda: control)
    monkeypatch.setattr(controller, "run", tick)
    with pytest.raises(RuntimeError, match="ambiguous"):
        controller.run_chain()
    tick.assert_called_once()


@pytest.mark.parametrize("key", ["controlled/postgres-maintenance/2026-10-24/22",
                                  "postgres-maintenance/2026-10-24/22",
                                  "admin/postgres-maintenance/2"])
def test_vm_vacuum_consumes_only_controller_request_and_keeps_terminal_receipt(monkeypatch, key):
    module = runpy.run_path(str(Path("scripts/gcp/ledger_backup_executor.py")))
    statements = []
    def sql(statement):
        statements.append(statement)
        return key if len(statements) == 1 else ""
    module["maintain_postgres"].__globals__["sql"] = sql
    command = Mock(return_value=SimpleNamespace(returncode=0))
    monkeypatch.setattr(module["subprocess"], "run", command)
    assert module["maintain_postgres"]()["status"] == "succeeded"
    assert "SKIP LOCKED" in statements[0] and 'vm_claimed' in statements[0]
    assert "VACUUM (ANALYZE)" in command.call_args.kwargs["input"]
    assert '"status":"succeeded"' in statements[-1]


def test_prune_limits_deletion_to_rebuildable_serving(monkeypatch):
    from ingestion_core.serving_projection import StockServingProjection
    connection = MagicMock()
    cursor = connection.__enter__.return_value.cursor.return_value.__enter__.return_value
    cursor.rowcount = 0
    result = StockServingProjection(lambda: connection).prune_tiered()
    assert result == {"status": "succeeded", "ohlcv_deleted": 0, "financial_deleted": 0}
    sql = " ".join(call.args[0] for call in cursor.execute.call_args_list)
    assert "750 days" in sql and "120 days" in sql and "24 months" in sql
    deletion = next(call for call in cursor.execute.call_args_list if "WITH targets" in call.args[0])
    assert "UNION SELECT unnest" in deletion.args[0]
    assert {"2317", "2454", "6488", "8069"} <= set(deletion.args[1][0])
    assert "DELETE FROM private." not in sql and "DELETE FROM control.stock_serving_recent" in sql


def test_acceptance_dispatch_unknown_is_not_retried(monkeypatch):
    import sys
    sys.path.insert(0, str(Path("scripts/gcp").resolve()))
    import three_pipeline_acceptance as acceptance
    job = {"etag": "known", "template": {"template": {"containers": [{}]}}}
    monkeypatch.setattr(acceptance.jobs, "job", lambda name: job)
    dispatch = Mock(return_value={"name": "untrusted"})
    monkeypatch.setattr(acceptance.jobs, "cloud", dispatch)
    with pytest.raises(RuntimeError, match="dispatch_unknown"):
        acceptance.invoke("janus-batch-controller", {}, {}, lambda: None)
    dispatch.assert_called_once()


def test_controlled_compensation_uses_elapsed_slot_without_changing_day_clock():
    now = datetime(2026, 10, 29, 1, 10, tzinfo=timezone.utc)
    row = controller.controlled_rows(now, "compensation", "2026-10-29")[0]
    assert row[0] == "controlled/mobile-ledger/2026-10-29/00"
    assert row[2].hour == 0 and row[2].minute == 30
    assert row == controller.controlled_rows(now.replace(hour=4), "compensation", "2026-10-29")[0]


@pytest.mark.parametrize("sheet_unavailable", [False, True])
def test_compensation_processes_durable_queue_even_when_sheet_is_empty(monkeypatch, sheet_unavailable):
    from services.api import private_pipeline_runtime as runtime
    monkeypatch.setenv("MOBILE_LEDGER_ONLY", "true")
    monkeypatch.setenv("MOBILE_LEDGER_DATABASE_URL", "unused")
    monkeypatch.setattr(runtime, "load_postgres_bundle", lambda *args: None)
    monkeypatch.setattr(runtime, "repository_from_env", MagicMock)
    monkeypatch.setattr(runtime, "PostgresWorkspaceRepository", lambda *args: MagicMock())
    consume = Mock(return_value={"processed": 0, "errors": 0})
    if sheet_unavailable:
        consume.side_effect = runtime.MobileLedgerQueueError("unavailable")
    monkeypatch.setattr(runtime, "process_mobile_ledger_queue", consume)
    monkeypatch.setattr(runtime.CorePriceReader, "from_env", MagicMock)
    monkeypatch.setattr(runtime.PrivateIcebergStore, "from_env", MagicMock)
    monkeypatch.setattr(runtime, "PrivatePipeline", MagicMock())
    worker = Mock(return_value={"failed": 0, "succeeded": 1})
    monkeypatch.setattr(runtime, "run_queue_worker", worker)
    if sheet_unavailable:
        with pytest.raises(RuntimeError, match="business execution failed"):
            runtime.main()
    else:
        runtime.main()
    worker.assert_called_once()


def test_admin_includes_new_pipeline_steps():
    from packages.admin_api.batch_dashboard import TASKS
    assert {"serving-prune", "postgres-maintenance"} <= set(TASKS)
