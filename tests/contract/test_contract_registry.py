import json
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]


class ContractRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = json.loads((ROOT / "packages/contracts/registry.json").read_text())
        cls.policy = json.loads((ROOT / "packages/governance/policy.json").read_text())

    def test_required_ids_and_events_exist(self):
        self.assertIn("twse", self.registry["sourceIds"])
        self.assertIn("core", self.registry["datasetIds"])
        self.assertIn("CoreDatasetReadyV1", self.registry["schemas"])
        self.assertIn("MartReportReadyV1", self.registry["schemas"])

    def test_governance_blocking_policy(self):
        self.assertEqual(self.policy["developmentCompletenessGate"], 0.30)
        self.assertTrue(self.policy["blocking"]["manualReviewRequired"])
        self.assertTrue(self.policy["blocking"]["criticalQualityFlag"])
        self.assertEqual(self.policy["blocking"]["highRiskScoreAtLeast"], 75)


if __name__ == "__main__":
    unittest.main()
