"""B9 immutable OOS audit and fail-closed quality-gate unit tests."""
import importlib.util
from pathlib import Path
import unittest


FILE = Path(__file__).resolve().parents[1] / "scripts/gcp/b9-specialist-oos-quality.py"
SPEC = importlib.util.spec_from_file_location("b9_quality", FILE)
b9 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(b9)
CORE = "sha256:" + "a" * 64


def fixture():
    refs, artifacts = [], []
    for role in b9.ROLES:
        refs.append({"symbol": "TEST", "role": role,
                     "input_hash": CORE, "source_core_snapshot_id": CORE})
        artifacts.append({
            "artifact_kind": "mart_specialist_v1", "symbol": "TEST",
            "role": role, "input_hash": CORE, "core_snapshot_id": CORE,
            "model_status": "oos_not_validated", "status": "partial",
            "publication_authority": False, "llm_api_tokens": 0,
            "ceo_triggered": False, "plain_language": "尚未通過模型品質驗收",
            "feature_contributions": [], "metrics": {}, "missing_data": ["model"],
            "provenance_ids": ["source"],
        })
    manifest = {
        "artifact_kind": "mart_specialist_execution_v1",
        "core_snapshot_id": CORE, "llm_api_tokens": 0,
        "ceo_triggered": False, "publication_authority": False,
        "specialists": refs,
    }
    evaluation = [{
        "artifact_kind": "mart_oos_evaluation_v1",
        "core_snapshot_id": CORE, "specialist_role": "fundamental",
        "model_name": "lightgbm", "horizon_days": 5,
        "status": "evaluated", "promotion_eligible": False,
        "folds": [{"month": "2026-08"}],
        "predictions": [{
            "symbol": "TEST", "training_label_cutoff": "2026-07-25",
            "analysis_as_of": "2026-08-01", "outcome_as_of": "2026-08-08",
        }],
        "metrics": {"rank_ic": 0.1, "probability_calibration": {"status": "insufficient_oos_predictions"}},
    }]
    return manifest, evaluation, artifacts


class B9QualityTests(unittest.TestCase):
    def test_evaluated_fold_does_not_promote_champion_or_pass_quality(self):
        manifest, evaluation, artifacts = fixture()
        r = b9.summarize(manifest, evaluation, artifacts, expected_core=CORE)
        self.assertEqual(r["artifact_integrity"], "pass")
        self.assertEqual(r["model_quality"], "not_verified")
        self.assertEqual(r["b9_status"], "partial")
        self.assertFalse(r["champion_promotion"])
        self.assertEqual(r["oos_evaluations_with_samples"], 1)
        self.assertEqual(r["roles"]["event"]["reason"], "no_persisted_event_classifier_oos")
        self.assertEqual(r["per_prediction_source_authorization_and_provenance"],
                         "not_independently_in_persisted_predictions")

    def test_rejects_stale_or_mismatched_core(self):
        manifest, evaluation, artifacts = fixture()
        with self.assertRaisesRegex(b9.AuditError, "Core differs"):
            b9.summarize(manifest, evaluation, artifacts, expected_core="sha256:" + "b" * 64)

    def test_rejects_invalid_future_leakage(self):
        manifest, evaluation, artifacts = fixture()
        evaluation[0]["predictions"][0]["training_label_cutoff"] = "2026-08-01"
        with self.assertRaisesRegex(b9.AuditError, "leakage"):
            b9.summarize(manifest, evaluation, artifacts, expected_core=CORE)

    def test_rejects_any_automatic_promotion(self):
        manifest, evaluation, artifacts = fixture()
        evaluation[0]["promotion_eligible"] = True
        with self.assertRaisesRegex(b9.AuditError, "promotion"):
            b9.summarize(manifest, evaluation, artifacts, expected_core=CORE)

    def test_rejects_missing_fifth_role(self):
        manifest, evaluation, artifacts = fixture()
        manifest["specialists"].pop()
        artifacts.pop()
        with self.assertRaisesRegex(b9.AuditError, "five specialist"):
            b9.summarize(manifest, evaluation, artifacts, expected_core=CORE)

    def test_rejects_llm_token_or_publication_boundary_violation(self):
        manifest, evaluation, artifacts = fixture()
        artifacts[0]["llm_api_tokens"] = 1
        with self.assertRaisesRegex(b9.AuditError, "governance contract"):
            b9.summarize(manifest, evaluation, artifacts, expected_core=CORE)


if __name__ == "__main__":
    unittest.main()
