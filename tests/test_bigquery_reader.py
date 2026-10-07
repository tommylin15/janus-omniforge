import io
import json
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "jobs/intelligence-mart"))
from intelligence_mart.bigquery_reader import BigQueryAnalyticsReader

URI = "gs://core/warehouse/metadata/00001-12345678-1234-1234-1234-123456789abc.metadata.json"


def setup_reader(*, estimate=100, rows=None, changed=False):
    from google.cloud.bigquery import SchemaField
    fields = [SchemaField("symbol", "STRING"), SchemaField("amount", "NUMERIC"),
              SchemaField("trade_date", "DATE"), SchemaField("observed_at", "TIMESTAMP"),
              SchemaField("source_id", "STRING"), SchemaField("provenance_id", "STRING")]
    metadata = {"format-version": 2, "current-snapshot-id": 42, "current-schema-id": 1,
                "schemas": [{"schema-id": 1, "fields": [{"name": f.name} for f in fields]}]}
    external = SimpleNamespace(location="us-central1", etag="v1", schema=fields,
        external_data_configuration=SimpleNamespace(source_format="ICEBERG", source_uris=[URI]))
    calls = []
    payload = rows if rows is not None else [{"symbol": "2330", "amount": Decimal("1.2300"),
        "trade_date": date(2026, 10, 6), "observed_at": datetime(2026, 10, 6, tzinfo=timezone.utc),
        "source_id": "twse", "provenance_id": None}]
    class Client:
        def get_table(self, table_id):
            assert table_id == "dev.analytics.ohlcv"
            if changed and any(not c.dry_run for c in calls):
                return SimpleNamespace(etag="v2")
            return external
        def query(self, sql, *, job_config, location, timeout):
            assert "SELECT *" not in sql and "IN UNNEST(@symbols)" in sql
            assert location == "us-central1" and timeout == 60
            calls.append(job_config)
            if not job_config.dry_run:
                assert 0 < job_config.maximum_bytes_billed <= 1000
            return SimpleNamespace(total_bytes_processed=estimate, total_bytes_billed=100,
                                   result=lambda **kw: payload, cancel=lambda: None)
        def close(self):
            pass
    catalog = SimpleNamespace(load_table=lambda _: SimpleNamespace(io=SimpleNamespace(
        new_input=lambda _: SimpleNamespace(open=lambda: io.BytesIO(json.dumps(metadata).encode())))))
    manifest = {"snapshot_id": "core-fixed", "iceberg_tables": {
        "core.ohlcv_v1": {"snapshot_id": 42, "metadata_location": URI}}}
    reader = BigQueryAnalyticsReader(Client(), catalog, {"core.ohlcv_v1": "dev.analytics.ohlcv"},
                                    location="us-central1", maximum_bytes_billed=1000,
                                    date_bounds={"core.ohlcv_v1": ("trade_date", "2026-10-01", "2026-10-06")})
    return reader, manifest, metadata, external, calls


def test_probe_defaults_to_dry_run_and_preserves_native_values_on_explicit_read():
    reader, manifest, _, _, calls = setup_reader()
    dry = reader.probe(manifest, ("2330",), core_snapshot_id="core-fixed")
    assert dry.datasets == {} and dry.telemetry["total_rows"] is None
    assert len(calls) == 1 and calls[0].dry_run
    result = reader.read(manifest, ("2330",), core_snapshot_id="core-fixed")
    row = result.datasets["ohlcv"][0]
    assert row["amount"] == Decimal("1.2300") and isinstance(row["amount"], Decimal)
    assert row["trade_date"] == date(2026, 10, 6)
    assert row["observed_at"].tzinfo == timezone.utc
    assert row["provenance_id"] is None and row["source_id"] == "twse"
    assert row["__snapshot_id"] == 42
    assert result.telemetry["scan_evidence"]["ohlcv"]["billed_bytes"] == 100


def test_shared_catalog_mapping_is_verified_before_and_after_every_read():
    reader, manifest, _, _, calls = setup_reader()
    reader.table_ids = {"core.ohlcv_v1": "dev.catalog.fixed.ohlcv"}
    checked = []
    reader.shared_metadata_loader = lambda table: checked.append(table) or URI
    result = reader.read(manifest, ("2330",), core_snapshot_id="core-fixed")
    assert len(checked) == 3 and not result.telemetry["transition_only"]
    reader.shared_metadata_loader = lambda _: "gs://drift"
    count = len(calls)
    with pytest.raises(ValueError, match="mapping mismatch"):
        reader.read(manifest, ("2330",), core_snapshot_id="core-fixed")
    assert len(calls) == count


def test_column_selection_cannot_remove_filter_columns():
    reader, manifest, _, _, calls = setup_reader()
    reader.selected_fields = {"core.ohlcv_v1": ("amount",)}
    with pytest.raises(ValueError, match="preserve date and symbol"):
        reader.read(manifest, ("2330",), core_snapshot_id="core-fixed")
    assert not calls


@pytest.mark.parametrize("failure", ["identity", "snapshot", "uri", "region", "schema", "mapping", "bounds", "private"])
def test_invalid_fences_never_submit_jobs(failure):
    reader, manifest, metadata, external, calls = setup_reader()
    if failure == "identity": manifest["snapshot_id"] = "other"
    if failure == "snapshot": metadata["current-snapshot-id"] = 43
    if failure == "uri": manifest["iceberg_tables"]["core.ohlcv_v1"]["metadata_location"] = "gs://core/latest.json"
    if failure == "region": external.location = "EU"
    if failure == "schema": external.schema = external.schema[:-1]
    if failure == "mapping": external.external_data_configuration.source_uris = ["gs://other/latest.json"]
    if failure == "bounds": reader.date_bounds = {}
    if failure == "private":
        manifest["iceberg_tables"]["private.ohlcv_v1"] = manifest["iceberg_tables"].pop("core.ohlcv_v1")
        reader.table_ids = {"private.ohlcv_v1": "dev.analytics.ohlcv"}
    with pytest.raises(ValueError): reader.read(manifest, ("2330",), core_snapshot_id="core-fixed")
    assert not calls


@pytest.mark.parametrize("estimate", [1001])
def test_unknown_or_over_budget_scan_never_submits_live_query(estimate):
    reader, manifest, _, _, calls = setup_reader(estimate=estimate)
    with pytest.raises(ValueError): reader.read(manifest, ("2330",), core_snapshot_id="core-fixed")
    assert len(calls) == 1 and calls[0].dry_run


def test_zero_lower_bound_dry_run_reports_unknown_cost():
    reader, manifest, _, _, calls = setup_reader(estimate=0)
    result = reader.probe(manifest, ("2330",), core_snapshot_id="core-fixed")
    evidence = result.telemetry["scan_evidence"]["ohlcv"]
    assert evidence["estimated_bytes"] is None
    assert evidence["dry_run_lower_bound_bytes"] == 0
    assert len(calls) == 1 and calls[0].dry_run


def test_unknown_estimate_keeps_execution_byte_budget():
    reader, manifest, _, _, calls = setup_reader(estimate=0)
    result = reader.probe(manifest, ("2330",), core_snapshot_id="core-fixed", dry_run=False,
                          )
    evidence = result.telemetry["scan_evidence"]["ohlcv"]
    assert evidence["estimated_bytes"] is None and evidence["billed_bytes"] == 100
    assert calls[-1].maximum_bytes_billed == 1000
    assert result.telemetry["unknown_estimate_policy"] == 'bounded-execution'


@pytest.mark.parametrize('budget,timeout', [(1_073_741_825, 60), (1000, 61), (0, 60)])
def test_automatic_policy_rejects_budget_or_timeout_above_ceiling(budget, timeout):
    with pytest.raises(ValueError):
        BigQueryAnalyticsReader(None, None, {}, location='us-central1',
                                maximum_bytes_billed=budget, timeout=timeout, date_bounds={})


def test_default_execution_budget_is_one_gib():
    reader = BigQueryAnalyticsReader(None, None, {}, location='us-central1', date_bounds={})
    assert reader.maximum_bytes_billed == 1_073_741_824


def test_overflow_and_mapping_race_reject_output():
    for options in ({"rows": [{}, {}]}, {"changed": True}):
        reader, manifest, _, _, _ = setup_reader(**options)
        with pytest.raises(ValueError):
            reader.read(manifest, ("2330",), core_snapshot_id="core-fixed", row_limit=1)


def test_timeout_cancels_job_and_never_returns_partial_snapshot():
    reader, manifest, _, _, calls = setup_reader()
    query = reader.client.query
    cancelled = []
    def timeout_query(*args, **kwargs):
        job = query(*args, **kwargs)
        if not kwargs["job_config"].dry_run:
            def fail(**kw):
                raise TimeoutError("bounded timeout")
            job.result = fail
            job.cancel = lambda: cancelled.append(True)
        return job
    reader.client.query = timeout_query
    with pytest.raises(TimeoutError):
        reader.read(manifest, ("2330",), core_snapshot_id="core-fixed")
    assert cancelled == [True] and len(calls) == 2


def test_probe_subset_keeps_original_manifest_identity_but_read_requires_full_mapping():
    reader, manifest, _, _, _ = setup_reader()
    manifest["iceberg_tables"]["core.events_v1"] = {"snapshot_id": 99}
    result = reader.probe(manifest, ("2330",), core_snapshot_id="core-fixed",
                          table_scope=("core.ohlcv_v1",))
    assert result.core_snapshot_id == "core-fixed"
    assert result.telemetry["table_scope"] == ["core.ohlcv_v1"]
    with pytest.raises(ValueError, match="mapping"):
        reader.read(manifest, ("2330",), core_snapshot_id="core-fixed")


def test_all_dry_runs_precede_queries_and_each_query_uses_remaining_execution_budget():
    reader, manifest, _, _, calls = setup_reader(estimate=0)
    manifest['iceberg_tables']['core.benchmark_v1'] = dict(manifest['iceberg_tables']['core.ohlcv_v1'])
    reader.table_ids['core.benchmark_v1'] = 'dev.analytics.ohlcv'
    reader.date_bounds['core.benchmark_v1'] = reader.date_bounds['core.ohlcv_v1']
    result = reader.read(manifest, ('2330',), core_snapshot_id='core-fixed')
    assert [c.dry_run for c in calls] == [True, True, None, None]
    assert [c.maximum_bytes_billed for c in calls[2:]] == [1000, 900]
    assert result.telemetry['execution_byte_budget'] == 1000
