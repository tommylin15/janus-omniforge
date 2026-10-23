"""Regression tests for research market-sector package preflight (offline fixtures)."""
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "research/chatgpt/market_sector_package_preflight.py"
SPEC = importlib.util.spec_from_file_location("market_sector_package_preflight", SCRIPT)
PREFLIGHT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREFLIGHT)

DAYS = ["2025-01-02", "2025-01-03", "2025-01-06", "2025-01-07",
        "2025-01-08", "2025-01-09", "2025-01-10", "2025-01-13",
        "2025-01-14", "2025-01-15"]


def put_partition(root, source, period, records):
    folder = root / source / period[:7]
    if source == "twse_sector":
        folder /= period
    folder.mkdir(parents=True, exist_ok=True)
    raw = json.dumps({"official": "fixture"}, ensure_ascii=False).encode()
    normalized = json.dumps(records, ensure_ascii=False).encode()
    names = []
    for tag, payload in [("raw", raw), ("normalized", normalized)]:
        sha = hashlib.sha256(payload).hexdigest()
        name = f"{tag}-{sha}.json"
        (folder / name).write_bytes(payload)
        names.append((name, sha))
    receipt = {
        "status": "VERIFIED", "source": source, "period": period,
        "rows": len(records), "classification": "RESEARCH_ONLY",
        "retrieved_at_utc": "2026-10-23T00:00:00Z",
        "source_url": "https://www.twse.com.tw/test" if source.startswith("twse") else "https://www.tpex.org.tw/test",
        "normalized": names[1][0], "checksums": dict(names),
        "first_date": min(x["trade_date"] for x in records),
        "last_date": max(x["trade_date"] for x in records),
    }
    (folder / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
    return folder


def fixture(root):
    for prefix, market, idx in [("twse", "TWSE", "TAIEX"), ("tpex", "TPEX", "TPEX")]:
        mk = []
        sect = []
        for day in DAYS:
            mk.append({"market": market, "trade_date": day, "index_id": idx,
                       "open": 100, "high": 105, "low": 95, "close": 102})
            daily = [{"market": market, "trade_date": day, "index_id": f"sector-{i}",
                      "close": 100+i, "type": "sector_price_index"} for i in range(11)]
            sect.extend(daily)
            if prefix == "twse":
                put_partition(root, "twse_sector", day, daily)
        put_partition(root, prefix + "_market", "2025-01", mk)
        if prefix == "tpex":
            put_partition(root, prefix + "_sector", "2025-01", sect)


class MarketSectorPackagePreflightTests(unittest.TestCase):
    def test_consistent_fixture_passes_without_publication(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root)
            output = PREFLIGHT.run(root, "2025-01", "2025-01")
            self.assertEqual(output["status"], "PASS", output["issues"])
            self.assertEqual(output["verified_partitions"], 13)
            self.assertFalse(output["publication_allowed"])
            self.assertEqual(output["industry_membership_crosswalk"], "NOT_VERIFIED")

    def test_modified_payload_fails_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root)
            item = next((root / "tpex_market" / "2025-01").glob("normalized-*.json"))
            item.write_bytes(item.read_bytes() + b" ")
            output = PREFLIGHT.run(root, "2025-01", "2025-01")
            self.assertEqual(output["status"], "BLOCKED")
            self.assertIn("PAYLOAD_SHA_MISMATCH", [v["code"] for v in output["issues"]])

    def test_missing_day_and_ohlc_violation_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root)
            (root / "twse_sector" / "2025-01" / DAYS[0] / "receipt.json").unlink()
            output = PREFLIGHT.run(root, "2025-01", "2025-01")
            codes = {v["code"] for v in output["issues"]}
            self.assertEqual(output["status"], "BLOCKED")
            self.assertIn("MISSING_RECEIPT", codes)
            self.assertIn("TRADING_DAY_SET_MISMATCH", codes)


if __name__ == "__main__":
    unittest.main()
