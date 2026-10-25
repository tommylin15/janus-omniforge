"""SEQ05 quickfill never fetches online data in unit tests."""
import ast
import calendar
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
import html
import json
from pathlib import Path
import re


def helpers():
    path = Path(__file__).resolve().parents[1] / "scripts/gcp/seq05_oneoff_core.py"
    source = ast.parse(path.read_text())
    chosen = [n for n in source.body if isinstance(n, ast.FunctionDef)
              and n.name in {"positive", "extract_finmind_pb", "extract_yahoo_bvps"}]
    namespace = {"date":date,"AS_OF":date(2026,10,24), "MARKET":"TWSE", "MONTHS":tuple(
        f"{y}-{m:02d}" for y in (2025,2026) for m in range(1,13)
        if "2025-10"<=f"{y}-{m:02d}"<="2026-08"),"Decimal":Decimal,
        "InvalidOperation":InvalidOperation, "defaultdict":defaultdict,
        "calendar":calendar, "json":json, "re":re, "html":html}
    exec(compile(ast.Module(body=chosen,type_ignores=[]),str(path),"exec"),namespace)
    return namespace


def test_finmind_last_trading_day_only():
    h=helpers()
    raw=json.dumps({"status":200,"data":[
        {"stock_id":"2882","date":"2025-10-30","PBR":1.2},
        {"stock_id":"2882","date":"2025-10-31","PBR":1.3},
        {"stock_id":"2882","date":"2025-11-28","PBR":1.4},
        {"stock_id":"2882","date":"2026-09-30","PBR":1.9},
    ]}).encode()
    rows=h["extract_finmind_pb"](raw)
    assert [(r["observed_date"],r["pb_ratio"]) for r in rows] == [
        ("2025-10-31","1.3"),("2025-11-28","1.4")]


def test_yahoo_reported_bvps_no_total_equity_inference():
    h=helpers()
    raw="<html><p>2026 Q2 每股淨值 69.37 元</p></html>".encode()
    row=h["extract_yahoo_bvps"](raw)
    assert (row["fiscal_year"],row["fiscal_quarter"],row["value"]) == (2026,2,"69.37")
    assert row["unit"]=="TWD_per_share"


def test_no_other_symbol_accepted():
    h=helpers()
    raw=json.dumps({"status":200,"data":[{"stock_id":"2330","date":"2025-10-31","PBR":2.0}]}).encode()
    try:
        h["extract_finmind_pb"](raw)
    except ValueError as err:
        assert "symbol_mismatch" in str(err)
    else:
        raise AssertionError("cross-symbol rows must fail")
