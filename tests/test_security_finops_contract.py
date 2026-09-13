import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class SecurityFinOpsContractTests(unittest.TestCase):
    def test_dev_security_and_cost_guards_are_declared(self):
        provision = (ROOT / "scripts/gcp/provision-dev.sh").read_text()
        deploy = (ROOT / "scripts/gcp/deploy-dev.sh").read_text()
        acceptance = (ROOT / "scripts/gcp/security-finops-dev.sh").read_text()

        self.assertNotIn("serviceAccount:web-runtime", provision)
        for account in ("ingestion-core", "intelligence-mart", "janus-user-api", "janus-private-pipeline"):
            self.assertIn(f'--service-account="{account}@${{project}}.iam.gserviceaccount.com"', deploy)
        self.assertIn("--min-instances=0 --max-instances=2", deploy)
        self.assertIn("--threshold-rule=percent=0.1", acceptance)
        self.assertIn("--threshold-rule=percent=0.5", acceptance)
        self.assertIn("--threshold-rule=percent=1.0", acceptance)
        self.assertNotIn("snapshots create", acceptance)
        self.assertIn("snapshots list", acceptance)
        self.assertIn("containeranalysis.googleapis.com", acceptance)
        self.assertIn("containerscanning.googleapis.com", acceptance)

    def test_flutter_contains_no_service_account_credentials(self):
        source = "\n".join(
            path.read_text(encoding="utf-8", errors="ignore")
            for path in (ROOT / "apps/user_app/lib").rglob("*.dart")
        ).lower()
        self.assertNotIn('"private_key"', source)
        self.assertNotIn('"service_account"', source)


if __name__ == "__main__":
    unittest.main()
