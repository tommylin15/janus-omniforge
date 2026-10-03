"""Dev Mart retention; historical manifest references remain readable."""
from datetime import datetime, timedelta, timezone
import json
import os
from hashlib import sha256

from .storage import MartMaintenanceStore, sql_catalog_from_environment
from .runtime import _settings
from ingestion_core.stage import GcsObjectStore
from ingestion_core.iceberg_maintenance import maintain_financials
from ingestion_core.retention import clean_orphans
from packages.postgres_bundle import load_postgres_bundle


def run():
    mode = os.environ.get("MART_RETENTION_MODE", "dry-run")
    bucket = os.environ.get("MART_BUCKET")
    if mode not in {"dry-run", "apply"} or bucket != "gen-lang-client-0593591102-dev-mart":
        raise ValueError("Mart retention is restricted to the existing dev bucket")
    load_postgres_bundle("JANUS_MART_POSTGRES_BUNDLE", {
        "CATALOG_DB_PASSWORD": ("mart_catalog_password", "catalog_password"),
        "PUBLICATION_DB_PASSWORD": ("mart_publication_password", "publication_password"),
    })
    import psycopg
    settings = _settings("PUBLICATION_DB")
    settings["dbname"] = settings.pop("name")
    apply = mode == "apply"
    now = datetime.now(timezone.utc)
    catalog = sql_catalog_from_environment()
    mart = MartMaintenanceStore(catalog, f"gs://{bucket}/warehouse")
    store = GcsObjectStore(bucket)
    def capacity():
        objects = store.objects("")
        return {"objects": len(objects), "bytes": sum(int(item["size"]) for item in objects)}
    tables, orphans = [], []
    try:
        with psycopg.connect(**settings, sslmode=os.environ.get("PUBLICATION_DB_SSLMODE", "require"), connect_timeout=5, autocommit=True) as connection:
            if not connection.execute("SELECT pg_try_advisory_lock(1835102836,2)").fetchone()[0]:
                raise RuntimeError("public data mutation lock is busy")
            try:
                before = capacity()
                from .artifact_retention import clean_specialist_artifacts
                specialist_artifacts = clean_specialist_artifacts(store, apply=apply, now=now)
                references = connection.execute("SELECT table_identifier,iceberg_snapshot_id,artifact_uri FROM publication.mart_report_index LIMIT 100001").fetchall()
                if len(references) > 100000:
                    raise RuntimeError("Mart retention reference limit exceeded")
                for dataset in mart.IDENTIFIERS:
                    identifier = mart.table_identifier(dataset)
                    if not catalog.table_exists(identifier):
                        continue
                    table = catalog.load_table(identifier)
                    from pyiceberg.expressions import LessThan
                    expired = LessThan("analysis_date", (now - timedelta(days=90)).date())
                    removed = table.scan(row_filter=expired).to_arrow().num_rows
                    if apply and removed:
                        table.delete(expired, snapshot_properties={"janus.retention-policy": "public-data-retention-v1"})
                        if catalog.load_table(identifier).scan(row_filter=expired).to_arrow().num_rows:
                            raise RuntimeError("Mart retention readback mismatch")
                    protected_ids = {int(snapshot) for name, snapshot, _ in references if name == identifier}
                    protected_metadata = {uri for name, _, uri in references if name == identifier}
                    result = maintain_financials(core=mart, store=store, apply=apply, now=now, identifier=identifier,
                                                protected_snapshot_ids=protected_ids, protected_metadata=protected_metadata)
                    tables.append({**result, "planned_rows_removed": removed, "rows_removed": removed if apply else 0})
                    orphans.append(clean_orphans(mart, store, identifier, apply=apply, now=now))
                after = capacity() if apply else before
            finally:
                connection.execute("SELECT pg_advisory_unlock(1835102836,2)")
        result = {"component": "mart-retention", "mode": mode, "policy_version": "public-data-retention-v1",
                  "retention_days": 90, "tables": tables, "orphans": orphans,
                  "specialist_artifacts": specialist_artifacts,
                  "storage": {"before": before, "after": after, "active_bytes_reduced": before["bytes"] - after["bytes"]},
                  "storage_scope": "live_objects_only", "billable_bytes_reclaimed": None,
                  "historical_manifests": "protected", "model_calls": 0, "publication_writes": 0}
        payload = json.dumps(result, sort_keys=True).encode()
        name = "maintenance/retention/" + now.strftime("%Y-%m-%dT%H%M%SZ") + "-" + sha256(payload).hexdigest() + ".json"
        if not store.create(name, payload, "application/json") and store.read(name) != payload:
            raise RuntimeError("Mart retention report conflict")
        if store.read(name) != payload:
            raise RuntimeError("Mart retention report readback mismatch")
        return {**result, "artifact_uri": f"gs://{bucket}/{name}"}
    finally:
        mart.close()
