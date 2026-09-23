import json
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]


class ContractRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = json.loads((ROOT / "packages/contracts/registry.json").read_text())
        cls.policy = json.loads((ROOT / "packages/governance/policy.json").read_text())

    def test_janus_contracts_exist_and_agent_schemas_are_absent(self):
        self.assertIn("twse", self.registry["sourceIds"])
        self.assertIn("core", self.registry["datasetIds"])
        self.assertIn("CoreDatasetReadyV1", self.registry["schemas"])
        self.assertIn("MartReportReadyV1", self.registry["schemas"])
        for schema_name in ("RuntimeBindingV1", "AgentEventV1", "ContextEgressV1", "ContextSourceV1",
                            "ContextSelectorV1", "ContextPreviewV1", "ContextResolveV1", "ApprovalRequestV1"):
            self.assertNotIn(schema_name, self.registry["schemas"])
        for schema_name in ("MartEvidenceV1", "MartRolePayloadV1", "MartScopedAnalysisV1", "MartPublicationIndexV1", "MartCandidateHealthV1"):
            self.assertIn(schema_name, self.registry["schemas"])
        self.assertEqual(set(self.registry["enums"]["analysisOutcome"]),
                         {"complete", "invalid", "review_required", "risk_blocked", "insufficient_data"})

    def test_governance_blocking_policy(self):
        self.assertEqual(self.policy["developmentCompletenessGate"], 0.30)
        self.assertTrue(self.policy["blocking"]["manualReviewRequired"])
        self.assertTrue(self.policy["blocking"]["criticalQualityFlag"])
        self.assertEqual(self.policy["blocking"]["highRiskScoreAtLeast"], 75)

    def test_control_plane_contracts_and_availability_states_exist(self):
        self.assertEqual(
            set(self.registry["enums"]["dataAvailabilityStatus"]),
            {"success", "empty", "partial", "fallback", "stale", "unavailable", "schema_drift", "failed"},
        )
        for schema_name in ("StockMasterV1", "DatasetCollectionConfigV1", "ExecutionV1"):
            self.assertIn(schema_name, self.registry["schemas"])
        control_schema = json.loads((ROOT / "packages/contracts/control_plane.v1.json").read_text())
        self.assertIn("StockMasterV1", control_schema["definitions"])
        self.assertIn("DatasetCollectionConfigV1", control_schema["definitions"])
        self.assertIn("ExecutionV1", control_schema["definitions"])
        self.assertIn("CoverageMembershipV1", control_schema["definitions"])
        self.assertEqual(set(self.registry["enums"]["coverageTier"]), {"market_wide", "core_focus", "market_macro"})
        self.assertEqual(self.registry["sourceCatalog"]["fugle"]["authorizationStatus"], "candidate")


if __name__ == "__main__":
    unittest.main()
