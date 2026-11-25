"""台灣證券交易所（TWSE）與櫃買中心（TPEx）除權息公司行動解析器。

僅處理公開市場除權息資訊，全面使用 Decimal 精確解析，不含任何私人帳本欄位。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import re
from typing import Any, Callable, Iterable
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import NAMESPACE_URL, uuid5

ZERO = Decimal("0")
DEFAULT_PAR_VALUE = Decimal("10")

TWSE_EX_PREVIEW_URL = "https://www.twse.com.tw/rwd/zh/exRight/TWT48U"
TWSE_EX_RESULT_URL = "https://www.twse.com.tw/rwd/zh/exRight/TWT49U"
TPEX_EX_PREVIEW_URL = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_exright_preannounce"
TPEX_EX_RESULT_URL = "https://www.tpex.org.tw/www/zh-tw/exright/dailyquo"


@dataclass(frozen=True)
class CorporateActionRecord:
    """標準化公共公司行動紀錄（現金股利與股票股利拆分為獨立紀錄）。"""

    action_id: str
    symbol: str
    market: str
    security_type: str
    ex_date: date
    payment_date: date | None
    action_type: str
    cash_dividend_per_share: Decimal
    stock_dividend_ratio: Decimal
    par_value: Decimal | None
    source_name: str
    source_updated_at: datetime


def _action_uuid(symbol: str, ex_date: date, action_type: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"janus-corp-action/{symbol}/{ex_date.isoformat()}/{action_type}"))


def _parse_decimal(raw: Any, default: Decimal | None = ZERO) -> Decimal | None:
    if raw is None:
        return default
    text = str(raw).strip().replace(",", "")
    if not text or text in {"-", "--", "N/A", "null", "無", "尚未公告"}:
        return default
    try:
        value = Decimal(text)
    except InvalidOperation:
        return default
    if not value.is_finite() or value < ZERO:
        return default
    return value


def _parse_tw_date(raw: Any) -> date | None:
    """解析民國日期（如 115年09月17日、115/09/17、1150917）或西元 YYYY-MM-DD / YYYYMMDD。"""
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or text in {"-", "--", "N/A", "null", "尚未公告"}:
        return None
    match_roc_cjk = re.fullmatch(r"(\d{2,3})年(\d{1,2})月(\d{1,2})日", text)
    if match_roc_cjk:
        y, m, d = (int(match_roc_cjk.group(1)) + 1911, int(match_roc_cjk.group(2)), int(match_roc_cjk.group(3)))
        return date(y, m, d)
    normalized = text.replace("/", "-")
    if normalized.isdigit() and len(normalized) == 8:
        return date(int(normalized[:4]), int(normalized[4:6]), int(normalized[6:]))
    if normalized.isdigit() and len(normalized) == 7:
        return date(int(normalized[:3]) + 1911, int(normalized[3:5]), int(normalized[5:]))
    if re.fullmatch(r"\d{2,3}-\d{1,2}-\d{1,2}", normalized):
        y, m, d = (int(part) for part in normalized.split("-"))
        return date(y + 1911, m, d)
    try:
        return date.fromisoformat(normalized)
    except ValueError:
        return None


def _pick(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
    return None


def _infer_security_type(symbol: str, *, name: str = "", explicit: str | None = None) -> str:
    if explicit in {"common_stock", "financial", "etf", "reit", "ky_stock"}:
        return explicit
    upper = symbol.strip().upper()
    if re.fullmatch(r"00\d{2,4}[A-Z]?", upper):
        return "etf"
    if upper.endswith("T1") or "REIT" in name.upper():
        return "reit"
    if "-KY" in name.upper():
        return "ky_stock"
    return "common_stock"


def _build_split_records(
    *,
    symbol: str,
    market: str,
    security_type: str,
    ex_date: date,
    payment_date: date | None,
    cash_per_share: Decimal,
    stock_ratio: Decimal,
    par_value: Decimal | None,
    source_name: str,
    observed_at: datetime,
) -> list[CorporateActionRecord]:
    records: list[CorporateActionRecord] = []
    if cash_per_share > ZERO:
        records.append(
            CorporateActionRecord(
                action_id=_action_uuid(symbol, ex_date, "CASH_DIVIDEND"),
                symbol=symbol,
                market=market,
                security_type=security_type,
                ex_date=ex_date,
                payment_date=payment_date,
                action_type="CASH_DIVIDEND",
                cash_dividend_per_share=cash_per_share,
                stock_dividend_ratio=ZERO,
                par_value=par_value,
                source_name=source_name,
                source_updated_at=observed_at,
            )
        )
    if stock_ratio > ZERO:
        records.append(
            CorporateActionRecord(
                action_id=_action_uuid(symbol, ex_date, "STOCK_DIVIDEND"),
                symbol=symbol,
                market=market,
                security_type=security_type,
                ex_date=ex_date,
                payment_date=payment_date,
                action_type="STOCK_DIVIDEND",
                cash_dividend_per_share=ZERO,
                stock_dividend_ratio=stock_ratio,
                par_value=par_value,
                source_name=source_name,
                source_updated_at=observed_at,
            )
        )
    return records


def _extract_dict_rows(document: Any) -> list[dict[str, Any]]:
    if isinstance(document, list):
        return [item for item in document if isinstance(item, dict)]
    if isinstance(document, dict):
        if isinstance(document.get("tables"), list) and document["tables"]:
            table = document["tables"][0]
            fields = table.get("fields") or []
            return [dict(zip(fields, row, strict=False)) for row in table.get("data", [])]
        if isinstance(document.get("data"), list):
            fields = document.get("fields") or []
            if fields and document["data"] and isinstance(document["data"][0], list):
                return [dict(zip(fields, row, strict=False)) for row in document["data"]]
            return [item for item in document["data"] if isinstance(item, dict)]
    return []


def parse_twse_ex_dividend_rows(
    payload: bytes,
    *,
    source_name: str = "TWSE",
    observed_at: datetime | None = None,
) -> tuple[CorporateActionRecord, ...]:
    """解析 TWSE TWT48U / TWT49U 除權息 JSON，現金與股票拆為獨立事件。"""
    doc = json.loads(payload)
    now = observed_at or datetime.now(timezone.utc)
    records: list[CorporateActionRecord] = []
    for row in _extract_dict_rows(doc):
        symbol = str(_pick(row, "symbol", "Code", "股票代號", "公司代號", "證券代號") or "").strip().upper()
        if not re.fullmatch(r"[0-9A-Z]{4,8}", symbol):
            continue
        ex_date = _parse_tw_date(_pick(row, "ex_date", "除權息日期", "除息日期", "除權日期", "日期"))
        if ex_date is None:
            continue
        payment_date = _parse_tw_date(_pick(row, "payment_date", "發放日", "現金股利發放日", "股利發放日"))
        name = str(_pick(row, "company_name", "Name", "名稱", "股票名稱", "公司名稱") or "").strip()
        security_type = _infer_security_type(symbol, name=name, explicit=_pick(row, "security_type"))
        par_value = _parse_decimal(_pick(row, "par_value", "面額"), default=DEFAULT_PAR_VALUE)

        cash_per_share = _parse_decimal(
            _pick(row, "cash_dividend_per_share", "現金股利", "每股現金股利", "權值+息值", "息值"),
            default=ZERO,
        ) or ZERO
        # 優先採用權威配股率（股／每股）；若僅提供每張配股數（千股為單位）則換算成每股比率。
        stock_ratio = _parse_decimal(_pick(row, "stock_dividend_ratio", "無償配股率", "配股率"), default=None)
        if stock_ratio is None:
            per_thousand = _parse_decimal(_pick(row, "每仟股無償配股數", "每千股配股"), default=None)
            if per_thousand is not None:
                stock_ratio = per_thousand / Decimal("1000")
            else:
                stock_yuan = _parse_decimal(_pick(row, "股票股利", "盈餘配股", "公積配股"), default=ZERO) or ZERO
                denom = par_value if par_value and par_value > ZERO else DEFAULT_PAR_VALUE
                stock_ratio = stock_yuan / denom if stock_yuan > ZERO else ZERO

        records.extend(
            _build_split_records(
                symbol=symbol,
                market="TWSE",
                security_type=security_type,
                ex_date=ex_date,
                payment_date=payment_date,
                cash_per_share=cash_per_share,
                stock_ratio=stock_ratio,
                par_value=par_value,
                source_name=source_name,
                observed_at=now,
            )
        )
    return tuple(records)


def parse_tpex_ex_dividend_rows(
    payload: bytes,
    *,
    source_name: str = "TPEX",
    observed_at: datetime | None = None,
) -> tuple[CorporateActionRecord, ...]:
    """解析 TPEx 除權息 JSON（相容 OpenAPI 與每日報表表格欄位）。"""
    doc = json.loads(payload)
    now = observed_at or datetime.now(timezone.utc)
    records: list[CorporateActionRecord] = []
    for row in _extract_dict_rows(doc):
        symbol = str(
            _pick(row, "symbol", "SecuritiesCompanyCode", "代號", "股票代號", "公司代號") or ""
        ).strip().upper()
        if not re.fullmatch(r"[0-9A-Z]{4,8}", symbol):
            continue
        ex_date = _parse_tw_date(_pick(row, "ex_date", "ExdividendDate", "除權息日期", "除息交易日", "除權交易日"))
        if ex_date is None:
            continue
        payment_date = _parse_tw_date(_pick(row, "payment_date", "PaymentDate", "發放日", "現金股利發放日"))
        name = str(_pick(row, "company_name", "CompanyName", "名稱", "公司名稱") or "").strip()
        security_type = _infer_security_type(symbol, name=name, explicit=_pick(row, "security_type"))
        par_value = _parse_decimal(_pick(row, "par_value", "面額"), default=DEFAULT_PAR_VALUE)

        cash_per_share = _parse_decimal(
            _pick(row, "cash_dividend_per_share", "CashDividend", "現金股利", "息值"),
            default=ZERO,
        ) or ZERO
        stock_ratio = _parse_decimal(_pick(row, "stock_dividend_ratio", "StockDividendRatio", "配股率", "無償配股率"), default=None)
        if stock_ratio is None:
            per_thousand = _parse_decimal(_pick(row, "每仟股無償配股數", "StockDividendSharesPerThousand"), default=None)
            if per_thousand is not None:
                stock_ratio = per_thousand / Decimal("1000")
            else:
                stock_yuan = _parse_decimal(_pick(row, "StockDividend", "股票股利"), default=ZERO) or ZERO
                denom = par_value if par_value and par_value > ZERO else DEFAULT_PAR_VALUE
                stock_ratio = stock_yuan / denom if stock_yuan > ZERO else ZERO

        records.extend(
            _build_split_records(
                symbol=symbol,
                market="TPEX",
                security_type=security_type,
                ex_date=ex_date,
                payment_date=payment_date,
                cash_per_share=cash_per_share,
                stock_ratio=stock_ratio,
                par_value=par_value,
                source_name=source_name,
                observed_at=now,
            )
        )
    return tuple(records)


def _default_https_get(url: str) -> bytes:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (compatible; JanusAI-CorporateActions/1.0)",
        },
    )
    with urlopen(request, timeout=25) as response:
        return response.read()


def fetch_twse_ex_dividend_preview(
    *,
    transport: Callable[[str], bytes] | None = None,
) -> tuple[CorporateActionRecord, ...]:
    """抓取 TWSE 除權息預告表（TWT48U），支援注入 transport 進行離線測試。"""
    url = f"{TWSE_EX_PREVIEW_URL}?{urlencode({'response': 'json'})}"
    raw = (transport or _default_https_get)(url)
    return parse_twse_ex_dividend_rows(raw, source_name="TWSE_TWT48U")


def fetch_tpex_ex_dividend_preview(
    *,
    transport: Callable[[str], bytes] | None = None,
) -> tuple[CorporateActionRecord, ...]:
    """抓取 TPEx 除權息預告資料，支援注入 transport 進行離線測試。"""
    raw = (transport or _default_https_get)(TPEX_EX_PREVIEW_URL)
    return parse_tpex_ex_dividend_rows(raw, source_name="TPEX_OPENAPI")


def merge_corporate_actions(
    *batches: Iterable[CorporateActionRecord],
) -> tuple[CorporateActionRecord, ...]:
    """依 (symbol, ex_date, action_type) 去重，保留較新或已有發放日之紀錄。"""
    merged: dict[tuple[str, date, str], CorporateActionRecord] = {}
    for batch in batches:
        for item in batch:
            key = (item.symbol, item.ex_date, item.action_type)
            existing = merged.get(key)
            if existing is None:
                merged[key] = item
                continue
            # 優先保留有 payment_date 或 source_updated_at 較新的資料
            if (existing.payment_date is None and item.payment_date is not None) or (
                item.source_updated_at >= existing.source_updated_at
                and not (existing.payment_date is not None and item.payment_date is None)
            ):
                merged[key] = item
    return tuple(sorted(merged.values(), key=lambda x: (x.ex_date, x.symbol, x.action_type)))
