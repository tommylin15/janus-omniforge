"""Unit tests for bounded read-only market membership inventory."""
from pathlib import Path
import runpy
import unittest

MODULE = runpy.run_path(str(Path(__file__).resolve().parents[1] / "scripts" / "gcp" / "b9-quant-history-inventory.py"))
summarize = MODULE["summarize"]
URI = "gs://gen-lang-client-0593591102-dev-mart/executions/12345678-1234-1234-1234-123456789012/market-membership.json"
BASE = {"analysis_as_of": "2026-10-09", "symbols": [str(i) for i in range(1101, 1111)],
        "membership_version": "v1"}


class QuantMembershipInventoryTests(unittest.TestCase):
    def test_legacy_date_only_is_never_historical_pit_pass(self):
        out = summarize([(URI, BASE, "sha256:" + "a"*64)])
        self.assertEqual(out["distinct_as_of_dates"], 1)
        self.assertEqual(out["counts"]["missing_source_time_or_authorization"], 1)
        self.assertEqual(out["independently_verified_historical_pit_dates"], 0)
        self.assertFalse(out["promotion_eligible"])
        self.assertFalse(out["canonical_write"])

    def test_source_clock_claim_does_not_prove_upstream_membership(self):
        item = dict(BASE, source_observed_at="2026-10-08", source_published_at="2026-10-08",
                    source_provenance_id="official-immutable-x", source_authorization="official")
        out = summarize([(URI, item, "sha256:" + "a"*64)])
        self.assertEqual(out["counts"]["source_clock_fields_claimed_pit"], 1)
        self.assertEqual(out["independently_verified_historical_pit_dates"], 0)

    def test_conflicting_date_detected_without_a_source_override(self):
        one = (URI, BASE, "sha256:" + "a"*64)
        two = (URI.replace("12345678", "22345678"),
               dict(BASE, membership_version="v2"), "sha256:" + "b"*64)
        out = summarize([one, two])
        self.assertEqual(out["conflicting_dates"], 1)

    def test_bad_path_rejected(self):
        with self.assertRaisesRegex(ValueError, "outside"):
            summarize([(URI.replace("dev-mart", "fake-bucket"), BASE, "sha256:" + "a"*64)])


if __name__ == "__main__":
    unittest.main()
