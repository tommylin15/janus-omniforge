import json
import sys
import unittest
from datetime import date
from hashlib import sha256
from pathlib import Path


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from packages.web_api.public import IcebergArtifactReader, PublicMartService, PublicReportNotFound


class _Index:
    def __init__(self, value): self.value = value
    def latest(self, *_args): return self.value


class PublicMartTests(unittest.TestCase):
    def test_only_complete_publishable_artifact_is_returned(self):
        index = {"execution_id": "exec-1", "analysis_as_of": date(2026, 9, 12), "scope_type": "symbol", "scope_id": "2330"}
        row = {**index, "publication_status": "published", "analysis_outcome": "complete", "confidence": .8,
               "completeness": .9, "schema_version": "1", "model_version": "1",
               "governance_snapshot_version": "gov-1", "payload_json": json.dumps({"score": 80})}
        result = PublicMartService(_Index(index), lambda _: row).report("symbol", "2330")
        self.assertEqual(result["data"], {"score": 80})
        self.assertNotIn("artifact_uri", result)

    def test_blocked_or_insufficient_artifact_fails_closed(self):
        index = {"execution_id": "exec-1", "analysis_as_of": "2026-09-12", "scope_type": "symbol", "scope_id": "2330"}
        for outcome in ("risk_blocked", "insufficient_data"):
            row = {**index, "publication_status": "blocked", "analysis_outcome": outcome}
            with self.assertRaises(PublicReportNotFound):
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
