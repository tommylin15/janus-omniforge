"""Immutable Stage object, sidecar, manifest, and quarantine persistence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Protocol
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

from packages.provenance import Provenance, content_hash, idempotency_key


class ObjectStore(Protocol):
    def create(self, name: str, payload: bytes, content_type: str) -> bool: ...


class LocalObjectStore:
    """Filesystem implementation with GCS-compatible create-if-absent semantics."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def create(self, name: str, payload: bytes, content_type: str) -> bool:
        del content_type
        target = (self.root / name).resolve()
        if self.root not in target.parents:
            raise ValueError("object name escaped the store root")
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        except FileExistsError:
            return False
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
        return True


class GcsObjectStore:
    """Minimal GCS JSON API client using Cloud Run metadata credentials."""

    def __init__(self, bucket: str, timeout_seconds: float = 15.0) -> None:
        if not bucket or "/" in bucket:
            raise ValueError("invalid GCS bucket")
        self.bucket = bucket
        self.timeout_seconds = timeout_seconds

    def _token(self) -> str:
        request = Request(
            "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token",
            headers={"Metadata-Flavor": "Google"},
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:
            return json.load(response)["access_token"]

    def create(self, name: str, payload: bytes, content_type: str) -> bool:
        endpoint = (
            "https://storage.googleapis.com/upload/storage/v1/b/"
            f"{quote(self.bucket, safe='')}/o?uploadType=media&ifGenerationMatch=0&name={quote(name, safe='')}"
        )
        request = Request(
            endpoint,
            data=payload,
            method="POST",
            headers={"Authorization": f"Bearer {self._token()}", "Content-Type": content_type},
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds):
                return True
        except HTTPError as error:
            if error.code in {409, 412}:
                return False
            raise


@dataclass(frozen=True)
class StageResult:
    object_name: str
    sidecar_name: str
    manifest_name: str
    idempotency_key: str
    reused: bool


class StageWriter:
    def __init__(self, store: ObjectStore) -> None:
        self.store = store

    def write_raw(
        self,
        *,
        payload: bytes,
        media_type: str,
        extension: str,
        execution_id: str,
        provenance: Provenance,
    ) -> StageResult:
        if content_hash(payload) != provenance.content_hash:
            raise ValueError("payload does not match provenance content_hash")
        execution_id = self._segment(execution_id)
        extension = self._segment(extension.lower().lstrip("."))
        if extension not in {"json", "csv"}:
            raise ValueError("Stage raw payload must be JSON or CSV")
        key = idempotency_key(
            provenance.source_id, provenance.dataset_id, provenance.observed_at, provenance.content_hash
        )
        date = provenance.observed_at.astimezone(timezone.utc).date().isoformat()
        prefix = f"raw/{provenance.source_id}/{provenance.dataset_id}/observed_date={date}/{key}"
        object_name = f"{prefix}/payload.{extension}"
        sidecar_name = f"{prefix}/metadata.json"
        manifest_name = f"executions/{execution_id}/stage/{key}.json"

        created = self.store.create(object_name, payload, media_type)
        sidecar = {
            "schema_version": "1.0.0",
            "idempotency_key": key,
            "raw_object_name": object_name,
            "provenance": provenance.to_dict(),
        }
        self.store.create(sidecar_name, self._json(sidecar), "application/json")
        self.store.create(manifest_name, self._json(sidecar), "application/json")
        return StageResult(object_name, sidecar_name, manifest_name, key, reused=not created)

    def quarantine(
        self,
        *,
        payload: bytes,
        media_type: str,
        extension: str,
        execution_id: str,
        provenance: Provenance,
        violations: list[dict[str, str]],
    ) -> str:
        if not violations:
            raise ValueError("quarantine requires at least one violation")
        execution_id = self._segment(execution_id)
        extension = self._segment(extension.lower().lstrip("."))
        key = idempotency_key(
            provenance.source_id, provenance.dataset_id, provenance.observed_at, provenance.content_hash
        )
        prefix = f"quarantine/{provenance.dataset_id}/execution={execution_id}/{key}"
        self.store.create(f"{prefix}/payload.{extension}", payload, media_type)
        self.store.create(
            f"{prefix}/violations.json",
            self._json({"schema_version": "1.0.0", "provenance": provenance.to_dict(), "violations": violations}),
            "application/json",
        )
        return prefix

    @staticmethod
    def _segment(value: str) -> str:
        if not value or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for character in value):
            raise ValueError("unsafe object path segment")
        return value

    @staticmethod
    def _json(value: object) -> bytes:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
