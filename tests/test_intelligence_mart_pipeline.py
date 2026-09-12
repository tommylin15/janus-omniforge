import io
import json
import os
import shutil
import sys
import unittest
from uuid import uuid4
from datetime import date, timedelta
from pathlib import Path
from urllib.error import HTTPError
from unittest.mock import patch


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "jobs" / "intelligence-mart"))

from intelligence_mart.analysis import analyze, prompt_bundle
from intelligence_mart.gemini import GeminiNarrator, _select_stable_models
from intelligence_mart.storage import MART_TABLES, MartIcebergStore


AS_OF = date(2026, 9, 10)


def row(dataset, position=0, **values):
    observed = AS_OF.isoformat() + "T00:00:00Z"
    return {"source_id": "mops" if dataset in {"financials", "events"} else "twse",
            "provenance_id": f"prov-{dataset}-{position}", "observed_at": observed, **values}


def datasets():
    start = AS_OF - timedelta(days=20)
    ohlcv = [row("ohlcv", offset, symbol="2330", trade_date=(start + timedelta(days=offset)).isoformat(),
                  close=100 + offset, high=101 + offset, low=99 + offset,
                  volume_shares=1_000_000 + offset, turnover_twd=100_000_000 + offset)
             for offset in range(21)]
    benchmark = [row("benchmark", offset, benchmark_id="TAIEX", trade_date=(start + timedelta(days=offset)).isoformat(), close=20_000 + offset)
                 for offset in range(21)]
    institutional = [row("institutional", offset, symbol="2330", trade_date=(start + timedelta(days=offset)).isoformat(),
                         investor_type="foreign", net_shares=10_000) for offset in range(21)]
    financials = [row("financials", 1, symbol="2330", fiscal_year=2025, fiscal_quarter=4,
                      published_at="2026-03-10", metric="revenue", value="100", unit="TWD_thousands"),
                  row("financials", 2, symbol="2330", fiscal_year=2026, fiscal_quarter=2,
                      published_at="2026-08-10", metric="revenue", value="120", unit="TWD_thousands")]
    valuation = [row("valuation", 1, symbol="2330", observed_date=AS_OF.isoformat(), pe_ratio="15", pb_ratio="2",
                     dividend_yield_percent="2.5")]
    return {"ohlcv": ohlcv, "benchmark": benchmark, "institutional": institutional,
            "financials": financials, "valuation": valuation, "events": []}


def report(source=None, execution_id="11111111-1111-1111-1111-111111111111", **option_overrides):
    prompts, digest = prompt_bundle()
    options = {"schema_version": "1", "feature_version": "1", "model_version": "deterministic-v1",
               "governance_snapshot_version": "gov-1", **option_overrides}
    return analyze(execution_id=execution_id, analysis_as_of=AS_OF.isoformat(),
                   core_snapshot_id="core-1", requested_symbols=("2330",), options=options,
                   datasets=source or datasets(), prompts=prompts, prompt_hash=digest)[0]


class MartPipelineTests(unittest.TestCase):
    def test_five_roles_are_deterministic_and_publishable(self):
        first, second = report(), report()
        self.assertEqual(first, second)
        self.assertEqual([role["role"] for role in first["roles"]],
                         ["fundamental", "valuation", "positioning", "quant", "event_risk"])
        self.assertEqual(first["aggregate"]["analysis_outcome"], "complete")
        self.assertEqual(first["aggregate"]["publication_status"], "publishable")
        self.assertEqual(first["features"]["quant"]["return_20d"], 20.0)

    def test_rebuild_hash_excludes_execution_identity(self):
        self.assertEqual(report()["deterministic_hash"], report(execution_id="22222222-2222-2222-2222-222222222222")["deterministic_hash"])

    def test_insufficient_data_is_an_outcome_not_a_publication_status(self):
        sparse = {"ohlcv": datasets()["ohlcv"]}
        result = report(sparse)
        self.assertEqual(result["aggregate"]["analysis_outcome"], "insufficient_data")
        self.assertEqual(result["aggregate"]["publication_status"], "blocked")

    def test_high_event_risk_blocks_publication(self):
        source = datasets()
        source["events"] = [row("events", 1, symbol="2330", event_type="material_information",
                                published_at="2026-09-10T01:00:00Z", severity="high")]
        result = report(source)
        self.assertEqual(result["aggregate"]["analysis_outcome"], "risk_blocked")
        self.assertIn("high_event_risk", result["aggregate"]["reason"])

    def test_future_evidence_never_reaches_features_or_roles(self):
        source = datasets()
        source["events"] = [row("events", 1, symbol="2330", event_type="future",
                                published_at="2026-09-11T01:00:00Z", severity=100)]
        result = report(source)
        self.assertFalse(any(item["metric"] == "future" for item in result["evidence"]))
        self.assertIn("future_leakage", {item["reason"] for item in result["rejected_evidence"]})
        self.assertEqual(result["aggregate"]["analysis_outcome"], "invalid")

    def test_manual_review_is_a_separate_blocked_outcome(self):
        result = report(manual_review_required=True)
        self.assertEqual(result["aggregate"]["analysis_outcome"], "review_required")
        self.assertEqual(result["aggregate"]["publication_status"], "blocked")

    def test_daily_brief_rejects_mixed_as_of_or_unpublished_inputs(self):
        with self.assertRaisesRegex(ValueError, "daily brief"):
            report(scopes=[{"type": "market", "id": "TW"}], published_components=[
                {"analysis_as_of": "2026-09-09", "publication_status": "published", "artifact_uri": "gs://mart/old"}
            ])

    def test_prompt_fence_is_immutable(self):
        with self.assertRaisesRegex(ValueError, "prompt fence"):
            report(prompt_hash="sha256:" + "0" * 64)

    def test_industry_scope_keeps_immutable_membership(self):
        result = report(scopes=[{"type": "industry", "id": "semiconductor", "symbols": ["2330"]}])
        self.assertEqual(result["scope"]["type"], "industry")
        self.assertEqual(result["membership_snapshot"], ["2330"])
        self.assertRegex(result["membership_snapshot_hash"], r"^sha256:[0-9a-f]{64}$")

    def test_public_iceberg_tables_are_v2_partitioned_and_idempotent(self):
        from pyiceberg.catalog import load_catalog
        root = Path(".tmp") / f"mart-unit-{uuid4()}"
        root.mkdir(parents=True)
        warehouse = (root / "warehouse").as_posix()
        catalog = load_catalog("mart-test", type="sql", uri="sqlite:///" + (root / "catalog.db").as_posix(),
                               warehouse=warehouse)
        store = MartIcebergStore(catalog, warehouse)
        try:
                store.ensure_tables()
                self.assertTrue(all(catalog.table_exists(f"mart.{name}_v1") for name in MART_TABLES))
                first = store.write([report()])[("symbol", "2330")]
                second = store.write([report()])[("symbol", "2330")]
                self.assertEqual(first["iceberg_snapshot_id"], second["iceberg_snapshot_id"])
                table = catalog.load_table("mart.mart_scoped_analysis_v1")
                self.assertEqual(table.metadata.format_version, 2)
                self.assertIn("payload_json", {field.name for field in table.schema().fields})
                self.assertEqual(len(table.scan().to_arrow()), 1)
        finally:
            store.close()
            catalog.engine.dispose()
            shutil.rmtree(root)


class _Response:
    def __init__(self, payload): self.payload = payload
    def __enter__(self): return io.BytesIO(json.dumps(self.payload).encode())
    def __exit__(self, *_): pass


class GeminiNarratorTests(unittest.TestCase):
    def test_stable_model_selection_is_ordered_and_bounded(self):
        selected = _select_stable_models({"models": [
            {"name": "models/gemini-3.5-flash", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/gemini-3.8-flash", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/gemini-3.7-flash", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/gemini-3.6-flash", "supportedGenerationMethods": ["generateContent"]},
        ]})
        self.assertEqual(selected, ("gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.6-flash"))

    def test_paid_gemini_requires_explicit_billing_approval(self):
        with patch.dict(os.environ, {"GEMINI_PAID_ENABLED":"true","GEMINI_BILLING_APPROVED":"false"}, clear=True), self.assertRaisesRegex(ValueError, "billing gate"):
            GeminiNarrator("secret")
        with patch.dict(os.environ, {"GEMINI_PAID_ENABLED":"true","GEMINI_BILLING_APPROVED":"true"}, clear=True):
            self.assertEqual(GeminiNarrator("secret").model, "gemini-2.5-flash")

    def test_dev_acceptance_faults_are_structured_and_have_no_placeholder(self):
        for fault in ("quota", "provider_unavailable", "invalid_structured_output"):
            with self.subTest(fault=fault), patch.dict(os.environ, {"ENVIRONMENT":"dev","MART_ACCEPTANCE_FAULT":fault}, clear=True):
                result = GeminiNarrator("secret", attempts=2, sleeper=lambda _: None).narrate(report(), prompt_bundle()[0])
                self.assertEqual((result["status"], result["error"]["kind"]), ("failed", fault))
                self.assertNotIn("narrative", result)

    def test_429_is_bounded_then_structured_output_succeeds(self):
        calls = []
        narrative = {"summary": "evidence only", "bull_case": [], "bear_case": [], "risks": [], "evidence_ids": []}
        def opener(request, timeout):
            calls.append((request, timeout))
            if len(calls) == 1:
                raise HTTPError(request.full_url, 429, "quota secret", {}, None)
            return _Response({"candidates": [{"content": {"parts": [{"text": json.dumps(narrative)}]}}]})
        deterministic = report()
        before = json.loads(json.dumps(deterministic))
        result = GeminiNarrator("secret", opener=opener, sleeper=lambda _: None).narrate(deterministic, prompt_bundle()[0])
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(len(calls), 2)
        self.assertEqual(deterministic, before)

    def test_ungrounded_number_is_a_structured_failure_without_placeholder(self):
        narrative = {"summary": "target 999999", "bull_case": [], "bear_case": [], "risks": [], "evidence_ids": []}
        narrator = GeminiNarrator("secret", opener=lambda *_args, **_kwargs: _Response(
            {"candidates": [{"content": {"parts": [{"text": json.dumps(narrative)}]}}]}))
        result = narrator.narrate(report(), prompt_bundle()[0])
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error"]["kind"], "invalid_structured_output")
        self.assertNotIn("narrative", result)

    def test_rest_schema_uses_current_response_format(self):
        captured = {}
        narrative = {"summary": "evidence only", "bull_case": [], "bear_case": [], "risks": [], "evidence_ids": []}
        def opener(request, timeout):
            captured.update(json.loads(request.data))
            return _Response({"candidates": [{"content": {"parts": [{"text": json.dumps(narrative)}]}}]})
        result = GeminiNarrator("secret", opener=opener).narrate(report(), prompt_bundle()[0])
        self.assertEqual(result["status"], "succeeded")
        schema = captured["generationConfig"]["responseFormat"]["text"]["schema"]
        self.assertEqual(captured["generationConfig"]["responseFormat"]["text"]["mimeType"], "APPLICATION_JSON")
        self.assertEqual((schema["type"], schema["properties"]["bull_case"]["type"], schema["properties"]["bull_case"]["items"]["type"]),
                         ("object", "array", "string"))

    def test_http_error_keeps_only_bounded_redacted_diagnostics(self):
        payload = {"error": {"status": "INVALID_ARGUMENT", "message": "api_key=top-secret invalid schema",
                             "details": [{"reason": "API_KEY_INVALID", "metadata": {"secret": "hidden"}}]}}
        def opener(request, timeout):
            raise HTTPError(request.full_url, 400, "bad request", {}, io.BytesIO(json.dumps(payload).encode()))
        result = GeminiNarrator("secret", opener=opener).narrate(report(), prompt_bundle()[0])
        self.assertEqual(result["error"]["provider_status"], "INVALID_ARGUMENT")
        self.assertEqual(result["error"]["provider_reason"], "API_KEY_INVALID")
        self.assertIn("<redacted>", result["error"]["message"])
        self.assertNotIn("top-secret", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
