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
    print(json.dumps(output, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
