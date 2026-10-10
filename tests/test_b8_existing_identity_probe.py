"""Pure safety checks for B8 existing-authority diagnosis; no GCP calls."""
import importlib.util
from pathlib import Path
import urllib.error
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/gcp/b8-existing-identity-probe.py"
spec = importlib.util.spec_from_file_location("b8_identity_probe", SCRIPT)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class TestB8IdentityProbe(unittest.TestCase):
    def test_same_project_identity_only(self):
        data = {"spec": {"template": {"spec": {"serviceAccountName":
            "janus-intelligence-mart@gen-lang-client-0593591102.iam.gserviceaccount.com"}}}}
        self.assertEqual(probe.identity_from_resource(data),
                         "janus-intelligence-mart@gen-lang-client-0593591102.iam.gserviceaccount.com")
        data["spec"]["template"]["spec"]["serviceAccountName"] = "different@other-project.iam.gserviceaccount.com"
        self.assertIsNone(probe.identity_from_resource(data))

    def test_ambiguous_identity_fails_closed(self):
        data = {"spec": {"serviceAccountName": "a@gen-lang-client-0593591102.iam.gserviceaccount.com",
                         "template": {"serviceAccountName":
                         "b@gen-lang-client-0593591102.iam.gserviceaccount.com"}}}
        self.assertIsNone(probe.identity_from_resource(data))

    def test_pointer_extraction(self):
        self.assertEqual(probe.metadata_location({"nested": {"metadata-location": "gs://fixed"}}), "gs://fixed")
        self.assertIsNone(probe.metadata_location({"nested": {"other": 123}}))

    def test_safe_http_classification(self):
        self.assertEqual(probe.safe_code(urllib.error.HTTPError("url", 403, "forbidden", {}, None)), "HTTP_403")
        self.assertEqual(probe.safe_code(TimeoutError()), "TIMEOUT")
        self.assertEqual(probe.safe_code(ValueError("Bearer secret")), "UNVERIFIED")


if __name__ == "__main__":
    unittest.main()
