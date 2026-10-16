"""D01 2026-10-16 immutable TPEx official source and Mart gate regression."""
from __future__ import annotations

import unittest
from scripts.gcp.d01_owner_eod_1016_publish import bounded_code, DAY, SCOPED


class D01OwnerPublicationContractTests(unittest.TestCase):
    def test_exact_date_and_scope(self):
        self.assertEqual(DAY.isoformat(), "2026-10-16")
        self.assertEqual(SCOPED, {"00697B", "00719B"})
        code = bounded_code()
        compile(code, "<d01-owner-publication>", "exec")
        self.assertIn("target=date(2026,10,16)", code)
        self.assertNotIn("target=date(2026,10,14)", code)
        self.assertIn("d01_owner_same_day_price_coverage_missing", code)

    def test_insert_only_official_immutable_provenance(self):
        code = bounded_code()
        self.assertIn("repo.save_official_eod_quotes(history)", code)
        self.assertIn("official_stored_provenance_not_authorized", code)
        self.assertIn("TPEX_OFFICIAL_DATED_URL", code)
        self.assertIn("TPEX_OFFICIAL_EOD_URL", code)
        self.assertIn('Decimal(row["price"])!=Decimal(source["price"])', code)
        self.assertNotIn('row["record_sha256"]!=source["record_sha256"]', code)
        self.assertNotIn('row["source_uri"]!=source["source_uri"]', code)

    def test_same_owner_mart_write_remains_after_guards(self):
        code = bounded_code()
        self.assertLess(code.index("official_stored_provenance_not_authorized"),
                        code.index("pipeline.run_user(owner,valuation"))
        self.assertIn("write_guard=repo.private_mart_write_lock", code)
        self.assertIn("ledger_version_changed_during_mart_write", code)
        self.assertIn("owner_aggregate_value_pnl_still_withheld", code)


if __name__ == "__main__":
    unittest.main()
