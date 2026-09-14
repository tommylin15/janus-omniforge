import json
import sys
import unittest
from datetime import date
from hashlib import sha256
from pathlib import Path


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from packages.web_api.public import (IcebergArtifactReader, PostgreSQLPublicIndex, PublicMartService,
                                     PublicReportNotFound, PublicReportWaiting, PublicStockNotFound)


class _Index:
    def __init__(self, value): self.value = value
    def latest(self, *_args): return self.value
    def symbol_enabled(self, symbol): return symbol == "2330"


class PublicMartTests(unittest.TestCase):
    def test_publication_index_queries_only_the_publishable_view(self):
        calls = []

        class Cursor:
            def __enter__(self): return self
            def __exit__(self, *_args): pass
            def execute(self, sql, parameters): calls.append((sql, parameters))
            def fetchone(self): return None

        class Connection:
            def cursor(self): return Cursor()

        PostgreSQLPublicIndex(Connection()).latest("symbol", "2330", date(2026, 9, 12))
        self.assertIn("FROM publication.publishable_mart_reports", calls[0][0])
        self.assertNotIn("publication.mart_report_index", calls[0][0])
        self.assertEqual(calls[0][1], ["symbol", "2330", date(2026, 9, 12)])

    def test_stock_lookup_queries_only_the_enabled_publication_view(self):
        calls = []

        class Cursor:
            def __enter__(self): return self
            def __exit__(self, *_args): pass
            def execute(self, sql, parameters): calls.append((sql, parameters))
            def fetchone(self): return (1,)

        class Connection:
            def cursor(self): return Cursor()

        self.assertTrue(PostgreSQLPublicIndex(Connection()).symbol_enabled("2330"))
        self.assertIn("FROM publication.enabled_stock_symbols", calls[0][0])
        self.assertNotIn("control.stock_master", calls[0][0])

    def test_public_index_reconnects_once_after_connection_failure(self):
        class Disconnected(Exception):
            sqlstate = "08006"

        class Cursor:
            def __init__(self, value): self.value = value
            def __enter__(self): return self
            def __exit__(self, *_args): pass
            def execute(self, *_args):
                if isinstance(self.value, Exception): raise self.value
            def fetchone(self): return self.value

        class Connection:
            closed = False
            def __init__(self, value): self.value = value
            def cursor(self): return Cursor(self.value)
            def close(self): self.closed = True

        replacements = [Connection((1,))]
        index = PostgreSQLPublicIndex(Connection(Disconnected("lost")), lambda: replacements.pop())
        self.assertTrue(index.symbol_enabled("2330"))
        self.assertEqual(replacements, [])

    def test_public_index_does_not_retry_sql_or_permission_errors(self):
        class Cursor:
            def __enter__(self): return self
            def __exit__(self, *_args): pass
            def execute(self, *_args): raise PermissionError("denied")
        class Connection:
            closed = False
            def cursor(self): return Cursor()

        reconnects = []
        with self.assertRaises(PermissionError):
            PostgreSQLPublicIndex(Connection(), lambda: reconnects.append(True)).symbol_enabled("2330")
        self.assertEqual(reconnects, [])

    def test_symbol_policy_distinguishes_missing_stock_from_waiting_report(self):
        with self.assertRaises(PublicStockNotFound):
            PublicMartService(_Index(None), lambda _: {}).report("symbol", "9999")
        with self.assertRaises(PublicReportWaiting):
            PublicMartService(_Index(None), lambda _: {}).report("symbol", "2330")

    def test_only_complete_publishable_artifact_is_returned(self):
        index = {"execution_id": "exec-1", "analysis_as_of": date(2026, 9, 12), "scope_type": "symbol", "scope_id": "2330"}
        row = {**index, "publication_status": "published", "analysis_outcome": "complete", "confidence": .8,
               "completeness": .9, "schema_version": "1", "model_version": "1",
               "governance_snapshot_version": "gov-1", "payload_json": json.dumps({"score": 80})}
        result = PublicMartService(_Index(index), lambda _: row).report("symbol", "2330")
        self.assertEqual(result["data"], {"score": 80})
        self.assertEqual(result["execution_id"], "exec-1")
        self.assertNotIn("artifact_uri", result)

    def test_blocked_or_insufficient_artifact_fails_closed(self):
        index = {"execution_id": "exec-1", "analysis_as_of": "2026-09-12", "scope_type": "symbol", "scope_id": "2330"}
        for outcome in ("risk_blocked", "insufficient_data"):
            row = {**index, "publication_status": "blocked", "analysis_outcome": outcome}
            with self.assertRaises(PublicReportNotFound):
                PublicMartService(_Index(index), lambda _: row).report("symbol", "2330")

    def test_payload_with_storage_or_secret_fields_fails_closed(self):
        index = {"execution_id": "exec-1", "analysis_as_of": "2026-09-12", "scope_type": "symbol", "scope_id": "2330"}
        row = {**index, "publication_status": "published", "analysis_outcome": "complete", "confidence": .8,
               "completeness": .9, "schema_version": "1", "model_version": "1",
               "governance_snapshot_version": "gov-1",
               "payload_json": json.dumps({"score": 80, "evidence": {"access_token": "must-not-leak"}})}
        with self.assertRaisesRegex(ValueError, "forbidden field"):
            PublicMartService(_Index(index), lambda _: row).report("symbol", "2330")

    def test_reader_verifies_gcs_hash_and_exact_snapshot(self):
        metadata = b"immutable metadata"
        index = {"artifact_uri": "gs://mart/metadata/1.json", "artifact_hash": f"sha256:{sha256(metadata).hexdigest()}",
                 "table_identifier": "mart.mart_scoped_analysis_v1", "iceberg_snapshot_id": 42,
                 "execution_id": "exec-1", "scope_type": "symbol", "scope_id": "2330"}
        scan_calls = []
        class Scan:
            def to_arrow(self): return type("Arrow", (), {"to_pylist": lambda self: [{"payload_json": "{}"}]})()
        class Table:
            def scan(self, **kwargs): scan_calls.append(kwargs); return Scan()
        class Catalog:
            def load_table(self, identifier): self.identifier = identifier; return Table()
        class Store:
            def read(self, name): self.name = name; return metadata
        reader = IcebergArtifactReader(Catalog(), lambda bucket: Store())
        reader(index)
        self.assertEqual(scan_calls[0]["snapshot_id"], 42)


if __name__ == "__main__":
    unittest.main()
