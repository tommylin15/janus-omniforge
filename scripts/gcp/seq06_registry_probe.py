"""Read exactly four dev model Registry pointers and their already-referenced bytes.

No listing, no uploads, no generation update, no Registry mutation.
Safe negative results are UNKNOWN/MISSING, never invented ACTIVE claims.
"""
from __future__ import annotations
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

PROJECT = "gen-lang-client-0593591102"
BUCKET = PROJECT + "-dev-mart"
POINTERS = {
    "risk": "risk-models/registry/risk-active.json",
    "quant": "models/registry/quant-active.json",
    "fundamental": "models/registry/fundamental-active.json",
    "valuation": "models/registry/valuation-active.json",
}
MAX_BYTES = 20 * 1024 * 1024


def cloud(*args):
    return subprocess.run(["gcloud", "storage", *args, "--project", PROJECT],
                          text=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=90, check=False)


def main():
    output = {"schema_version": "seq06-gcs-pointer-readonly.v1",
              "gcs_writes": 0, "user_publication_approval": True, "roles": {}}
    for role, key in POINTERS.items():
        uri = f"gs://{BUCKET}/{key}"
        read = cloud("cat", uri)
        if read.returncode:
            message = read.stderr.decode("utf-8", "replace").lower()
            missing = any(phrase in message for phrase in (
                "not found", "404", "no urls matched", "matched no objects",
                "no objects matched", "not exist", "does not exist"))
            denied = any(phrase in message for phrase in ("403", "permission", "access denied"))
            state = "POINTER_MISSING" if missing else ("ACCESS_DENIED" if denied else "READ_ERROR")
            output["roles"][role] = {"status": state, "model_active": "NOT_VERIFIED"}
            continue
        try:
            ptr = json.loads(read.stdout)
            mode = ptr.get("mode")
            if ptr.get("role") != role or mode not in ("ACTIVE", "DETERMINISTIC", "INACTIVE"):
                raise ValueError("pointer role/mode invalid")
            item = {"status": "POINTER_READ", "mode": mode, "model_version": ptr.get("model_version"),
                    "feature_version": ptr.get("feature_version"),
                    "model_sha256": ptr.get("model_sha256"), "model_active": False}
            if mode == "ACTIVE":
                model_uri = ptr.get("model_gcs_uri", "")
                prefix = f"gs://{BUCKET}/" + ("risk-models/candidates/" if role == "risk"
                                                     else f"models/candidates/{role}/")
                if (not model_uri.startswith(prefix) or ".." in model_uri
                        or not model_uri.endswith((".ubj", ".json"))):
                    raise ValueError("untrusted model URI")
                expected = ptr.get("model_sha256")
                if not isinstance(expected, str) or not re.fullmatch("[0-9a-f]{64}", expected):
                    raise ValueError("invalid checksum")
                with tempfile.TemporaryDirectory() as temp:
                    dest = Path(temp) / "model"
                    cp = cloud("cp", model_uri, str(dest))
                    if cp.returncode:
                        item["status"] = "MODEL_READ_ERROR"
                    elif dest.stat().st_size > MAX_BYTES:
                        item["status"] = "MODEL_TOO_LARGE"
                    else:
                        digest = hashlib.sha256(dest.read_bytes()).hexdigest()
                        item["status"] = "ACTIVE_MODEL_BYTES_MATCH" if digest == expected else "MODEL_SHA_MISMATCH"
                        item["model_active"] = digest == expected
            output["roles"][role] = item
        except (ValueError, TypeError, json.JSONDecodeError, OSError) as error:
            output["roles"][role] = {"status": "INVALID_POINTER_OR_MODEL", "error_type": type(error).__name__,
                                     "model_active": False}
    # SEQ-08 is a separate atomic five-head pointer, not the legacy four role pointers.
    # This is a STRICTLY READ-ONLY probe; candidate presence alone is never ACTIVE.
    seq08_key = "models/registry/seq08-four-models-active.json"
    result = {"status": "POINTER_MISSING", "model_active": False}
    read = cloud("cat", f"gs://{BUCKET}/{seq08_key}")
    if read.returncode == 0:
        try:
            ptr = json.loads(read.stdout)
            expected = {
                "quant": ("quant", "3fb509cb7ca8aa5e4a0ec3ca9139a1d355995478a624e1043853f59500cbffe9", 15),
                "risk": ("risk", "e00d302b082fb135991dc4e6f146cf4b9b7dbb56311daae27539564a629e05eb", 12),
                "fundamental": ("fundamental", "05fa3167f10c650389c4e481c3e3a7de8a2b70f9133ad867f0404c3eb9758b0c", 15),
                "valuation_pe": ("valuation", "56060b37fb1c18efa9ba3e5c7352b10eca12c8d13990bc6031cdfad15d3bc610", 5),
                "valuation_pb": ("valuation", "c0984c82039307788e2af4c962a5e7376bdd2b29a30cecfcff557a91811ffe7a", 5)
            }
            if (ptr.get("schema_version") != 1 or ptr.get("role") != "four-models"
                    or ptr.get("mode") != "ACTIVE"
                    or ptr.get("source_bundle_sha256") != "91df593d9d13cad1858017f989e568c82ece99ca80fa900c6443073a342545a8"
                    or ptr.get("serving_version") != "seq08-five-head-serving-v1"
                    or set(ptr.get("heads", {})) != set(expected)):
                raise ValueError("seq08_pointer_contract_mismatch")
            verified = {}
            for head, (role, digest, count) in expected.items():
                item = ptr["heads"][head]
                name = item.get("model_path", "")
                if (item.get("role") != role or item.get("model_sha256") != digest
                        or not isinstance(item.get("feature_order"), list)
                        or len(item["feature_order"]) != count
                        or not isinstance(name, str) or ".." in name
                        or not name.startswith(f"models/candidates/{role}/")
                        or not name.endswith("/model.ubj")):
                    raise ValueError("seq08_head_contract_mismatch")
                blob = cloud("cat", f"gs://{BUCKET}/{name}")
                if blob.returncode or len(blob.stdout) > MAX_BYTES or hashlib.sha256(blob.stdout).hexdigest() != digest:
                    raise ValueError("seq08_head_bytes_unverified")
                verified[head] = "GCS_MODEL_SHA256_VERIFIED"
            result = {"status": "ACTIVE_POINTER_AND_ALL_FIVE_SHA_READBACK_PASS",
                      "model_active": True, "heads": verified}
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
            result = {"status": "INVALID_POINTER_OR_HEAD", "model_active": False,
                      "error_type": type(error).__name__}
    else:
        message = read.stderr.decode("utf-8", "replace").lower()
        if any(x in message for x in ("not found", "404", "no urls matched", "does not exist", "matched no objects")):
            result = {"status": "POINTER_MISSING", "model_active": False}
        elif any(x in message for x in ("403", "access denied", "permission")):
            result = {"status": "ACCESS_DENIED", "model_active": False}
        else:
            result = {"status": "READ_ERROR", "model_active": False}
    output["seq08_new_model_bundle"] = result
    print(json.dumps(output, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
