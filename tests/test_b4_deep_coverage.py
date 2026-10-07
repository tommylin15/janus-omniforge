import json
from datetime import date, timedelta
from hashlib import sha256
from pathlib import Path
import sys

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "jobs/intelligence-mart"))

from intelligence_mart.analytics_reader import AnalyticsSnapshot
from intelligence_mart.runtime import AnalysisExecution
from intelligence_mart.specialist_runtime import specialist_processor
from intelligence_mart.specialists import analyze_specialists, specialist_input_hashes


class Store:
    def __init__(self):
        self.data = {}

    def create(self, name, data, kind):
        if name in self.data:
            return False
        self.data[name] = data
        return True

    def read(self, name):
        if name not in self.data:
            raise FileNotFoundError(name)
        return self.data[name]


def source(*, event=False, event_date="2026-05-01"):
    start = date(2026, 1, 1)
    prices = [
        {
            "symbol": "2330",
            "source_id": "twse",
            "provenance_id": f"p-{offset}",
            "observed_at": str(start + timedelta(days=offset)),
            "trade_date": str(start + timedelta(days=offset)),
            "close": 100 + offset,
            "volume_shares": 100000,
            "turnover_twd": 10000000,
        }
        for offset in range(121)
    ]
    events = []
    if event:
        events.append({
            "symbol": "2330",
            "source_id": "mops",
            "provenance_id": "event-1",
            "published_at": event_date,
            "observed_at": event_date,
            "event_type": "earnings",
            "severity": "high",
        })
    return {
        "ohlcv": prices,
        "benchmark": [dict(row, symbol=None, benchmark_id="TAIEX", close=10000 + offset)
                      for offset, row in enumerate(prices)],
        "financials": [],
        "valuation": [],
        "events": events,
    }


def core_manifest(execution_id, snapshot_id, datasets):
    return {
        "execution_id": execution_id,
        "analysis_as_of": "2026-05-01",
        "snapshot_id": snapshot_id,
        "iceberg_tables": {"core.ohlcv_v1": {"snapshot_id": 1}},
        "datasets": datasets,
    }


def options(core, uri, payload):
    return {
        "analysis_as_of": core["analysis_as_of"],
        "core_execution_id": core["execution_id"],
        "core_snapshot_id": core["snapshot_id"],
        "core_snapshot_uri": uri,
        "core_snapshot_hash": "sha256:" + sha256(payload).hexdigest(),
        "schema_version": "1",
        "feature_version": "2",
        "model_version": "deterministic-v1",
        "governance_snapshot_version": "gov-1",
        "scopes": [],
    }


def test_selected_event_role_does_not_execute_price_risk(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("risk metrics must not run for event-only dirty update")

    monkeypatch.setattr("intelligence_mart.specialists.risk_metrics", fail_if_called)
    artifacts = analyze_specialists(
        source(event=True), "2330", "2026-05-01", "core", roles=("event",)
    )
    assert [artifact["role"] for artifact in artifacts] == ["event"]
    assert artifacts[0]["llm_api_tokens"] == 0
    assert artifacts[0]["ceo_triggered"] is False


def test_dependency_hash_changes_only_affected_event_role():
    before = specialist_input_hashes(source(event=False), "2330", "2026-05-01", "core")
    after = specialist_input_hashes(source(event=True), "2330", "2026-05-01", "core")
    changed = {role for role in before if before[role] != after[role]}
    assert changed == {"event"}


def test_dependency_hash_includes_rejected_role_evidence():
    before = specialist_input_hashes(source(event=False), "2330", "2026-05-01", "core")
    rejected = specialist_input_hashes(
        source(event=True, event_date="2026-05-02"), "2330", "2026-05-01", "core"
    )
    changed = {role for role in before if before[role] != rejected[role]}
    assert changed == {"event"}


def test_deep_coverage_reuses_clean_roles_and_skips_market_screening(monkeypatch):
    stores = {"core": Store(), "mart": Store()}
    first_core = core_manifest("core-ex-1", "core-1", source(event=False))
    second_core = core_manifest("core-ex-2", "core-2", source(event=True))
    first_payload = json.dumps(first_core, sort_keys=True).encode()
    second_payload = json.dumps(second_core, sort_keys=True).encode()
    stores["core"].data["core-1.json"] = first_payload
    stores["core"].data["core-2.json"] = second_payload

    monkeypatch.setenv("MART_BUCKET", "mart")
    monkeypatch.setattr(
        "intelligence_mart.coverage.load_target_rows",
        lambda *args: [{"symbol": "2330", "watchlisted": True, "held": False}],
    )
    monkeypatch.setattr(
        "intelligence_mart.specialist_runtime.load_market_membership",
        lambda *args: (_ for _ in ()).throw(
            AssertionError("deep coverage must not load liquid-500 membership")
        ),
    )

    readers = []

    class InjectedReader:
        def __init__(self):
            self.closed = False
            readers.append(self)

        def read(self, manifest, requested_symbols, *, core_snapshot_id, row_limit=250_000):
            assert requested_symbols == ("2330",)
            assert manifest["snapshot_id"] == core_snapshot_id
            datasets = {name: [dict(row) for row in rows]
                        for name, rows in manifest["datasets"].items()}
            rows_by_dataset = {name: len(rows) for name, rows in sorted(datasets.items())}
            return AnalyticsSnapshot(
                core_snapshot_id=core_snapshot_id,
                datasets=datasets,
                telemetry={
                    "source": "b4-injected-test",
                    "core_snapshot_id": core_snapshot_id,
                    "rows_by_dataset": rows_by_dataset,
                    "total_rows": sum(rows_by_dataset.values()),
                    "scan_evidence": {},
                },
            )

        def close(self):
            self.closed = True

    def run(execution_id, core, uri, payload):
        return specialist_processor(
            AnalysisExecution(
                execution_id,
                "deep-coverage",
                (),
                0,
                options(core, uri, payload),
            ),
            None,
            store_factory=stores.__getitem__,
            reader_factory=InjectedReader,
        )

    first = run("b4-first", first_core, "gs://core/core-1.json", first_payload)
    assert first["screening_count"] == 0
    assert first["specialist_count"] == 5
    assert first["specialist_computed_count"] == 5
    assert first["specialist_reused_count"] == 0
    assert len(first["dirty_specialists"]) == 5
    assert readers[-1].closed

    first_manifest = json.loads(stores["mart"].read("executions/b4-first/specialist-manifest.json"))
    assert first_manifest["screening"] is None
    assert first_manifest["market_membership"] is None
    assert first_manifest["llm_api_tokens"] == 0
    assert first_manifest["ceo_triggered"] is False
    assert "user_id" not in json.dumps(first_manifest)

    unchanged = run("b4-unchanged", first_core, "gs://core/core-1.json", first_payload)
    assert unchanged["specialist_count"] == 5
    assert unchanged["specialist_computed_count"] == 0
    assert unchanged["specialist_reused_count"] == 5
    assert unchanged["dirty_specialists"] == []
    assert readers[-1].closed

    event_changed = run("b4-event", second_core, "gs://core/core-2.json", second_payload)
    assert event_changed["specialist_count"] == 5
    assert event_changed["specialist_computed_count"] == 1
    assert event_changed["specialist_reused_count"] == 4
    assert {item["role"] for item in event_changed["dirty_specialists"]} == {"event"}
    assert readers[-1].closed

    event_manifest = json.loads(stores["mart"].read("executions/b4-event/specialist-manifest.json"))
    by_role = {item["role"]: item for item in event_manifest["specialists"]}
    assert by_role["event"]["source_core_snapshot_id"] == "core-2"
    assert all(by_role[role]["source_core_snapshot_id"] == "core-1"
               for role in ("fundamental", "valuation", "quant", "risk"))
    assert by_role["event"]["reused"] is False
    assert all(by_role[role]["reused"] is True
               for role in ("fundamental", "valuation", "quant", "risk"))
