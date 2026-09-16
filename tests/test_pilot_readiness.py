import os
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "jobs" / "intelligence-mart"))

from intelligence_mart.outcomes import evaluate_outcome
from intelligence_mart.runtime import AnalysisExecution, PostgreSQLPublicationIndex


def candidate(horizon=5):
    return {
        "analysis_execution_id": "11111111-1111-1111-1111-111111111111",
        "analysis_as_of": date(2026, 9, 1), "scope_type": "symbol", "scope_id": "2330",
        "horizon_days": horizon, "pilot_baseline_id": "22222222-2222-2222-2222-222222222222",
        "membership_snapshot_hash": "sha256:" + "1" * 64,
    }


class PilotReadinessTests(unittest.TestCase):
    def test_outcome_uses_exact_trading_horizon_and_benchmark(self):
        days = [date(2026, 9, 1) + timedelta(days=value) for value in range(6)]
        ohlcv = [{"symbol": "2330", "trade_date": day, "close": 100 + index,
                  "high": 101 + index, "low": 99 + index, "provenance_id": f"p{index}"}
                 for index, day in enumerate(days)]
        benchmark = [{"benchmark_id": "TAIEX", "trade_date": day, "close": 1000 + index,
                      "provenance_id": f"b{index}"} for index, day in enumerate(days)]

        result = evaluate_outcome(candidate(), ohlcv, benchmark)

        self.assertEqual((result["status"], result["entry_date"], result["outcome_date"]),
                         ("valid", days[0], days[5]))
        self.assertIsNotNone(result["relative_return_ratio"])
        self.assertTrue(result["provenance_id"].startswith("sha256:"))

    def test_outcome_distinguishes_pending_from_permanent_exclusion(self):
        as_of = date(2026, 9, 1)
        pending = evaluate_outcome(candidate(), [
            {"symbol": "2330", "trade_date": as_of, "close": 100},
            {"symbol": "2330", "trade_date": as_of + timedelta(days=1), "close": 101},
        ], [])
        excluded = evaluate_outcome(candidate(), [
            {"symbol": "2330", "trade_date": as_of + timedelta(days=value), "close": 100}
            for value in range(1, 7)
        ], [])
        self.assertEqual(pending["status"], "pending")
        self.assertEqual((excluded["status"], excluded["exclusion_reason"]),
                         ("excluded", "missing_entry_price"))

    def test_baseline_records_all_revision_dimensions(self):
        calls = []

        class Context:
            def __enter__(self): return self
            def __exit__(self, *_): pass

        class Cursor(Context):
            def execute(self, query, params): calls.append((query, params))
            def fetchone(self): return (calls[-1][1][0],)

        class Connection:
            def transaction(self): return Context()
            def cursor(self): return Cursor()

        execution = AnalysisExecution("e", "first-batch", ("2330",), 0, {
            "schema_version": "schema-1", "feature_version": "feature-1",
            "signal_revision": "signal-1", "model_version": "model-1",
            "governance_snapshot_version": "gov-1", "source_config_revision": "source-1",
        })
        environment = {"JANUS_GIT_SHA": "a" * 40, "JANUS_IMAGE_DIGEST": "sha256:" + "b" * 64,
                       "MART_LLM_ENABLED": "true"}
        with patch.dict(os.environ, environment, clear=True):
            baseline = PostgreSQLPublicationIndex(Connection()).register_baseline(
                execution, "prompt-1", "sha256:" + "c" * 64)

        self.assertEqual(baseline, calls[0][1][0])
        self.assertEqual(calls[0][1][4:], (
            "a" * 40, "sha256:" + "b" * 64, "gov-1", "prompt-1", "sha256:" + "c" * 64,
            "schema-1", "feature-1", "signal-1", "gemini", "model-1", "source-1"))

    def test_migration_and_backup_are_bounded_and_append_preserving(self):
        migration = (ROOT / "infra/postgres/migrations/025_pilot_readiness.sql").read_text(encoding="utf-8")
        backup = (ROOT / "scripts/gcp/ledger-durability-dev.sh").read_text(encoding="utf-8")
        restore = (ROOT / "scripts/gcp/cloudbuild-ledger-restore.yaml").read_text(encoding="utf-8")
        for field in ("git_sha", "image_digest", "governance_revision", "prompt_hash",
                      "schema_revision", "feature_revision", "signal_revision", "model_provider",
                      "model_version", "source_config_revision"):
            self.assertIn(field, migration)
        self.assertIn("WHERE publication.pilot_analysis_outcomes.status='pending'", (ROOT / "jobs/intelligence-mart/intelligence_mart/runtime.py").read_text(encoding="utf-8"))
        self.assertIn("'' 14", backup)
        self.assertIn("'' 6", backup)
        self.assertIn("managed-folders", backup)
        self.assertIn("--network none", restore)
        self.assertNotIn("compute instances create", backup)
        self.assertNotIn("disks snapshot", backup)


if __name__ == "__main__":
    unittest.main()
