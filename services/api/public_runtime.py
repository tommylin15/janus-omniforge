"""Bounded read-only Core and public Mart runtimes for FastAPI."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from threading import Lock
from typing import Any, Sequence

from packages.web_api import CoreQueryService, IcebergArtifactReader, PostgreSQLPublicIndex, PublicMartService


def market_serving_query(identifier: str, parameters: Sequence[Any]):
    """Fixed PostgreSQL reads; homepage never scans canonical Parquet files."""
    dataset = {"core.benchmark_v1": "benchmark", "core.institutional_v1": "institutional",
               "core.market_activity_v1": "market-activity", "core.financials_v1": "financials"}.get(identifier)
    if dataset is None:
        return None
    table = "publication.market_serving_recent"
    if dataset in {"institutional", "financials"} and len(parameters) == 3:
        symbol, limit, offset = parameters
        if not isinstance(limit, int) or not isinstance(offset, int):
            return None
        return (f"SELECT payload_json FROM {table} WHERE dataset_id=%s AND symbol=%s "
                "ORDER BY sort_at DESC,natural_key LIMIT %s OFFSET %s",
                (dataset, str(symbol).upper(), min(max(limit, 1), 600), max(offset, 0)), True)
    if dataset == "benchmark":
        if len(parameters) != 2 or parameters[0] != "TAIEX" or not isinstance(parameters[1], int):
            return None
        return (f"SELECT payload_json FROM {table} WHERE dataset_id=%s AND symbol=%s "
                "ORDER BY sort_at DESC LIMIT %s", (dataset, "TAIEX", min(max(parameters[1], 1), 200)), True)
    if parameters:
        return None
    if dataset == 'financials':
        return None
    fields = ({"day_trade_shares": "day_trade_shares", "day_trade_buy_twd": "day_trade_buy_twd",
               "day_trade_sell_twd": "day_trade_sell_twd"} if dataset == "market-activity" else
              {"foreign_net_shares": "foreign", "investment_trust_net_shares": "investment_trust",
               "dealer_net_shares": "dealer"})
    category, value = ("metric", "value") if dataset == "market-activity" else ("investor_type", "net_shares")
    aggregates = ",".join(
        f"sum((payload_json->>'{value}')::numeric) FILTER (WHERE payload_json->>'{category}'='{kind}') AS {alias}"
        for alias, kind in fields.items())
    return (f"SELECT payload_json->>'trade_date' AS trade_date,count(*) AS row_count,"
            "count(DISTINCT symbol) AS covered_symbols,array_agg(DISTINCT source_id) AS source_ids,"
            "array_agg(DISTINCT provenance_id) AS provenance_ids,array_agg(DISTINCT execution_id::text) AS execution_ids,"
            f"{aggregates} FROM {table} WHERE dataset_id=%s AND sort_at=("
            f"SELECT max(sort_at) FROM {table} WHERE dataset_id=%s) GROUP BY payload_json->>'trade_date'",
            (dataset, dataset), False)


def _emit_core_query_source(identifier: str, source: str) -> None:
    dataset = {
        "core.ohlcv_v1": "ohlcv",
        "core.valuation_v1": "valuation",
        "core.events_v1": "events",
        "core.benchmark_v1": "benchmark",
        "core.institutional_v1": "institutional",
        "core.market_activity_v1": "market-activity",
    }.get(identifier, "unknown")
    print(json.dumps({
        "component": "janus-api",
        "operation": "core_query_source",
        "source": source,
        "dataset": dataset,
    }, sort_keys=True), flush=True)


def _required(*names: str) -> dict[str, str]:
    values = {name: os.environ.get(name, "").strip() for name in names}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise ValueError(f"missing public runtime settings:{','.join(missing)}")
    return values


def _catalog_settings() -> dict[str, str]:
    from packages.postgres_bundle import load_postgres_bundle

    load_postgres_bundle("JANUS_API_POSTGRES_BUNDLE", {
        "CATALOG_DB_PASSWORD": ("web_catalog_password", "catalog_password"),
    })
    warehouse = os.environ.get("CORE_ICEBERG_WAREHOUSE", "").strip()
    bucket = os.environ.get("CORE_BUCKET", "").strip()
    if not bucket and warehouse.startswith("gs://"):
        bucket = warehouse[5:].split("/", 1)[0]
    settings = {
        "GCP_PROJECT_ID": os.environ.get("GCP_PROJECT_ID", "").strip(),
        "CORE_BUCKET": bucket,
        "CATALOG_DB_HOST": (os.environ.get("CATALOG_DB_HOST", "").strip()
                             or os.environ.get("POSTGRES_HOST", "").strip()),
        "CATALOG_DB_NAME": (os.environ.get("CATALOG_DB_NAME", "").strip()
                             or os.environ.get("POSTGRES_DB", "").strip()),
        "CATALOG_DB_USER": (os.environ.get("CATALOG_DB_USER", "").strip()
                             or os.environ.get("CORE_CATALOG_USER", "").strip()),
        "CATALOG_DB_PASSWORD": os.environ.get("CATALOG_DB_PASSWORD", "").strip(),
    }
    missing = [name for name, value in settings.items() if not value]
    if missing:
        raise ValueError(f"missing public runtime settings:{','.join(missing)}")
    if settings["CATALOG_DB_USER"] != "janus_web_catalog":
        raise ValueError("public query runtime requires janus_web_catalog")
    return settings


def build_core_service() -> CoreQueryService:
    from packages.postgres_bundle import load_postgres_bundle

    load_postgres_bundle("JANUS_API_POSTGRES_BUNDLE", {
        "PUBLICATION_DB_PASSWORD": ("web_publication_password",),
    })
    settings = _catalog_settings()
    reader = None
    lock = Lock()
    serving_lock = Lock()
    serving_connection: Any | None = None

    def connect_serving():
        import psycopg
        publication_user = os.environ.get("PUBLICATION_DB_USER", "janus_public_api").strip()
        if publication_user != "janus_public_api":
            raise ValueError("public query runtime requires janus_public_api")
        password = os.environ.get("PUBLICATION_DB_PASSWORD", "").strip()
        if not password:
            raise ValueError("PUBLICATION_DB_PASSWORD is required")
        return psycopg.connect(
            host=os.environ.get("PUBLICATION_DB_HOST", settings["CATALOG_DB_HOST"]),
            dbname=os.environ.get("PUBLICATION_DB_NAME", settings["CATALOG_DB_NAME"]),
            user=publication_user, password=password,
            sslmode=os.environ.get("PUBLICATION_DB_SSLMODE", "require"), connect_timeout=5,
            options="-c statement_timeout=2000 -c default_transaction_read_only=on", autocommit=True,
        )

    def serving_rows(identifier: str, parameters: Sequence[Any]) -> list[dict[str, Any]] | None:
        nonlocal serving_connection
        market_query = market_serving_query(identifier, parameters)
        if market_query is not None:
            serving_connection = serving_connection or connect_serving()
            try:
                with serving_connection.cursor() as cursor:
                    statement, values, payload_only = market_query
                    cursor.execute(statement, values)
                    records = cursor.fetchall()
                    if payload_only:
                        return [value if isinstance(value, dict) else json.loads(value) for (value,) in records]
                    names = [column.name for column in cursor.description]
                    return [dict(zip(names, record)) for record in records]
            except Exception:
                serving_connection.close()
                serving_connection = None
                raise
        dataset = {
            "core.ohlcv_v1": "ohlcv",
            "core.valuation_v1": "valuation",
            "core.events_v1": "events",
        }.get(identifier)
        if dataset is None or len(parameters) != 3:
            return None
        symbol, limit, offset = parameters
        if not isinstance(limit, int) or not isinstance(offset, int):
            return None
        for attempt in range(2):
            try:
                serving_connection = serving_connection or connect_serving()
                with serving_connection.cursor() as cursor:
                    cursor.execute(
                        """SELECT payload_json
                           FROM publication.stock_serving_recent
                           WHERE dataset_id=%s AND symbol=%s
                           ORDER BY sort_at DESC
                           LIMIT %s OFFSET %s""",
                        (dataset, str(symbol).upper(), limit, offset),
                    )
                    rows = cursor.fetchall()
                return [value if isinstance(value, dict) else json.loads(value) for (value,) in rows]
            except Exception as error:
                disconnected = bool(getattr(serving_connection, "closed", False)) or str(
                    getattr(error, "sqlstate", "")).startswith("08")
                if serving_connection is not None:
                    try:
                        serving_connection.close()
                    except Exception:
                        pass
                    serving_connection = None
                if attempt or not disconnected:
                    return None
        return None

    # A slow Iceberg fallback must not hold the PostgreSQL first-paint reader.
    def query(identifier: str, sql: str, parameters: Sequence[Any] = ()):
        nonlocal reader
        with serving_lock:
            rows = serving_rows(identifier, parameters)
            if market_serving_query(identifier, parameters) is not None:
                _emit_core_query_source(identifier, "serving_projection")
                return rows or []
            if rows is not None:
                _emit_core_query_source(identifier, "serving_projection")
                return rows
        with lock:
            _emit_core_query_source(identifier, "iceberg_fallback")
            if reader is None:
                from packages.duckdb_query import DuckDBIcebergCore, IcebergQuery
                iceberg = DuckDBIcebergCore.from_postgres(
                    host=settings["CATALOG_DB_HOST"], dbname=settings["CATALOG_DB_NAME"],
                    user=settings["CATALOG_DB_USER"], password=settings["CATALOG_DB_PASSWORD"],
                    warehouse=os.environ.get("ICEBERG_WAREHOUSE", f"gs://{settings['CORE_BUCKET']}/warehouse"),
                    project_id=settings["GCP_PROJECT_ID"], sslmode=os.environ.get("CATALOG_DB_SSLMODE", "require"),
                    read_only=True,
                )
                reader = IcebergQuery(iceberg.catalog, engine=iceberg.engine)
            return reader.query(identifier, sql, parameters)

    def serving_series(dataset: str, symbol: str, limit: int):
        # Return None on connection failure (vs [] for an empty projection).
        # Share the PostgreSQL connection lock; never fall back to Iceberg.
        identifier = f"core.{dataset}_v1"
        with serving_lock:
            return serving_rows(identifier, (symbol, limit, 0))

    def read_valuation_profile(symbol: str, metric: str) -> dict[str, Any] | None:
        # A single published, owner-independent row; never a Core/GCS scan.
        nonlocal serving_connection
        if metric not in {"pe_ratio", "pb_ratio"}:
            return None
        for attempt in range(2):
            try:
                serving_connection = serving_connection or connect_serving()
                with serving_connection.cursor() as cursor:
                    cursor.execute(
                        """SELECT payload_json FROM publication.stock_valuation_five_year
                           WHERE symbol=%s AND metric=%s LIMIT 1""",
                        (symbol, metric),
                    )
                    row = cursor.fetchone()
                    if not row:
                        return None
                    value = row[0]
                    return value if isinstance(value, dict) else json.loads(value)
            except Exception as error:
                disconnected = bool(getattr(serving_connection, "closed", False)) or str(
                    getattr(error, "sqlstate", "")).startswith("08")
                if serving_connection is not None:
                    try:
                        serving_connection.close()
                    except Exception:
                        pass
                    serving_connection = None
                if attempt or not disconnected:
                    return None
        return None

    def serving_valuation_profile(symbol: str, metric: str) -> dict[str, Any] | None:
        with serving_lock:
            return read_valuation_profile(symbol, metric)

    def read_home_market_snapshot() -> dict[str, Any] | None:
        # Write-time aggregation projection; reads single pre-aggregated row by PK in <5ms.
        nonlocal serving_connection
        for attempt in range(2):
            try:
                serving_connection = serving_connection or connect_serving()
                with serving_connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT payload_json FROM publication.home_market_snapshot WHERE snapshot_id = 1"
                    )
                    row = cursor.fetchone()
                    if row and row[0]:
                        val = row[0]
                        return val if isinstance(val, dict) else json.loads(val)
                return None
            except Exception as error:
                disconnected = bool(getattr(serving_connection, "closed", False)) or str(
                    getattr(error, "sqlstate", "")).startswith("08")
                if serving_connection is not None:
                    try:
                        serving_connection.close()
                    except Exception:
                        pass
                    serving_connection = None
                if attempt or not disconnected:
                    return None
        return None

    def serving_home_market_snapshot() -> dict[str, Any] | None:
        with serving_lock:
            return read_home_market_snapshot()

    return CoreQueryService(query, max_limit=int(os.environ.get("WEB_QUERY_MAX_ROWS", "200")),
                            serving_series=serving_series,
                            serving_home_market_snapshot=serving_home_market_snapshot,
                            serving_valuation_profile=serving_valuation_profile)


def build_public_service() -> PublicMartService:
    from packages.postgres_bundle import load_postgres_bundle

    stage = "publication bundle"
    try:
        load_postgres_bundle("JANUS_API_POSTGRES_BUNDLE", {"PUBLICATION_DB_PASSWORD": ("web_publication_password",)})
        stage = "catalog bundle/settings"
        settings = _catalog_settings() | _required("PUBLICATION_DB_PASSWORD")
        publication_user = os.environ.get("PUBLICATION_DB_USER", "janus_public_api").strip()
        if publication_user != "janus_public_api":
            raise ValueError("public query runtime requires janus_public_api")

        stage = "imports"
        import psycopg
        from pyiceberg.catalog.sql import SqlCatalog
        from sqlalchemy import URL
        from ingestion_core.stage import GcsObjectStore

        stage = "catalog"
        uri = URL.create(
            "postgresql+psycopg", username=settings["CATALOG_DB_USER"],
            password=settings["CATALOG_DB_PASSWORD"], host=settings["CATALOG_DB_HOST"],
            port=5432, database=settings["CATALOG_DB_NAME"],
            query={"sslmode": os.environ.get("CATALOG_DB_SSLMODE", "require"), "options": "-csearch_path=catalog"},
        )
        catalog = SqlCatalog(
            "janus", type="sql", uri=uri,
            warehouse=os.environ.get("ICEBERG_WAREHOUSE", f"gs://{settings['CORE_BUCKET']}/warehouse"),
            init_catalog_tables="false",
            **{"py-io-impl": "pyiceberg.io.pyarrow.PyArrowFileIO", "gcs.project-id": settings["GCP_PROJECT_ID"],
               "pool_size": 1, "max_overflow": 0, "pool_timeout": 5, "pool_pre_ping": "true"},
        )
        stage = "publication connection"
        def connect_publication():
            return psycopg.connect(
                host=os.environ.get("PUBLICATION_DB_HOST", settings["CATALOG_DB_HOST"]),
                dbname=os.environ.get("PUBLICATION_DB_NAME", settings["CATALOG_DB_NAME"]),
                user=publication_user,
                password=settings["PUBLICATION_DB_PASSWORD"],
                sslmode=os.environ.get("PUBLICATION_DB_SSLMODE", "require"), connect_timeout=5,
                options="-c statement_timeout=5000 -c default_transaction_read_only=on", autocommit=True,
            )
        connection = connect_publication()
        return PublicMartService(
            PostgreSQLPublicIndex(connection, connect_publication), IcebergArtifactReader(catalog, GcsObjectStore),
        )
    except Exception as error:
        raise RuntimeError(f"public runtime setup failed at {stage}:{type(error).__name__}") from error


class PipelineService:
    """Thin wrapper to trigger Cloud Run Jobs with execution-scoped overrides."""

    def __init__(self, *, project: str, region: str, ingestion_job: str, mart_job: str) -> None:
        self._project = project
        self._region = region
        self._ingestion_job = ingestion_job
        self._mart_job = mart_job

    @classmethod
    def from_env(cls) -> "PipelineService":
        project = os.environ.get("GCP_PROJECT_ID", "").strip()
        region = os.environ.get("GCP_REGION", "us-central1").strip()
        ingestion_job = os.environ.get("INGESTION_JOB", "janus-ingestion-core").strip()
        mart_job = os.environ.get("MART_JOB", "janus-intelligence-mart").strip()
        if not project:
            raise ValueError("GCP_PROJECT_ID is required for pipeline service")
        return cls(project=project, region=region, ingestion_job=ingestion_job, mart_job=mart_job)

    def _jobs_url(self, job: str) -> str:
        return f"https://run.googleapis.com/v2/projects/{self._project}/locations/{self._region}/jobs/{job}"

    def _authorized_session(self) -> Any:
        import google.auth
        from google.auth.transport.requests import AuthorizedSession
        credentials, _ = google.auth.default(scopes=("https://www.googleapis.com/auth/cloud-platform",))
        return AuthorizedSession(credentials)

    def supplement(self) -> dict[str, Any]:
        """Wake the durable symbol queue; the worker enforces the shared writer lock."""
        env = [{'name': name, 'value': value} for name, value in (
            ('JANUS_DATA_SUPPLEMENT_MODE', 'demand'), ('QUEUE_CONSUMER', 'false'),
            ('MART_JOB', ''), ('ICEBERG_MAINTENANCE_MODE', ''),
            ('JANUS_SERVING_SCHEMA_MIGRATION', ''), ('JANUS_CONTROL_MIGRATION', ''))]
        response = self._authorized_session().post(self._jobs_url(self._ingestion_job) + ':run',
            json={'overrides': {'taskCount': 1, 'containerOverrides': [{'env': env}]}}, timeout=10)
        response.raise_for_status()
        return {'status': 'accepted'}

    def backfill(self, start_date: str, end_date: str, *, trigger_mart: bool = False) -> dict[str, Any]:
        """Execute a bounded ingestion backfill without mutating the Cloud Run Job definition."""
        from datetime import date as _date

        first = _date.fromisoformat(start_date)
        last = _date.fromisoformat(end_date)
        if first > last:
            raise ValueError("start_date must not be after end_date")
        if (last - first).days > 366:
            raise ValueError("backfill range cannot exceed 367 calendar days")

        env = [
            {"name": "INGESTION_DATE", "value": ""},
            {"name": "BACKFILL_START_DATE", "value": start_date},
            {"name": "BACKFILL_END_DATE", "value": end_date},
            {"name": "FORCE_REFRESH", "value": "true"},
            {"name": "QUEUE_CONSUMER", "value": "false"},
            {"name": "MART_JOB", "value": self._mart_job if trigger_mart else ""},
        ]
        payload = {"overrides": {"containerOverrides": [{"env": env}]}}
        session = self._authorized_session()
        run_resp = session.post(self._jobs_url(self._ingestion_job) + ":run", json=payload, timeout=10)
        run_resp.raise_for_status()
        run_data = run_resp.json()
        return {
            "status": "accepted",
            "start_date": start_date,
            "end_date": end_date,
            "trigger_mart": trigger_mart,
            "execution_name": run_data.get("metadata", {}).get("name", ""),
        }


def build_pipeline_service() -> PipelineService:
    return PipelineService.from_env()


@lru_cache(maxsize=2)
def _maintenance_evidence(minute: int) -> dict[str, Any]:
    """Read recent persisted receipts, never enumerate a bucket on page load."""
    from google.cloud import storage
    now = datetime.fromtimestamp(minute * 60, timezone.utc)
    result = {}
    try:
        client = storage.Client()
    except Exception:
        return result
    for component, bucket_name in (("core", os.getenv("CORE_BUCKET", "")),
                                    ("mart", os.getenv("MART_BUCKET", ""))):
        if not bucket_name:
            continue
        try:
            receipt = None
            for age in range(7):
                prefix = 'maintenance/retention/' + (now - timedelta(days=age)).strftime('%Y-%m-%d')
                blobs = list(client.list_blobs(bucket_name, prefix=prefix, max_results=17))
                if len(blobs) > 16:
                    raise RuntimeError('maintenance receipt bound exceeded')
                for blob in sorted(blobs, key=lambda item: item.name, reverse=True):
                    if blob.size is None or blob.size > 1_048_576:
                        continue
                    document = json.loads(blob.download_as_bytes())
                    if document.get('mode') == 'apply':
                        receipt = document
                        observed_at = blob.updated.isoformat() if blob.updated else None
                        break
                if receipt is not None:
                    break
            if receipt is None:
                continue
            storage_data = receipt.get('storage', {})
            for layer in (('core', 'stage') if component == 'core' else ('mart',)):
                layer_data = storage_data if layer == 'mart' else storage_data.get(layer, {})
                after = layer_data.get('after', {})
                result[layer.title()] = {'maintenance_at': observed_at,
                    'live_objects': after.get('objects'), 'active_bytes': after.get('bytes')}
        except Exception:
            # Missing access/receipts do not imply empty storage or a successful cleanup.
            continue
    return result


def build_admin_service():
    from packages.admin_api import AdminService
    from packages.postgres_bundle import load_postgres_bundle

    load_postgres_bundle("JANUS_API_POSTGRES_BUNDLE", {
        "CONTROL_DB_PASSWORD": ("web_control_password", "control_password"),
    })
    settings = {
        "CONTROL_DB_HOST": os.environ.get("CONTROL_DB_HOST", "").strip() or os.environ.get("POSTGRES_HOST", "").strip(),
        "CONTROL_DB_NAME": os.environ.get("CONTROL_DB_NAME", "").strip() or os.environ.get("POSTGRES_DB", "").strip(),
        "CONTROL_DB_USER": os.environ.get("CONTROL_DB_USER", "").strip() or "janus_web_control",
        "CONTROL_DB_PASSWORD": os.environ.get("CONTROL_DB_PASSWORD", "").strip(),
    }
    missing = [name for name, value in settings.items() if not value]
    if missing:
        raise ValueError(f"missing admin runtime settings:{','.join(missing)}")

    import psycopg
    from ingestion_core.postgres_control import PostgreSQLControlPlane

    def connect():
        return psycopg.connect(
            host=settings["CONTROL_DB_HOST"], dbname=settings["CONTROL_DB_NAME"],
            user=settings["CONTROL_DB_USER"], password=settings["CONTROL_DB_PASSWORD"],
            sslmode=os.environ.get("CONTROL_DB_SSLMODE", "require"), connect_timeout=5,
        )

    def wake_batch_controller():
        import google.auth
        from google.auth.transport.requests import AuthorizedSession
        credentials, _ = google.auth.default(scopes=("https://www.googleapis.com/auth/cloud-platform",))
        response = AuthorizedSession(credentials).post(
            "https://run.googleapis.com/v2/projects/gen-lang-client-0593591102/locations/us-central1/jobs/janus-batch-controller:run",
            json={}, timeout=10)
        if not 200 <= response.status_code < 300:
            raise RuntimeError("batch controller wakeup unavailable")

    return AdminService(PostgreSQLControlPlane(connect), core=build_core_service(),
                        batch_wake=wake_batch_controller,
                        maintenance_reader=lambda: _maintenance_evidence(int(datetime.now(timezone.utc).timestamp()) // 60))
