"""SEQ-08 direct new-model serving: four roles, five verified XGBoost heads.

This module intentionally never calls old Risk8/Deterministic model loaders.
No pointer => missing status; all predictions are owner-free Core-only.
Registry activation must occur separately, after real Dev X parity verification.
"""
from __future__ import annotations

from hashlib import sha256
import json
import math
from urllib.error import HTTPError

from .four_model_serving import canonical, fingerprint
from .analyst_inputs import QUANT15, RISK12, FUND15, SEQ08_FEATURE_VERSION
from .valuation_ml_mapping import FEATURES as VAL5, VERSION as VAL_VERSION

ACTIVE_NAME = "models/registry/seq08-four-models-active.json"
BUNDLE_SHA = "91df593d9d13cad1858017f989e568c82ece99ca80fa900c6443073a342545a8"
VERSION = "seq08-five-head-serving-v1"
MAX_BYTES = 20 * 1024 * 1024
MAX_TARGETS = 250
HEADS = {
    "quant": ("quant", "quant-xgb15-20261023", "p_up_20d",
              "3fb509cb7ca8aa5e4a0ec3ca9139a1d355995478a624e1043853f59500cbffe9", tuple(QUANT15)),
    "risk": ("risk", "risk-xgb12-20261024", "future_rms_vol20",
             "e00d302b082fb135991dc4e6f146cf4b9b7dbb56311daae27539564a629e05eb", tuple(RISK12)),
    "fundamental": ("fundamental", "fundamental-rc1-xgb15-20261024", "next_month_revenue_yoy_pct",
                    "05fa3167f10c650389c4e481c3e3a7de8a2b70f9133ad867f0404c3eb9758b0c", tuple(FUND15)),
    "valuation_pe": ("valuation", "valuation-v26-fold2026", "log_pe",
                     "56060b37fb1c18efa9ba3e5c7352b10eca12c8d13990bc6031cdfad15d3bc610", tuple(VAL5)),
    "valuation_pb": ("valuation", "valuation-v26-fold2026", "log_pb",
                     "c0984c82039307788e2af4c962a5e7376bdd2b29a30cecfcff557a91811ffe7a", tuple(VAL5)),
}
ROLES = ("quant", "risk", "fundamental", "valuation")


def expected_pointer():
    """Static audited intended promotion payload, NOT a promotion action."""
    return {
        "schema_version": 1, "mode": "ACTIVE", "role": "four-models",
        "source_bundle_sha256": BUNDLE_SHA, "serving_version": VERSION,
        "heads": {key: {
            "role": role, "model_version": version, "output_name": output,
            "model_sha256": digest, "feature_order": list(order),
            "model_path": f"models/candidates/{role}/{version}/{key}/model.ubj",
        } for key, (role, version, output, digest, order) in HEADS.items()},
    }


def validate_pointer(pointer):
    if not isinstance(pointer, dict):
        raise ValueError("invalid SEQ08 model pointer")
    if pointer.get("mode") == "INACTIVE":
        return None
    if pointer != expected_pointer():
        raise ValueError("SEQ08 model pointer differs from frozen five approved heads")
    return pointer


def _num(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    v = float(value)
    return v if math.isfinite(v) else None


def _is_missing(exc):
    return isinstance(exc, FileNotFoundError) or isinstance(exc, HTTPError) and exc.code == 404


def _load_xgb(raw, order):
    from xgboost import Booster
    model = Booster()
    model.load_model(bytearray(raw))
    if model.num_features() != len(order):
        raise ValueError("native head training/serving dimension mismatch")
    if model.feature_names is not None and list(model.feature_names) != list(order):
        raise ValueError("native head feature order mismatch")
    return model


def _predict_xgb(model, matrix, order):
    import numpy as np
    from xgboost import DMatrix
    result = model.predict(DMatrix(np.array(matrix, dtype=float), feature_names=list(order)),
                           validate_features=True)
    if result.ndim != 1 or len(result) != len(matrix):
        raise ValueError("native head prediction shape mismatch")
    return [float(v) for v in result]


class Session:
    def __init__(self, store, bucket, *, loader=_load_xgb, predictor=_predict_xgb):
        if not bucket or "/" in bucket:
            raise ValueError("existing Mart bucket required")
        self.store, self.bucket = store, bucket
        self.loader, self.predictor = loader, predictor
        self.models = {}

    def _active(self):
        try:
            raw = self.store.read(ACTIVE_NAME)
        except (FileNotFoundError, HTTPError) as e:
            if _is_missing(e):
                return None
            raise
        return validate_pointer(json.loads(raw))

    def _model(self, head):
        if head not in self.models:
            ptr = expected_pointer()["heads"][head]
            raw = self.store.read(ptr["model_path"])
            if not raw or len(raw) > MAX_BYTES or sha256(raw).hexdigest() != ptr["model_sha256"]:
                raise ValueError(f"{head}: model bytes mismatch")
            self.models[head] = self.loader(raw, ptr["feature_order"])
        return self.models[head]

    def _cache_name(self, key, row, inputs):
        ptr = expected_pointer()["heads"][key]
        identity = fingerprint({
            "serving_version": VERSION, "head": key, "model_sha256": ptr["model_sha256"],
            "symbol": row["symbol"], "input_as_of": inputs["input_as_of"],
            "feature_version": inputs["feature_version"],
            "feature_order": ptr["feature_order"],
            "values": [inputs["values"][feature] for feature in ptr["feature_order"]],
        })
        return f"models/inference-cache/v1/{key}/{identity[7:]}.json", identity

    def _cached(self, name, identity, head):
        try:
            raw = self.store.read(name)
        except (FileNotFoundError, HTTPError) as e:
            if _is_missing(e):
                return None
            raise
        item = json.loads(raw)
        expected_hash = fingerprint({k:v for k,v in item.items() if k != "output_hash"})
        if (item.get("identity") != identity or item.get("head") != head
                or item.get("output_hash") != expected_hash
                or _num(item.get("value")) is None):
            raise ValueError("SEQ08 inference cache identity or payload mismatch")
        return float(item["value"])

    def _save(self, name, identity, head, value):
        item = {"identity": identity, "head": head, "value": value}
        item["output_hash"] = fingerprint(item)
        raw = canonical(item)
        if not self.store.create(name, raw, "application/json") and self.store.read(name) != raw:
            raise ValueError("SEQ08 immutable cross-job cache conflict")

    def run(self, analyst_inputs):
        rows = analyst_inputs["rows"]
        if len(rows) > MAX_TARGETS or len({r["symbol"] for r in rows}) != len(rows):
            raise ValueError("SEQ08 owner-free target union exceeds 250 unique symbols")
        ptr = self._active()
        statuses = {r["symbol"]: {role: {
            "status": "MISSING_OR_INACTIVE_ARTIFACT", "model_version": None, "prediction": None}
            for role in ROLES} for r in rows}
        if ptr is not None:
            pending = {key: [] for key in HEADS}
            cached = {}
            for row in rows:
                for role in ROLES:
                    feature = row["roles"][role]
                    keys = ("valuation_pe", "valuation_pb") if role == "valuation" else (role,)
                    model_versions = {HEADS[k][1] for k in keys}
                    status = {"status": "FEATURE_INCOMPATIBLE_OR_MISSING",
                        "model_version": next(iter(model_versions)),
                        "model_sha256": {k: HEADS[k][3] for k in keys},
                        "output_name": [HEADS[k][2] for k in keys],
                        "input_as_of": feature.get("input_as_of"),
                        "missing_features": feature.get("missing_features", []),
                        "reasons": feature.get("reasons", []),
                        "prediction": None}
                    statuses[row["symbol"]][role] = status
                    order = HEADS[keys[0]][4]
                    expected_version = VAL_VERSION if role == "valuation" else SEQ08_FEATURE_VERSION[role]
                    if (feature.get("feature_order") != list(order)
                            or feature.get("feature_version") != expected_version
                            or feature.get("missing_features")
                            or not feature.get("feature_ready")
                            or not feature.get("input_as_of")):
                        continue
                    vector = [_num(feature.get("values", {}).get(k)) for k in order]
                    if any(v is None for v in vector):
                        continue
                    if role == "fundamental" and feature.get("abstention_reasons"):
                        status.update(status="ABSTAINED_X_ONLY",
                                      reasons=feature["abstention_reasons"])
                        continue
                    # Disallow trivial rank computed from target-only data.
                    if role == "quant" and not 0 < vector[-1] <= 1:
                        continue
                    for key in keys:
                        name, identity = self._cache_name(key, row, feature)
                        value = self._cached(name, identity, key)
                        if value is None:
                            pending[key].append((row["symbol"], vector, name, identity))
                        else:
                            cached[(row["symbol"], key)] = (value, True)
            for key, items in pending.items():
                if not items:
                    continue
                model = self._model(key)
                predicted = self.predictor(model, [v for _,v,_,_ in items], list(HEADS[key][4]))
                if len(predicted) != len(items):
                    raise ValueError("native model batch output count mismatch")
                for (symbol, _, name, identity), value in zip(items, predicted):
                    value = _num(value)
                    if value is None:
                        raise ValueError(f"{key}: nonfinite native model output")
                    if key == "quant" and not 0 <= value <= 1:
                        raise ValueError("Quant probability outside [0,1]")
                    if key == "risk":
                        value = max(0., value)  # Research-approved nonnegative RMS clip.
                    self._save(name, identity, key, value)
                    cached[(symbol, key)] = (value, False)
            for row in rows:
                for role in ROLES:
                    keys = ("valuation_pe", "valuation_pb") if role == "valuation" else (role,)
                    vals = [cached.get((row["symbol"], key)) for key in keys]
                    if all(v is not None for v in vals):
                        result = statuses[row["symbol"]][role]
                        outputs = {HEADS[k][2]: values[0] for k, values in zip(keys, vals)}
                        result.update(
                            status="ACTIVE_CACHED" if all(v[1] for v in vals) else "ACTIVE_PREDICTED",
                            prediction=outputs if role == "valuation" else vals[0][0],
                            outputs=outputs,
                        )
        return {
            "artifact_kind": "mart_four_model_serving_v1",
            "schema_version": VERSION,
            "analysis_as_of": analyst_inputs["analysis_as_of"],
            "core_snapshot_id": analyst_inputs["core_snapshot_id"],
            "source_analyst_input_hash": analyst_inputs["output_hash"],
            "owner_fields_exposed": False, "publication_authority": False,
            "rows": [{"symbol": row["symbol"], "roles": statuses[row["symbol"]]} for row in rows],
        }


def materialize(store, bucket, analyst_inputs, execution_id):
    from .runtime import _write_immutable_json
    artifact = Session(store, bucket).run(analyst_inputs)
    artifact["output_hash"] = fingerprint(artifact)
    path = f"executions/{execution_id}/four-model-serving.json"
    return _write_immutable_json(store, bucket, path, artifact)
