"""Private-safe, immutable AI target admission for Mart provider workers."""

from __future__ import annotations

from datetime import date
from hashlib import sha256
import json
import os
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field, model_validator


VERSION = "1.0.0"
_SOURCE_FUNCTION = "control.mart_ai_target_symbols"


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode()


def _hash(value: object) -> str:
    return f"sha256:{sha256(_canonical(value)).hexdigest()}"


class TargetMember(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    symbol: str = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9._:-]+$")
    watchlisted: bool
    held: bool

    @model_validator(mode="after")
    def require_membership(self):
        if not (self.watchlisted or self.held):
            raise ValueError("AI target member must be watchlisted or held")
        return self


def load_target_rows(connection: Any, analysis_as_of: str) -> list[dict[str, Any]]:
    """Read only the de-identified control projection; no private table access is allowed here."""
    with connection.transaction(), connection.cursor() as cursor:
        cursor.execute(
            "SELECT symbol,watchlisted,held FROM control.mart_ai_target_symbols(%s::date) ORDER BY symbol",
            (analysis_as_of,),
        )
        rows = cursor.fetchall()
    members = []
    for row in rows:
        symbol, watchlisted, held = row
        members.append(TargetMember(symbol=str(symbol), watchlisted=bool(watchlisted), held=bool(held)).model_dump())
    return members


def load_or_create_target_snapshot(connection, execution_id, analysis_as_of, store, bucket):
    name = f"executions/{execution_id}/specialist-targets.json"
    try:
        snapshot = json.loads(store.read(name))
    except FileNotFoundError:
        snapshot = None
    except Exception as error:
        from urllib.error import HTTPError
        if not isinstance(error, HTTPError) or error.code != 404:
            raise
        snapshot = None
    if snapshot is None:
        symbols = sorted({r["symbol"] for r in load_target_rows(connection, analysis_as_of)})
        snapshot = {"artifact_kind": "mart_specialist_coverage_v1", "schema_version": VERSION,
                    "execution_id": execution_id, "analysis_as_of": analysis_as_of,
                    "symbols": symbols, "membership_hash": _hash(symbols),
                    "source_function": _SOURCE_FUNCTION, "private_fields_exposed": False}
        snapshot["snapshot_hash"] = _hash(snapshot)
    if snapshot["execution_id"] != execution_id or snapshot["analysis_as_of"] != analysis_as_of \
            or snapshot["symbols"] != sorted(set(snapshot["symbols"])) \
            or snapshot["membership_hash"] != _hash(snapshot["symbols"]) \
            or snapshot["private_fields_exposed"] \
            or snapshot["snapshot_hash"] != _hash({k: v for k, v in snapshot.items() if k != "snapshot_hash"}):
        raise RuntimeError("invalid specialist target snapshot fence")
    payload = _canonical(snapshot)
    if not store.create(name, payload, "application/json") and store.read(name) != payload:
        raise RuntimeError("immutable specialist target conflict")
    return snapshot, {"artifact_uri": f"gs://{bucket}/{name}", "artifact_hash": "sha256:" + sha256(payload).hexdigest()}
