"""Exact-snapshot Core reads and public Mart Iceberg v2 writes."""

from __future__ import annotations

from datetime import date
import json
import os
from typing import Any


MART_TABLES = (
    "mart_screening_signals", "mart_core_alpha", "mart_risk_portfolio",
    "mart_alternative_sentiment", "mart_scoped_analysis", "mart_market_regime_daily",
    "mart_sector_rotation_daily", "mart_topic_trends_daily", "mart_candidate_health",
    "mart_daily_brief", "mart_llm_narratives",
)


def sql_catalog_from_environment() -> Any:
    from pyiceberg.catalog.sql import SqlCatalog
    from sqlalchemy import URL

    required = {name: os.environ.get(name, "").strip() for name in (
        "CATALOG_DB_HOST", "CATALOG_DB_NAME", "CATALOG_DB_USER", "CATALOG_DB_PASSWORD", "GCP_PROJECT_ID", "MART_BUCKET",
    )}
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise ValueError(f"missing Iceberg catalog settings: {','.join(missing)}")
    uri = URL.create(
        "postgresql+psycopg", username=required["CATALOG_DB_USER"], password=required["CATALOG_DB_PASSWORD"],
        host=required["CATALOG_DB_HOST"], port=5432, database=required["CATALOG_DB_NAME"],
        query={"sslmode": os.environ.get("CATALOG_DB_SSLMODE", "require"), "options": "-csearch_path=catalog"},
    )
    warehouse = os.environ.get("MART_ICEBERG_WAREHOUSE", f"gs://{required['MART_BUCKET']}/warehouse").strip()
    if not warehouse.startswith(f"gs://{required['MART_BUCKET']}/"):
        raise ValueError("MART_ICEBERG_WAREHOUSE must remain inside MART_BUCKET")
    return SqlCatalog(
        "janus", type="sql", uri=uri, warehouse=warehouse, init_catalog_tables="false",
        **{"py-io-impl": "pyiceberg.io.pyarrow.PyArrowFileIO", "gcs.project-id": required["GCP_PROJECT_ID"],
           "pool_size": 1, "max_overflow": 0, "pool_timeout": 5, "pool_pre_ping": "true"},
    )


def load_core_datasets(catalog: Any, manifest: dict[str, Any], requested_symbols: tuple[str, ...],
                       *, row_limit: int = 100_000) -> dict[str, list[dict[str, Any]]]:
    """Read only snapshot IDs carried by the immutable Core manifest."""
    embedded = manifest.get("datasets")
    if embedded is not None:
        if not isinstance(embedded, dict) or any(not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows)
                                                 for rows in embedded.values()):
            raise ValueError("Core manifest datasets must be arrays")
        if sum(map(len, embedded.values())) > row_limit:
            raise ValueError("Core snapshot row limit exceeded")
        return {str(name): [dict(row) for row in rows] for name, rows in embedded.items()}
    tables = manifest.get("iceberg_tables", {})
    if not isinstance(tables, dict):
        raise ValueError("Core manifest iceberg_tables must be an object")
    from pyiceberg.expressions import In

    datasets: dict[str, list[dict[str, Any]]] = {}
    remaining = row_limit
    for identifier, fence in sorted(tables.items()):
        if remaining <= 0:
            raise ValueError("Core snapshot row limit exceeded")
        if not isinstance(fence, dict) or fence.get("snapshot_id") is None:
            raise ValueError("Core table is missing an immutable snapshot ID")
        if not str(identifier).startswith("core.") or not str(identifier).endswith("_v1"):
            raise ValueError("Core manifest contains a non-Core table")
        dataset_id = str(identifier).split(".", 1)[1][:-3].replace("_", "-")
        table = catalog.load_table(identifier)
        field_names = {field.name for field in table.schema().fields}
        filter_ = In("symbol", set(requested_symbols)) if requested_symbols and "symbol" in field_names else None
        scan_options: dict[str, Any] = {"snapshot_id": int(fence["snapshot_id"]), "limit": remaining}
        if filter_ is not None:
            scan_options["row_filter"] = filter_
        scan = table.scan(**scan_options)
        rows = scan.to_arrow().to_pylist()
        remaining -= len(rows)
        if remaining < 0:
            raise ValueError("Core snapshot row limit exceeded")
        datasets[dataset_id] = [dict(row, __table_identifier=identifier, __snapshot_id=fence["snapshot_id"]) for row in rows]
    return datasets


class MartIcebergStore:
    """A fixed public schema with JSON payload columns for versioned data products."""

    def __init__(self, catalog: Any, warehouse: str, namespace: str = "mart") -> None:
        if "://" in warehouse and not warehouse.startswith(("gs://", "file://")):
            raise ValueError("Mart Iceberg warehouse must be a gs:// or local test URI")
        self.catalog, self.warehouse, self.namespace = catalog, warehouse.rstrip("/"), namespace
        catalog.create_namespace_if_not_exists(namespace)

    def ensure_tables(self) -> None:
        import pyarrow as pa

        schema = pa.schema([
            pa.field("execution_id", pa.string(), nullable=False),
            pa.field("analysis_date", pa.date32(), nullable=False),
            pa.field("scope_type", pa.string(), nullable=False),
            pa.field("scope_id", pa.string(), nullable=False),
            pa.field("symbol", pa.string()),
            pa.field("industry", pa.string()),
            pa.field("coverage", pa.string(), nullable=False),
            pa.field("membership_snapshot_hash", pa.string(), nullable=False),
            pa.field("core_snapshot_id", pa.string(), nullable=False),
            pa.field("governance_snapshot_version", pa.string(), nullable=False),
            pa.field("schema_version", pa.string(), nullable=False),
            pa.field("feature_version", pa.string(), nullable=False),
            pa.field("model_version", pa.string(), nullable=False),
            pa.field("prompt_version", pa.string(), nullable=False),
            pa.field("prompt_hash", pa.string(), nullable=False),
            pa.field("completeness", pa.float64(), nullable=False),
            pa.field("confidence", pa.float64(), nullable=False),
            pa.field("data_quality", pa.string(), nullable=False),
            pa.field("analysis_outcome", pa.string(), nullable=False),
            pa.field("publication_status", pa.string(), nullable=False),
            pa.field("deterministic_hash", pa.string(), nullable=False),
            pa.field("artifact_ref", pa.string(), nullable=False),
            pa.field("payload_json", pa.string(), nullable=False),
        ])
        for table_name in MART_TABLES:
            identifier = f"{self.namespace}.{table_name}_v1"
            if self.catalog.table_exists(identifier):
                table = self.catalog.load_table(identifier)
                normalize = lambda type_: "string" if str(type_) == "large_string" else str(type_)
                actual = [(field.name, normalize(field.type)) for field in table.schema().as_arrow()]
                expected = [(field.name, normalize(field.type)) for field in schema]
                if table.metadata.format_version != 2 or actual != expected:
                    raise ValueError(f"incompatible public Mart schema: {identifier}; create a new version")
                continue
            table = self.catalog.create_table(
                identifier, schema, location=f"{self.warehouse}/{table_name}_v1",
                properties={"format-version": "2", "write.format.default": "parquet", "write.parquet.compression-codec": "zstd"},
            )
            with table.update_spec() as spec:
                spec.add_field("analysis_date", "month")
                spec.add_field("scope_id", "bucket[32]")

    @staticmethod
    def _state(score: float | None) -> str:
        if score is None:
            return "insufficient_data"
        if score >= 60:
            return "accumulating"
        if score <= 40:
            return "distributing"
        return "neutral"

    def _products(self, reports: list[dict[str, Any]], narratives: dict[tuple[str, str], dict[str, Any]]) -> dict[str, list[tuple[dict[str, Any], Any]]]:
        products: dict[str, list[tuple[dict[str, Any], Any]]] = {name: [] for name in MART_TABLES}
        for report in reports:
            scope, features, aggregate = report["scope"], report["features"], report["aggregate"]
            products["mart_scoped_analysis"].append((report, report))
            if scope["type"] == "symbol":
                products["mart_screening_signals"].append((report, features["screening"]))
                products["mart_core_alpha"].append((report, {key: features[key] for key in ("fundamental", "valuation", "quant", "event_risk")}))
                products["mart_risk_portfolio"].append((report, {"event_risk": features["event_risk"], "quant": features["quant"]}))
                health = (round(max(1, min(100, aggregate["aggregate_score"])))
                          if aggregate["analysis_outcome"] == "complete" and aggregate["aggregate_score"] is not None else None)
                position_score = next(role["score"] for role in report["roles"] if role["role"] == "positioning")
                narrative = narratives.get((scope["type"], scope["id"]))
                explanation = narrative["narrative"] if narrative and narrative.get("status") == "succeeded" else None
                products["mart_candidate_health"].append((report, {"stock_id": scope["id"], "mart_health_score": health,
                    "stock_name": scope.get("name", scope["id"]),
                    "chips_status": self._state(position_score) if health is not None else "insufficient_data",
                    "data_status": aggregate["publication_status"],
                    "analysis_as_of": report["analysis_as_of"], "confidence": aggregate["confidence"],
                    "evidence_refs": [item["evidence_id"] for item in report["evidence"]],
                    "ai_whitepaper_analysis": explanation["summary"] if explanation else None,
                    "ai_evidence_refs": explanation["evidence_ids"] if explanation else []}))
            elif scope["type"] == "industry":
                products["mart_sector_rotation_daily"].append((report, {"membership_snapshot": scope["symbols"],
                    "institutional_5d_strength": features["positioning"]["net_volume_ratio_5d"],
                    "institutional_20d_strength": features["positioning"]["net_volume_ratio_20d"],
                    "institutional_5d_strength_change": (features["positioning"]["net_volume_ratio_5d"] - features["positioning"]["net_volume_ratio_previous_5d"]
                                                          if features["positioning"]["net_volume_ratio_5d"] is not None and features["positioning"]["net_volume_ratio_previous_5d"] is not None else None),
                    "turnover_20d": features["quant"]["turnover_20d"], "state": self._state(aggregate["aggregate_score"])}))
            elif scope["type"] == "market":
                products["mart_market_regime_daily"].append((report, {"state": self._state(aggregate["aggregate_score"]), "score": aggregate["aggregate_score"]}))
                topics = sorted({item["metric"] for item in report["evidence"] if item["dataset_id"] == "events"})
                products["mart_topic_trends_daily"].append((report, {"topics": topics}))
                if report.get("published_components"):
                    products["mart_daily_brief"].append((report, {"analysis_as_of": report["analysis_as_of"],
                        "market_scope": scope["id"], "published_components": report["published_components"]}))
            narrative = narratives.get((scope["type"], scope["id"]))
            if narrative and narrative.get("status") == "succeeded":
                products["mart_llm_narratives"].append((report, narrative))
        return products

    def write(self, reports: list[dict[str, Any]], narratives: dict[tuple[str, str], dict[str, Any]] | None = None) -> dict[tuple[str, str], dict[str, Any]]:
        import pyarrow as pa

        self.ensure_tables()
        references: dict[tuple[str, str], dict[str, Any]] = {}
        for table_name, values in self._products(reports, narratives or {}).items():
            if not values:
                continue
            identifier = f"{self.namespace}.{table_name}_v1"
            table = self.catalog.load_table(identifier)
            rows = []
            for report, payload in values:
                scope, aggregate = report["scope"], report["aggregate"]
                rows.append({
                    "execution_id": report["execution_id"], "analysis_date": date.fromisoformat(report["analysis_as_of"]),
                    "scope_type": scope["type"], "scope_id": scope["id"], "core_snapshot_id": report["core_snapshot_id"],
                    "symbol": scope["id"] if scope["type"] == "symbol" else None,
                    "industry": scope["id"] if scope["type"] == "industry" else None,
                    "coverage": str(scope.get("coverage", {"market": "market_wide", "industry": "industry_membership", "symbol": "symbol"}[scope["type"]])),
                    "membership_snapshot_hash": report["membership_snapshot_hash"],
                    "governance_snapshot_version": str(report["governance_snapshot_version"]),
                    "schema_version": str(report["schema_version"]), "feature_version": str(report["feature_version"]),
                    "model_version": str(report["model_version"]), "completeness": aggregate["completeness"],
                    "prompt_version": report["prompt_version"], "prompt_hash": report["prompt_hash"],
                    "confidence": aggregate["confidence"], "data_quality": report["data_quality"],
                    "analysis_outcome": aggregate["analysis_outcome"], "publication_status": aggregate["publication_status"],
                    "deterministic_hash": report["deterministic_hash"],
                    "artifact_ref": f"iceberg://{identifier}/{report['execution_id']}/{scope['type']}/{scope['id']}",
                    "payload_json": json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str),
                })
            incoming = pa.Table.from_pylist(rows, schema=table.schema().as_arrow())
            from pyiceberg.expressions import In
            existing = table.scan(row_filter=In("execution_id", {row["execution_id"] for row in rows})).to_arrow().to_pylist()
            existing_by_key = {(row["execution_id"], row["scope_type"], row["scope_id"]): row for row in existing}
            changed = [row for row in rows if existing_by_key.get((row["execution_id"], row["scope_type"], row["scope_id"])) != row]
            if changed:
                table.upsert(pa.Table.from_pylist(changed, schema=table.schema().as_arrow()),
                             join_cols=["execution_id", "scope_type", "scope_id"])
            refreshed = self.catalog.load_table(identifier)
            snapshot = refreshed.current_snapshot()
            if table_name == "mart_scoped_analysis":
                for report in reports:
                    scope = report["scope"]
                    references[(scope["type"], scope["id"])] = {
                        "table_identifier": identifier, "iceberg_snapshot_id": snapshot.snapshot_id if snapshot else None,
                        "artifact_uri": refreshed.metadata_location,
                    }
        return references

    def close(self) -> None:
        engine = getattr(self.catalog, "engine", None)
        if engine is not None:
            engine.dispose()
