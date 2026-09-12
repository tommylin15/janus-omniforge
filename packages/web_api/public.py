"""Read-only public Mart lookup through the publication index."""

from __future__ import annotations

from datetime import date, datetime
from hashlib import sha256
import json
import re
from typing import Any, Callable
from urllib.parse import urlsplit


class PublicReportNotFound(LookupError):
    pass


class PostgreSQLPublicIndex:
    """The public role can only select the fail-closed publication view."""

    FIELDS = (
        "execution_id", "analysis_as_of", "scope_type", "scope_id", "artifact_uri",
        "artifact_hash", "table_identifier", "iceberg_snapshot_id", "schema_version",
        "feature_version", "model_version", "governance_snapshot_version", "prompt_version",
        "completeness", "confidence", "data_quality", "analysis_outcome", "publication_status",
    )

    def __init__(self, connection: Any) -> None:
        self.connection = connection

    def latest(self, scope_type: str, scope_id: str, analysis_as_of: date | None) -> dict[str, Any] | None:
        clause, values = "", [scope_type, scope_id]
        if analysis_as_of is not None:
            clause, values = " AND analysis_as_of=%s", [scope_type, scope_id, analysis_as_of]
        with self.connection.cursor() as cursor:
            cursor.execute(
                f"SELECT {','.join(self.FIELDS)} FROM publication.publishable_mart_reports "
                f"WHERE scope_type=%s AND scope_id=%s{clause} "
                "ORDER BY analysis_as_of DESC,ready_at DESC,execution_id DESC LIMIT 1",
                values,
            )
            row = cursor.fetchone()
        return dict(zip(self.FIELDS, row, strict=True)) if row else None


class IcebergArtifactReader:
    """Verify the immutable metadata object, then scan the indexed snapshot."""

    def __init__(self, catalog: Any, store_factory: Callable[[str], Any]) -> None:
        self.catalog, self.store_factory = catalog, store_factory

    def __call__(self, index: dict[str, Any]) -> dict[str, Any]:
        uri = urlsplit(str(index["artifact_uri"]))
        if uri.scheme != "gs" or not uri.netloc or not uri.path.strip("/"):
            raise ValueError("invalid public artifact reference")
        metadata = self.store_factory(uri.netloc).read(uri.path.lstrip("/"))
        if f"sha256:{sha256(metadata).hexdigest()}" != index["artifact_hash"]:
            raise ValueError("public artifact hash mismatch")
        if index["table_identifier"] != "mart.mart_scoped_analysis_v1":
            raise ValueError("invalid public Mart table")

        from pyiceberg.expressions import And, EqualTo

        table = self.catalog.load_table(index["table_identifier"])
        rows = table.scan(
            snapshot_id=int(index["iceberg_snapshot_id"]),
            row_filter=And(
                EqualTo("execution_id", str(index["execution_id"])),
                And(EqualTo("scope_type", index["scope_type"]), EqualTo("scope_id", index["scope_id"])),
            ),
            limit=2,
        ).to_arrow().to_pylist()
        if len(rows) != 1:
            raise ValueError("public artifact row is missing or ambiguous")
        return rows[0]


class PublicMartService:
    SCOPE_TYPES = frozenset({"market", "industry", "symbol"})

    def __init__(self, index: PostgreSQLPublicIndex, read_artifact: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
        self.index, self.read_artifact = index, read_artifact

    def report(self, scope_type: str, scope_id: str, *, analysis_as_of: str = "") -> dict[str, Any]:
        if scope_type not in self.SCOPE_TYPES or not re.fullmatch(r"[\w.:-]{1,80}", scope_id):
            raise ValueError("invalid public report scope")
        as_of = date.fromisoformat(analysis_as_of) if analysis_as_of else None
        index = self.index.latest(scope_type, scope_id, as_of)
        if index is None:
            raise PublicReportNotFound
        row = self.read_artifact(index)
        if (
            row.get("analysis_outcome") != "complete"
            or row.get("publication_status") not in {"publishable", "published"}
            or str(row.get("execution_id")) != str(index["execution_id"])
            or row.get("scope_type") != scope_type
            or row.get("scope_id") != scope_id
        ):
            raise PublicReportNotFound
        payload = json.loads(row["payload_json"])
        if not isinstance(payload, dict):
            raise ValueError("public artifact payload must be an object")
        return {
            "analysis_as_of": self._iso(index["analysis_as_of"]),
            "scope_type": scope_type,
            "scope_id": scope_id,
            "data_status": row["publication_status"],
            "confidence": row["confidence"],
            "completeness": row["completeness"],
            "schema_version": row["schema_version"],
            "model_version": row["model_version"],
            "governance_snapshot_version": row["governance_snapshot_version"],
            "data": payload,
        }

    @staticmethod
    def _iso(value: Any) -> str:
        return value.isoformat() if isinstance(value, (date, datetime)) else str(value)
