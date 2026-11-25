"""純後端 Decimal 確定性股利推算與對帳引擎（零 LLM、零浮點數）。"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, ROUND_FLOOR
import os
import re
from typing import Any, Iterable
from uuid import NAMESPACE_URL, uuid5

from .private_pipeline import effective_ledger_events

ZERO = Decimal("0")
ONE = Decimal("1")
DEFAULT_REMIT_FEE = Decimal("10")
NHI_THRESHOLD = Decimal("20000")
NHI_RATE = Decimal("0.0211")
CASH_RECONCILE_TOLERANCE = Decimal("50")
STOCK_RECONCILE_TOLERANCE = Decimal("1")

ACTION_TO_LEDGER_TYPE = {
    "CASH_DIVIDEND": "CASH_DIV",
    "STOCK_DIVIDEND": "STOCK_DIV",
}


def dividend_auto_scan_enabled() -> bool:
    """盤後股利自動掃描排程開關（可透過環境變數關閉回退）。"""
    return os.getenv("DIVIDEND_AUTO_SCAN_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}


def _to_decimal(value: Any, default: Decimal = ZERO) -> Decimal:
    if value is None:
        return default
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _draft_uuid(user_id: Any, symbol: str, ex_date: date, action_type: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"janus-dividend-draft/{user_id}/{symbol}/{ex_date.isoformat()}/{action_type}"))


def resolve_security_type(
    symbol: str,
    *,
    action_security_type: str | None = None,
    identity: dict[str, Any] | None = None,
) -> str:
    """判定台股標的類別，供二代健保補充保費與所得提示使用。"""
    kind = str((identity or {}).get("instrument_kind") or "").upper()
    name = str((identity or {}).get("name") or "").strip().upper()
    upper = symbol.strip().upper()
    if kind in {"ETF", "BOND_ETF"} or re.fullmatch(r"00\d{2,4}[A-Z]?", upper):
        return "etf"
    if action_security_type in {"etf", "reit", "ky_stock", "financial"}:
        return action_security_type
    if upper.endswith("T1") or "REIT" in name:
        return "reit"
    if "-KY" in name:
        return "ky_stock"
    if action_security_type == "common_stock":
        return "common_stock"
    return "common_stock"


def eligible_shares_before_ex_date(
    events: Iterable[dict[str, Any]],
    symbol: str,
    ex_date: date,
) -> Decimal:
    """重播除權息日前一交易日收盤前（trade_date < ex_date）之有效基準股數。"""
    target = symbol.strip().upper()
    held = ZERO
    for row in effective_ledger_events(list(events)):
        if str(row.get("symbol") or "").strip().upper() != target:
            continue
        trade_date = row.get("trade_date")
        if isinstance(trade_date, str):
            trade_date = date.fromisoformat(trade_date[:10])
        if trade_date is None or trade_date >= ex_date:
            continue
        shares = _to_decimal(row.get("shares"))
        event_type = row.get("event_type")
        if event_type in {"BUY", "STOCK_DIV"}:
            held += shares
        elif event_type == "SELL":
            held -= shares
    return max(ZERO, held)


def _find_matching_manual_dividend(
    effective_events: list[dict[str, Any]],
    *,
    symbol: str,
    action_type: str,
    ex_date: date,
    payment_date: date | None,
    expected_cash_gross: Decimal | None,
    expected_cash_net: Decimal | None,
    expected_stock_shares: Decimal | None,
) -> dict[str, Any] | None:
    """比對帳本是否已有使用者手動輸入之同區間股利交易，防止重複提醒與入帳。"""
    target_ledger_type = ACTION_TO_LEDGER_TYPE[action_type]
    window_start = ex_date - timedelta(days=3)
    # 歷史結果表可能無 payment_date，放寬至除權息日後 90 天以涵蓋一般發放期
    window_end = (payment_date + timedelta(days=21)) if payment_date else (ex_date + timedelta(days=90))
    target_symbol = symbol.strip().upper()
    cash_tolerance = (
        max(CASH_RECONCILE_TOLERANCE, expected_cash_gross * Decimal("0.03"))
        if expected_cash_gross is not None
        else CASH_RECONCILE_TOLERANCE
    )
    stock_tolerance = (
        max(STOCK_RECONCILE_TOLERANCE, expected_stock_shares * Decimal("0.01"))
        if expected_stock_shares is not None
        else STOCK_RECONCILE_TOLERANCE
    )
    for row in effective_events:
        if str(row.get("symbol") or "").strip().upper() != target_symbol:
            continue
        if row.get("event_type") != target_ledger_type:
            continue
        trade_date = row.get("trade_date")
        if isinstance(trade_date, str):
            trade_date = date.fromisoformat(trade_date[:10])
        if trade_date is None or not (window_start <= trade_date <= window_end):
            continue
        if action_type == "CASH_DIVIDEND":
            gross = _to_decimal(row.get("cash_amount"))
            net = gross - _to_decimal(row.get("fee")) - _to_decimal(row.get("tax"))
            for expected in (expected_cash_gross, expected_cash_net):
                if expected is not None and (
                    abs(gross - expected) <= cash_tolerance or abs(net - expected) <= cash_tolerance
                ):
                    return row
        else:
            shares = _to_decimal(row.get("shares"))
            if expected_stock_shares is not None and abs(shares - expected_stock_shares) <= stock_tolerance:
                return row
    return None


def compute_dividend_draft(
    *,
    user_id: Any,
    action: dict[str, Any],
    events: list[dict[str, Any]],
    ledger_version: int,
    identity: dict[str, Any] | None = None,
    default_remit_fee: Decimal = DEFAULT_REMIT_FEE,
) -> dict[str, Any] | None:
    """依公司行動與使用者交易重播結果，確定性推算單筆待確認股利草稿。"""
    symbol = str(action["symbol"]).strip().upper()
    ex_date = action["ex_date"]
    if isinstance(ex_date, str):
        ex_date = date.fromisoformat(ex_date[:10])
    payment_date = action.get("payment_date")
    if isinstance(payment_date, str):
        payment_date = date.fromisoformat(payment_date[:10])
    action_type = str(action["action_type"])

    effective = effective_ledger_events(events)
    eligible = eligible_shares_before_ex_date(effective, symbol, ex_date)
    if eligible <= ZERO:
        return None

    security_type = resolve_security_type(
        symbol,
        action_security_type=action.get("security_type"),
        identity=identity,
    )
    company_name = str((identity or {}).get("name") or action.get("company_name") or symbol).strip()
    warnings: list[str] = []
    if payment_date is None:
        warnings.append("PAYMENT_DATE_TBD")

    if action_type == "CASH_DIVIDEND":
        rate = _to_decimal(action.get("cash_dividend_per_share"))
        if rate <= ZERO:
            return None
        gross = (eligible * rate).quantize(ONE, rounding=ROUND_FLOOR)
        if gross <= ZERO:
            return None
        remit_fee = max(ZERO, _to_decimal(default_remit_fee))
        nhi_fee = ZERO
        if gross >= NHI_THRESHOLD:
            if security_type in {"common_stock", "financial"}:
                nhi_fee = (gross * NHI_RATE).quantize(ONE, rounding=ROUND_FLOOR)
                warnings.append("NHI_ESTIMATED")
            elif security_type in {"etf", "reit"}:
                warnings.append("ETF_EQUALIZATION_CHECK")
            elif security_type == "ky_stock":
                warnings.append("KY_OVERSEAS_INCOME")
        elif security_type == "ky_stock":
            warnings.append("KY_OVERSEAS_INCOME")
        net_cash = max(ZERO, gross - remit_fee - nhi_fee)
        matched = _find_matching_manual_dividend(
            effective,
            symbol=symbol,
            action_type=action_type,
            ex_date=ex_date,
            payment_date=payment_date,
            expected_cash_gross=gross,
            expected_cash_net=net_cash,
            expected_stock_shares=None,
        )
        return {
            "draft_id": _draft_uuid(user_id, symbol, ex_date, action_type),
            "user_id": user_id,
            "symbol": symbol,
            "company_name": company_name,
            "security_type": security_type,
            "action_type": action_type,
            "ex_date": ex_date,
            "payment_date": payment_date,
            "eligible_shares": eligible,
            "rate_per_share": rate,
            "gross_cash_amount": gross,
            "estimated_remit_fee": remit_fee,
            "estimated_nhi_fee": nhi_fee,
            "net_cash_amount": net_cash,
            "estimated_stock_shares": None,
            "fractional_shares": None,
            "confirmed_stock_shares": None,
            "status": "ALREADY_RECORDED" if matched else "PENDING",
            "warnings": warnings,
            "ledger_version_at_calc": ledger_version,
            "confirmed_trade_id": matched.get("event_id") if matched else None,
        }

    if action_type == "STOCK_DIVIDEND":
        # 嚴格使用權威配股率 stock_dividend_ratio，不寫死除以 10 元面額以相容彈性面額股。
        ratio = _to_decimal(action.get("stock_dividend_ratio"))
        if ratio <= ZERO:
            return None
        raw_shares = eligible * ratio
        whole_shares = raw_shares.quantize(ONE, rounding=ROUND_FLOOR)
        fractional = raw_shares - whole_shares
        if fractional > ZERO:
            warnings.append("HAS_FRACTIONAL_SHARES")
        if whole_shares <= ZERO:
            warnings.append("FRACTIONAL_ONLY")
        matched = _find_matching_manual_dividend(
            effective,
            symbol=symbol,
            action_type=action_type,
            ex_date=ex_date,
            payment_date=payment_date,
            expected_cash_gross=None,
            expected_cash_net=None,
            expected_stock_shares=whole_shares,
        )
        return {
            "draft_id": _draft_uuid(user_id, symbol, ex_date, action_type),
            "user_id": user_id,
            "symbol": symbol,
            "company_name": company_name,
            "security_type": security_type,
            "action_type": action_type,
            "ex_date": ex_date,
            "payment_date": payment_date,
            "eligible_shares": eligible,
            "rate_per_share": ratio,
            "gross_cash_amount": None,
            "estimated_remit_fee": ZERO,
            "estimated_nhi_fee": ZERO,
            "net_cash_amount": None,
            "estimated_stock_shares": whole_shares,
            "fractional_shares": fractional,
            "confirmed_stock_shares": whole_shares,
            "status": "ALREADY_RECORDED" if matched else "PENDING",
            "warnings": warnings,
            "ledger_version_at_calc": ledger_version,
            "confirmed_trade_id": matched.get("event_id") if matched else None,
        }

    raise ValueError(f"unsupported action_type: {action_type}")


def reconcile_draft_with_existing(
    existing: dict[str, Any] | None,
    computed: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """合併既有草稿狀態與最新確定性重算結果（保護 CONFIRMED / DISMISSED 不被覆寫）。"""
    if existing is None:
        return computed
    status = existing.get("status")
    if status in {"CONFIRMED", "DISMISSED"}:
        return existing
    if computed is None:
        # 補登除權息日前賣出導致基準持股歸零時，將尚未確認之草稿轉為忽略
        return {
            **existing,
            "status": "DISMISSED",
            "warnings": list(dict.fromkeys([*(existing.get("warnings") or []), "ELIGIBLE_SHARES_ZERO"])),
        }

    prev_shares = _to_decimal(existing.get("eligible_shares"))
    next_shares = _to_decimal(computed.get("eligible_shares"))
    if prev_shares != next_shares:
        warnings = list(dict.fromkeys([*(computed.get("warnings") or []), "LEDGER_UPDATED_RECALC"]))
        return {
            **computed,
            "draft_id": existing["draft_id"],
            "user_note": existing.get("user_note"),
            "warnings": warnings,
        }

    # 若基準股數未變且仍在 PENDING，保留使用者微調後的匯費／補充保費／實領金額／實得股數
    if status == "PENDING" and computed.get("status") == "PENDING":
        return {
            **computed,
            "draft_id": existing["draft_id"],
            "estimated_remit_fee": existing.get("estimated_remit_fee", computed["estimated_remit_fee"]),
            "estimated_nhi_fee": existing.get("estimated_nhi_fee", computed["estimated_nhi_fee"]),
            "net_cash_amount": existing.get("net_cash_amount", computed["net_cash_amount"]),
            "confirmed_stock_shares": existing.get("confirmed_stock_shares", computed["confirmed_stock_shares"]),
            "user_note": existing.get("user_note"),
        }

    return {
        **computed,
        "draft_id": existing["draft_id"],
        "user_note": existing.get("user_note"),
    }
