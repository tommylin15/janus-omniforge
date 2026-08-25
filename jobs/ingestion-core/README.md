# Ingestion Core job

Implemented foundations:

- immutable JSON/CSV Stage payloads with provenance sidecars;
- deterministic content hashes and idempotent create-if-absent writes;
- execution manifests and quarantine payloads;
- Cloud Run GCS writes using metadata-server short-lived credentials;
- deterministic OHLCV Core DQ and null-preserving incremental merge;
- Iceberg v2 schema and bounded month/symbol-bucket partitioning.

The Stage writer accepts only controlled source/dataset identifiers and safe
path segments. Extreme moves over 11% are retained with a review warning; they
are not silently deleted. Zero handling is field-semantic rather than global.
