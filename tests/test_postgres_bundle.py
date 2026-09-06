import os
import unittest

from packages.postgres_bundle import load_postgres_bundle


class PostgresBundleTest(unittest.TestCase):
    def test_bundle_fills_only_missing_runtime_fields(self):
        os.environ["TEST_POSTGRES_BUNDLE"] = '{"password":"new","url":"postgres://db"}'
        os.environ.pop("TEST_PASSWORD", None)
        os.environ["TEST_URL"] = "existing"
        try:
            load_postgres_bundle("TEST_POSTGRES_BUNDLE", {
                "TEST_PASSWORD": "password", "TEST_URL": "url",
            })
            self.assertEqual(os.environ["TEST_PASSWORD"], "new")
            self.assertEqual(os.environ["TEST_URL"], "existing")
        finally:
            for name in ("TEST_POSTGRES_BUNDLE", "TEST_PASSWORD", "TEST_URL"):
                os.environ.pop(name, None)

    def test_bundle_rejects_missing_fields(self):
        os.environ["TEST_POSTGRES_BUNDLE"] = '{"password":"new"}'
        try:
            with self.assertRaises(ValueError):
                load_postgres_bundle("TEST_POSTGRES_BUNDLE", {"TEST_URL": "url"})
        finally:
            os.environ.pop("TEST_POSTGRES_BUNDLE", None)


if __name__ == "__main__":
    unittest.main()
