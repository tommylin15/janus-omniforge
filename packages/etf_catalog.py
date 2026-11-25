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
import logging
import os
import re
from time import time
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen


ISIN_URL = "https://isin.twse.com.tw/isin/class_main.jsp"
TWSE_OPENAPI_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap47_L"
DEFAULT_SHIOAJI_PROXY_URL = "https://shioaji-quote-proxy-131494961796.asia-east1.run.app"
_PROXY_ALLOWED_HOSTS = frozenset({"openapi.twse.com.tw", "isin.twse.com.tw"})
_TWD_CURRENCIES = frozenset({"新台幣", "新臺幣", "台幣", "臺幣", "TWD", "NTD"})
_BIG5_CHARSETS = frozenset({"big5", "ms950", "cp950", "big5hkscs", "big5-hkscs"})
MARKETS = {"TWSE": "1", "TPEX": "2"}
_CODE = re.compile(r"^0[0-9A-Z]{3,7}$")
_MARKET_CACHE: dict[tuple[str, int, date], list[OfficialEtf]] = {}
LOGGER = logging.getLogger("janus.etf_catalog")


class EtfCatalogUnavailable(RuntimeError):
    """An official catalogue read or schema check failed."""


class _UnapprovedProxyEndpoint(EtfCatalogUnavailable):
    """Raised when proxy endpoint fails strict allowlist validation."""


@dataclass(frozen=True)
class OfficialEtf:
    symbol: str
    name: str
    market: str
    listed_on: date
    source_id: str = "twse_isin_etf"


def clear_cache() -> None:
    _lookup_cached.cache_clear()
    _MARKET_CACHE.clear()


def _cache_get(key: str, hour_bucket: int, day: date) -> list[OfficialEtf] | None:
    records = _MARKET_CACHE.get((key, hour_bucket, day))
    return list(records) if records is not None else None


def _cache_set(key: str, hour_bucket: int, day: date, records: list[OfficialEtf]) -> None:
    stale_keys = [k for k in _MARKET_CACHE if k[0] == key and (k[1], k[2]) != (hour_bucket, day)]
    for stale in stale_keys:
        _MARKET_CACHE.pop(stale, None)
    _MARKET_CACHE[(key, hour_bucket, day)] = list(records)


def _should_use_proxy(opener, use_proxy: bool | None) -> bool:
    if use_proxy is not None:
        return bool(use_proxy)
    if opener is not None and opener is not urlopen:
        return False
    if os.getenv("JANUS_ETF_PROXY_ENABLED", "true").lower() != "true":
        return False
    return bool(
        os.getenv("K_SERVICE")
        or os.getenv("CLOUD_RUN_JOB")
        or os.getenv("JANUS_ETF_PROXY_FORCE", "").lower() == "true"
    )


def _proxy_base_url() -> str:
    raw = os.getenv("JANUS_SHIOAJI_PROXY_URL", DEFAULT_SHIOAJI_PROXY_URL).strip().rstrip("/")
    parsed = urlsplit(raw)
    expected = urlsplit(DEFAULT_SHIOAJI_PROXY_URL)
    if parsed.scheme != "https" or parsed.hostname != expected.hostname or parsed.path not in ("", "/"):
        raise _UnapprovedProxyEndpoint("unapproved ETF proxy endpoint")
    return raw


def _proxy_identity_token(audience: str, *, opener=None) -> str:
    actual_opener = urlopen if opener is None else opener
    endpoint = (
        "http://metadata.google.internal/computeMetadata/v1/instance/"
        "service-accounts/default/identity?" + urlencode({"audience": audience, "format": "full"})
    )
    request = Request(endpoint, headers={"Metadata-Flavor": "Google"})
    with actual_opener(request, timeout=2.0) as response:
        token = response.read(8192).decode("utf-8").strip()
    if not token or len(token) >= 8192:
        raise EtfCatalogUnavailable("ETF proxy identity token unavailable")
    return token


def _fetch_text_via_proxy(url: str, *, timeout_seconds: float, opener=None) -> str:
    actual_opener = urlopen if opener is None else opener
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or host not in _PROXY_ALLOWED_HOSTS or parsed.port not in (None, 443):
        raise _UnapprovedProxyEndpoint("unapproved ETF upstream URL")
    base_url = _proxy_base_url()
    token = _proxy_identity_token(base_url, opener=actual_opener)
    upstream_timeout = max(2.0, min(20.0, float(timeout_seconds)))
    request_timeout = max(float(timeout_seconds) + 4.0, 8.0)
    payload = json.dumps({"url": url, "timeout": upstream_timeout}).encode("utf-8")
    request = Request(
        base_url + "/fetch",
        data=payload,
        method="POST",
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    with actual_opener(request, timeout=request_timeout) as response:
        raw = response.read(4_000_001)
    if len(raw) > 4_000_000:
        raise EtfCatalogUnavailable("oversized ETF proxy response")
    envelope = json.loads(raw.decode("utf-8"))
    if (
        not isinstance(envelope, dict)
        or envelope.get("status") != "success"
        or envelope.get("http_status") != 200
        or not isinstance(envelope.get("body"), str)
    ):
        raise EtfCatalogUnavailable("ETF proxy upstream failed")
    body = envelope["body"]
    if len(body) > 2_000_000:
        raise EtfCatalogUnavailable("oversized ETF proxy body")
    return body


def _parse_official_date(raw: object, *, today: date) -> date | None:
    text = str(raw or "").strip()
    if not text:
        return None
    parsed: date | None = None
    try:
        if re.fullmatch(r"\d{8}", text):
            parsed = date(int(text[:4]), int(text[4:6]), int(text[6:8]))
        elif re.fullmatch(r"\d{7}", text):
            parsed = date(int(text[:3]) + 1911, int(text[3:5]), int(text[5:7]))
        else:
            match = re.fullmatch(r"(\d{2,4})[/-](\d{1,2})[/-](\d{1,2})", text)
            if match:
                year = int(match.group(1))
                if year < 1900:
                    year += 1911
                parsed = date(year, int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None
    if parsed is None or parsed < date(1990, 1, 1) or parsed > today:
        return None
    return parsed


def _decode_isin_bytes(body: bytes, declared_charset: str | None) -> str:
    declared = (declared_charset or "").strip().lower()
    if not declared or declared in _BIG5_CHARSETS:
        encodings = ("cp950", "big5")
    else:
        encodings = (declared, "cp950", "big5")
    for encoding in encodings:
        try:
            return body.decode(encoding, errors="strict")
        except (UnicodeError, LookupError):
            continue
    raise UnicodeError("unable to decode official ISIN HTML")


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
        listed_on = _parse_official_date(listed, today=today)
        if (not looks_like_etf_code(code) or not name or "\ufffd" in name
                or len(name) > 100 or listed_on is None
                or not re.fullmatch(r"TW[0-9A-Z]{10}", row[1])):
            continue
        record = OfficialEtf(code, name, market, listed_on)
        if code in found and found[code] != record:
            raise EtfCatalogUnavailable("conflicting official ETF identity")
        found[code] = record
    if not found:
        raise EtfCatalogUnavailable("empty or changed official ETF catalogue")
    return sorted(found.values(), key=lambda item: item.symbol)


def fetch_isin_etfs(
    market: str,
    *,
    timeout_seconds: float = 4.0,
    opener=None,
    use_proxy: bool | None = None,
) -> list[OfficialEtf]:
    if market not in MARKETS:
        raise ValueError("invalid ETF market")
    actual_opener = urlopen if opener is None else opener
    hour_bucket = int(time() // 3600)
    today = date.today()
    cache_key = f"isin:{market}"
    can_cache = (opener is None or opener is urlopen) and use_proxy is None
    if can_cache:
        cached = _cache_get(cache_key, hour_bucket, today)
        if cached is not None:
            return cached
    url = f"{ISIN_URL}?Page=1&chklike=Y&issuetype=I&market={MARKETS[market]}"
    if _should_use_proxy(opener, use_proxy):
        try:
            body_text = _fetch_text_via_proxy(url, timeout_seconds=timeout_seconds, opener=actual_opener)
            records = parse_isin_etfs(body_text, market=market, as_of=today)
            if can_cache:
                _cache_set(cache_key, hour_bucket, today, records)
            return records
        except _UnapprovedProxyEndpoint:
            raise
        except (EtfCatalogUnavailable, OSError, UnicodeError, ValueError, RuntimeError) as exc:
            LOGGER.warning("ISIN ETF proxy fetch failed (%s); falling back to direct", type(exc).__name__)
    request = Request(url, headers={"User-Agent": "Janus-Research/1.0", "Accept": "text/html"})
    try:
        with actual_opener(request, timeout=timeout_seconds) as response:
            body = response.read(2_000_001)
            if len(body) > 2_000_000:
                raise EtfCatalogUnavailable("oversized ETF catalogue")
            # The official ISIN directory is served in Big5/CP950 on some hosts.
            declared = response.headers.get_content_charset() if getattr(response, "headers", None) else None
            decoded = _decode_isin_bytes(body, declared)
        records = parse_isin_etfs(decoded, market=market, as_of=today)
        if can_cache:
            _cache_set(cache_key, hour_bucket, today, records)
        return records
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
        code = str(item.get("基金代號") or item.get("證券代號") or "").strip().upper()
        name = str(item.get("基金簡稱") or "").strip()
        listed = str(item.get("上市日期") or "").strip()
        currency = str(item.get("計幣別") or "").strip()
        if currency and currency.upper() not in _TWD_CURRENCIES:
            continue
        if code.endswith(("C", "K")) or not looks_like_etf_code(code) or not name or "\ufffd" in name or len(name) > 100:
            continue
        listing = _parse_official_date(listed, today=today)
        if listing is None:
            continue
        record = OfficialEtf(code, name, "TWSE", listing, "twse_openapi_etf")
        if code in found and found[code] != record:
            raise EtfCatalogUnavailable("conflicting TWSE ETF identity")
        found[code] = record
    if not found:
        raise EtfCatalogUnavailable("invalid or empty TWSE ETF JSON")
    return sorted(found.values(), key=lambda item: item.symbol)


def fetch_twse_openapi_etfs(
    *,
    timeout_seconds: float = 4.0,
    opener=None,
    use_proxy: bool | None = None,
) -> list[OfficialEtf]:
    actual_opener = urlopen if opener is None else opener
    hour_bucket = int(time() // 3600)
    today = date.today()
    cache_key = "twse_openapi"
    can_cache = (opener is None or opener is urlopen) and use_proxy is None
    if can_cache:
        cached = _cache_get(cache_key, hour_bucket, today)
        if cached is not None:
            return cached
    if _should_use_proxy(opener, use_proxy):
        try:
            body_text = _fetch_text_via_proxy(TWSE_OPENAPI_URL, timeout_seconds=timeout_seconds, opener=actual_opener)
            records = parse_twse_openapi_etfs(json.loads(body_text.lstrip("\ufeff")), as_of=today)
            if can_cache:
                _cache_set(cache_key, hour_bucket, today, records)
            return records
        except _UnapprovedProxyEndpoint:
            raise
        except (EtfCatalogUnavailable, OSError, UnicodeError, ValueError, RuntimeError) as exc:
            LOGGER.warning("TWSE OpenAPI ETF proxy fetch failed (%s); falling back to direct", type(exc).__name__)
    request = Request(TWSE_OPENAPI_URL, headers={"User-Agent": "Janus-Research/1.0", "Accept": "application/json"})
    try:
        with actual_opener(request, timeout=timeout_seconds) as response:
            body = response.read(2_000_001)
        if len(body) > 2_000_000:
            raise EtfCatalogUnavailable("oversized TWSE ETF catalogue")
        records = parse_twse_openapi_etfs(json.loads(body.decode("utf-8-sig")), as_of=today)
        if can_cache:
            _cache_set(cache_key, hour_bucket, today, records)
        return records
    except (OSError, UnicodeError, ValueError) as exc:
        raise EtfCatalogUnavailable("TWSE ETF OpenAPI unavailable") from exc


def fetch_market_etfs(market: str, *, timeout_seconds: float = 4.0) -> list[OfficialEtf]:
    if market == "TWSE":
        try:
            return fetch_twse_openapi_etfs(timeout_seconds=timeout_seconds)
        except _UnapprovedProxyEndpoint:
            raise
        except EtfCatalogUnavailable:
            pass
    return fetch_isin_etfs(market, timeout_seconds=timeout_seconds)

@lru_cache(maxsize=8)
def _lookup_cached(symbol: str, hour_bucket: int) -> OfficialEtf | None:
    # A failed listed-market source must not prevent an OTC ETF from resolving.
    unavailable = False
    for market in MARKETS:
        try:
            records = fetch_market_etfs(market, timeout_seconds=4.0)
        except _UnapprovedProxyEndpoint:
            raise
        except EtfCatalogUnavailable:
            unavailable = True
            continue
        for record in records:
            if record.symbol == symbol:
                return record
        if market == "TWSE":
            # The official fund OpenAPI is monthly: a newly listed ETF may
            # appear on ISIN before the monthly file is refreshed.
            try:
                for record in fetch_isin_etfs("TWSE", timeout_seconds=4.0):
                    if record.symbol == symbol:
                        return record
            except _UnapprovedProxyEndpoint:
                raise
            except EtfCatalogUnavailable:
                unavailable = True
    if unavailable:
        raise EtfCatalogUnavailable("one or more official ETF markets unavailable")
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
        if market == "TWSE":
            # The official OpenAPI is updated monthly, but ISIN may already
            # list newly admitted ETFs. Preserve the fuller ISIN set while
            # preferring the Chinese name from OpenAPI for matching symbols.
            try:
                fresh = fetch_isin_etfs("TWSE", timeout_seconds=8.0)
                rows = list({
                    **{item.symbol: item for item in fresh},
                    **{item.symbol: item for item in rows},
                }.values())
            except EtfCatalogUnavailable:
                pass
        # Not a volume threshold: prevents a partial HTML document from
        # replacing a previously complete market catalogue.
        if len(rows) < 10:
            raise EtfCatalogUnavailable("suspiciously small official ETF catalogue")
        output.extend(rows)
    if len({item.symbol for item in output}) != len(output):
        raise EtfCatalogUnavailable("duplicate ETF symbol across markets")
    return output
