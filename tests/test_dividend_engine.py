"""股利自動推算引擎與 TWSE/TPEx 公司行動解析器單元測試（TC-01 ～ TC-06）。"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
import json
from uuid import uuid4

from packages.corporate_actions import (
    merge_corporate_actions,
    parse_tpex_ex_dividend_rows,
    parse_twse_ex_dividend_rows,
)
from services.api.dividend_engine import (
    compute_dividend_draft,
    dividend_auto_scan_enabled,
    eligible_shares_before_ex_date,
    reconcile_draft_with_existing,
)

OWNER_A = uuid4()


def _buy(symbol: str, trade_date: date, shares: str, version: int) -> dict:
    return {
        "event_id": uuid4(),
        "user_id": OWNER_A,
        "ledger_version": version,
        "event_action": "ORIGINAL",
        "event_type": "BUY",
        "trade_date": trade_date,
        "symbol": symbol,
        "shares": Decimal(shares),
        "price": Decimal("100"),
        "cash_amount": None,
        "fee": Decimal("0"),
        "tax": Decimal("0"),
        "currency": "TWD",
    }


def _sell(symbol: str, trade_date: date, shares: str, version: int) -> dict:
    return {
        "event_id": uuid4(),
        "user_id": OWNER_A,
        "ledger_version": version,
        "event_action": "ORIGINAL",
        "event_type": "SELL",
        "trade_date": trade_date,
        "symbol": symbol,
        "shares": Decimal(shares),
        "price": Decimal("110"),
        "cash_amount": None,
        "fee": Decimal("0"),
        "tax": Decimal("0"),
        "currency": "TWD",
    }


def test_tc01_ex_date_cutoff_includes_prior_day_excludes_same_day():
    events = [
        _buy("2330", date(2026, 9, 16), "1000", 1),
        _buy("2330", date(2026, 9, 17), "500", 2),
    ]
    assert eligible_shares_before_ex_date(events, "2330", date(2026, 9, 17)) == Decimal("1000")

    same_day_only = [_buy("2330", date(2026, 9, 17), "1000", 1)]
    action = {
        "symbol": "2330",
        "ex_date": date(2026, 9, 17),
        "payment_date": date(2026, 10, 15),
        "action_type": "CASH_DIVIDEND",
        "cash_dividend_per_share": Decimal("4.0"),
        "security_type": "common_stock",
    }
    assert compute_dividend_draft(user_id=OWNER_A, action=action, events=same_day_only, ledger_version=1) is None

    draft = compute_dividend_draft(user_id=OWNER_A, action=action, events=events, ledger_version=2)
    assert draft is not None
    assert draft["eligible_shares"] == Decimal("1000")
    assert draft["gross_cash_amount"] == Decimal("4000")
    assert draft["estimated_remit_fee"] == Decimal("10")
    assert draft["estimated_nhi_fee"] == Decimal("0")
    assert draft["net_cash_amount"] == Decimal("3990")


def test_tc02_same_day_cash_and_stock_dividends_split_cleanly():
    events = [_buy("2884", date(2026, 7, 1), "2000", 1)]
    cash_action = {
        "symbol": "2884",
        "ex_date": date(2026, 8, 1),
        "payment_date": date(2026, 8, 28),
        "action_type": "CASH_DIVIDEND",
        "cash_dividend_per_share": Decimal("2.5"),
        "security_type": "financial",
    }
    stock_action = {
        "symbol": "2884",
        "ex_date": date(2026, 8, 1),
        "payment_date": date(2026, 8, 28),
        "action_type": "STOCK_DIVIDEND",
        "stock_dividend_ratio": Decimal("0.1"),
        "security_type": "financial",
    }
    cash_draft = compute_dividend_draft(user_id=OWNER_A, action=cash_action, events=events, ledger_version=1)
    stock_draft = compute_dividend_draft(user_id=OWNER_A, action=stock_action, events=events, ledger_version=1)
    assert cash_draft["action_type"] == "CASH_DIVIDEND"
    assert cash_draft["gross_cash_amount"] == Decimal("5000")
    assert stock_draft["action_type"] == "STOCK_DIVIDEND"
    assert stock_draft["estimated_stock_shares"] == Decimal("200")
    assert stock_draft["fractional_shares"] == Decimal("0")
    assert cash_draft["draft_id"] != stock_draft["draft_id"]


def test_tc03_flexible_par_value_uses_authoritative_stock_dividend_ratio():
    events = [_buy("6488", date(2026, 5, 1), "1234", 1)]
    action = {
        "symbol": "6488",
        "ex_date": date(2026, 6, 10),
        "payment_date": None,
        "action_type": "STOCK_DIVIDEND",
        "stock_dividend_ratio": Decimal("0.08"),
        "par_value": Decimal("5"),
        "security_type": "common_stock",
    }
    draft = compute_dividend_draft(user_id=OWNER_A, action=action, events=events, ledger_version=1)
    assert draft["estimated_stock_shares"] == Decimal("98")
    assert draft["fractional_shares"] == Decimal("0.72")
    assert "HAS_FRACTIONAL_SHARES" in draft["warnings"]
    assert "PAYMENT_DATE_TBD" in draft["warnings"]


def test_tc04_nhi_threshold_rules_for_etf_common_and_ky_stocks():
    events = [_buy("0056", date(2026, 1, 5), "10000", 1), _buy("2330", date(2026, 1, 5), "5000", 2)]
    etf_action = {
        "symbol": "0056",
        "ex_date": date(2026, 4, 20),
        "payment_date": date(2026, 5, 15),
        "action_type": "CASH_DIVIDEND",
        "cash_dividend_per_share": Decimal("2.5"),
    }
    etf_draft = compute_dividend_draft(
        user_id=OWNER_A,
        action=etf_action,
        events=events,
        ledger_version=2,
        identity={"name": "元大高股息", "instrument_kind": "ETF"},
    )
    assert etf_draft["security_type"] == "etf"
    assert etf_draft["gross_cash_amount"] == Decimal("25000")
    assert etf_draft["estimated_nhi_fee"] == Decimal("0")
    assert "ETF_EQUALIZATION_CHECK" in etf_draft["warnings"]

    common_action = {
        "symbol": "2330",
        "ex_date": date(2026, 4, 20),
        "payment_date": date(2026, 5, 15),
        "action_type": "CASH_DIVIDEND",
        "cash_dividend_per_share": Decimal("5.0"),
        "security_type": "common_stock",
    }
    common_draft = compute_dividend_draft(user_id=OWNER_A, action=common_action, events=events, ledger_version=2)
    assert common_draft["gross_cash_amount"] == Decimal("25000")
    assert common_draft["estimated_nhi_fee"] == Decimal("527")
    assert common_draft["net_cash_amount"] == Decimal("24463")
    assert "NHI_ESTIMATED" in common_draft["warnings"]

    ky_events = [_buy("3661", date(2026, 1, 5), "5000", 1)]
    ky_action = {
        "symbol": "3661",
        "ex_date": date(2026, 6, 1),
        "payment_date": date(2026, 7, 1),
        "action_type": "CASH_DIVIDEND",
        "cash_dividend_per_share": Decimal("5.0"),
    }
    ky_draft = compute_dividend_draft(
        user_id=OWNER_A,
        action=ky_action,
        events=ky_events,
        ledger_version=1,
        identity={"name": "世芯-KY"},
    )
    assert ky_draft["security_type"] == "ky_stock"
    assert ky_draft["estimated_nhi_fee"] == Decimal("0")
    assert "KY_OVERSEAS_INCOME" in ky_draft["warnings"]


def test_tc05_manual_dividend_auto_reconciles_to_already_recorded():
    manual_cash_id = uuid4()
    events = [
        _buy("2330", date(2026, 1, 5), "1000", 1),
        {
            "event_id": manual_cash_id,
            "user_id": OWNER_A,
            "ledger_version": 2,
            "event_action": "ORIGINAL",
            "event_type": "CASH_DIV",
            "trade_date": date(2026, 4, 15),
            "symbol": "2330",
            "shares": None,
            "price": None,
            "cash_amount": Decimal("4000"),
            "fee": Decimal("10"),
            "tax": Decimal("0"),
            "currency": "TWD",
        },
    ]
    action = {
        "symbol": "2330",
        "ex_date": date(2026, 3, 18),
        "payment_date": date(2026, 4, 15),
        "action_type": "CASH_DIVIDEND",
        "cash_dividend_per_share": Decimal("4.0"),
        "security_type": "common_stock",
    }
    draft = compute_dividend_draft(user_id=OWNER_A, action=action, events=events, ledger_version=2)
    assert draft["status"] == "ALREADY_RECORDED"
    assert draft["confirmed_trade_id"] == manual_cash_id


def test_tc06_reconcile_recalculates_stale_but_protects_confirmed_and_dismissed():
    action = {
        "symbol": "2330",
        "ex_date": date(2026, 9, 17),
        "payment_date": date(2026, 10, 15),
        "action_type": "CASH_DIVIDEND",
        "cash_dividend_per_share": Decimal("4.0"),
        "security_type": "common_stock",
    }
    initial_events = [_buy("2330", date(2026, 9, 1), "1000", 1)]
    existing_pending = compute_dividend_draft(
        user_id=OWNER_A, action=action, events=initial_events, ledger_version=1
    )
    updated_events = [*initial_events, _buy("2330", date(2026, 9, 10), "1000", 2)]
    recomputed = compute_dividend_draft(
        user_id=OWNER_A, action=action, events=updated_events, ledger_version=2
    )
    merged = reconcile_draft_with_existing(existing_pending, recomputed)
    assert merged["eligible_shares"] == Decimal("2000")
    assert merged["gross_cash_amount"] == Decimal("8000")
    assert "LEDGER_UPDATED_RECALC" in merged["warnings"]

    # 已確認或已忽略者不受補登舊交易覆寫
    confirmed = {**existing_pending, "status": "CONFIRMED", "confirmed_trade_id": uuid4()}
    assert reconcile_draft_with_existing(confirmed, recomputed) is confirmed
    dismissed = {**existing_pending, "status": "DISMISSED"}
    assert reconcile_draft_with_existing(dismissed, recomputed) is dismissed

    # 若補登賣出導致基準股數歸零，未確認草稿應自動忽略
    sold_out_events = [*initial_events, _sell("2330", date(2026, 9, 10), "1000", 2)]
    assert compute_dividend_draft(user_id=OWNER_A, action=action, events=sold_out_events, ledger_version=2) is None
    zeroed = reconcile_draft_with_existing(existing_pending, None)
    assert zeroed["status"] == "DISMISSED"


def test_twse_and_tpex_parsers_and_feature_flag(monkeypatch):
    monkeypatch.setenv("DIVIDEND_AUTO_SCAN_ENABLED", "false")
    assert dividend_auto_scan_enabled() is False
    monkeypatch.setenv("DIVIDEND_AUTO_SCAN_ENABLED", "true")
    assert dividend_auto_scan_enabled() is True

    twse_raw = json.dumps({
        "fields": ["除權息日期", "股票代號", "名稱", "現金股利", "無償配股率", "發放日"],
        "data": [["115年08月01日", "2884", "玉山金", "1.2", "0.10", "115/08/28"]],
    }).encode("utf-8")
    twse_records = parse_twse_ex_dividend_rows(twse_raw, observed_at=datetime(2026, 8, 1, tzinfo=timezone.utc))
    assert len(twse_records) == 2
    assert {r.action_type for r in twse_records} == {"CASH_DIVIDEND", "STOCK_DIVIDEND"}
    assert twse_records[0].ex_date == date(2026, 8, 1)
    assert twse_records[0].payment_date == date(2026, 8, 28)

    tpex_raw = json.dumps([
        {
            "SecuritiesCompanyCode": "6488",
            "CompanyName": "環球晶",
            "ExdividendDate": "115/06/10",
            "CashDividend": "8.0",
            "StockDividendRatio": "0.05",
            "PaymentDate": "115/07/10",
        }
    ]).encode("utf-8")
    tpex_records = parse_tpex_ex_dividend_rows(tpex_raw)
    assert len(tpex_records) == 2
    merged = merge_corporate_actions(twse_records, tpex_records)
    assert len(merged) == 4
