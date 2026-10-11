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

    def test_logical_filename_hash_is_not_immutable_bytes_hash(self):
        """Regression: GCS path uses payload output_hash, ref uses full-byte SHA256."""
        from unittest.mock import patch

        manifest, evaluation, artifacts = fixture()
        execution = "11111111-1111-4111-8111-111111111111"
        base = "gs://" + b9.BUCKET + "/"
        manifest_uri = base + "executions/" + execution + "/specialist-manifest.json"
        eval_uri = base + "executions/" + execution + "/oos-evaluation.json"
        eval_hash = "sha256:" + "e" * 64
        manifest["execution_id"] = execution
        manifest["evaluation"] = {"artifact_uri": eval_uri, "artifact_hash": eval_hash}
        responses = {manifest_uri: (manifest, "sha256:" + "f" * 64),
                     eval_uri: (evaluation, eval_hash)}
        for i, (ref, artifact) in enumerate(zip(manifest["specialists"], artifacts, strict=True), start=1):
            logical_hash = "sha256:" + f"{i:064x}"
            bytes_hash = "sha256:" + f"{i+10:064x}"
            artifact["output_hash"] = logical_hash
            uri = base + "specialists/" + logical_hash[7:] + ".json"
            ref.update(artifact_uri=uri, artifact_hash=bytes_hash)
            responses[uri] = (artifact, bytes_hash)
        with patch.object(b9, "_read_gcs_json", side_effect=lambda uri: responses[uri]):
            result = b9.audit(manifest_uri, CORE)
            self.assertEqual(result["specialist_artifacts_verified"], 5)
            self.assertEqual(result["model_quality"], "not_verified")

            # Tampering with one byte-level hash must still fail closed.
            manifest["specialists"][0]["artifact_hash"] = "sha256:" + "0" * 64
            with self.assertRaisesRegex(b9.AuditError, "bytes hash mismatch"):
                b9.audit(manifest_uri, CORE)

    def test_v5_prediction_lineage_is_present_but_not_automatically_promoted(self):
        manifest, evaluation, artifacts = fixture()
        prediction = evaluation[0]["predictions"][0]
        prediction.update(sample_source_authorization="official",
                          sample_provenance_id="sha256:input-evidence",
                          feature_available_at="2026-08-01",
                          label_available_at="2026-08-08")
        r = b9.summarize(manifest, evaluation, artifacts, expected_core=CORE)
        self.assertEqual(r["prediction_lineage_present"], 1)
        self.assertEqual(r["prediction_lineage_legacy_missing"], 0)
        self.assertEqual(r["per_prediction_source_authorization_and_provenance"],
                         "fields_present_and_temporally_valid_source_readback_not_verified")
        self.assertFalse(r["champion_promotion"])
        self.assertEqual(r["model_quality"], "not_verified")
        prediction["feature_available_at"] = "2026-08-02"
        with self.assertRaisesRegex(b9.AuditError, "PIT/label availability"):
            b9.summarize(manifest, evaluation, artifacts, expected_core=CORE)

    def test_partial_prediction_lineage_fails_closed(self):
        manifest, evaluation, artifacts = fixture()
        evaluation[0]["predictions"][0]["sample_source_authorization"] = "official"
        with self.assertRaisesRegex(b9.AuditError, "partially persisted OOS"):
            b9.summarize(manifest, evaluation, artifacts, expected_core=CORE)

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


    def test_model_diagnostics_keep_partial_with_realistic_small_cohort(self):
        manifest, evaluation, artifacts = fixture()
        item = evaluation[0]
        item["predictions"][0].update(prediction=0.03, excess_return=0.02,
                                      probability=0.55)
        report = b9.summarize(manifest, evaluation, artifacts, expected_core=CORE)
        detail = report["roles"]["fundamental"]["oos_evaluations"][0]["diagnostics"]
        self.assertEqual(detail["paired_forecasts"], 1)
        self.assertEqual(detail["max_same_date_symbols"], 1)
        self.assertEqual(detail["dates_with_at_least_10_symbols"], 0)
        self.assertAlmostEqual(detail["mse_constant_zero"], 0.0004)
        self.assertIsNone(detail["brier"])
        self.assertIn("historical_pit_membership_not_verified", detail["quality_blockers"])
        self.assertIn("probability_calibration_insufficient", detail["quality_blockers"])
        self.assertEqual(report["roles"]["event"]["quality_blockers"],
                         ["authorized_human_labels_and_classifier_oos_missing"])
        self.assertEqual(report["model_quality"], "not_verified")

    def test_regime_monthly_challenger_stability_is_descriptive_only(self):
        manifest, evaluation, artifacts = fixture()
        evaluation.append({
            "core_snapshot_id": CORE, "model_name": "statsmodels_markov_regime",
            "status": "research_oos_evaluated", "promotion_eligible": False,
            "oos_returns": 40,
            "oos_folds": [
                {"month": "2026-07", "test_returns": 20,
                 "markov_log_score_sum": 45., "gaussian_log_score_sum": 40.},
                {"month": "2026-08", "test_returns": 20,
                 "markov_log_score_sum": 38., "gaussian_log_score_sum": 40.},
            ],
        })
        report = b9.summarize(manifest, evaluation, artifacts, expected_core=CORE)
        diagnostic = report["roles"]["risk"]["oos_evaluations"][0]["diagnostics"]
        self.assertEqual(diagnostic["positive_improvement_months"], 1)
        self.assertEqual(diagnostic["nonpositive_improvement_months"], 1)
        self.assertAlmostEqual(diagnostic["worst_monthly_improvement"], -0.1)
        self.assertEqual(report["roles"]["risk"]["quality_gate"], "not_verified")
        self.assertEqual(diagnostic["daily_environment_evidence_status"],
                         "unavailable_legacy_monthly_aggregate")
        self.assertIsNone(diagnostic["environment_and_tail"])
        self.assertEqual(diagnostic["longest_nonpositive_month_streak"], 1)
        self.assertAlmostEqual(diagnostic["return_weighted_log_score_improvement"], 0.075)
        self.assertEqual(len(diagnostic["monthly_scores"]), 2)

    def test_regime_daily_prior_only_tail_and_volatility_are_reconciled(self):
        manifest, evaluations, artifacts = fixture()
        risk = {
            "core_snapshot_id": CORE, "model_name": "statsmodels_markov_regime",
            "status": "research_oos_evaluated", "promotion_eligible": False,
            "oos_returns": 4, "oos_folds": [
                {"month": "2026-07", "training_end": "2026-06-30",
                 "test_start": "2026-07-01", "test_end": "2026-07-02",
                 "test_returns": 2, "markov_log_score_sum": 3.0, "gaussian_log_score_sum": 2.0},
                {"month": "2026-08", "training_end": "2026-07-31",
                 "test_start": "2026-08-01", "test_end": "2026-08-02",
                 "test_returns": 2, "markov_log_score_sum": -1.0, "gaussian_log_score_sum": 2.0},
            ],
        }
        records = [
            ("2026-07-01", "2026-06-30", 0.02, 2.0, 1.0, 0.9),
            ("2026-07-02", "2026-06-30", -0.03, 1.0, 1.0, 0.8),
            ("2026-08-01", "2026-07-31", 0.001, -1.0, 1.0, 0.1),
            ("2026-08-02", "2026-07-31", 0.004, 0.0, 1.0, 0.2),
        ]
        risk["risk_oos_daily"] = [{
            "date": day, "month": day[:7], "training_end": train,
            "market_return": observed, "markov_log_score": markov,
            "gaussian_log_score": gaussian, "predicted_high_vol_probability": state,
            "realized_high_vol": abs(observed) >= 0.01,
            "realized_extreme_vol": abs(observed) >= 0.025,
            "realized_left_tail": observed <= -0.02,
            "markov_tail_probability": 0.12,
            "gaussian_tail_probability": 0.05,
            "historical_abs_vol_p75": 0.01, "historical_abs_vol_p95": 0.025,
            "historical_left_tail_p05": -0.02,
        } for day, train, observed, markov, gaussian, state in records]
        evaluations.append(risk)
        detail = b9.summarize(manifest, evaluations, artifacts, expected_core=CORE)[
            "roles"]["risk"]["oos_evaluations"][0]["diagnostics"]
        self.assertEqual(detail["daily_environment_evidence_status"],
                         "reconciled_prior_only_oos_daily_diagnostics")
        self.assertEqual(detail["environment_and_tail"]["state_switches"], 1)
        self.assertEqual(detail["environment_and_tail"]["tail_events"], 1)
        self.assertEqual(detail["environment_and_tail"]["groups"]["high_realized_vol"]["observations"], 2)
        self.assertEqual(detail["environment_and_tail"]["groups"]["low_realized_vol"]["observations"], 2)
        self.assertEqual(detail["longest_nonpositive_month_streak"], 1)
        self.assertEqual(detail["positive_improvement_months"], 1)
        self.assertEqual(detail["nonpositive_improvement_months"], 1)
        self.assertAlmostEqual(detail["return_weighted_log_score_improvement"], -0.5)
        self.assertFalse(b9.summarize(manifest, evaluations, artifacts, expected_core=CORE)["champion_promotion"])

        # A byte-valid future-dated training fence or changed daily density must fail closed.
        risk["risk_oos_daily"][0]["training_end"] = "2026-07-01"
        with self.assertRaisesRegex(b9.AuditError, "training"):
            b9.summarize(manifest, evaluations, artifacts, expected_core=CORE)
        risk["risk_oos_daily"][0]["training_end"] = "2026-06-30"
        risk["risk_oos_daily"][0]["markov_log_score"] += 1
        with self.assertRaisesRegex(b9.AuditError, "reconcile"):
            b9.summarize(manifest, evaluations, artifacts, expected_core=CORE)

    def test_valid_cross_section_still_requires_historical_membership(self):
        manifest, evaluation, artifacts = fixture()
        template = evaluation[0]["predictions"][0]
        evaluation[0]["predictions"] = [
            {**template, "symbol": f"SYM{i}", "prediction": i / 100.,
             "excess_return": i / 200.} for i in range(10)
        ]
        report = b9.summarize(manifest, evaluation, artifacts, expected_core=CORE)
        detail = report["roles"]["fundamental"]["oos_evaluations"][0]["diagnostics"]
        self.assertEqual(detail["max_same_date_symbols"], 10)
        self.assertEqual(detail["dates_with_at_least_10_symbols"], 1)
        self.assertIn("historical_pit_membership_not_verified", detail["quality_blockers"])
        self.assertFalse(report["champion_promotion"])



if __name__ == "__main__":
    unittest.main()
