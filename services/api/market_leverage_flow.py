"""Bounded official TWSE EOD leverage and institutional cash flow.

Public *listed-market* research context, never intraday, never an estimate from
net shares. No new Scheduler, broker subscription, or owner data reads.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from threading import Lock
from time import monotonic
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo
import json

TAIPEI = ZoneInfo("Asia/Taipei")
_BASE = "https://www.twse.com.tw/rwd/zh"
_CACHE_LOCK = Lock()
_CACHE: dict[str, object] = {}


def _official_json(url: str) -> dict:
    """Only module-owned fixed TWSE hosts/paths and numeric dates are used."""
    request = Request(url, headers={"Accept": "application/json",
                                    "User-Agent": "JanusResearch/1.0"})
    with urlopen(request, timeout=2.5) as response:
        raw = response.read(256 * 1024 + 1)
    if len(raw) > 256 * 1024:
        raise ValueError("official response exceeds bounded size")
    result = json.loads(raw.decode("utf-8-sig"))
    return result if isinstance(result, dict) else {}


def _valid_day(payload: dict, day: date) -> bool:
    if payload.get("stat") != "OK":
        return False
    declared = str(payload.get("date") or "").replace("/", "").replace("-", "")
    if not declared:
        # A response with no date cannot be safely assigned to a requested day.
        return False
    roc = f"{day.year - 1911:03d}{day.month:02d}{day.day:02d}"
    return declared in {day.strftime("%Y%m%d"), roc}


def _tables(payload: dict):
    if isinstance(payload.get("tables"), list):
        for table in payload["tables"]:
            if isinstance(table, dict):
                yield table
    if isinstance(payload.get("data"), list):
        yield payload


def _amount(value: object) -> Decimal | None:
    if value is None:
        return None
    normalized = str(value).strip().replace(",", "").replace("−", "-")
    if not normalized or normalized in {"-", "--", "—", "N/A"}:
        return None
    try:
        amount = Decimal(normalized)
        return amount if amount.is_finite() else None
    except (ValueError, InvalidOperation):
        return None


def parse_margin(payload: dict, day: date) -> dict | None:
    """Select only official *money* balance (thousand TWD), not share counts."""
    if not _valid_day(payload, day):
        return None
    for table in _tables(payload):
        fields = [str(f).replace(" ", "") for f in table.get("fields", [])]
        if not {"前日餘額", "今日餘額"}.issubset(fields):
            continue
        former, latter = fields.index("前日餘額"), fields.index("今日餘額")
        for row in table.get("data", []):
            if (not isinstance(row, list) or len(row) <= max(former, latter)
                    or "融資金額" not in str(row[0])
                    or not any(unit in str(row[0]) for unit in ("仟元", "千元"))):
                continue
            previous, current = _amount(row[former]), _amount(row[latter])
            if previous is None or current is None or min(previous, current) < 0:
                continue
            return {"date": day.isoformat(),
                    "balance_thousand_twd": str(current),
                    # Use TWSE's own "previous balance" because adjustments
                    # can revise previously published today balances.
                    "change_thousand_twd": str(current - previous),
                    "previous_balance_thousand_twd": str(previous)}
    return None


def parse_institutional(payload: dict, day: date) -> dict | None:
    """TWSE official buy/sell/net *TWD*, with dealer self+hedging combined."""
    if not _valid_day(payload, day):
        return None
    for table in _tables(payload):
        fields = [str(f).replace(" ", "") for f in table.get("fields", [])]
        net_index = next((i for i, name in enumerate(fields)
                          if "買賣超" in name or "買賣差額" in name), -1)
        if net_index < 0:
            continue
        values: dict[str, list[Decimal]] = {"foreign": [], "trust": [], "dealer": []}
        for row in table.get("data", []):
            if not isinstance(row, list) or len(row) <= net_index:
                continue
            name = str(row[0]).replace(" ", "")
            amount = _amount(row[net_index])
            if amount is None:
                continue
            if name.startswith("外資及陸資"):
                values["foreign"].append(amount)
            elif name.startswith("投信"):
                values["trust"].append(amount)
            elif name.startswith("自營商"):
                values["dealer"].append(amount)
        if not all(values.values()):
            continue
        # If a provider publishes both detailed and subtotal dealer rows,
        # do not count both. Prefer the two separately named official legs.
        dealers = values["dealer"]
        dealer_named = [row for row in table["data"] if isinstance(row, list)
                        and row and str(row[0]).replace(" ", "").startswith("自營商")]
        detail = [v for row, v in zip(dealer_named, dealers)
                  if "自行買賣" in str(row[0]) or "避險" in str(row[0])]
        dealer_total = sum(detail) if detail else dealers[0]
        return {"foreign": str(values["foreign"][0]),
                "trust": str(values["trust"][0]),
                "dealer": str(dealer_total)}
    return None


def collect_market_leverage_flow(today: date, *, fetcher=_official_json) -> dict:
    """At most 16 weekday margin days plus 7 weekday flow days."""
    weekdays = [today - timedelta(days=offset) for offset in range(26)
                if (today - timedelta(days=offset)).weekday() < 5][:16]

    def request(day: date, kind: str):
        path, params = (
            ("marginTrading/MI_MARGN", {"date": day.strftime("%Y%m%d"),
                                        "selectType": "MS", "response": "json"})
            if kind == "margin" else
            ("fund/BFI82U", {"dayDate": day.strftime("%Y%m%d"),
                             "type": "day", "response": "json"})
        )
        try:
            payload = fetcher(f"{_BASE}/{path}?{urlencode(params)}")
            return (day, kind, parse_margin(payload, day) if kind == "margin"
                    else parse_institutional(payload, day))
        except (OSError, TimeoutError, ValueError, TypeError):
            return (day, kind, None)

    tasks = [(day, "margin") for day in weekdays]
    tasks += [(day, "institutional") for day in weekdays[:7]]
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda args: request(*args), tasks))
    margin = [row for _, kind, row in results if kind == "margin" and row]
    margin = sorted(margin, key=lambda row: row["date"])[-10:]
    flow = sorted([(day.isoformat(), row) for day, kind, row in results
                   if kind == "institutional" and row], key=lambda pair: pair[0])
    previous = flow[-2][1] if len(flow) > 1 else {}
    current = flow[-1][1] if flow else {}
    items = []
    for kind in ("foreign", "trust", "dealer"):
        net = _amount(current.get(kind))
        earlier = _amount(previous.get(kind))
        items.append({"investor_type": kind,
                      "net_twd": str(net) if net is not None else None,
                      "previous_net_twd": str(earlier) if earlier is not None else None,
                      "delta_twd": str(net - earlier) if net is not None and earlier is not None else None})
    return {
        "source": "twse_official_eod",
        "scope": "TWSE_listed_only",
        "not_intraday": True,
        "margin": {
            "status": "available" if len(margin) == 10 else "partial" if margin else "missing",
            "as_of": margin[-1]["date"] if margin else None,
            "history": margin,
            "session_count": len(margin),
            "requested_sessions": 10,
            "unit": "thousand_TWD",
        },
        "institutional": {
            "status": "available" if len(flow) >= 2 else "partial" if flow else "missing",
            "as_of": flow[-1][0] if flow else None,
            "previous_as_of": flow[-2][0] if len(flow) > 1 else None,
            "unit": "TWD",
            "items": items,
        },
    }


def cached_market_leverage_flow() -> dict:
    """Process-local singleflight, hourly TTL; no per-minute official polling."""
    now = datetime.now(TAIPEI)
    with _CACHE_LOCK:
        if _CACHE.get("expires_at", 0) > monotonic():
            return _CACHE["result"]  # type: ignore[return-value]
        result = collect_market_leverage_flow(now.date())
        _CACHE.update(result=result, expires_at=monotonic() + 3600)
        return result
