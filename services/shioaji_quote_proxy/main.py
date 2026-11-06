"""Shioaji Real-time Quote Proxy on Cloud Run (asia-east1).

Provides high-frequency, low-latency market quote forwarding from SinoPac Shioaji
with automatic fallback to TWSE MIS. Scoped for private Cloud Run IAM callers.
"""

from __future__ import annotations

import json
import logging
import os
import re
from contextlib import asynccontextmanager
from threading import Lock
from time import monotonic
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

import httpx
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

ALLOWED_INTEL_HOSTS = frozenset({
    "blave.org",
    "www.blave.org",
    "api.blave.org",
    "atlas-ai-trading.com",
    "www.atlas-ai-trading.com",
    "daily-tw.up.railway.app",
    "gooaye.teamtaiwan.win",
    "xn--g10a.tw",
    "www.twse.com.tw",
    "openapi.twse.com.tw",
    "mis.twse.com.tw",
    "mops.twse.com.tw",
    "www.tpex.org.tw",
    "www.taifex.com.tw",
    "api.finmindtrade.com",
    "api.cnyes.com",
    "ws.api.cnyes.com",
    "news.cnyes.com",
    "money.udn.com",
    "www.moneydj.com",
    "statementdog.com",
    "histock.tw",
    "www.histock.tw",
    "tw.stock.yahoo.com",
    "query1.finance.yahoo.com",
})


class IntelFetchRequest(BaseModel):
    url: str
    timeout: float = 12.0
    headers: Optional[Dict[str, str]] = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
LOGGER = logging.getLogger("shioaji_proxy")
TAIWAN_TZ = timezone(timedelta(hours=8))

# Global client holder
CLIENT: Optional[ShioajiManager] = None


def resolve_credentials() -> tuple[str, str, str, str]:
    """Extract Shioaji credentials from bundle JSON or direct environment variables."""
    api_key = os.getenv("SHIOAJI_API_KEY", "").strip()
    secret_key = os.getenv("SHIOAJI_SECRET_KEY", "").strip()
    person_id = os.getenv("SHIOAJI_PERSON_ID", "").strip()
    password = os.getenv("SHIOAJI_PASSWORD", "").strip()

    for bundle_var in ("JANUS_RUNTIME_BUNDLE", "JANUS_API_POSTGRES_BUNDLE"):
        raw = os.getenv(bundle_var, "").strip()
        if not raw:
            continue
        try:
            bundle = json.loads(raw)
            if isinstance(bundle, dict):
                if not api_key:
                    for k in ("shioaji_api_key", "SHIOAJI_API_KEY", "sinopac_api_key", "SINOPAC_API_KEY", "shioaji_key"):
                        if str(bundle.get(k, "")).strip():
                            api_key = str(bundle[k]).strip()
                            break
                if not secret_key:
                    for k in ("shioaji_secret_key", "SHIOAJI_SECRET_KEY", "sinopac_secret_key", "SINOPAC_SECRET_KEY", "shioaji_secret"):
                        if str(bundle.get(k, "")).strip():
                            secret_key = str(bundle[k]).strip()
                            break
                if not person_id:
                    for k in ("shioaji_person_id", "SHIOAJI_PERSON_ID", "sinopac_person_id", "person_id"):
                        if str(bundle.get(k, "")).strip():
                            person_id = str(bundle[k]).strip()
                            break
                if not password:
                    for k in ("shioaji_password", "SHIOAJI_PASSWORD", "sinopac_password", "password"):
                        if str(bundle.get(k, "")).strip():
                            password = str(bundle[k]).strip()
                            break
        except Exception as err:
            LOGGER.warning("Could not parse %s as JSON: %s", bundle_var, err)

    return api_key, secret_key, person_id, password


class ShioajiManager:
    """Manages Shioaji API lifecycle, contract cache, and quote retrieval."""

    def __init__(self, api_key: str = "", secret_key: str = "", person_id: str = "", password: str = ""):
        self.api_key = api_key
        self.secret_key = secret_key
        self.person_id = person_id
        self.password = password
        self.api: Any = None
        self._connection_lock = Lock()
        self._fallback_checked: Dict[str, float] = {}
        self.logged_in: bool = False
        self.contracts_fetched: bool = False
        self.last_login_attempt: Optional[datetime] = None
        self.login_error: Optional[str] = None

    def initialize(self) -> bool:
        """Attempt only simulation login with bounded cooldown."""
        now = datetime.now(TAIWAN_TZ)
        if self.last_login_attempt and (now - self.last_login_attempt).total_seconds() < 120:
            return False
        self.last_login_attempt = now
        if not self.api_key or not self.secret_key:
            self.login_error = "Missing api_key or secret_key"
            LOGGER.warning("Shioaji credentials missing or incomplete.")
            return False

        try:
            import shioaji as sj
            # Strict read-only simulation contract. Never try production.
            self.api = sj.Shioaji(simulation=True)
            accounts = self.api.login(
                api_key=self.api_key,
                secret_key=self.secret_key,
            )

            self.logged_in = True
            self.login_error = None
            LOGGER.info("Shioaji login successful. Accounts: %s", len(accounts) if accounts else 0)
            try:
                self.api.fetch_contracts(contract_download=True)
                self.contracts_fetched = True
                LOGGER.info("Shioaji contracts downloaded successfully.")
            except Exception as e:
                LOGGER.warning("Could not download contracts synchronously: %s", e)
            return True
        except ImportError:
            self.login_error = "shioaji module not installed"
            LOGGER.error("shioaji package not installed in runtime.")
            return False
        except Exception as e:
            self.logged_in = False
            self.login_error = type(e).__name__
            LOGGER.error("Shioaji simulation login failed: %s", type(e).__name__)
            return False

    def get_order_book(self, symbol: str) -> Dict[str, Any] | None:
        """Five-level depth from simulation-only BidAsk subscription cache."""
        try:
            with self._connection_lock:
                if not self.logged_in:
                    self.initialize()
                if not self.logged_in or self.api is None:
                    return None
                if not hasattr(self, "_stream_cache"):
                    if __package__:
                        from .streaming import StreamCache
                    else:
                        from streaming import StreamCache
                    self._stream_cache = StreamCache(self.api)
            return self._stream_cache.read_book(symbol)
        except Exception as error:
            LOGGER.warning("Shioaji BidAsk unavailable: %s", type(error).__name__)
            return None

    def historical_minutes(self, symbol: str, trade_day: datetime.date) -> Dict[str, Any]:
        """At most one backend query per API backfill claim, simulation-only."""
        with self._connection_lock:
            if not self.logged_in:
                self.initialize()
            if not self.logged_in or self.api is None:
                return {"status": "unavailable", "symbol": symbol,
                        "date": trade_day.isoformat(),
                        "source": "shioaji_kbars", "points": []}
            if __package__:
                from .kbars import session_kbars
            else:
                from kbars import session_kbars
            return session_kbars(self.api, symbol, trade_day)

    def _on_contracts_fetched(self, security_type: Any) -> None:
        self.contracts_fetched = True
        LOGGER.info("Shioaji contracts background callback received for %s", security_type)

    def get_quotes(self, symbols: List[str]) -> Dict[str, Any]:
        """Shared demand-driven quotes, with bounded MIS fallback on stream errors."""
        quotes: Dict[str, Any] = {}
        try:
            with self._connection_lock:
                if not self.logged_in:
                    self.initialize()
                if self.logged_in and not hasattr(self, "_stream_cache"):
                    # Docker runs "uvicorn main:app" from /app, not as a
                    # package. CI imports services.shioaji_quote_proxy.main.
                    if __package__:
                        from .streaming import StreamCache
                    else:
                        from streaming import StreamCache
                    self._stream_cache = StreamCache(self.api)
            if hasattr(self, "_stream_cache"):
                quotes = self._stream_cache.read(symbols)
        except Exception as error:
            # Never leak broker account/session data in exceptions or responses.
            # A stream SDK failure must not turn the entire /quotes API into 500.
            LOGGER.warning("Shioaji streaming unavailable: %s", type(error).__name__)
        now = monotonic()
        # Fallback stays inside this proxy and is throttled per symbol.
        # If Shioaji supplies a trade but no prior-close reference (observed
        # with ETFs), a *same-session* MIS trade with y may replace it. Never
        # blend a MIS reference into a Shioaji-sourced price or substitute a
        # previous day's close for today's trade.
        pending = []
        with self._connection_lock:
            for symbol in symbols:
                missing = symbol not in quotes
                missing_prior = not missing and quotes[symbol].get("previous_close") is None
                if (missing or missing_prior) and now - self._fallback_checked.get(symbol, -1e12) >= 60:
                    self._fallback_checked[symbol] = now
                    pending.append(symbol)
        if pending:
            for symbol, mis in fetch_twse_mis(pending).items():
                if symbol not in quotes:
                    quotes[symbol] = mis
                    continue
                if (quotes[symbol].get("previous_close") is not None
                    or mis.get("previous_close") is None):
                    continue
                try:
                    stream_at = datetime.fromisoformat(str(quotes[symbol]["trade_time"])).astimezone(TAIWAN_TZ)
                    mis_at = datetime.fromisoformat(str(mis["trade_time"])).astimezone(TAIWAN_TZ)
                    same_day = stream_at.date() == mis_at.date() == datetime.now(TAIWAN_TZ).date()
                    close_enough = abs((stream_at - mis_at).total_seconds()) <= 60
                except (KeyError, TypeError, ValueError):
                    continue
                if same_day and close_enough:
                    quotes[symbol] = mis
        return quotes


def fetch_twse_mis(symbols: List[str]) -> Dict[str, Any]:
    """Fetch quotes directly from mis.twse.com.tw inside Taiwan Cloud Run container."""
    results: Dict[str, Any] = {}
    if not symbols:
        return results
    if len(symbols) > 10:
        for offset in range(0, len(symbols), 10):
            results.update(fetch_twse_mis(symbols[offset:offset + 10]))
        return results

    channels = []
    for s in symbols:
        s_clean = s.strip().upper()
        # Probe both tse and otc channel formats
        if s_clean == "TAIEX":
            channels.append("tse_t00.tw")
        else:
            channels.append(f"tse_{s_clean}.tw")
            channels.append(f"otc_{s_clean}.tw")

    ex_ch = "|".join(channels)
    url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch={ex_ch}&json=1&delay=0"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://mis.twse.com.tw/stock/index.jsp",
        "Accept": "application/json, */*",
    }
    try:
        with httpx.Client(timeout=8.0, follow_redirects=False) as client:
            resp = client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("msgArray", []):
                    if f"{item.get('ex', '')}_{item.get('c', '')}.tw" not in channels:
                        continue
                    c = str(item.get("c", "")).strip().upper()
                    if not c:
                        continue
                    # Parse price fields
                    def parse_val(v: Any) -> Optional[float]:
                        try:
                            f = float(str(v).strip())
                            return f if f > 0 else None
                        except (ValueError, TypeError):
                            return None

                    z = parse_val(item.get("z"))
                    if z is None and "trade" in item and isinstance(item["trade"], dict):
                        z = parse_val(item["trade"].get("z"))
                    if z is None:
                        # Yesterday's close is not an intraday execution.
                        continue

                    y = parse_val(item.get("y"))
                    o = parse_val(item.get("o"))
                    h = parse_val(item.get("h"))
                    l = parse_val(item.get("l"))
                    v = parse_val(item.get("v"))
                    diff = round(z - y, 2) if (z is not None and y is not None) else None
                    rate = round((diff / y) * 100, 2) if (diff is not None and y and y > 0) else None

                    # Five bids and asks
                    b_str = str(item.get("b", "")).strip("_").split("_") if item.get("b") else []
                    a_str = str(item.get("a", "")).strip("_").split("_") if item.get("a") else []
                    bids = [float(x) for x in b_str if parse_val(x) is not None]
                    asks = [float(x) for x in a_str if parse_val(x) is not None]

                    date_raw = str(item.get("d") or "")
                    time_raw = str(item.get("t") or (item.get("trade") or {}).get("t") or "")
                    try:
                        quote_at = datetime.strptime(
                            date_raw + " " + time_raw, "%Y%m%d %H:%M:%S"
                        ).replace(tzinfo=TAIWAN_TZ)
                        if quote_at > datetime.now(TAIWAN_TZ):
                            continue
                    except (TypeError, ValueError):
                        continue
                    key = "TAIEX" if str(item.get("c", "")).strip().lower() == "t00" else c
                    results[key] = {
                        "symbol": key, "trade_time": quote_at.isoformat(),
                        "received_at": datetime.now(TAIWAN_TZ).isoformat(),
                        "exchange": str(item.get("ex") or "").upper(),
                        "is_final": False,
                        "name": str(item.get("n", "")).strip(),
                        "open": o,
                        "high": h,
                        "low": l,
                        "close": z,
                        "previous_close": y,
                        "change_price": diff,
                        "change_rate": rate,
                        "volume": int(v) if v is not None else None,
                        "bid_price": bids,
                        "ask_price": asks,
                        "sys_time": data.get("queryTime", {}).get("sysTime"),
                        "source": "twse_mis",
                    }
    except Exception as err:
        LOGGER.warning("TWSE MIS query failed: %s", err)

    return results


@asynccontextmanager
async def lifespan(app: FastAPI):
    global CLIENT
    api_key, secret_key, person_id, password = resolve_credentials()
    CLIENT = ShioajiManager(api_key, secret_key, person_id, password)
    # Lazy login: health probes and cold starts must not consume broker sessions.
    yield
    if CLIENT and CLIENT.api and CLIENT.logged_in:
        try:
            CLIENT.api.logout()
        except Exception:
            pass


app = FastAPI(
    title="Janus Shioaji Quote Proxy",
    description="Dedicated Shioaji real-time quote forwarding service in asia-east1",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
def health() -> Dict[str, Any]:
    now = datetime.now(TAIWAN_TZ)
    return {
        "status": "ok",
        "service": "janus-shioaji-quote-proxy",
        "region": "asia-east1",
        "timestamp": now.isoformat(),
        "shioaji": {
            "logged_in": CLIENT.logged_in if CLIENT else False,
            "contracts_fetched": CLIENT.contracts_fetched if CLIENT else False,
            "has_credentials": bool(CLIENT and CLIENT.api_key and CLIENT.secret_key),
            "simulation": True if CLIENT and CLIENT.logged_in else None,
            "mode": "simulation_only",
            "subscribed_count": CLIENT._stream_cache.subscribed_count()
                if CLIENT and hasattr(CLIENT, "_stream_cache") else 0,
            "login_error": CLIENT.login_error if CLIENT else None,
            "last_login_attempt": CLIENT.last_login_attempt.isoformat() if CLIENT and CLIENT.last_login_attempt else None,
        },
    }




@app.get("/kbars")
def get_historical_kbars(symbol: str = Query(..., max_length=10),
                         day: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$")) -> Dict[str, Any]:
    """Private IAM only; used ONCE per due backfill claim, not for polling."""
    target = symbol.strip().upper()
    if not (re.fullmatch(r"[0-9A-Z]{4,10}", target) or target == "TAIEX"):
        raise HTTPException(status_code=400, detail="Invalid kbar symbol")
    try:
        trading_day = datetime.strptime(day, "%Y-%m-%d").date()
    except ValueError as error:
        raise HTTPException(status_code=400, detail="Invalid kbar day") from error
    if trading_day != datetime.now(TAIWAN_TZ).date():
        raise HTTPException(status_code=400, detail="Historical request must be current session")
    if CLIENT is None:
        return {"status": "unavailable", "symbol": target,
                "date": day, "source": "shioaji_kbars", "points": []}
    return CLIENT.historical_minutes(target, trading_day)

@app.get("/quotes")
def get_quotes(symbols: str = Query(..., description="Comma-separated stock symbols, e.g. '2382,2327,5876'")) -> Dict[str, Any]:
    sym_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    if any(not re.fullmatch(r"[0-9A-Z]{4,10}|TAIEX", symbol) for symbol in sym_list):
        raise HTTPException(status_code=400, detail="Invalid quote symbol")
    if not sym_list:
        raise HTTPException(status_code=400, detail="No symbols provided")
    if len(sym_list) > 30:
        raise HTTPException(status_code=400, detail="Max 30 symbols allowed per request")

    quotes = CLIENT.get_quotes(sym_list) if CLIENT else fetch_twse_mis(sym_list)
    return {
        "status": "success",
        "count": len(quotes),
        "timestamp": datetime.now(TAIWAN_TZ).isoformat(),
        "quotes": quotes,
    }


@app.get("/order-book/{symbol}")
def order_book(symbol: str) -> Dict[str, Any]:
    """Private IAM-only five-level book: one demand, never SDK snapshots polling."""
    sym = symbol.strip().upper()
    if not re.fullmatch(r"[0-9A-Z]{4,10}", sym):
        raise HTTPException(status_code=400, detail="Invalid order-book symbol")
    data = CLIENT.get_order_book(sym) if CLIENT else None
    return {
        "status": "available" if data else "missing",
        "symbol": sym,
        "source": "shioaji_bidask",
        "data": data,
    }


@app.get("/quote/{symbol}")
def get_quote(symbol: str) -> Dict[str, Any]:
    sym = symbol.strip().upper()
    if not re.fullmatch(r"[0-9A-Z]{4,10}|TAIEX", sym):
        raise HTTPException(status_code=400, detail="Invalid quote symbol")
    quotes = CLIENT.get_quotes([sym]) if CLIENT else fetch_twse_mis([sym])
    if sym not in quotes:
        raise HTTPException(status_code=404, detail=f"Quote not found for symbol {sym}")
    return {
        "status": "success",
        "timestamp": datetime.now(TAIWAN_TZ).isoformat(),
        "data": quotes[sym],
    }


@app.post("/fetch")
def fetch_external_intel(req: IntelFetchRequest) -> Dict[str, Any]:
    """Forward GET request to allowlisted Taiwan market intelligence & official APIs from asia-east1."""
    raw_url = (req.url or "").strip()
    if not raw_url or len(raw_url) > 2000:
        raise HTTPException(status_code=400, detail="Invalid URL")
    parsed = urlsplit(raw_url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or host not in ALLOWED_INTEL_HOSTS or parsed.port not in (None, 443):
        raise HTTPException(status_code=400, detail=f"Host not in allowlist: {host}")

    req_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json,text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    if host.endswith("twse.com.tw"):
        req_headers["Referer"] = "https://www.twse.com.tw/"
    if req.headers:
        for k, v in req.headers.items():
            if k.lower() in {"accept", "referer", "accept-language"} and isinstance(v, str):
                req_headers[k] = v

    timeout_sec = max(2.0, min(25.0, float(req.timeout or 12.0)))
    try:
        with httpx.Client(timeout=timeout_sec, follow_redirects=True, max_redirects=3) as client:
            resp = client.get(raw_url, headers=req_headers)
            content_type = resp.headers.get("content-type", "")
            text = resp.text[:1_500_000]
            return {
                "status": "success" if resp.status_code == 200 else "upstream_error",
                "http_status": resp.status_code,
                "url": str(resp.url),
                "content_type": content_type,
                "body": text,
                "region": "asia-east1",
            }
    except Exception as exc:
        return {
            "status": "error",
            "http_status": 502,
            "url": raw_url,
            "error": f"{type(exc).__name__}: {str(exc)[:300]}",
            "region": "asia-east1",
        }
