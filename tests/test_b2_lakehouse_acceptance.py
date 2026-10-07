"""Run with python -m unittest discover -s tests -p test_b2_lakehouse_acceptance.py."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location(
    "b2", Path(__file__).parents[1] / "scripts/gcp/b2-lakehouse-acceptance.py"
)
b2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b2)


class CommandTest(unittest.TestCase):
    def test_core_pruning_checks_pointer_before_and_after_queries(self):
        evidence = {"shared_catalog_mapping": {"core.ohlcv_v1": {
            "metadata_location": "gs://fixed", "snapshot_id": 123,
        }}}
        budget = Mock(jobs=[], billed=20, remaining=b2.BUDGET - 20)
        budget.query.side_effect = [
            {"evidence": {"processed_bytes": n}, "response": {}} for n in (10, 100)
        ]
        with patch.object(b2, "load_table", return_value={"metadata-location": "gs://fixed"}):
            b2.prove_core_pruning(evidence, budget)
        self.assertTrue(evidence["core_partition_pruning"]["pass"])
        budget.query.reset_mock()
        with patch.object(b2, "load_table", return_value={"metadata-location": "gs://drift"}):
            with self.assertRaisesRegex(RuntimeError, "pointer changed"):
                b2.prove_core_pruning(evidence, budget)
        budget.query.assert_not_called()
        budget.query.side_effect = [
            {"evidence": {"processed_bytes": n}, "response": {}} for n in (10, 100)
        ]
        with patch.object(b2, "load_table", side_effect=[
            {"metadata-location": "gs://fixed"}, {"metadata-location": "gs://drift"},
        ]):
            with self.assertRaisesRegex(RuntimeError, "pointer changed"):
                b2.prove_core_pruning(evidence, budget)
        self.assertEqual(budget.query.call_count, 2)

    def test_budget_survives_restart_and_unknown_job_blocks_query(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            journal = Path(directory) / "jobs.json"
            journal.write_text(json.dumps([{"billed_bytes": 10}]))
            self.assertEqual(b2.BigQueryBudget(journal).remaining, b2.BUDGET - 10)
            journal.write_text(json.dumps([{"job_id": "pending", "billed_bytes": None}]))
            with self.assertRaisesRegex(RuntimeError, "unknown"):
                b2.BigQueryBudget(journal)

    def test_platform_dispatch_and_command_failure(self):
        for platform, executable in (("nt", "gcloud.cmd"), ("posix", "gcloud")):
            with patch.object(b2.os, "name", platform), patch.object(b2.subprocess, "run") as run:
                run.return_value.returncode = 0
                b2.run("gcloud", "version")
                self.assertEqual(run.call_args.args[0], [executable, "version"])
                b2.run("python", "--version")
                self.assertEqual(run.call_args.args[0], ["python", "--version"])
                run.return_value.returncode = 1
                run.return_value.stderr = "denied"
                with self.assertRaisesRegex(RuntimeError, "denied"):
                    b2.run("gcloud", "version")
                self.assertEqual(b2.run("gcloud", "version", check=False).returncode, 1)
