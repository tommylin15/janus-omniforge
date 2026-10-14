"""Unit tests for read-only Cloud Monitoring GCS operation aggregation."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


path = Path(__file__).parents[1] / "scripts" / "gcp" / "iceberg-gcs-ops-audit.py"
spec = importlib.util.spec_from_file_location("iceberg_gcs_ops_audit", path)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class GcsOpsAuditTests(unittest.TestCase):
    def test_aggregate_by_bucket_method_does_not_call_unknown_cost_zero(self):
        series = [
            {"resource": {"labels": {"bucket_name": "janus-dev-core"}},
             "metric": {"labels": {"method": "ReadObject"}},
             "points": [{"value": {"int64Value": "100"}}, {"value": {"int64Value": "35"}}]},
            {"resource": {"labels": {"bucket_name": "janus-dev-core"}},
             "metric": {"labels": {"method": "ListObjects"}},
             "points": [{"value": {"int64Value": "20"}}]},
            {"resource": {"labels": {"bucket_name": "janus-dev-stage"}},
             "metric": {"labels": {"method": "WriteObject"}},
             "points": [{"value": {"int64Value": "50"}}]},
        ]
        result = audit.aggregate_series(series)
        self.assertEqual(result["total_requests"], 205)
        self.assertEqual(result["buckets"][0], {"bucket": "janus-dev-core", "requests": 155})
        self.assertEqual(result["methods"][0],
                         {"bucket": "janus-dev-core", "method": "ReadObject", "requests": 135})

    def test_empty_series_is_empty_counter_not_billing_proof(self):
        result = audit.aggregate_series([])
        self.assertEqual(result["total_requests"], 0)
        self.assertEqual(result["buckets"], [])


if __name__ == "__main__":
    unittest.main()
