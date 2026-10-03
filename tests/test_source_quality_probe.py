import importlib.util
from pathlib import Path
import unittest
import tempfile
import json
from unittest.mock import patch


class SourceQualityTests(unittest.TestCase):
    def test_eps_comparison_requires_a_direct_single_quarter_context(self):
        root = Path(__file__).parents[1]
        spec = importlib.util.spec_from_file_location("xbrl_probe", root / "ops/data-supplement-xbrl-probe.py")
        probe = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(probe)
        row = {"stock_id": "2327", "date": "2026-06-30", "type": "EPS", "value": 4.59}
        cumulative = {"concept": "ifrs-full:BasicEarningsLossPerShare", "period_start": "2026-01-01",
                      "period_end": "2026-06-30", "period_basis": "year_to_date", "value": "8.48",
                      "unit": "TWD_per_share", "context_id": "h1"}
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, "janus-finmind-2327-TaiwanStockFinancialStatements.json").write_text(json.dumps({"data": [row]}))
            with patch.object(probe.tempfile, "gettempdir", return_value=folder):
                result = probe.crosscheck_facts([cumulative], "2327", 2026, 2)
                self.assertEqual(result["checks"], [])
                single = dict(cumulative, period_start="2026-04-01", period_basis="single_quarter", value="4.59", context_id="q2")
                result = probe.crosscheck_facts([cumulative, single], "2327", 2026, 2)
                self.assertEqual((result["matched"], result["mismatched"]), (1, 0))

    def test_conflicts_invalid_numbers_and_wrong_identity_are_detected(self):
        spec = importlib.util.spec_from_file_location("quality_probe", Path(__file__).parents[1] / "ops/data-supplement-source-quality.py")
        probe = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(probe)
        rows = [{"stock_id": "2327", "date": "2026-06-30", "type": "EPS", "value": value}
                for value in (4.59, 4.59, 4.58, "NaN")]
        result = probe.audit_rows(rows, "2327", "TaiwanStockFinancialStatements")
        self.assertEqual(result["duplicate_keys"], 3)
        self.assertEqual(result["conflicting_keys"], 1)
        self.assertEqual(len(result["invalid_values"]), 1)
        self.assertFalse(result["pit_numeric_revision_verified"])
        with self.assertRaises(ValueError):
            probe.audit_rows(rows, "2330", "TaiwanStockFinancialStatements")

        official = {"year": "115", "seasonName": "上半年度", "companyAbbreviation": "國巨*",
                    "subsidiary": [{"companyId": "2327"}],
                    "CCSI": {"unit": "單位：新台幣仟元"}, "CAL": {"unit": "單位：新台幣仟元", "urlList": [
                        {"url": "https://mopsov.twse.com.tw/server-java/t164sb01?CO_ID=2327&SYEAR=2026&SSEASON=2"}]}}
        probe.validate_official_result(official, "2327", 2, "國巨*")
        with self.assertRaises(ValueError):
            probe.validate_official_result(official, "2330", 2, "國巨*")
        with self.assertRaises(ValueError):
            probe.validate_official_result(official, "2327", 1, "國巨*")
        with self.assertRaises(ValueError):
            probe.validate_official_result(official | {"CAL": {"unit": "元"}}, "2327", 2, "國巨*")
