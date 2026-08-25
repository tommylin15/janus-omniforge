"""Validated provenance primitives shared by ingestion and audit tooling."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
from typing import Any
from urllib.parse import urlsplit, urlunsplit


SOURCE_IDS = frozenset({"twse", "tpex", "mops", "finmind", "fugle", "shioaji", "taiex", "tpex-benchmark"})
DATASET_IDS = frozenset({"ohlcv", "valuation", "institutional", "financials", "events", "market-activity", "benchmark"})
QUALITY_FLAGS = frozenset({"good", "warning", "critical", "unknown"})


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


def safe_url(value: str) -> str:
    """Remove credentials, query, and fragment before persistence."""
    parsed = urlsplit(value)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname:
        raise ValueError("source_url must be an absolute HTTP(S) URL")
    host = parsed.hostname
    if parsed.port:
        host = f"{host}:{parsed.port}"
    return urlunsplit((parsed.scheme, host, parsed.path, "", ""))


def content_hash(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def idempotency_key(source_id: str, dataset_id: str, observed_at: datetime, digest: str) -> str:
    material = "\n".join((source_id, dataset_id, _utc(observed_at).isoformat(), digest)).encode()
    return hashlib.sha256(material).hexdigest()


@dataclass(frozen=True)
class Provenance:
    provenance_id: str
    source_id: str
    source_url: str
    dataset_id: str
    observed_at: datetime
    published_at: datetime | None
    fetched_at: datetime
    content_hash: str
    is_fallback: bool = False
    quality_flags: tuple[str, ...] = ("good",)
    quality_details: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.source_id not in SOURCE_IDS:
            raise ValueError(f"unsupported source_id: {self.source_id}")
        if self.dataset_id not in DATASET_IDS:
            raise ValueError(f"unsupported dataset_id: {self.dataset_id}")
        if not self.provenance_id:
            raise ValueError("provenance_id is required")
        if not self.content_hash.startswith("sha256:") or len(self.content_hash) != 71:
            raise ValueError("content_hash must be sha256:<64 lowercase hex chars>")
        int(self.content_hash[7:], 16)
        if not self.quality_flags or any(flag not in QUALITY_FLAGS for flag in self.quality_flags):
            raise ValueError("quality_flags contains an unsupported value")
        _utc(self.observed_at)
        _utc(self.fetched_at)
        if self.published_at is not None:
            _utc(self.published_at)
        object.__setattr__(self, "source_url", safe_url(self.source_url))

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        for field in ("observed_at", "published_at", "fetched_at"):
            value = result[field]
            result[field] = _utc(value).isoformat().replace("+00:00", "Z") if value else None
        result["quality_flags"] = list(self.quality_flags)
        return result
