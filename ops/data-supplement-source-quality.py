"""Bounded private/internal source audit; no Core writes or token logging."""
import json
import argparse
import os
from collections import Counter
from datetime import date
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from pathlib import Path
import tempfile
import time
from urllib.parse import urlencode, urlparse, parse_qs
from urllib.request import Request, urlopen


SYMBOLS = ("1102", "1301", "2002", "2327", "2330", "2412", "2801", "2851", "2882", "4958", "5876")
DATASETS = ("TaiwanStockFinancialStatements", "TaiwanStockBalanceSheet",
            "TaiwanStockCashFlowsStatement", "TaiwanStockMonthRevenue")


def audit_rows(rows, symbol, dataset):
    keys, invalid, values = Counter(), [], {}
    for row in rows:
        if str(row.get("stock_id")) != symbol:
            raise ValueError("source returned an unexpected stock identity")
        day = date.fromisoformat(row["date"])
        metric = row.get("type", "revenue")
        key = (row.get("revenue_year", day.year), row.get("revenue_month", day.isoformat()), metric)
        keys[key] += 1
        value = row.get("value", row.get("revenue"))
        try:
            number = Decimal(str(value))
            if not number.is_finite():
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            invalid.append({"date": row["date"], "metric": metric})
        values.setdefault(key, set()).add(str(value))
    dates = sorted({r["date"] for r in rows})
    quarters = sorted({f"{d[:4]}Q{(int(d[5:7])-1)//3+1}" for d in dates})
    monthly = dataset == "TaiwanStockMonthRevenue"
    latest = {r.get("type", "revenue"): r.get("value", r.get("revenue"))
              for r in rows if dates and r["date"] == dates[-1]}
    return {"rows": len(rows), "first_record_date": dates[0] if dates else None,
            "latest_record_date": dates[-1] if dates else None,
            "history_periods": sorted({f'{r["revenue_year"]}-{int(r["revenue_month"]):02d}' for r in rows}) if monthly else quarters,
            "fields": sorted({k for r in rows for k in r}), "metrics": sorted(latest),
            "duplicate_keys": sum(n-1 for n in keys.values()),
            "conflicting_keys": sum(len(v)>1 for v in values.values()), "invalid_values": invalid,
            "pit_numeric_revision_verified": False}


def main(symbols=SYMBOLS):
    token = os.environ.get("FINMIND_API_TOKEN", "")
    headers = {"User-Agent": "Janus-Source-Quality/1.0", "Accept": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    profiles = json.loads(Path(tempfile.gettempdir(), "janus-twse-profiles.json").read_text(encoding="utf-8-sig"))
    profiles = {str(r["公司代號"]): r for r in profiles}
    path = Path("ops/data-supplement-source-quality.json")
    report = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"scope": "bounded private/internal cross-industry audit", "analysis_as_of": "2026-10-01",
              "authenticated": bool(token), "core_writes": 0, "symbols": {}}
    for symbol in symbols:
        profile = profiles[symbol]
        summary = {"official_name": profile["公司簡稱"], "official_industry_code": profile["產業別"], "datasets": {}}
        report["symbols"][symbol] = summary
        for dataset in DATASETS:
            query = urlencode({"dataset": dataset, "data_id": symbol, "start_date": "2023-07-01", "end_date": "2026-10-01"})
            try:
                with urlopen(Request("https://api.finmindtrade.com/api/v4/data?" + query, headers=headers), timeout=30) as response:
                    raw = response.read()
                payload = json.loads(raw)
                if payload.get("status") != 200 or not isinstance(payload.get("data"), list):
                    raise ValueError("source did not return successful dataset rows")
                Path(tempfile.gettempdir(), f"janus-finmind-{symbol}-{dataset}.json").write_bytes(raw)
                summary["datasets"][dataset] = audit_rows(payload["data"], symbol, dataset) | {"response_sha256": sha256(raw).hexdigest()}
            except Exception as error:
                summary["datasets"][dataset] = {"error_type": type(error).__name__, "http_status": getattr(error, "code", None)}
            Path("ops/data-supplement-source-quality.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
            item = summary["datasets"][dataset]
            print(json.dumps({"symbol": symbol, "dataset": dataset, "rows": item.get("rows"),
                              "periods": len(item.get("history_periods", [])), "error_type": item.get("error_type")}), flush=True)
            time.sleep(2)


def validate_official_result(result, symbol, quarter, expected_name):
    if result.get("year") != "115" or result.get("seasonName") != {1: "第１季", 2: "上半年度"}[quarter]:
        raise ValueError("official summary fiscal identity mismatch")
    links = [urlparse(row.get("url", "")) for row in result.get("CAL", {}).get("urlList", [])]
    identities = [parse_qs(link.query) for link in links if link.hostname == "mopsov.twse.com.tw"
                  and link.path == "/server-java/t164sb01"]
    if result.get("companyAbbreviation") != expected_name or not any(
            query.get("CO_ID") == [symbol] and query.get("SYEAR") == ["2026"]
            and query.get("SSEASON") == [str(quarter)] for query in identities):
        raise ValueError("official summary company identity mismatch")
    for table in ("CCSI", "CAL"):
        if result.get(table, {}).get("unit") != "單位：新台幣仟元":
            raise ValueError("official currency unit changed")


def crosscheck(symbols=SYMBOLS):
    report = json.loads(Path("ops/data-supplement-source-quality.json").read_text(encoding="utf-8"))
    for symbol, summary in report["symbols"].items():
        if symbol not in symbols:
            continue
        official, hashes = {}, {}
        for quarter in (1, 2):
            raw = Path(tempfile.gettempdir(), f"janus-mops-{symbol}-2026q{quarter}.json").read_bytes()
            payload = json.loads(raw.decode("utf-8-sig"))
            if payload.get("code") != 200:
                raise ValueError("official summary unavailable")
            official[quarter] = payload["result"]
            hashes[str(quarter)] = sha256(raw).hexdigest()
            validate_official_result(official[quarter], symbol, quarter, summary["official_name"])
        if official[1]["reportType"] != official[2]["reportType"]:
            raise ValueError("official report scope changed between quarters")
        checks = []
        for dataset, table in ((DATASETS[0], "CCSI"), (DATASETS[1], "CAL")):
            rows = json.loads(Path(tempfile.gettempdir(), f"janus-finmind-{symbol}-{dataset}.json").read_bytes())["data"]
            audit = audit_rows(rows, symbol, dataset)
            if audit["duplicate_keys"] or audit["conflicting_keys"] or audit["invalid_values"]:
                raise ValueError("source audit failed before numeric comparison")
            for row in rows:
                if row["date"] != "2026-06-30" or row["type"].endswith("_per") or row["type"] == "EPS":
                    continue
                label = {"TotalAssets": "資產總計", "Liabilities": "負債總計", "Equity": "權益總計"}.get(row["type"], row["origin_name"])
                values = []
                for quarter in ((1, 2) if table == "CCSI" else (2,)):
                    matches = [r[1] for r in official[quarter][table]["data"] if r[0] == label and r[1] != "-"]
                    if len(matches) != 1:
                        break
                    values.append(Decimal(matches[0].replace(",", "")))
                else:
                    expected = (values[1]-values[0] if table == "CCSI" else values[0])*1000
                    actual = Decimal(str(row["value"]))
                    checks.append({"dataset": dataset, "metric": row["type"], "official_label": label,
                                   "expected_twd": str(expected), "matches": expected == actual})
        income = summary["datasets"][DATASETS[0]]
        summary["official_crosscheck"] = {"period": "2026Q2", "report_type": official[2]["reportType"],
            "official_response_hashes": hashes, "checks": checks,
            "matched": sum(r["matches"] for r in checks), "mismatched": sum(not r["matches"] for r in checks),
            "eps_in_finmind_latest": "EPS" in income["metrics"],
            "official_eps_cumulative": [r[1] for r in official[2]["CCSI"]["data"] if r[0].startswith("基本每股盈餘")],
            "pit_numeric_revision_verified": False}
        print(symbol, summary["official_crosscheck"]["matched"], "matched;",
              summary["official_crosscheck"]["mismatched"], "mismatched; EPS present:", "EPS" in income["metrics"])
    Path("ops/data-supplement-source-quality.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--crosscheck", action="store_true")
    parser.add_argument("--symbol", action="append", choices=SYMBOLS)
    arguments = parser.parse_args()
    selected = tuple(arguments.symbol or SYMBOLS)
    crosscheck(selected) if arguments.crosscheck else main(selected)
