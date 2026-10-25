"""SEQ-06: bounded, version-pinned serving for non-Risk specialists.

Risk retains its existing GCS+PostgreSQL ACTIVE gate and pinned eight-factor
reader. This module never promotes candidates or converts deterministic
specialists into ML predictions. All caches are immutable and owner-free.
"""
from __future__ import annotations

from hashlib import sha256
import json
import math
import re
from urllib.error import HTTPError

ROLES = ("quant", "fundamental", "valuation")
TARGETS = {
    "quant": {"p_up_20d"},
    "fundamental": {"next_month_revenue_yoy_pct"},
    "valuation": {"log_pe", "log_pb"},
}
# Units correspond to the existing janus_precision reference factor formulas,
# not to an arbitrary Colab candidate schema. Unknown units fail closed.
UNITS = {
    "ret5": "ratio", "ret20": "ratio", "ret60": "ratio",
    "ma20_distance": "ratio", "ma60_distance": "ratio",
    "vol20": "annualized_rms_ratio", "vol60": "annualized_rms_ratio",
    "drawdown60": "ratio", "volume_ratio20": "ratio",
    "log_turnover20": "log1p_TWD", "market_code": "twse_0_tpex_1",
    "yoy_m": "percentage_points", "yoy_3m": "percentage_points",
    "yoy_change1": "percentage_points", "growth_acceleration": "percentage_points",
    "mom_m": "percentage_points", "log_revenue": "log1p_TWD",
    "season_sin": "unitless", "season_cos": "unitless",
    "revenue_vol3": "std_log1p_TWD",
}
MAX_MODEL_BYTES = 20 * 1024 * 1024
MAX_TARGETS = 250
SHA = re.compile(r"^[0-9a-f]{64}$")
VERSION = "seq06-model-serving-v1"


def canonical(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def fingerprint(obj):
    return "sha256:" + sha256(canonical(obj)).hexdigest()


def _missing(error):
    if isinstance(error, FileNotFoundError):
        return True
    if isinstance(error, HTTPError) and error.code == 404:
        return True
    return False


def _read_optional(store, name):
    try:
        return store.read(name)
    except (FileNotFoundError, HTTPError) as error:
        if not _missing(error):
            raise
        return None


def validate_pointer(pointer, role, bucket):
    """Reject unreviewed, unsupported, non-versioned or non-dev model pointers."""
    if not isinstance(pointer, dict) or role not in ROLES:
        raise ValueError("invalid model pointer")
    if (pointer.get("schema_version") != 1 or pointer.get("role") != role
            or pointer.get("mode") not in ("ACTIVE", "INACTIVE")):
        raise ValueError("model pointer schema/role/mode mismatch")
    if pointer["mode"] == "INACTIVE":
        return None
    if (pointer.get("promotion_gate") != "VALIDATED"
            or pointer.get("preprocessing") != "identity"
            or pointer.get("format") not in ("XGBOOST_JSON", "XGBOOST_UBJ")
            or not re.fullmatch(r"[0-9a-f]{40}", str(pointer.get("source_git_sha", "")))):
        raise ValueError("model pointer is not an approved compatible bundle")
    order = pointer.get("feature_order")
    units = pointer.get("feature_units")
    if (not isinstance(order, list) or not order or len(order) != len(set(order))
            or not all(isinstance(key, str) and key for key in order)
            or not isinstance(units, list) or len(units) != len(order)
            or any(UNITS.get(k) != u for k, u in zip(order, units))):
        raise ValueError("model feature order or unit contract mismatch")
    if (not isinstance(pointer.get("feature_version"), str) or not pointer["feature_version"]
            or not isinstance(pointer.get("model_version"), str) or not pointer["model_version"]
            or pointer.get("output_name") not in TARGETS[role]
            or not isinstance(pointer.get("model_sha256"), str)
            or not SHA.fullmatch(pointer["model_sha256"])):
        raise ValueError("model target/version/checksum missing")
    uri = f"gs://{bucket}/models/candidates/{role}/"
    path = str(pointer.get("model_gcs_uri", ""))
    ext = ".json" if pointer["format"] == "XGBOOST_JSON" else ".ubj"
    if (not path.startswith(uri) or not path.endswith(ext)
            or path.count("/") < uri.count("/") + 1 or ".." in path):
        raise ValueError("model URI outside existing bounded dev Mart prefix")
    if (pointer.get("output_name") == "p_up_20d"
            and pointer.get("output_unit") != "probability"
            or pointer.get("output_name") == "next_month_revenue_yoy_pct"
            and pointer.get("output_unit") != "percentage_points"
            or pointer.get("output_name") in ("log_pe", "log_pb")
            and pointer.get("output_unit") != "natural_log_multiple"):
        raise ValueError("model output unit mismatch")
    return pointer


def xgb_loader(raw, pointer):
    """No pickle, arbitrary Python, or remote executable code in model bundles."""
    from xgboost import Booster
    booster = Booster()
    booster.load_model(bytearray(raw))
    if booster.num_features() != len(pointer["feature_order"]):
        raise ValueError("XGBoost training/serving feature dimension mismatch")
    saved_names = booster.feature_names
    if saved_names is not None and saved_names != pointer["feature_order"]:
        raise ValueError("XGBoost feature names mismatch")
    return booster


def xgb_predict(booster, vectors, names):
    import numpy as np
    from xgboost import DMatrix
    arr = np.array(vectors, dtype=float)
    out = booster.predict(DMatrix(arr, feature_names=names), validate_features=True)
    if out.ndim != 1 or len(out) != len(vectors):
        raise ValueError("unexpected model prediction shape")
    return [float(v) for v in out]


class ServingSession:
    """One download per role/version per execution, one batch predict per dirty role.

    No module-global RAM sharing is assumed across Cloud Run Jobs. Immutable GCS
    result cache is keyed by exact model bytes and reference X, never owner IDs.
    """

    def __init__(self, store, bucket, *, loader=xgb_loader, predictor=xgb_predict):
        if not bucket or "/" in bucket:
            raise ValueError("existing Mart bucket required")
        self.store, self.bucket = store, bucket
        self.loader, self.predictor = loader, predictor
        self._models = {}

    def _active(self, role):
        raw = _read_optional(self.store, f"models/registry/{role}-active.json")
        if raw is None:
            return None
        return validate_pointer(json.loads(raw), role, self.bucket)

    def _model(self, pointer):
        identity = (pointer["model_gcs_uri"], pointer["model_sha256"])
        if identity not in self._models:
            name = pointer["model_gcs_uri"][len(f"gs://{self.bucket}/"):]
            raw = self.store.read(name)
            if len(raw) > MAX_MODEL_BYTES or sha256(raw).hexdigest() != pointer["model_sha256"]:
                raise ValueError("model bytes exceed limit or checksum mismatch")
            self._models[identity] = self.loader(raw, pointer)
        return self._models[identity]

    @staticmethod
    def _value(value):
        if isinstance(value, bool) or not isinstance(value, (float, int)):
            return None
        v = float(value)
        return v if math.isfinite(v) else None

    def _cache_identity(self, role, row, features, pointer):
        return fingerprint({"version": VERSION, "role": role, "symbol": row["symbol"],
            "model_sha256": pointer["model_sha256"], "model_version": pointer["model_version"],
            "output_name": pointer["output_name"], "feature_version": features["feature_version"],
            "input_as_of": features["input_as_of"], "feature_order": pointer["feature_order"],
            "values": [features["values"][k] for k in pointer["feature_order"]]})

    def _cached(self, role, row, features, pointer):
        identity = self._cache_identity(role, row, features, pointer)
        name = f"models/inference-cache/v1/{role}/{identity[7:]}.json"
        raw = _read_optional(self.store, name)
        if raw is None:
            return identity, name, None
        item = json.loads(raw)
        if (item.get("cache_identity") != identity or item.get("symbol") != row["symbol"]
                or item.get("role") != role or item.get("model_sha256") != pointer["model_sha256"]
                or item.get("output_name") != pointer["output_name"]
                or fingerprint({k: v for k, v in item.items() if k != "output_hash"}) != item.get("output_hash")
                or self._value(item.get("value")) is None):
            raise ValueError("cross-job inference cache identity mismatch")
        if pointer["output_name"] == "p_up_20d" and not 0 <= item["value"] <= 1:
            raise ValueError("invalid cached probability")
        return identity, name, item["value"]

    def _save(self, name, identity, role, row, pointer, value):
        item = {"cache_identity": identity, "symbol": row["symbol"], "role": role,
                "model_sha256": pointer["model_sha256"],
                "model_version": pointer["model_version"],
                "output_name": pointer["output_name"], "value": value}
        item["output_hash"] = fingerprint(item)
        payload = canonical(item)
        if not self.store.create(name, payload, "application/json") and self.store.read(name) != payload:
            raise ValueError("immutable inference cache conflict")

    def run(self, analyst_inputs, *, risk_active=False):
        rows = analyst_inputs["rows"]
        if len(rows) > MAX_TARGETS or len({r["symbol"] for r in rows}) != len(rows):
            raise ValueError("model target union exceeds 250 unique symbols")
        results = {r["symbol"]: {"symbol": r["symbol"], "roles": {
            "risk": {"status": "ACTIVE_SEPARATE_RISK_PIPELINE" if risk_active else "NOT_ACTIVE",
                     "model_version": None, "prediction": None}}} for r in rows}
        for role in ROLES:
            pointer = self._active(role)
            if pointer is None:
                for result in results.values():
                    result["roles"][role] = {"status": "MISSING_OR_INACTIVE_ARTIFACT",
                        "model_version": None, "prediction": None}
                continue
            model = None
            pending = []
            for row in rows:
                f = row["roles"][role]
                output = {"status": "FEATURE_INCOMPATIBLE_OR_MISSING",
                          "model_version": pointer["model_version"],
                          "model_sha256": pointer["model_sha256"],
                          "output_name": pointer["output_name"], "prediction": None}
                results[row["symbol"]]["roles"][role] = output
                if (f.get("feature_order") != pointer["feature_order"]
                        or f.get("feature_version") != pointer["feature_version"]
                        or not f.get("input_as_of")
                        or f.get("missing_features")
                        or not f.get("feature_ready")):
                    continue
                vector = [self._value(f.get("values", {}).get(k)) for k in pointer["feature_order"]]
                if any(v is None for v in vector):
                    continue
                identity, name, cached = self._cached(role, row, f, pointer)
                if cached is not None:
                    output.update(status="ACTIVE_CACHED", prediction=cached, input_as_of=f["input_as_of"])
                else:
                    pending.append((row, f, vector, identity, name))
            if pending:
                model = self._model(pointer)
                values = self.predictor(model, [v for _, _, v, _, _ in pending], pointer["feature_order"])
                if len(values) != len(pending):
                    raise ValueError("model prediction batch dimension mismatch")
                for (row, f, _, identity, name), value in zip(pending, values):
                    value = self._value(value)
                    if (value is None or (pointer["output_name"] == "p_up_20d"
                            and not 0 <= value <= 1)):
                        raise ValueError("model output invalid for declared target")
                    self._save(name, identity, role, row, pointer, value)
                    results[row["symbol"]]["roles"][role].update(
                        status="ACTIVE_PREDICTED", prediction=value, input_as_of=f["input_as_of"])
        return {"artifact_kind": "mart_four_model_serving_v1", "schema_version": VERSION,
                "analysis_as_of": analyst_inputs["analysis_as_of"],
                "core_snapshot_id": analyst_inputs["core_snapshot_id"],
                "source_analyst_input_hash": analyst_inputs["output_hash"],
                "owner_fields_exposed": False, "publication_authority": False,
                "rows": [results[r["symbol"]] for r in rows]}


def materialize_four_model_serving(store, bucket, analyst_inputs, execution_id, *, risk_active=False):
    from .runtime import _write_immutable_json
    artifact = ServingSession(store, bucket).run(analyst_inputs, risk_active=risk_active)
    artifact["output_hash"] = fingerprint(artifact)
    name = f"executions/{execution_id}/four-model-serving.json"
    return _write_immutable_json(store, bucket, name, artifact)
