"""Rebuild S0 inventory from pinned runtime evidence; never infer canonical facts."""
import json
from pathlib import Path


def build_matrix(runtime):
    symbols = runtime["symbols"]
    if not set(runtime["active_target_symbols"]).issubset(symbols):
        raise ValueError("active targets are missing from runtime inventory")
    rows, times = [], []
    for symbol, result in sorted(symbols.items()):
        datasets, features = result["datasets"], result["qualified_features"]
        financial = datasets.get("financials", {})
        periods = {day[:7] for day in financial.get("qualified_dates", [])}
        prices = datasets.get("ohlcv", {}).get("qualified_dates", [])
        requirements = [
            ("fundamental", "financial_history_12q", ("financials",), "12 qualified quarters", "provenance_time_gap", "source_publication_revision_evidence", "Raw fiscal periods do not establish PIT-qualified numeric versions."),
            ("fundamental", "monthly_revenue_history_12m", ("financials",), "12 qualified monthly observations", "source_gap", "approved_monthly_revenue_adapter", "Monthly revenue is not present in this pinned Core snapshot."),
            ("fundamental", "revenue_trend_percent", ("financials",), "12 quarters with comparable metric/scope/period basis", "semantic_gap", "normalization_and_feature", "Current trend concatenates metric aliases rather than one comparable series."),
            ("fundamental", "eps_trend_percent", ("financials",), "12 quarters with EPS/share basis and revision identity", "semantic_gap", "normalization_and_feature", "Cumulative EPS cannot be subtracted to recover single-quarter EPS; share basis requires evidence."),
            ("fundamental", "balance_sheet", ("financials",), "12 quarterly balance snapshots", "metric_mapping_gap", "approved_statement_adapter", "Current Core does not identify balance-sheet observations as a distinct statement family."),
            ("fundamental", "cash_flow", ("financials",), "12 quarters with cumulative/single-quarter basis", "metric_mapping_gap", "approved_statement_adapter", "Current Core does not identify cash-flow observations as a distinct statement family."),
            ("fundamental", "industry_applicability", ("stock-profile", "financials"), "effective industry membership and statement scope", "metric_mapping_gap", "profile_normalization", "Financial fields need industry applicability; an empty value alone is not not_applicable evidence."),
            ("valuation", "roe", ("financials",), "profit period and matching average equity basis", "metric_mapping_gap", "normalization_and_derived_metric", "Qualified ROE input or an approved derivation is absent."),
            ("valuation", "debt_to_equity", ("financials",), "same-date liabilities and equity with scope/unit match", "semantic_gap", "normalization_and_derived_metric", "Debt-to-assets (負債比率) is not debt-to-equity."),
            ("valuation", "peer_benchmark", ("valuation", "stock-profile"), "same-as-of industry peers and versioned comparison contract", "source_gap", "bounded_industry_comparison", "Single-stock PE/PB/yield values do not establish a peer benchmark."),
            ("valuation", "valuation_time_identity", ("valuation",), "dated PE/PB/yield evidence", "unknown", "time_contract_audit", "Market observations have record time; publication absence alone is not a PIT defect. Mapping remains to be audited."),
            ("positioning", "investor_class_breakdown", ("institutional",), "5/20/60 trading days by investor class", "metric_mapping_gap", "feature", "Current features aggregate investor classes; the required breakdown is not exposed."),
            ("positioning", "volume_denominator", ("institutional", "ohlcv"), "date-joined 5/20/60-day numerator and denominator", "semantic_gap", "feature_date_join", "Current numerator and denominator use independent series tails, without a date join."),
            ("positioning", "independent_crosscheck", ("institutional",), "bounded independent-source comparison", "unknown", "source_crosscheck", "No independent positioning cross-check is recorded in this runtime evidence."),
            ("quant", "return_60d", ("ohlcv",), "61 valid trading-day closes", "history_depth_gap", "snapshot_read_window_or_backfill", "The pinned qualified price window is shorter than 61 observations."),
            ("quant", "return_120d", ("ohlcv",), "121 valid trading-day closes", "history_depth_gap", "snapshot_read_window_or_backfill", "The pinned qualified price window is shorter than 121 observations."),
            ("quant", "benchmark_alignment", ("ohlcv", "benchmark"), "date-joined price/benchmark returns", "semantic_gap", "feature_date_join", "Current beta pairs series tails by count rather than matching return date intervals."),
            ("event_risk", "max_severity", ("events",), "versioned taxonomy for qualified events", "semantic_gap", "deterministic_event_taxonomy", "A null severity cannot turn existing events into no-event/zero-risk evidence."),
            ("event_risk", "event_publication", ("events",), "authoritative publication/effective time", "unknown", "source_time_contract", "Qualified events have publication timestamps, but source authority needs separate verification; zero rows do not prove no events."),
        ]
        for role, feature, names, required, gap, layer, reason in requirements:
            dates = sorted({day for name in names for day in datasets.get(name, {}).get("qualified_dates", [])})
            source_ids = sorted({source for name in names for source in datasets.get(name, {}).get("source_ids", [])})
            available = {name: {key: datasets.get(name, {}).get(key) for key in
                               ("raw_rows", "qualified_rows", "periods", "statements", "qualified_dates")}
                         for name in names}
            if feature == "financial_history_12q":
                available["qualified_period_count"] = len(periods)
            if feature in {"return_60d", "return_120d"}:
                available["qualified_trading_dates"] = len(prices)
            rows.append({"analysis_as_of": runtime["analysis_as_of"], "symbol": symbol,
                         "role": role, "dataset_id": list(names), "feature_id": feature,
                         "required_history": required, "available_history": available,
                         "feature_value": features.get(role, {}).get(feature),
                         "latest_record_at": dates[-1] if dates else None,
                         "published_at_quality": {name: datasets.get(name, {}).get("missing_published_at") for name in names},
                         "availability_at_quality": {name: datasets.get(name, {}).get("missing_availability_at") for name in names},
                         "source_id": source_ids, "source_authorization": "existing official/approved_fallback; new adapters require admission",
                         "gap_class": gap, "gap_status": "unknown" if gap == "unknown" else "confirmed_gap",
                         "blocking": True, "remediation_layer": layer,
                         "execution": "janus-intelligence-mart-8v2vh", "core_execution_id": runtime["core_execution_id"],
                         "core_snapshot_id": runtime["core_snapshot_id"], "resolution": reason,
                         "evidence": ["ops/data-supplement-s0-runtime.json", "doc/data-supplement-s0-evidence.md"]})
        for name, dataset in sorted(datasets.items()):
            times.append({"symbol": symbol, "dataset_id": name,
                          "record_time": "fiscal quarter end" if name == "financials" else "source observation/effective date",
                          "publication_required": name in {"financials", "events"},
                          "publication_missing": dataset["missing_published_at"],
                          "availability_missing": dataset["missing_availability_at"],
                          "qualified_rows": dataset["qualified_rows"],
                          "interpretation": "First-receipt availability does not establish historical numeric revision identity."
                          if name == "financials" else "Market observed time is permitted; event publication authority needs audit."
                          if name == "events" else "Missing independent publication time is not automatically a market-data defect."})
    return {"status": "s0_partial_investigation", "analysis_as_of": runtime["analysis_as_of"],
            "acceptance_policy": "2026-10-02 user decision: verified data first; historical publication/revision unknown is permitted for current research, never for pre-receipt PIT replay",
            "scope": "all active targets plus pinned baseline symbols", "active_target_symbols": runtime["active_target_symbols"],
            "core_snapshot_id": runtime["core_snapshot_id"], "rows": rows, "time_semantics": times,
            "unresolved": "Source revision binding, applicability, independent cross-check and full S0 acceptance remain pending."}


if __name__ == "__main__":
    runtime = json.loads(Path("ops/data-supplement-s0-runtime.json").read_text(encoding="utf-8"))
    report = build_matrix(runtime)
    Path("ops/data-supplement-s0-gap-matrix.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"symbols": len(runtime["symbols"]), "active_targets": len(report["active_target_symbols"]),
                      "requirements": len(report["rows"]), "time_semantics": len(report["time_semantics"])}))
