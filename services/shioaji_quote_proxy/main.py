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
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import httpx
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

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
        self.logged_in: bool = False
        self.contracts_fetched: bool = False
        self.last_login_attempt: Optional[datetime] = None
        self.login_error: Optional[str] = None

    def initialize(self) -> bool:
        """Attempt to initialize and log into Shioaji."""
        self.last_login_attempt = datetime.now(TAIWAN_TZ)
        if not self.api_key or not self.secret_key:
            self.login_error = "Missing api_key or secret_key"
            LOGGER.warning("Shioaji credentials missing or incomplete.")
            return False

        try:
            import shioaji as sj
            LOGGER.info("Connecting to Shioaji (Production mode)...")
            self.api = sj.Shioaji(simulation=False)
            try:
                accounts = self.api.login(
                    api_key=self.api_key,
                    secret_key=self.secret_key,
                )
            except Exception as prod_err:
                if "production permission" in str(prod_err).lower():
                    LOGGER.info("Production permission denied, trying Shioaji simulation mode...")
                    self.api = sj.Shioaji(simulation=True)
                    accounts = self.api.login(
                        api_key=self.api_key,
                        secret_key=self.secret_key,
                    )
                else:
                    raise prod_err

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
            self.login_error = f"{type(e).__name__}: {str(e)[:200]}"
            LOGGER.error("Shioaji login failed: %s", self.login_error)
            return False

    def _on_contracts_fetched(self, security_type: Any) -> None:
        self.contracts_fetched = True
        LOGGER.info("Shioaji contracts background callback received for %s", security_type)

    def get_quotes(self, symbols: List[str]) -> Dict[str, Any]:
        """Fetch quotes from Shioaji snapshots. Fallback to TWSE MIS if needed."""
        results: Dict[str, Any] = {}
        missing_symbols: List[str] = []

        if self.logged_in and self.api:
            contracts = []
            symbol_contract_map = {}
            for sym in symbols:
                sym_clean = sym.strip().upper()
                try:
                    # Look up in Stocks (TSE / OTC)
                    contract = getattr(self.api.Contracts.Stocks, sym_clean, None)
                    if contract is not None:
                        contracts.append(contract)
                        symbol_contract_map[contract.code] = sym_clean
                    else:
                        missing_symbols.append(sym_clean)
                except Exception:
                    missing_symbols.append(sym_clean)

            if contracts:
                try:
                    snapshots = self.api.snapshots(contracts)
                    for snap in snapshots:
                        code = getattr(snap, "code", "")
                        sym = symbol_contract_map.get(code, code)
                        results[sym] = {
                            "symbol": sym,
                            "name": getattr(snap, "name", ""),
                            "open": getattr(snap, "open", None),
                            "high": getattr(snap, "high", None),
                            "low": getattr(snap, "low", None),
                            "close": getattr(snap, "close", None),
                            "change_price": getattr(snap, "change_price", None),
                            "change_rate": getattr(snap, "change_rate", None),
                            "volume": getattr(snap, "total_volume", getattr(snap, "volume", None)),
                            "bid_price": getattr(snap, "buy_price", None),
                            "bid_volume": getattr(snap, "buy_volume", None),
                            "ask_price": getattr(snap, "sell_price", None),
                            "ask_volume": getattr(snap, "sell_volume", None),
                            "ts": getattr(snap, "ts", None),
                            "source": "shioaji",
                        }
                except Exception as e:
                    LOGGER.warning("Error fetching snapshots from Shioaji: %s", e)
                    missing_symbols = symbols  # fallback all

        # Fallback to TWSE MIS for any missing symbols
        pending = [s for s in symbols if s not in results or results[s].get("close") is None]
        if pending:
            LOGGER.info("Fetching fallback quotes from TWSE MIS for: %s", pending)
            mis_data = fetch_twse_mis(pending)
            for sym, quote in mis_data.items():
                results[sym] = quote

        return results


def fetch_twse_mis(symbols: List[str]) -> Dict[str, Any]:
    """Fetch quotes directly from mis.twse.com.tw inside Taiwan Cloud Run container."""
    results: Dict[str, Any] = {}
    if not symbols:
        return results

    channels = []
    for s in symbols:
        s_clean = s.strip().upper()
        # Probe both tse and otc channel formats
        channels.append(f"tse_{s_clean}.tw")
        channels.append(f"otc_{s_clean}.tw")

    ex_ch = "|".join(channels[:20])
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
                        # use yesterday close if not traded
                        z = parse_val(item.get("y"))

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

                    results[c] = {
                        "symbol": c,
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
                        "trade_time": item.get("t") or item.get("%"),
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
    if api_key and secret_key:
        CLIENT.initialize()
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
            "login_error": CLIENT.login_error if CLIENT else None,
            "last_login_attempt": CLIENT.last_login_attempt.isoformat() if CLIENT and CLIENT.last_login_attempt else None,
        },
    }


@app.get("/quotes")
def get_quotes(symbols: str = Query(..., description="Comma-separated stock symbols, e.g. '2382,2327,5876'")) -> Dict[str, Any]:
    sym_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
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


@app.get("/quote/{symbol}")
def get_quote(symbol: str) -> Dict[str, Any]:
    sym = symbol.strip().upper()
    quotes = CLIENT.get_quotes([sym]) if CLIENT else fetch_twse_mis([sym])
    if sym not in quotes:
        raise HTTPException(status_code=404, detail=f"Quote not found for symbol {sym}")
    return {
        "status": "success",
        "timestamp": datetime.now(TAIWAN_TZ).isoformat(),
        "data": quotes[sym],
    }
