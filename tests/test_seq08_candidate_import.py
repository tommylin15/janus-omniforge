"""Only real new model heads may enter the SEQ-08 create-only candidate stage."""
from hashlib import sha256
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts/gcp"))
from seq08_candidate_import import verify, import_create_only


class Model:
    feature_names = None

    def __init__(self, n):
        self.n = n

    def num_features(self):
        return self.n


def fixture(tmp_path):
    expected, bundle = {}, {}
    for key, role, target, n in (
        ("quant", "quant", "p_up_20d", 15),
        ("risk", "risk", "future_rms_vol20", 12),
        ("fundamental", "fundamental", "next_month_revenue_yoy_pct", 15),
        ("valuation_pe", "valuation", "log_pe", 5),
        ("valuation_pb", "valuation", "log_pb", 5),
    ):
        raw = key.encode()
        name = f"{key}.ubj"
        (tmp_path / name).write_bytes(raw)
        expected[key] = (role, target, n, sha256(raw).hexdigest())
        from seq08_candidate_import import COMMITTED_FEATURES
        names = COMMITTED_FEATURES.get(key, [f"f{x}" for x in range(n)])
        bundle[key] = {
            "role": role, "output_name": target, "file": name,
            "feature_order": names, "feature_units": ["unit"] * n,
            "preprocessing": "identity", "model_version": "v20261025",
        }
    return bundle, expected


def test_all_five_verified_without_any_legacy_models(tmp_path):
    manifest, expected = fixture(tmp_path)
    validated = verify(manifest, tmp_path, expected=expected,
                       loader=lambda raw: Model(expected[raw.decode()][2]))
    assert len(validated) == 5
    assert set(x["role"] for x in validated.values()) == {
        "risk", "quant", "fundamental", "valuation"
    }


def test_missing_head_and_changed_source_fail_closed(tmp_path):
    manifest, expected = fixture(tmp_path)
    del manifest["valuation_pb"]
    with pytest.raises(ValueError, match="five new model heads"):
        verify(manifest, tmp_path, expected=expected, loader=lambda _: Model(5))
    manifest, expected = fixture(tmp_path)
    (tmp_path / "risk.ubj").write_bytes(b"other")
    with pytest.raises(ValueError, match="SHA256"):
        verify(manifest, tmp_path, expected=expected, loader=lambda raw: Model(expected[raw.decode()][2]))


def test_bad_preprocessing_feature_order_or_dimension_fail(tmp_path):
    manifest, expected = fixture(tmp_path)
    manifest["risk"]["feature_order"].reverse()
    with pytest.raises(ValueError, match="feature order"):
        verify(manifest, tmp_path, expected=expected, loader=lambda raw: Model(expected[raw.decode()][2]))
    manifest, expected = fixture(tmp_path)
    manifest["quant"]["preprocessing"] = "standard_scaler"
    with pytest.raises(ValueError, match="preprocessing"):
        verify(manifest, tmp_path, expected=expected, loader=lambda _: Model(15))
    manifest, expected = fixture(tmp_path)
    with pytest.raises(ValueError, match="dimension"):
        verify(manifest, tmp_path, expected=expected, loader=lambda _: Model(1))


def test_gcs_candidate_upload_create_only_readback(tmp_path):
    manifest, expected = fixture(tmp_path)
    approved = verify(manifest, tmp_path, expected=expected,
                      loader=lambda raw: Model(expected[raw.decode()][2]))

    class Blob:
        def __init__(self, store, name):
            self.store, self.name = store, name

        def exists(self):
            return self.name in self.store

        def download_as_bytes(self):
            return self.store[self.name]

        def upload_from_string(self, raw, content_type=None, if_generation_match=None):
            assert content_type == "application/octet-stream" and if_generation_match == 0
            assert self.name not in self.store
            self.store[self.name] = raw

    class Bucket:
        def __init__(self):
            self.data = {}

        def blob(self, name):
            return Blob(self.data, name)

    bucket = Bucket()
    import_create_only("existing-mart", approved, bucket)
    import_create_only("existing-mart", approved, bucket)
    first = next(iter(bucket.data))
    bucket.data[first] = b"tampered"
    with pytest.raises(ValueError, match="candidate conflict"):
        import_create_only("existing-mart", approved, bucket)
