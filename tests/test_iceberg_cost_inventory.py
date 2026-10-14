"""Bounded Core GCS inventory is read-only and explicit about truncation."""
from __future__ import annotations

from io import BytesIO
import json
import sys
from pathlib import Path
from unittest.mock import patch
import unittest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "jobs" / "ingestion-core"))
from ingestion_core.stage import GcsObjectStore


class BoundedGcsInventoryTests(unittest.TestCase):
    def test_pages_are_bounded_and_classified_without_object_gets(self):
        pages = [
            {"items": [{"name": "warehouse/ohlcv_v1/data/000.parquet", "size": "100"},
                       {"name": "warehouse/ohlcv_v1/metadata/000.metadata.json", "size": "200"}],
             "nextPageToken": "next"},
            {"items": [{"name": "warehouse/ohlcv_v1/metadata/000.avro", "size": "400"},
                       {"name": "executions/e1/core-snapshot.json", "size": "50"}]},
        ]
        urls = []

        def fake_urlopen(request, timeout):
            del timeout
            urls.append(request.full_url)
            return BytesIO(json.dumps(pages[len(urls) - 1]).encode())

        with patch.object(GcsObjectStore, "_token", return_value="redacted"), \
             patch("ingestion_core.stage.urlopen", side_effect=fake_urlopen):
            result = GcsObjectStore("allowed-dev-core").bounded_inventory(max_pages=2)
        self.assertTrue(result["complete"])
        self.assertFalse(result["truncated"])
        self.assertEqual(result["pages"], 2)
        self.assertEqual(result["visible_objects"], 4)
        self.assertEqual(result["visible_bytes"], 750)
        groups = {item["prefix"]: item for item in result["groups"]}
        self.assertEqual(groups["warehouse/ohlcv_v1/data"]["objects"], 1)
        self.assertEqual(groups["warehouse/ohlcv_v1/metadata-json"]["objects"], 1)
        self.assertEqual(groups["warehouse/ohlcv_v1/manifest-avro"]["objects"], 1)
        self.assertEqual(groups["executions"]["objects"], 1)
        self.assertIn("maxResults=1000", urls[0])
        self.assertIn("pageToken=next", urls[1])
        self.assertTrue(all("/o?" in url for url in urls))

    def test_page_budget_never_silently_presents_partial_count_as_complete(self):
        page = {"items": [{"name": "warehouse/valuation_v1/data/000.parquet", "size": "9"}],
                "nextPageToken": "more"}
        with patch.object(GcsObjectStore, "_token", return_value="redacted"), \
             patch("ingestion_core.stage.urlopen", return_value=BytesIO(json.dumps(page).encode())) as call:
            result = GcsObjectStore("allowed-dev-core").bounded_inventory(max_pages=1)
        self.assertFalse(result["complete"])
        self.assertTrue(result["truncated"])
        self.assertEqual(result["visible_objects"], 1)
        self.assertEqual(call.call_count, 1)

    def test_invalid_inventory_budget_rejected_without_io(self):
        with self.assertRaises(ValueError):
            GcsObjectStore("allowed-dev-core").bounded_inventory(max_pages=0)
        with self.assertRaises(ValueError):
            GcsObjectStore("allowed-dev-core").bounded_inventory(max_pages=26)


if __name__ == "__main__":
    unittest.main()
