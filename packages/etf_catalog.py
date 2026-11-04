"""Bounded, official TWSE ISIN catalogue for tradable listed/OTC ETFs.

This is a *tradeable identity* source, never the ordinary-equity model universe.
The ISIN service may return Big5 HTML; nothing is inferred from a ticker prefix
alone. Source failures never invent an instrument or an enabled state.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from html.parser import HTMLParser
import json
import re
from time import time
from urllib.request import Request, urlopen


ISIN_URL = "https://isin.twse.com.tw/isin/class_main.jsp"
TWSE_OPENAPI_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap47_L"
MARKETS = {"TWSE": "1", "TPEX": "2"}
_CODE = re.compile(r"^0[0-9A-Z]{3,7}$")
_DATE = re.compile(r"^\d{4}/\d{2}/\d{2}$")


class EtfCatalogUnavailable(RuntimeError):
    """An official catalogue read or schema check failed."""


@dataclass(frozen=True)
class OfficialEtf:
    symbol: str
    name: str
    market: str
    listed_on: date
    source_id: str = "twse_isin_etf"


class _TableRows(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = []

    def handle_data(self, value):
        if self._cell is not None:
            self._cell.append(value)

    def handle_endtag(self, tag):
        if tag in {"td", "th"} and self._cell is not None and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None


def looks_like_etf_code(text: str) -> bool:
    return bool(_CODE.fullmatch(text.strip().upper()))


def parse_isin_etfs(html: str, *, market: str, as_of: date | None = None) -> list[OfficialEtf]:
    """Parse only explicit ETF rows with verified exchange and listing date."""
    if market not in MARKETS:
        raise ValueError("invalid ETF market")
    parser = _TableRows()
    parser.feed(html)
    found: dict[str, OfficialEtf] = {}
    today = as_of or date.today()
    market_label = "上市" if market == "TWSE" else "上櫃"
    for row in parser.rows:
        # ordinal, ISIN, code, name, market, type, industry, listed date, CFI, note
        if len(row) < 9 or row[4] != market_label or row[5].upper() != "ETF":
            continue
        code, name, listed = row[2].upper(), row[3].strip(), row[7]
        # These series are foreign-currency classes; the Owner ledger is TWD-only.
        if code.endswith(("C", "K")):
            continue
        if (not looks_like_etf_code(code) or not name or "\ufffd" in name
                or len(name) > 100 or not _DATE.fullmatch(listed)
                or not re.fullmatch(r"TW[0-9A-Z]{10}", row[1])):
            continue
        try:
            listed_on = date.fromisoformat(listed.replace("/", "-"))
        except ValueError:
            continue
        if listed_on > today:
            continue
        record = OfficialEtf(code, name, market, listed_on)
        if code in found and found[code] != record:
            raise EtfCatalogUnavailable("conflicting official ETF identity")
        found[code] = record
    if not found:
        raise EtfCatalogUnavailable("empty or changed official ETF catalogue")
    return sorted(found.values(), key=lambda item: item.symbol)


def fetch_isin_etfs(market: str, *, timeout_seconds: float = 4.0, opener=urlopen) -> list[OfficialEtf]:
    if market not in MARKETS:
        raise ValueError("invalid ETF market")
    url = f"{ISIN_URL}?Page=1&chklike=Y&issuetype=3&market={MARKETS[market]}"
    request = Request(url, headers={"User-Agent": "Janus-Research/1.0", "Accept": "text/html"})
    try:
        with opener(request, timeout=timeout_seconds) as response:
            body = response.read(2_000_001)
            if len(body) > 2_000_000:
                raise EtfCatalogUnavailable("oversized ETF catalogue")
            # The official ISIN directory is served in Big5 on some hosts.
            declared = response.headers.get_content_charset() or "big5"
            try:
                decoded = body.decode(declared, errors="strict")
            except (UnicodeError, LookupError):
                decoded = body.decode("big5", errors="strict")
        return parse_isin_etfs(decoded, market=market)
    except (OSError, UnicodeError, ValueError) as exc:
        raise EtfCatalogUnavailable("official ETF catalogue unavailable") from exc




def parse_twse_openapi_etfs(payload: object, *, as_of: date | None = None) -> list[OfficialEtf]:
    """TWSE's official fund basic-info JSON (ETF series with listing dates)."""
    if not isinstance(payload, list):
        raise EtfCatalogUnavailable("invalid TWSE ETF JSON")
    found: dict[str, OfficialEtf] = {}
    today = as_of or date.today()
    for item in payload:
        if not isinstance(item, dict):
            continue
        code = str(item.get("基金代號", "")).strip().upper()
        name = str(item.get("基金簡稱", "")).strip()
        listed = str(item.get("上市日期", "")).strip()
        if code.endswith(("C", "K")) or not looks_like_etf_code(code) or not name or len(name) > 100:
            continue
        try:
            # The OpenAPI dataset has used slash-separated Gregorian dates.
            listing = date.fromisoformat(listed.replace("/", "-"))
        except ValueError:
            continue
        if listing > today or listing < date(1990, 1, 1):
            continue
        record = OfficialEtf(code, name, "TWSE", listing, "twse_openapi_etf")
        if code in found and found[code] != record:
            raise EtfCatalogUnavailable("conflicting TWSE ETF identity")
        found[code] = record
    if not found:
        raise EtfCatalogUnavailable("invalid or empty TWSE ETF JSON")
    return sorted(found.values(), key=lambda item: item.symbol)


def fetch_twse_openapi_etfs(*, timeout_seconds: float = 4.0, opener=urlopen) -> list[OfficialEtf]:
    request = Request(TWSE_OPENAPI_URL, headers={"User-Agent": "Janus-Research/1.0", "Accept": "application/json"})
    try:
        with opener(request, timeout=timeout_seconds) as response:
            body = response.read(2_000_001)
        if len(body) > 2_000_000:
            raise EtfCatalogUnavailable("oversized TWSE ETF catalogue")
        return parse_twse_openapi_etfs(json.loads(body.decode("utf-8-sig")))
    except (OSError, UnicodeError, ValueError) as exc:
        raise EtfCatalogUnavailable("TWSE ETF OpenAPI unavailable") from exc


def fetch_market_etfs(market: str, *, timeout_seconds: float = 4.0) -> list[OfficialEtf]:
    if market == "TWSE":
        try:
            return fetch_twse_openapi_etfs(timeout_seconds=timeout_seconds)
        except EtfCatalogUnavailable:
            pass
    return fetch_isin_etfs(market, timeout_seconds=timeout_seconds)

@lru_cache(maxsize=8)
def _lookup_cached(symbol: str, hour_bucket: int) -> OfficialEtf | None:
    # At most two bounded official reads per cold-cache hour; no fuzzy ticker admission.
    for market in MARKETS:
        for record in fetch_market_etfs(market):
            if record.symbol == symbol:
                return record
    return None


def find_official_etf(symbol: str) -> OfficialEtf | None:
    normalized = symbol.strip().upper()
    if not looks_like_etf_code(normalized):
        return None
    return _lookup_cached(normalized, int(time() // 3600))


def weekly_official_catalogue() -> list[OfficialEtf]:
    """Both markets must be readable before a weekly snapshot is accepted."""
    output: list[OfficialEtf] = []
    for market in MARKETS:
        rows = fetch_market_etfs(market, timeout_seconds=8.0)
        # Not a volume threshold: prevents a partial HTML document from
        # replacing a previously complete market catalogue.
        if len(rows) < 10:
            raise EtfCatalogUnavailable("suspiciously small official ETF catalogue")
        output.extend(rows)
    if len({item.symbol for item in output}) != len(output):
        raise EtfCatalogUnavailable("duplicate ETF symbol across markets")
    return output
