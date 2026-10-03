"""Read-only pinned dev Core inventory; no model or publication calls."""
import json
import os
from collections import Counter
from datetime import date
from hashlib import sha256
from urllib.parse import urlparse

from ingestion_core.stage import GcsObjectStore
from intelligence_mart.analysis import _research_rows, _features, _evidence_id, evidence_from_rows, validate_evidence
from intelligence_mart.ai_targets import load_target_rows
from intelligence_mart.storage import load_core_datasets, sql_catalog_from_environment
from packages.postgres_bundle import load_postgres_bundle


def main():
    load_postgres_bundle("JANUS_MART_POSTGRES_BUNDLE", {
        "CATALOG_DB_PASSWORD": ("mart_catalog_password", "catalog_password"),
        "PUBLICATION_DB_PASSWORD": ("mart_publication_password", "publication_password"),
    })
    source = GcsObjectStore("gen-lang-client-0593591102-dev-mart").read(
        "acceptance/ai-providers/inputs/71db43bc-7fd3-46dd-a740-ab58a4fd81ba.json")
    assert sha256(source).hexdigest() == "9e054d960a3f69242cc212684d081cd6109942d7a8696b638dfa52d6b68b3b73"
    request = json.loads(source)
    uri = urlparse(request["core_snapshot_uri"])
    payload = GcsObjectStore(uri.netloc).read(uri.path.lstrip("/"))
    assert "sha256:" + sha256(payload).hexdigest() == request["core_snapshot_hash"]
    manifest = json.loads(payload)
    assert manifest["snapshot_id"] == request["core_snapshot_id"]
    catalog = sql_catalog_from_environment()
    import psycopg
    settings = {name.lower(): os.environ[f"PUBLICATION_DB_{name}"] for name in ("HOST", "NAME", "USER", "PASSWORD")}
    with psycopg.connect(host=settings["host"], dbname=settings["name"], user=settings["user"], password=settings["password"],
                         sslmode=os.environ.get("PUBLICATION_DB_SSLMODE", "require"), connect_timeout=5,
                         options="-c default_transaction_read_only=on -c statement_timeout=15000") as connection:
        active_symbols = sorted({r["symbol"] for r in load_target_rows(connection, request["analysis_as_of"])})
    symbols = sorted(set(request["requested_symbols"]) | set(active_symbols))
    datasets = load_core_datasets(catalog, manifest, tuple(symbols))
    result = {"analysis_as_of": request["analysis_as_of"], "core_snapshot_id": manifest["snapshot_id"],
              "core_execution_id": manifest["execution_id"], "provider_calls": 0, "publication_writes": 0,
              "active_target_symbols": active_symbols, "symbols": {}}
    for symbol in symbols:
        scoped = {name: [row for row in rows if not row.get("symbol") or row["symbol"] == symbol]
                  for name, rows in datasets.items()}
        selected = _research_rows(scoped, date.fromisoformat(request["analysis_as_of"]))
        valid, rejected, blockers = validate_evidence(evidence_from_rows(selected, manifest["snapshot_id"]),
                                                     date.fromisoformat(request["analysis_as_of"]))
        valid_ids = {item["evidence_id"] for item in valid}
        validated = {name: [r for r in rows if _evidence_id(name, r, manifest["snapshot_id"]) in valid_ids]
                     for name, rows in selected.items()}
        summary = {}
        for name, rows in scoped.items():
            evidence = [item for item in valid if item["dataset_id"] == name]
            summary[name] = {
                "raw_rows": len(rows), "qualified_rows": len(evidence),
                "periods": sorted({str(row.get("fiscal_year")) + "Q" + str(row.get("fiscal_quarter"))
                                   for row in rows if row.get("fiscal_year")}),
                "statements": dict(Counter(str(row.get("statement_type")) for row in rows)),
                "metrics": sorted({str(row.get("metric")) for row in rows if row.get("metric")}),
                "qualified_dates": sorted({item["record_at"] for item in evidence if item["record_at"]}),
                "source_ids": sorted({str(row.get("source_id")) for row in rows}),
                "missing_published_at": sum(item["published_at"] is None for item in evidence),
                "missing_availability_at": sum(item["availability_at"] is None for item in evidence),
            }
        result["symbols"][symbol] = {"datasets": summary,
                                      "qualified_features": _features(validated),
                                      "rejected": dict(Counter(item["reason"] for item in rejected)),
                                      "blockers": blockers}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
