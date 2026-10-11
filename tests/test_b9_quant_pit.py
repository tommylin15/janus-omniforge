"""B9 Quant PIT retrospective research unit gates (fixtures are NOT live evidence)."""
from datetime import date, timedelta
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jobs" / "intelligence-mart"))
from intelligence_mart.quant_pit import MODELS, compare_four_models, historical_liquid_universe

CORE = "sha256:" + "a" * 64


def fixture():
    days = [(date(2026, 1, 1) + timedelta(days=i)).isoformat() for i in range(42)
            if (date(2026, 1, 1) + timedelta(days=i)).weekday() < 5]
    rows = []
    for symbol in range(1101, 1113):
        for day in days:
            rows.append({"symbol": str(symbol), "trade_date": day,
                         "turnover_twd": 1000 + symbol + 5 * days.index(day),
                         "source_authorization": "official",
                         "provenance_id": f"{symbol}-{day}",
                         "observed_at": day, "availability_at": day, "published_at": day})
    return days, rows


def model_inputs(days, cohort):
    chosen = [days[4], days[9], days[14]]
    predictions = {name: [] for name in MODELS}
    for day in chosen:
        for idx, symbol in enumerate(cohort["historical_universe"][day]["symbols"]):
            label = (idx - 5) / 500
            for offset, model in enumerate(MODELS):
                predictions[model].append({
                    "symbol": symbol, "analysis_as_of": day,
                    "outcome_as_of": days[days.index(day) + 5],
                    "excess_return": label, "momentum_5d": idx - 5,
                    "prediction": (idx - 5) / 1000 + offset / 100000,
                    "historical_universe_hash": cohort["historical_universe"][day]["membership_hash"],
                    "sample_source_authorization": "official",
                    "sample_provenance_id": f"approved-{symbol}-{day}",
                    "training_label_cutoff": days[0],
                    "feature_available_at": day,
                    "label_available_at": days[days.index(day) + 5],
                })
    return predictions


class TestQuantPit(unittest.TestCase):
    def test_as_known_prior_session_universe(self):
        days, rows = fixture()
        before = [dict(row) for row in rows]
        cohort = historical_liquid_universe(rows, days, core_snapshot_id=CORE,
                                            lookback=2, minimum=10, limit=10)
        self.assertNotIn(days[0], cohort["historical_universe"])
        entry = cohort["historical_universe"][days[2]]
        self.assertEqual(entry["selection_as_of"], days[1])
        self.assertEqual(len(entry["symbols"]), 10)
        self.assertTrue(cohort["research_only"])
        self.assertFalse(cohort["promotion_eligible"])
        self.assertEqual(cohort["source_replay_readback"], "not_verified")
        self.assertEqual(rows, before)

    def test_utc_date_rollover_and_naive_clock_are_not_backdated(self):
        from intelligence_mart.quant_pit import _day
        self.assertEqual(_day("2026-10-10T17:00:00Z").isoformat(), "2026-10-11")
        with self.assertRaisesRegex(ValueError, "timezone"):
            _day("2026-10-10T17:00:00")

    def test_later_backfill_cannot_be_backdated(self):
        days, rows = fixture()
        for row in rows:
            row["observed_at"] = days[-1]
        cohort = historical_liquid_universe(rows, days, core_snapshot_id=CORE,
                                            lookback=2, minimum=10, limit=10)
        self.assertFalse(cohort["historical_universe"])
        self.assertGreater(cohort["source_rejections"].get("not_known_before_entry", 0), 0)

    def test_source_missing_and_conflict_fail_closed(self):
        days, rows = fixture()
        rows[0]["source_authorization"] = "unknown"
        cohort = historical_liquid_universe(rows, days, core_snapshot_id=CORE,
                                            lookback=2, minimum=10, limit=10)
        self.assertGreater(cohort["source_rejections"]["unauthorized_or_unproven"], 0)
        days, rows = fixture()
        duplicate = dict(rows[0], turnover_twd=999999)
        with self.assertRaisesRegex(ValueError, "conflicting"):
            historical_liquid_universe([*rows, duplicate], days, core_snapshot_id=CORE,
                                       lookback=2, minimum=10, limit=10)

    def test_matched_four_model_rank_turnover_and_cost(self):
        days, rows = fixture()
        cohort = historical_liquid_universe(rows, days, core_snapshot_id=CORE,
                                            lookback=2, minimum=10, limit=10)
        report = compare_four_models(model_inputs(days, cohort), cohort, days,
                                     horizon_days=5, cost_bps=30)
        self.assertEqual(report["sessions"], 3)
        self.assertEqual(report["status"], "descriptive_only")
        self.assertTrue(report["matched_panel"])
        self.assertEqual(set(report["models"]), {*MODELS, "momentum_rule"})
        for value in report["models"].values():
            self.assertEqual(value["cross_sections"], 3)
            self.assertLess(value["after_cost_return"], value["gross_return"])
            self.assertGreater(value["mean_one_way_traded_notional"], 0)
        self.assertFalse(report["quality_pass"])
        self.assertFalse(report["champion_promotion"])

    def test_membership_hash_tampering_rejected_from_matched_panel(self):
        days, rows = fixture()
        cohort = historical_liquid_universe(rows, days, core_snapshot_id=CORE,
                                            lookback=2, minimum=10, limit=10)
        predictions = model_inputs(days, cohort)
        predictions["lightgbm"][0]["historical_universe_hash"] = "sha256:bad"
        report = compare_four_models(predictions, cohort, days, horizon_days=5)
        self.assertGreater(report["excluded"]["invalid_prediction_lineage_or_leakage"], 0)
        self.assertEqual(report["status"], "descriptive_only")
        self.assertFalse(report["quality_pass"])

    def test_no_source_builds_no_fake_features_or_models(self):
        from intelligence_mart.quant_pit import prepare_historical_quant_samples
        days, rows = fixture()
        result = prepare_historical_quant_samples({"ohlcv": []}, days, as_of=days[-1],
                                                   core_snapshot_id=CORE,
                                                   horizon_days=5)
        self.assertEqual(result["status"], "insufficient_historical_pit")
        self.assertEqual(result["samples"], [])
        self.assertFalse(result["cohort"]["promotion_eligible"])

    def test_missing_model_rows_do_not_backfill_labels(self):
        days, rows = fixture()
        cohort = historical_liquid_universe(rows, days, core_snapshot_id=CORE,
                                            lookback=2, minimum=10, limit=10)
        predictions = model_inputs(days, cohort)
        predictions["qlib_double_ensemble"] = []
        report = compare_four_models(predictions, cohort, days, horizon_days=5)
        self.assertEqual(report["sessions"], 0)
        self.assertEqual(report["status"], "insufficient_oos_cross_sections")
        self.assertIsNone(report["models"]["linear"]["rank_ic"])
        self.assertIsNone(report["models"]["linear"]["after_cost_return"])
        self.assertGreater(report["excluded"]["missing_matched_model_prediction"], 0)

    def test_mismatched_labels_and_duplicate_predictions_rejected(self):
        days, rows = fixture()
        cohort = historical_liquid_universe(rows, days, core_snapshot_id=CORE,
                                            lookback=2, minimum=10, limit=10)
        predictions = model_inputs(days, cohort)
        predictions["catboost"][0]["excess_return"] = 123
        with self.assertRaisesRegex(ValueError, "mismatched"):
            compare_four_models(predictions, cohort, days)
        predictions = model_inputs(days, cohort)
        predictions["linear"].append(dict(predictions["linear"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            compare_four_models(predictions, cohort, days)


if __name__ == "__main__":
    unittest.main()
