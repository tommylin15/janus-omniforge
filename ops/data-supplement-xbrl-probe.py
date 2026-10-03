"""Bounded official historical statement probe; no canonical writes or PIT claims."""
import json
from collections import Counter
from hashlib import sha256
from decimal import Decimal
from pathlib import Path
import sys
import tempfile
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jobs/ingestion-core"))
from ingestion_core.financial_publication import parse_xbrl_report


SYMBOLS = ("1102", "2327", "2330", "4958", "5876")
PERIODS = tuple((year, quarter) for year in range(2023, 2027) for quarter in range(1, 5)
                if (2023, 3) <= (year, quarter) <= (2026, 2))


def crosscheck_facts(facts, symbol, year, quarter):
    mapping = {
        "TaiwanStockFinancialStatements": {"EPS": "BasicEarningsLossPerShare", "Revenue": "Revenue",
            "IncomeAfterTaxes": "ProfitLoss", "IncomeAfterTax": "ProfitLoss",
            "EquityAttributableToOwnersOfParent": "ProfitLossAttributableToOwnersOfParent"},
        "TaiwanStockBalanceSheet": {"TotalAssets": "Assets", "Liabilities": "Liabilities", "Equity": "Equity",
            "EquityAttributableToOwnersOfParent": "EquityAttributableToOwnersOfParent"},
        "TaiwanStockCashFlowsStatement": {"CashFlowsFromOperatingActivities": "CashFlowsFromUsedInOperatingActivities",
            "CashFlowsProvidedFromFinancingActivities": "CashFlowsFromUsedInFinancingActivities"},
    }
    checks, missing = [], []
    period_end = f"{year}-" + {1: "03-31", 2: "06-30", 3: "09-30", 4: "12-31"}[quarter]
    for dataset, aliases in mapping.items():
        path = Path(tempfile.gettempdir(), f"janus-finmind-{symbol}-{dataset}.json")
        if not path.exists():
            missing.append({"dataset": dataset, "reason": "comparison response unavailable"})
            continue
        rows = json.loads(path.read_bytes())["data"]
        for row in rows:
            if row.get("stock_id") != symbol:
                raise ValueError("comparison response company identity mismatch")
            if row["date"] != period_end or row["type"] not in aliases:
                continue
            if dataset == "TaiwanStockBalanceSheet":
                start = period_end
            elif dataset == "TaiwanStockCashFlowsStatement":
                start = f"{year}-01-01"
            else:
                start = f"{year}-{(quarter-1)*3+1:02d}-01"
            matches = [fact for fact in facts if fact["concept"] == "ifrs-full:"+aliases[row["type"]]
                       and fact["period_start"] == start and fact["period_end"] == period_end]
            if len(matches) != 1:
                missing.append({"dataset": dataset, "metric": row["type"],
                                "reason": "no unique directly reported matching context; no EPS subtraction"})
                continue
            fact = matches[0]
            expected_unit = "TWD_per_share" if row["type"] == "EPS" else "TWD"
            if fact["unit"] != expected_unit:
                raise ValueError("comparison numeric unit mismatch")
            expected, actual = Decimal(fact["value"]), Decimal(str(row["value"]))
            if not actual.is_finite():
                raise ValueError("comparison value is not finite")
            checks.append({"dataset": dataset, "metric": row["type"], "context_id": fact["context_id"],
                           "period_basis": fact["period_basis"], "unit": fact["unit"],
                           "official_value": str(expected), "matches": expected == actual})
    return {"checks": checks, "matched": sum(r["matches"] for r in checks),
            "mismatched": sum(not r["matches"] for r in checks), "not_compared": missing}


def main():
    folder = Path(tempfile.gettempdir())
    filings = json.loads(Path("ops/data-supplement-filing-probe.json").read_text(encoding="utf-8"))["filings"]
    report = {"scope": "all active targets plus pinned baseline; private/internal only", "core_writes": 0,
              "numeric_revision_verified": False, "documents": []}
    output = Path("ops/data-supplement-xbrl-probe.json")
    for symbol in SYMBOLS:
        for year, quarter in PERIODS:
            item = {"symbol": symbol, "year": year, "quarter": quarter}
            url = "https://mopsov.twse.com.tw/server-java/t164sb01?" + urlencode({
                "step": "1", "CO_ID": symbol, "SYEAR": str(year), "SSEASON": str(quarter), "REPORT_ID": "C"})
            item["source_url"] = url
            cache = folder / f"janus-xbrl-{symbol}-{year}q{quarter}.raw"
            try:
                matching = [r for r in filings if (r["symbol"], r["fiscal_year"], r["fiscal_quarter"]) == (symbol, year, quarter)]
                if len(matching) != 1:
                    raise ValueError("filing identity is missing or ambiguous")
                if cache.exists():
                    raw = cache.read_bytes()
                else:
                    with urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=30) as response:
                        raw = response.read()
                    cache.write_bytes(raw)
                    time.sleep(2)
                # Official old pages mix Big5 wrappers and UTF-8 content. A byte-preserving
                # mapping keeps ASCII XBRL identifiers/numbers intact; Chinese prose is not parsed.
                html = raw.decode("latin-1")
                item["response_sha256"] = sha256(raw).hexdigest()
                rows = parse_xbrl_report(html, symbol, year, quarter)
                item["finmind_crosscheck"] = crosscheck_facts(rows, symbol, year, quarter)
                item.update({"filing_filename": matching[0]["filename"],
                             "official_uploaded_at": matching[0]["official_uploaded_at"],
                             "structural_decode": "byte-preserving Latin-1; ASCII XBRL facts/metadata only",
                             "facts": len(rows), "period_bases": dict(Counter(r["period_basis"] for r in rows)),
                             "industry_sector": rows[0]["industry_sector"], "report_type": rows[0]["report_type"],
                             "eps": [{k: r[k] for k in ("context_id", "period_start", "period_end", "period_basis", "value", "unit")}
                                     for r in rows if r["concept"] == "ifrs-full:BasicEarningsLossPerShare"],
                             "cash_flow_operating": [{k: r[k] for k in ("period_basis", "value", "unit")}
                                     for r in rows if r["concept"] == "ifrs-full:CashFlowsFromUsedInOperatingActivities"],
                             "balance_totals": {r["concept"]: r["value"] for r in rows if r["concept"] in
                                                {"ifrs-full:Assets", "ifrs-full:Liabilities", "ifrs-full:Equity"}},
                             "numeric_revision_verified": False,
                             "pit_binding": "Official current XBRL facts and filing upload index are separate evidence; original numeric revision binding pending."})
            except Exception as error:
                item["error_type"] = type(error).__name__
            report["documents"].append(item)
            output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
            print(json.dumps({k: item.get(k) for k in ("symbol", "year", "quarter", "facts", "error_type")}), flush=True)


if __name__ == "__main__":
    main()
