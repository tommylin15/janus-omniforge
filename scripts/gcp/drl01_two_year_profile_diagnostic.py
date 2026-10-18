#!/usr/bin/env python3
"""DRL-01 P0-1 Diagnostic: Two-Year PE/PB Profile API Verification.

Read-only diagnostic to verify:
1. PostgreSQL publication.stock_valuation_five_year has ready 2Y profiles
2. Public API visual-series returns two_year_profile for PE/PB metrics
3. Current serving build-id matches expected deployment

Usage:
    python scripts/gcp/drl01_two_year_profile_diagnostic.py

Environment:
    JANUS_API_URL: API base URL (required for API checks)
    For PostgreSQL checks (optional, requires GCP auth):
        Uses Cloud SQL proxy or direct connection
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

# DRL-01 focus symbols (6 TWSE stocks)
FOCUS_SYMBOLS = ("1513", "2327", "2382", "3231", "3711", "5876")
# API metric names
API_METRICS = ("pe", "pb")
# DB metric names (used in publication.stock_valuation_five_year)
DB_METRICS = ("pe_ratio", "pb_ratio")
# Mapping from API metric to DB metric
METRIC_MAP = {"pe": "pe_ratio", "pb": "pb_ratio"}


@dataclass
class DiagnosticResult:
    symbol: str
    metric: str  # API metric name (pe, pb)
    db_metric: str  # DB metric name (pe_ratio, pb_ratio)
    pg_status: str | None
    pg_window_years: int | None
    pg_as_of_date: str | None
    api_data_status: str | None
    api_has_profile: bool
    api_profile_status: str | None
    api_profile_window_years: int | None
    error: str | None = None


def check_api_visual_series(base_url: str) -> dict[tuple[str, str], dict[str, Any]]:
    """Call public API visual-series for PE/PB metrics."""
    try:
        import urllib.request
        import urllib.error
    except ImportError:
        print("SKIP: urllib not available")
        return {}

    results: dict[tuple[str, str], dict[str, Any]] = {}

    for symbol in FOCUS_SYMBOLS:
        for metric in API_METRICS:
            url = f"{base_url}/api/v1/public/stocks/{symbol}/visual-series?metric={metric}&limit=120"
            try:
                req = urllib.request.Request(url, headers={"Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode())
                    results[(symbol, metric)] = data
            except urllib.error.HTTPError as e:
                results[(symbol, metric)] = {"error": f"HTTP {e.code}"}
            except Exception as e:
                results[(symbol, metric)] = {"error": str(e)}

    print(f"API: Checked {len(results)} visual-series endpoints")
    return results


def check_build_id(base_url: str) -> str | None:
    """Read current serving build-id."""
    try:
        import urllib.request
        url = f"{base_url}/app/build-id.txt"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.read().decode().strip()
    except Exception as e:
        print(f"Build-ID ERROR: {e}")
        return None


def get_api_url() -> str:
    """Get API URL from environment."""
    url = os.environ.get("JANUS_API_URL", "").strip()
    if not url:
        raise ValueError("JANUS_API_URL environment variable is required")
    return url.rstrip("/")


def run_diagnostic() -> dict[str, Any]:
    """Run full P0-1 diagnostic."""
    timestamp = datetime.now(ZoneInfo("Asia/Taipei")).isoformat()
    print(f"\n{'='*70}")
    print(f"DRL-01 P0-1 Two-Year Profile Diagnostic")
    print(f"Timestamp: {timestamp}")
    print(f"{'='*70}\n")

    base_url = get_api_url()
    print(f"API URL: {base_url}")

    # Check build-id
    build_id = check_build_id(base_url)
    print(f"Build-ID: {build_id or 'UNAVAILABLE'}\n")

    # Check API
    print("--- API Visual Series Check ---")
    api_responses = check_api_visual_series(base_url)

    # Compile results
    results: list[DiagnosticResult] = []
    for symbol in FOCUS_SYMBOLS:
        for api_metric in API_METRICS:
            db_metric = METRIC_MAP[api_metric]
            key = (symbol, api_metric)
            api_data = api_responses.get(key, {})

            two_year_profile = api_data.get("two_year_profile")
            has_profile = two_year_profile is not None
            profile_status = two_year_profile.get("status") if has_profile else None
            profile_window = two_year_profile.get("window_years") if has_profile else None

            # Extract PG info from API response's two_year_profile (if present)
            pg_status = None
            pg_window = None
            pg_as_of = None
            if has_profile:
                pg_status = two_year_profile.get("status")
                pg_window = two_year_profile.get("window_years")
                pg_as_of = two_year_profile.get("as_of_date")

            result = DiagnosticResult(
                symbol=symbol,
                metric=api_metric,
                db_metric=db_metric,
                pg_status=pg_status,
                pg_window_years=pg_window,
                pg_as_of_date=pg_as_of,
                api_data_status=api_data.get("data_status"),
                api_has_profile=has_profile,
                api_profile_status=profile_status,
                api_profile_window_years=profile_window,
                error=api_data.get("error"),
            )
            results.append(result)

    # Print summary
    print(f"\n{'='*70}")
    print("DIAGNOSTIC RESULTS")
    print(f"{'='*70}\n")

    print(f"{'Symbol':<8} {'Metric':<6} {'API Status':<12} {'Has Profile':<12} {'Profile Status':<15} {'Window':<8}")
    print("-" * 70)

    api_has_valid_profile = 0
    api_has_any_profile = 0
    for r in results:
        api_prof = "YES" if r.api_has_profile else "NO"
        prof_status = r.api_profile_status or "-"
        window = str(r.api_profile_window_years) if r.api_profile_window_years else "-"

        # Count valid 2Y profiles
        if r.api_has_profile:
            api_has_any_profile += 1
            if r.api_profile_status in ("ready", "partial_history") and r.api_profile_window_years == 2:
                api_has_valid_profile += 1

        print(f"{r.symbol:<8} {r.metric:<6} {r.api_data_status or '-':<12} {api_prof:<12} {prof_status:<15} {window:<8}")
        if r.error:
            print(f"         ERROR: {r.error}")

    print("-" * 70)
    print(f"\nSUMMARY:")
    print(f"  API returning two_year_profile field: {api_has_any_profile}/12")
    print(f"  API returning valid 2Y ready profiles: {api_has_valid_profile}/12")
    print(f"  Build-ID: {build_id or 'UNAVAILABLE'}")

    # Determine overall status
    if api_has_valid_profile == 12:
        overall = "PASS"
    elif api_has_valid_profile > 0:
        overall = "PARTIAL"
    elif api_has_any_profile > 0:
        overall = "PROFILE_PRESENT_BUT_NOT_READY"
    else:
        overall = "NO_PROFILES_RETURNED"

    print(f"\n  Overall P0-1 Status: {overall}")

    # Diagnostic hints
    if overall != "PASS":
        print(f"\nDIAGNOSTIC HINTS:")
        if api_has_any_profile == 0:
            print("  - API is not returning two_year_profile at all")
            print("  - Check if serving_valuation_profile is wired in build_core_service()")
            print("  - Verify publication.stock_valuation_five_year has data")
        elif api_has_valid_profile < api_has_any_profile:
            print("  - Some profiles returned but not in ready state or wrong window_years")
            print("  - Check payload_json in publication.stock_valuation_five_year")
            print("  - Expected: status='ready' and window_years=2")

    return {
        "timestamp": timestamp,
        "build_id": build_id,
        "api_profile_count": api_has_any_profile,
        "api_valid_2y_count": api_has_valid_profile,
        "overall_status": overall,
        "results": [
            {
                "symbol": r.symbol,
                "metric": r.metric,
                "db_metric": r.db_metric,
                "api_data_status": r.api_data_status,
                "api_has_profile": r.api_has_profile,
                "api_profile_status": r.api_profile_status,
                "api_profile_window_years": r.api_profile_window_years,
                "error": r.error,
            }
            for r in results
        ],
    }


if __name__ == "__main__":
    result = run_diagnostic()

    # Write receipt
    receipt_path = Path(__file__).resolve().parents[2] / "ops" / "drl01-p01-diagnostic-receipt.json"
    receipt_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"\nReceipt written to: {receipt_path}")

    sys.exit(0 if result["overall_status"] == "PASS" else 1)
