"""SEQ-08: verify real approved new XGBoost candidates; never fall back to old models.

The safe default is read-only. --apply imports create-only immutable candidates
into the *existing* Dev Mart GCS bucket, never modifies a Registry pointer.
The five model files must be supplied from approved research bundles.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re

# Exact model digests from the approved 2026-10-25 SEQ-06 source verification.
EXPECTED = {
    "quant": ("quant", "p_up_20d", 15, "3fb509cb7ca8aa5e4a0ec3ca9139a1d355995478a624e1043853f59500cbffe9"),
    "risk": ("risk", "future_rms_vol20", 12, "e00d302b082fb135991dc4e6f146cf4b9b7dbb56311daae27539564a629e05eb"),
    "fundamental": ("fundamental", "next_month_revenue_yoy_pct", 15, "05fa3167f10c650389c4e481c3e3a7de8a2b70f9133ad867f0404c3eb9758b0c"),
    "valuation_pe": ("valuation", "log_pe", 5, "56060b37fb1c18efa9ba3e5c7352b10eca12c8d13990bc6031cdfad15d3bc610"),
    "valuation_pb": ("valuation", "log_pb", 5, "c0984c82039307788e2af4c962a5e7376bdd2b29a30cecfcff557a91811ffe7a"),
}
MAX_MODEL_BYTES = 20 * 1024 * 1024
COMMITTED_FEATURES = {
    "quant": ["ret5","ret20","ret60","ma20_distance","ma60_distance","vol20","vol60","drawdown60","volume_ratio20","log_turnover20","market_code","ret10","ret120","bollinger_z20","ret20_market_rank"],
    "fundamental": ["yoy_m","yoy_3m","yoy_change1","growth_acceleration","mom_m","log_revenue","season_sin","season_cos","revenue_vol3","market_code","revenue_sum6m","revenue_mean12m","revenue_growth_6m","base_log_twd","base_to_recent_log"],
    "risk": [
        "vol20", "vol60", "drawdown60", "abs_return5", "volume_ratio20",
        "atr14_pct", "abs_overnight_gap5", "log_turnover20", "downside_vol20",
        "worst_daily_ret20", "amihud_illiquidity", "drawdown_from_high120",
    ],
    "valuation_pe": ["roe_proxy", "debt_ratio", "log_total_assets", "revenue_yoy", "market_code"],
    "valuation_pb": ["roe_proxy", "debt_ratio", "log_total_assets", "revenue_yoy", "market_code"],
}


def verify(bundle, base, *, expected=EXPECTED, loader=None):
    """Validate every new weight, feature schema and output *before* any GCS write."""
    if not isinstance(bundle, dict) or set(bundle) != set(expected):
        raise ValueError("all five new model heads are required; no old-model substitute")
    base = Path(base).resolve()
    if loader is None:
        from xgboost import Booster

        def loader(raw):
            model = Booster()
            model.load_model(bytearray(raw))
            return model
    outputs = {}
    for key, (role, target, count, digest) in expected.items():
        item = bundle[key]
        if not isinstance(item, dict):
            raise ValueError(f"{key}: candidate metadata required")
        if (item.get("role") != role or item.get("output_name") != target
                or item.get("preprocessing") != "identity"):
            raise ValueError(f"{key}: role/target/preprocessing mismatch")
        order = item.get("feature_order")
        units = item.get("feature_units")
        if (not isinstance(order, list) or len(order) != count
                or len(set(order)) != count or not all(isinstance(s, str) and s for s in order)
                or not isinstance(units, list) or len(units) != count
                or not all(isinstance(u, str) and u for u in units)
                or (key in COMMITTED_FEATURES and order != COMMITTED_FEATURES[key])):
            raise ValueError(f"{key}: new feature order/units mismatch")
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,99}", str(item.get("model_version", ""))):
            raise ValueError(f"{key}: immutable candidate version required")
        relative = item.get("file")
        if not isinstance(relative, str) or not relative.endswith(".ubj"):
            raise ValueError(f"{key}: UBJ file required")
        path = (base / relative).resolve()
        if not path.is_relative_to(base) or not path.is_file() or path.is_symlink():
            raise ValueError(f"{key}: missing or unsafe source file")
        raw = path.read_bytes()
        if not raw or len(raw) > MAX_MODEL_BYTES or sha256(raw).hexdigest() != digest:
            raise ValueError(f"{key}: approved model bytes SHA256 mismatch")
        model = loader(raw)
        if model.num_features() != count:
            raise ValueError(f"{key}: model input dimension mismatch")
        names = model.feature_names
        if names is not None and names != order:
            raise ValueError(f"{key}: XGBoost internal feature order mismatch")
        blob = f"models/candidates/{role}/{item['model_version']}/{key}/model.ubj"
        outputs[key] = {
            "role": role, "output_name": target, "model_sha256": digest,
            "model_version": item["model_version"], "feature_order": order,
            "feature_units": units, "source_file": str(path), "object": blob,
            "bytes": len(raw),
        }
    if bundle["valuation_pe"]["feature_order"] != bundle["valuation_pb"]["feature_order"]:
        raise ValueError("Valuation PE/PB heads need one accounting input schema")
    return outputs


def import_create_only(bucket_name, verified, bucket=None):
    """Never modify Registry or overwrite an existing candidate; verify bytes read back."""
    if not bucket_name or "/" in bucket_name:
        raise ValueError("existing Mart bucket name required")
    if bucket is None:
        from google.cloud import storage
        bucket = storage.Client().bucket(bucket_name)
    for key, item in verified.items():
        raw = Path(item["source_file"]).read_bytes()
        if sha256(raw).hexdigest() != item["model_sha256"]:
            raise ValueError(f"{key}: model changed after preflight")
        blob = bucket.blob(item["object"])
        # Existing, identical candidates may be reused; never overwrite either variant.
        if blob.exists():
            if sha256(blob.download_as_bytes()).hexdigest() != item["model_sha256"]:
                raise ValueError(f"{key}: existing candidate conflict")
        else:
            blob.upload_from_string(raw, content_type="application/octet-stream", if_generation_match=0)
        downloaded = blob.download_as_bytes()
        if downloaded != raw:
            raise ValueError(f"{key}: GCS candidate readback mismatch")


def main(argv=None):
    parser = argparse.ArgumentParser(description="SEQ-08 approved five-head Dev candidate import")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--bundle-root", required=True, type=Path)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--apply", action="store_true", help="create-only GCS candidate import after all hashes PASS")
    args = parser.parse_args(argv)
    checked = verify(json.loads(args.manifest.read_text(encoding="utf-8")), args.bundle_root)
    if args.apply:
        import_create_only(args.bucket, checked)
    print(json.dumps({
        "state": "GCS_CANDIDATES_READBACK_PASS" if args.apply else "LOCAL_PREFLIGHT_PASS_ONLY",
        "roles": {k: {n: v for n, v in item.items() if n != "source_file"}
                  for k, item in checked.items()},
        "registry_mutations": 0, "model_promotion": False,
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
