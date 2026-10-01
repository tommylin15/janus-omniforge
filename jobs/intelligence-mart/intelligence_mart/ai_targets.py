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


class TargetSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    schema_version: str = Field(pattern=r"^1\.0\.0$")
    artifact_kind: str = Field(pattern=r"^mart_ai_target_snapshot_v1$")
    execution_id: str = Field(min_length=1)
    analysis_as_of: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    source_function: str = Field(pattern=r"^control\.mart_ai_target_symbols$")
    symbols: list[str]
    admitted_symbols: list[str]
    deferred_symbols: list[str]
    max_symbols: int = Field(ge=1, le=50)
    membership_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    snapshot_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    private_fields_exposed: bool = False

    @model_validator(mode="after")
    def validate_snapshot(self):
        date.fromisoformat(self.analysis_as_of)
        symbols = self.symbols
        if symbols != sorted(set(symbols)):
            raise ValueError("AI target symbols must be sorted and deduplicated")
        if self.admitted_symbols != symbols[: self.max_symbols]:
            raise ValueError("AI admitted symbols must be the deterministic bounded prefix")
        if self.deferred_symbols != symbols[self.max_symbols :]:
            raise ValueError("AI deferred symbols must contain every quota-deferred target")
        if self.membership_hash != _hash(symbols):
            raise ValueError("AI target membership hash mismatch")
        payload = self.model_dump(exclude={"snapshot_hash"})
        if self.snapshot_hash != _hash(payload):
            raise ValueError("AI target snapshot hash mismatch")
        if self.private_fields_exposed:
            raise ValueError("AI target snapshot must not expose private owner fields")
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


def target_snapshot(execution_id: str, analysis_as_of: str, rows: list[dict[str, Any]], *,
                    max_symbols: int | None = None) -> dict[str, Any]:
    bound = max_symbols if max_symbols is not None else int(os.environ.get("MART_AI_MAX_SYMBOLS_PER_EXECUTION", "5"))
    if bound not in range(1, 51):
        raise ValueError("MART_AI_MAX_SYMBOLS_PER_EXECUTION must be between 1 and 50")
    merged: dict[str, TargetMember] = {}
    for row in rows:
        item = TargetMember.model_validate(row)
        previous = merged.get(item.symbol)
        merged[item.symbol] = TargetMember(
            symbol=item.symbol,
            watchlisted=item.watchlisted or bool(previous and previous.watchlisted),
            held=item.held or bool(previous and previous.held),
        )
    normalized = sorted(merged.values(), key=lambda item: item.symbol)
    symbols = [item.symbol for item in normalized]
    payload = {
        "schema_version": VERSION,
        "artifact_kind": "mart_ai_target_snapshot_v1",
        "execution_id": execution_id,
        "analysis_as_of": analysis_as_of,
        "source_function": _SOURCE_FUNCTION,
        "symbols": symbols,
        "admitted_symbols": symbols[:bound],
        "deferred_symbols": symbols[bound:],
        "max_symbols": bound,
        "membership_hash": _hash(symbols),
        "private_fields_exposed": False,
    }
    payload["snapshot_hash"] = _hash(payload)
    return TargetSnapshot.model_validate(payload).model_dump()


def load_or_create_target_snapshot(
    connection: Any,
    execution_id: str,
    analysis_as_of: str,
    store: Any,
    bucket: str,
    *,
    max_symbols: int | None = None,
) -> tuple[dict[str, Any], dict[str, str]]:
    """Persist target admission once per execution; later retries replay the saved membership."""
    name = f"executions/{execution_id}/ai-targets.json"
    try:
        existing = json.loads(store.read(name))
    except FileNotFoundError:
        existing = None
    except Exception as error:
        from urllib.error import HTTPError
        if isinstance(error, HTTPError) and error.code == 404:
            existing = None
        else:
            raise
    if existing is not None:
        parsed = TargetSnapshot.model_validate(existing).model_dump()
        if parsed["execution_id"] != execution_id or parsed["analysis_as_of"] != analysis_as_of:
            raise RuntimeError("immutable AI target snapshot identity conflict")
        payload = _canonical(parsed)
        return parsed, {"artifact_uri": f"gs://{bucket}/{name}",
                        "artifact_hash": f"sha256:{sha256(payload).hexdigest()}"}

    snapshot = target_snapshot(execution_id, analysis_as_of, load_target_rows(connection, analysis_as_of),
                               max_symbols=max_symbols)
    payload = _canonical(snapshot)
    if not store.create(name, payload, "application/json") and store.read(name) != payload:
        raise RuntimeError("immutable AI target snapshot conflict")
    return snapshot, {"artifact_uri": f"gs://{bucket}/{name}",
                      "artifact_hash": f"sha256:{sha256(payload).hexdigest()}"}
