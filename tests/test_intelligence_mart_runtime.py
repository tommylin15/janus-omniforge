import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "jobs" / "intelligence-mart"))

from intelligence_mart.runtime import AnalysisExecution, consume_queued_analysis, deterministic_processor, postgres_smoke


def _analysis_options():
    payload = b'{"execution_id":"core-1","snapshot_id":"snapshot-1"}'
    from hashlib import sha256
    return payload, {"core_execution_id": "core-1", "analysis_as_of": "2026-09-10",
                     "core_snapshot_id": "snapshot-1", "schema_version": "1",
                     "feature_version": "1", "model_version": "1",
                     "governance_snapshot_version": "1",
                     "core_snapshot_uri": "gs://core/snapshots/snapshot-1.json",
                     "core_snapshot_hash": f"sha256:{sha256(payload).hexdigest()}"}


class _Cursor:
    def __init__(self, role):
        self.role = role
        self.result = None

    def __enter__(self): return self
    def __exit__(self, *_): pass
    def execute(self, query, params):
        self.result = (True,) if "has_table_privilege" in query else (self.role, "172.17.0.2/32", True)
    def fetchone(self): return self.result


class _Connection:
    def __init__(self, role): self.role = role
    def __enter__(self): return self
    def __exit__(self, *_): pass
    def cursor(self): return _Cursor(self.role)


class MartRuntimeTests(unittest.TestCase):
    def test_smoke_uses_separate_credentials_and_private_postgres(self):
        settings = {
            "CATALOG_DB_HOST": "10.42.0.5", "CATALOG_DB_NAME": "janus_control",
            "CATALOG_DB_USER": "janus_mart_catalog", "CATALOG_DB_PASSWORD": "catalog-secret",
            "PUBLICATION_DB_HOST": "10.42.0.5", "PUBLICATION_DB_NAME": "janus_control",
            "PUBLICATION_DB_USER": "janus_mart_publication", "PUBLICATION_DB_PASSWORD": "publication-secret",
        }
        calls = []

        def connect(**kwargs):
            calls.append(kwargs)
            return _Connection(kwargs["user"])

        with patch.dict(os.environ, settings, clear=True):
            result = postgres_smoke(connect)

        self.assertEqual([call["user"] for call in calls], ["janus_mart_catalog", "janus_mart_publication"])
        self.assertTrue(all(call["connect_timeout"] == 5 for call in calls))
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["databases"]["catalog"]["private"])

    def test_smoke_rejects_public_database_address(self):
        settings = {
            "CATALOG_DB_HOST": "203.0.113.10", "CATALOG_DB_NAME": "db",
            "CATALOG_DB_USER": "janus_mart_catalog", "CATALOG_DB_PASSWORD": "secret",
            "PUBLICATION_DB_HOST": "10.42.0.5", "PUBLICATION_DB_NAME": "db",
            "PUBLICATION_DB_USER": "janus_mart_publication", "PUBLICATION_DB_PASSWORD": "secret",
        }

        class PublicConnection(_Connection):
            def cursor(self):
                cursor = _Cursor(self.role)
                original = cursor.execute
                def execute(query, params):
                    original(query, params)
                    if "inet_server_addr" in query: cursor.result = (self.role, "8.8.8.8", True)
                cursor.execute = execute
                return cursor

        with patch.dict(os.environ, settings, clear=True), self.assertRaisesRegex(RuntimeError, "private"):
            postgres_smoke(lambda **kwargs: PublicConnection(kwargs["user"]))

    def test_analysis_claim_is_not_complete_without_matching_persisted_artifact(self):
        _, options = _analysis_options()
        execution = AnalysisExecution("execution-1", "first-batch", ("2330",), 0, options)

        class Queue:
            def __init__(self): self.transitions = []
            def claim(self, _worker_id): return execution
            def transition(self, *args, **kwargs): self.transitions.append((args, kwargs))

        queue = Queue()
        with self.assertRaisesRegex(ValueError, "persist an artifact"):
            consume_queued_analysis(queue, lambda _: {}, worker_id="mart-1")
        self.assertEqual(queue.transitions[0][0][2], "retrying")

    def test_analysis_completes_only_for_claimed_snapshot_artifact(self):
        _, options = _analysis_options()
        execution = AnalysisExecution("execution-1", "first-batch", ("2330",), 0, options)

        class Queue:
            def __init__(self): self.transitions = []
            def claim(self, _worker_id): return execution
            def transition(self, *args, **kwargs): self.transitions.append((args, kwargs))

        queue = Queue()
        result = consume_queued_analysis(
            queue,
            lambda _: {"artifact_uri": "gs://mart/execution-1/report.json",
                       "core_snapshot_id": "snapshot-1"},
            worker_id="mart-1",
        )
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(queue.transitions[0][0][2], "succeeded")

    def test_deterministic_processor_reads_fenced_core_and_writes_input_artifact(self):
        payload, options = _analysis_options()
        execution = AnalysisExecution("execution-1", "first-batch", ("2330",), 0, options)

        class Store:
            objects = {("core", "snapshots/snapshot-1.json"): payload}
            def __init__(self, bucket): self.bucket = bucket
            def read(self, name): return self.objects[(self.bucket, name)]
            def create(self, name, value, _content_type):
                key = (self.bucket, name)
                if key in self.objects: return False
                self.objects[key] = value
                return True

        with patch.dict(os.environ, {"MART_BUCKET": "mart"}, clear=True):
            first = deterministic_processor(execution, Store)
            stored = Store.objects[("mart", "executions/execution-1/input.json")]
            second = deterministic_processor(execution, Store)

        self.assertEqual(first, second)
        self.assertEqual(first["artifact_uri"], "gs://mart/executions/execution-1/input.json")
        self.assertEqual(json.loads(stored)["core_snapshot_hash"], options["core_snapshot_hash"])


if __name__ == "__main__":
    unittest.main()
