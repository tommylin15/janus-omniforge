import importlib.util
import json
from pathlib import Path
import unittest


class GapMatrixTests(unittest.TestCase):
    def test_active_targets_and_unqualified_history_stay_visible(self):
        root = Path(__file__).parents[1]
        spec = importlib.util.spec_from_file_location("gap_matrix", root / "ops/data-supplement-gap-matrix.py")
        probe = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(probe)
        runtime = json.loads((root / "ops/data-supplement-s0-runtime.json").read_text(encoding="utf-8"))
        matrix = probe.build_matrix(runtime)
        self.assertEqual(set(matrix["active_target_symbols"]), {"2327", "2330", "5876"})
        self.assertEqual({row["role"] for row in matrix["rows"]},
                         {"fundamental", "valuation", "positioning", "quant", "event_risk"})
        history = next(row for row in matrix["rows"] if row["symbol"] == "2327" and row["feature_id"] == "financial_history_12q")
        self.assertEqual(history["available_history"]["qualified_period_count"], 1)
        self.assertTrue(history["blocking"])
        broken = dict(runtime, symbols={key: value for key, value in runtime["symbols"].items() if key != "5876"})
        with self.assertRaises(ValueError):
            probe.build_matrix(broken)
