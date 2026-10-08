"""FastAPI boundary for the WBS 4J private workspace."""

from __future__ import annotations

import json
from functools import lru_cache
from datetime import datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import logging
import os
from pathlib import Path
from threading import Lock
from time import monotonic
from typing import Any, Callable
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from fastapi import APIRouter, BackgroundTasks, Body, Depends, FastAPI, Header, HTTPException, Query, Request, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

from packages.observability import redact
from packages.admin_api import AdminConflictError, AdminValidationError
from packages.web_api import (PublicReportNotFound, PublicReportWaiting, PublicStockNotFound,
                              QueryValidationError)
from .auth import (AuthenticatedAdmin, AuthenticatedUser, GoogleAdminAuthenticator,
                   GoogleUserAuthenticator, allowed_admin_emails,
                   allowed_user_emails)
from .context_sources import ContextSourceError, ContextSourceService, CoreContextReader
from .mcp_adapter import McpAdapter
from .mcp_oauth import McpOAuth, OAuthSettings, RepositoryOAuthCodeStore, parse_form
from .models import (AdminResponseOut, AnalysisFeedbackIn, CorePageOut, CoreSummaryOut, MarketHomeOut,
                     BrokerProfileIn, CorrectionIn, HealthOut, InvestmentProfileIn, InvestmentProfileOut, LedgerEventIn,
                     LedgerReversalIn, MonthlyLedgerSummaryOut,
                     NoteIn, NoteRevisionIn, PortfolioExposureOut, PortfolioPerformanceOut,
                     PortfolioStressOut, PortfolioSummaryOut,
                     PrivateResponseOut, PublicDatasetOut, PublicReportListOut, PublicReportOut, PublicWaitingOut,
                     WatchlistIn, WatchlistOrderIn,
                     GovernanceDiffIn, GovernanceEditIn, MembershipEditIn)
from .repository import ConflictError, NotFoundError, OversellError, repository_from_env
from .private_pipeline import ledger_net_cash_flow, stock_identity
from .private_recalc_queue import CloudRunPrivateRecalcTrigger, QueuedPrivateRecalculator
from .public_runtime import build_admin_service, build_core_service, build_pipeline_service, build_public_service
from .store import PrivateIcebergStore
from .intraday_quotes import MisQuotes, TAIPEI, market_phase, value_holdings
from .quote_router import QuoteRouter, ROUTE_VERSION


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)
AUDIT_LOGGER = logging.getLogger("uvicorn.error")
AUDIT_LOGGER.setLevel(logging.INFO)


def _router_family(path: str) -> str | None:
    for family, prefix in (("mcp", "/mcp"), ("public", "/api/v1/public/"), ("private", "/api/v1/me/"),
                           ("admin", "/api/v1/admin/"), ("admin", "/api/v1/core/")):
        if path.startswith(prefix):
            return family
    return None


class _RateLimiter:
    """Small per-process fixed-window guard; Cloud Run instance scaling remains the outer ceiling."""

    def __init__(self, limits: dict[str, int], *, window_seconds: int = 60) -> None:
        self.limits, self.window_seconds = limits, window_seconds
        self._buckets: dict[tuple[str, str], tuple[float, int]] = {}
        self._lock = Lock()

    def retry_after(self, family: str, identity: str) -> int:
        now, bucket = monotonic(), (family, identity)
        with self._lock:
            if bucket not in self._buckets and len(self._buckets) >= 4096:
                self._buckets = {key: value for key, value in self._buckets.items()
                                 if now - value[0] < self.window_seconds}
                if len(self._buckets) >= 4096:
                    self._buckets.pop(next(iter(self._buckets)))
            started, count = self._buckets.get(bucket, (now, 0))
            if now - started >= self.window_seconds:
                started, count = now, 0
            if count >= self.limits[family]:
                return max(1, int(self.window_seconds - (now - started) + .999))
            self._buckets[bucket] = (started, count + 1)
        return 0


def _positive_env(name: str, default: int) -> int:
    value = int(os.getenv(name, str(default)))
    if value < 1:
        raise ValueError(f"{name} must be positive")
    return value


class _PublicUserCORSMiddleware(CORSMiddleware):
    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] == "http" and not scope["path"].startswith(("/api/v1/public/", "/api/v1/me/")):
            await self.app(scope, receive, send)
            return
        await super().__call__(scope, receive, send)


_FLUTTER_NO_STORE_FILES = frozenset({
    "index.html",
    "admin-index.html",
    "manifest.json",
    "admin-manifest.json",
    "build-id.txt",
    "flutter_service_worker.js",
    "main.dart.js",
})


def _flutter_asset_headers(path: str = "") -> dict[str, str]:
    """Revalidate the dev app shell after deploy; cache only content-hashed bundles."""
    name = Path(path).name
    headers = {"Cross-Origin-Opener-Policy": "unsafe-none"}
    if not path or name in _FLUTTER_NO_STORE_FILES:
        headers["Cache-Control"] = "no-store, max-age=0"
    elif name.startswith("flutter_bootstrap"):
        headers["Cache-Control"] = "no-store, max-age=0"
    elif name.startswith("main.") and name.endswith(".dart.js"):
        headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return headers


class _Lazy:
    def __init__(self, factory: Callable[[], Any]) -> None:
        self.factory, self.value = factory, None

    def __getattr__(self, name: str) -> Any:
        if self.value is None: self.value = self.factory()
        return getattr(self.value, name)


def create_app(repository: Any | None = None, store: Any | None = None,
               verifier: Callable[..., Any] | None = None, *, audience: str | None = None,
               core: Any | None = None, query_core: Any | None = None,
               admin_verifier: Callable[..., Any] | None = None,
               admin_audience: str | None = None,
               admin_emails: frozenset[str] | None = None,
               admin_service: Any | None = None,
               pipeline_service: Any | None = None,
               public: Any | None = None,
               oauth_facade: Any | None = None,
               quotes: Any | None = None,
               private_recalculator: Any | None = None) -> FastAPI:
    from packages.postgres_bundle import load_postgres_bundle
    bundle_fields: dict[str, str | tuple[str, ...]] = {
        "GOOGLE_USER_CLIENT_ID": "google_user_client_id",
        "GOOGLE_ADMIN_CLIENT_ID": ("web_google_client_id", "google_client_id"),
    }
    if oauth_facade is None and os.getenv("MCP_OAUTH_ENABLED", "false").strip().lower() == "true":
        bundle_fields.update({
            "GOOGLE_USER_CLIENT_SECRET": "google_user_client_secret",
            "MCP_OAUTH_SIGNING_KEY": "mcp_oauth_signing_key",
        })
    load_postgres_bundle("JANUS_API_POSTGRES_BUNDLE", bundle_fields)
    quotes = quotes or MisQuotes()
    repository = repository or _Lazy(repository_from_env)
    quote_router = QuoteRouter(repository, quotes)
    store = store or _Lazy(PrivateIcebergStore.from_env)
    queued_recalculator = private_recalculator is None
    core = core or _Lazy(CoreContextReader.from_env)
    if query_core is None:
        def unavailable_core() -> Any:
            try:
                return build_core_service()
            except Exception as error:
                LOGGER.warning("core runtime unavailable: %s", type(error).__name__)
                raise HTTPException(status_code=503, detail="core query unavailable") from error
        query_core = _Lazy(unavailable_core)
    if public is None:
        def unavailable_public() -> Any:
            try:
                return build_public_service()
            except Exception as error:
                detail = str(error)
                prefix = "public runtime setup failed at "
                detail = detail.removeprefix(prefix) if detail.startswith(prefix) else type(error).__name__
                LOGGER.warning("public runtime unavailable: %s", detail)
                raise HTTPException(status_code=503, detail="public reports unavailable") from error
        public = _Lazy(unavailable_public)
    if admin_service is None:
        def unavailable_admin() -> Any:
            try:
                return build_admin_service()
            except Exception as error:
                LOGGER.warning("admin runtime unavailable: %s", type(error).__name__)
                raise HTTPException(status_code=503, detail="admin unavailable") from error
        admin_service = _Lazy(unavailable_admin)
    if pipeline_service is None:
        def unavailable_pipeline() -> Any:
            try:
                return build_pipeline_service()
            except Exception as error:
                LOGGER.warning("pipeline service unavailable: %s", type(error).__name__)
                raise HTTPException(status_code=503, detail="pipeline service unavailable") from error
        pipeline_service = _Lazy(unavailable_pipeline)

    if queued_recalculator:
        def private_recalc_worker_count() -> int:
            setting = admin_service.setting("private_recalc_workers").get("value") or {"workers": 2}
            workers = int(setting.get("workers", 2)) if isinstance(setting, dict) else 2
            if not 2 <= workers <= 8:
                raise RuntimeError("private recalculation worker setting is invalid")
            return workers

        private_recalculator = _Lazy(lambda: QueuedPrivateRecalculator(
            repository,
            private_recalc_worker_count,
            CloudRunPrivateRecalcTrigger.from_env(),
        ))

    contexts = ContextSourceService(repository,store,core)
    auth = GoogleUserAuthenticator(audience or os.getenv("GOOGLE_USER_CLIENT_ID", ""), repository,
                                   allowed_emails=allowed_user_emails(), verifier=verifier)
    admin_auth = GoogleAdminAuthenticator(
        admin_audience or os.getenv("GOOGLE_ADMIN_CLIENT_ID", ""),
        admin_emails if admin_emails is not None else allowed_admin_emails(),
        verifier=admin_verifier,
    )
    mcp_oauth = oauth_facade if oauth_facade is not None else _Lazy(lambda: McpOAuth(
        OAuthSettings.from_env(), RepositoryOAuthCodeStore(repository), repository.resolve_user,
    ))

    def oauth_service() -> McpOAuth:
        try:
            if not isinstance(mcp_oauth, _Lazy): return mcp_oauth
            if mcp_oauth.value is None:
                mcp_oauth.value = mcp_oauth.factory()
            return mcp_oauth.value
        except ValueError as error:
            LOGGER.warning("MCP OAuth configuration unavailable: %s", error)
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "MCP OAuth is unavailable") from error

    def quote_session(now: datetime | None = None) -> tuple[datetime, str]:
        current = now or datetime.now(TAIPEI)
        phase = market_phase(current)
        if phase in {"regular", "closing_pending_eod"}:
            try:
                schedule = admin_service.setting("schedule").get("value") or {}
                holidays = set(schedule.get("holiday_overrides", [])) | {
                    value for value in os.getenv("MARKET_HOLIDAYS", "").split(",") if value
                }
                if current.astimezone(TAIPEI).date().isoformat() in holidays:
                    phase = "closed"
            except Exception as error:
                LOGGER.warning("quote calendar unavailable: %s", type(error).__name__)
                phase = "closed"
        return current, phase

    def recalculate_private_mart(user_id: UUID, trigger_source: str) -> dict[str, Any]:
        if queued_recalculator:
            return dict(private_recalculator.run_user(user_id, trigger_source))
        return dict(private_recalculator.run_user(user_id))

    def recalculate_private_mart_safely(user_id: UUID) -> None:
        try:
            recalculate_private_mart(user_id, "mutation")
        except Exception as error:
            LOGGER.warning(
                "immediate private recalculation enqueue/dispatch failed; scheduled pipeline remains fallback: %s",
                type(error).__name__,
            )

    def resolve_prices(identities: dict[str, dict[str, Any]], *, force: bool = False):
        scoped = {
            symbol: identity for symbol, identity in identities.items()
            if identity.get("enabled", True) is not False
            and str(identity.get("market", "")).upper() in {"TWSE", "TWSE_INDEX"}
        }
        current, phase = quote_session()
        authorized = os.getenv("JANUS_MIS_QUOTES_ENABLED", "false").lower() == "true"
        prices, refresh = quote_router.resolve(
            scoped,
            refresh=bool(scoped) and authorized and phase == "regular",
            force=force,
            now=current,
        )
        return prices, refresh, current, phase, authorized

    api = FastAPI(title="Janus User API", version="0.1.0", docs_url=None, redoc_url=None)
    limiter = _RateLimiter({
        "public": _positive_env("PUBLIC_RATE_LIMIT_PER_MINUTE", 120),
        "private": _positive_env("PRIVATE_RATE_LIMIT_PER_MINUTE", 60),
        "admin": _positive_env("ADMIN_RATE_LIMIT_PER_MINUTE", 30),
        "mcp": _positive_env("MCP_RATE_LIMIT_PER_MINUTE", 60),
    })

    @api.middleware("http")
    async def boundary_policy(request: Request, call_next: Callable[..., Any]):
        started = monotonic()
        family = _router_family(request.url.path)
        if family and not request.url.path.endswith("/health"):
            authorization = request.headers.get("authorization", "")
            peer = request.client.host if request.client else "unknown"
            identity = peer if family == "public" else (
                sha256(authorization.encode()).hexdigest()[:16] if authorization else peer)
            retry = limiter.retry_after(family, identity)
            if retry:
                response = JSONResponse({"detail": "rate limit exceeded"}, status_code=429,
                                        headers={"Retry-After": str(retry)})
            else:
                response = await call_next(request)
        else:
            response = await call_next(request)
        request_id = str(uuid4())
        duration_ms = round((monotonic() - started) * 1000)
        response.headers["X-Request-ID"] = request_id
        if family:
            request_message = (f"api_request family={family} method={request.method} "
                               f"status={response.status_code} duration_ms={duration_ms} request_id={request_id}")
            LOGGER.info(request_message)
            AUDIT_LOGGER.info(request_message)
        if family and (family == "admin" or request.method not in {"GET", "HEAD", "OPTIONS"}
                       or response.status_code >= 400):
            audit_message = (f"api_audit family={family} method={request.method} "
                             f"status={response.status_code} duration_ms={duration_ms} request_id={request_id}")
            LOGGER.info(audit_message)
            AUDIT_LOGGER.info(audit_message)
        return response
    origins=[value.strip() for value in os.getenv("USER_CORS_ORIGINS","").split(",") if value.strip()]
    if origins:
        api.add_middleware(_PublicUserCORSMiddleware,allow_origins=origins,allow_credentials=False,
                           allow_methods=["GET","POST","PUT","PATCH","DELETE"],allow_headers=["Authorization","Content-Type","Idempotency-Key"])
    def authenticate(request: Request) -> AuthenticatedUser: return auth(request)
    def authenticate_admin(request: Request) -> Any: return admin_auth(request)
    public_router = APIRouter(prefix="/api/v1/public", tags=["public"])
    private = APIRouter(prefix="/api/v1/me", dependencies=[Depends(authenticate)], tags=["private"],
                        responses={200: {"model": PrivateResponseOut}})
    admin = APIRouter(prefix="/api/v1/admin", dependencies=[Depends(authenticate_admin)], tags=["admin"],
                      responses={200: {"model": AdminResponseOut}})
    legacy_core = APIRouter(prefix="/api/v1/core", dependencies=[Depends(authenticate_admin)], tags=["admin"])

    def user(request_user: AuthenticatedUser = Depends(authenticate)) -> AuthenticatedUser: return request_user
    def key(value: str = Header(alias="Idempotency-Key", min_length=8, max_length=128)) -> str: return value

    @api.get("/.well-known/oauth-protected-resource")
    def mcp_protected_resource() -> dict[str, Any]:
        return oauth_service().protected_resource_metadata()

    @api.get("/.well-known/oauth-authorization-server")
    def mcp_authorization_server() -> dict[str, Any]:
        return oauth_service().authorization_server_metadata()

    @api.get("/oauth/authorize")
    def mcp_authorize(request: Request) -> Response:
        return oauth_service().begin_authorization(dict(request.query_params))

    @api.get("/oauth/google/callback")
    def mcp_google_callback(request: Request) -> Response:
        return oauth_service().google_callback(dict(request.query_params))

    @api.post("/oauth/authorize/complete")
    async def mcp_authorize_complete(request: Request) -> Response:
        form = parse_form(request, await request.body())
        return oauth_service().complete_authorization(form.get("token", ""), form.get("approved") == "true")

    @api.post("/oauth/token")
    async def mcp_token(request: Request) -> dict[str, Any]:
        return oauth_service().exchange_token(parse_form(request, await request.body()))

    @api.post("/oauth/revoke", status_code=status.HTTP_200_OK)
    async def mcp_revoke(request: Request) -> Response:
        oauth_service().revoke_token(parse_form(request, await request.body()))
        return Response(status_code=status.HTTP_200_OK, headers={"Cache-Control": "no-store"})

    @api.post("/mcp")
    async def mcp_endpoint(request: Request) -> Response:
        body = await request.body()
        if len(body) > 65_536:
            return JSONResponse({"jsonrpc":"2.0","id":None,
                                 "error":{"code":-32600,"message":"Request too large"}}, status_code=413)
        try: value = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return JSONResponse({"jsonrpc":"2.0","id":None,
                                 "error":{"code":-32700,"message":"Parse error"}}, status_code=400)
        response, response_status, headers = McpAdapter(contexts, oauth_service(), repository).handle(
            value, request.headers.get("authorization", ""))
        if response is None: return Response(status_code=response_status, headers=headers)
        return JSONResponse(jsonable_encoder(response), status_code=response_status, headers=headers)

    async def conflict_handler(_request: Any, error: Exception):
        return JSONResponse({"detail":redact(error)}, status_code=status.HTTP_409_CONFLICT)

    async def missing_handler(_request: Any, error: Exception):
        return JSONResponse({"detail":redact(error) or "not found"}, status_code=status.HTTP_404_NOT_FOUND)

    async def invalid_handler(_request: Any, error: Exception):
        return JSONResponse({"detail":redact(error)}, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)

    async def unavailable_handler(_request: Any, error: Exception):
        LOGGER.warning("api request failed: %s", type(error).__name__)
        return JSONResponse({"detail":"service unavailable"}, status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

    async def admin_invalid_handler(_request: Any, error: Exception):
        return JSONResponse({"detail": redact(error)}, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)

    api.add_exception_handler(ConflictError, conflict_handler)
    api.add_exception_handler(AdminConflictError, conflict_handler)
    api.add_exception_handler(OversellError, conflict_handler)
    api.add_exception_handler(NotFoundError, missing_handler)
    api.add_exception_handler(PublicReportNotFound, missing_handler)
    api.add_exception_handler(PublicStockNotFound, missing_handler)
    api.add_exception_handler(ContextSourceError, invalid_handler)
    api.add_exception_handler(QueryValidationError, invalid_handler)
    api.add_exception_handler(AdminValidationError, admin_invalid_handler)
    api.add_exception_handler(Exception, unavailable_handler)

    @api.get("/health", response_model=HealthOut)
    def health() -> dict[str, str]: return {"status":"ok"}

    @public_router.get("/health", response_model=HealthOut)
    def public_health() -> dict[str, str]: return {"status":"ok"}

    static_dir = Path(__file__).resolve().parents[2] / "apps" / "web" / "static"
    flutter_dir = Path(__file__).resolve().parents[2] / "apps" / "user_app" / "build" / "web"

    @api.get("/", include_in_schema=False)
    def web_root():
        return RedirectResponse("/app")

    @api.get("/app", include_in_schema=False)
    def flutter_app_root():
        return FileResponse(
            flutter_dir / "index.html",
            headers=_flutter_asset_headers("index.html"),
        )

    @api.get("/app/admin", include_in_schema=False)
    @api.get("/app/admin/", include_in_schema=False)
    def flutter_admin_root():
        return FileResponse(
            flutter_dir / "admin-index.html",
            headers=_flutter_asset_headers("admin-index.html"),
        )

    @api.get("/app/{path:path}", include_in_schema=False)
    def flutter_app(path: str):
        candidate = flutter_dir / path
        if candidate.is_file():
            return FileResponse(candidate, headers=_flutter_asset_headers(path))
        shell = "admin-index.html" if path.startswith("admin/") else "index.html"
        return FileResponse(
            flutter_dir / shell,
            headers=_flutter_asset_headers(shell),
        )

    @api.get("/admin", include_in_schema=False)
    @api.get("/admin/stocks", include_in_schema=False)
    def admin_page():
        return FileResponse(static_dir / "admin.html")

    @api.get("/assets/admin.css", include_in_schema=False)
    def admin_css(): return FileResponse(static_dir / "admin.css")

    @api.get("/assets/admin.js", include_in_schema=False)
    def admin_js(): return FileResponse(static_dir / "admin.js")

    @api.get("/private-journal-acceptance.html", include_in_schema=False)
    def private_journal_acceptance():
        return FileResponse(static_dir / "private-journal-acceptance.html")

    @api.get("/usefulness-feedback-acceptance.html", include_in_schema=False)
    def usefulness_feedback_acceptance():
        return FileResponse(static_dir / "usefulness-feedback-acceptance.html")

    @public_router.get("/reports/{scope_type}/{scope_id}", response_model=PublicReportOut | PublicWaitingOut)
    def public_report(scope_type: str, scope_id: str, analysis_as_of: str = Query(default="", max_length=10)):
        try:
            return jsonable_encoder(public.report(scope_type, scope_id, analysis_as_of=analysis_as_of))
        except PublicReportWaiting:
            return {"analysis_as_of": analysis_as_of, "scope_type": "symbol", "scope_id": scope_id.upper(),
                    "data_status": "waiting", "data": {}}

    def public_report_list(scope_type: str, scope_id: str, analysis_as_of: str = "") -> dict[str, Any]:
        return {"items": [jsonable_encoder(public.report(scope_type, scope_id, analysis_as_of=analysis_as_of))]}

    @public_router.get("/daily-brief", response_model=PublicReportListOut)
    def daily_brief(scope_id: str = Query("market", max_length=80), analysis_as_of: str = Query("", max_length=10)):
        return public_report_list("market", scope_id, analysis_as_of)

    @lru_cache(maxsize=1)
    def market_home_snapshot(minute: int):
        result = query_core.market_home()
        prices, refresh, current, phase, authorized = resolve_prices({
            "TAIEX": {"market": "TWSE_INDEX", "enabled": True},
        })
        quote = prices.get("TAIEX")
        section = (result.get("sections") or {}).get("taiex")
        if quote and isinstance(section, dict):
            quote_date = str(quote.get("price_date") or "")
            eod_date = str(section.get("as_of") or "")
            if quote_date and (not eod_date or quote_date > eod_date):
                section.update({
                    "status": "available" if quote.get("state") == "intraday" else "partial",
                    "as_of": quote_date,
                    "freshness_days": 0,
                    "row_count": 1,
                    "coverage": {"requested_symbols": 1, "received_symbols": 1},
                    "provenance": {"source": "twse_mis", "route_version": ROUTE_VERSION},
                    "data": {"benchmark_id": "TAIEX", "close": quote.get("price")},
                    "quote_state": quote.get("state"),
                    "is_final": False,
                })
        result["latest_price"] = {
            "route_version": ROUTE_VERSION,
            "session": phase,
            "refresh_status": "blocked" if not authorized else refresh.get("status", "idle"),
            "checked_at": current.isoformat(),
        }
        return result

    @public_router.get("/market-home", response_model=MarketHomeOut)
    def market_home():
        return jsonable_encoder(market_home_snapshot(int(monotonic()) // 60))

    @public_router.get("/sector-rotation", response_model=PublicReportListOut)
    def sector_rotation(scope_id: str = Query(..., min_length=1, max_length=80), analysis_as_of: str = Query("", max_length=10)):
        return public_report_list("industry", scope_id, analysis_as_of)

    @public_router.get("/topics", response_model=PublicReportListOut)
    def topics(scope_id: str = Query("market", max_length=80), analysis_as_of: str = Query("", max_length=10)):
        return public_report_list("market", scope_id, analysis_as_of)

    @public_router.get("/candidates", response_model=PublicReportListOut)
    def candidates(scope_id: str = Query("market", max_length=80), analysis_as_of: str = Query("", max_length=10)):
        return public_report_list("market", scope_id, analysis_as_of)

    @public_router.get("/stock-health/{symbol}", response_model=PublicReportOut | PublicWaitingOut)
    def stock_health(symbol: str, analysis_as_of: str = Query("", max_length=10)):
        try:
            return jsonable_encoder(public.report("symbol", symbol, analysis_as_of=analysis_as_of))
        except PublicReportWaiting:
            return {"analysis_as_of": analysis_as_of, "scope_type": "symbol", "scope_id": symbol.upper(),
                    "data_status": "waiting", "data": {}}

    @public_router.get("/stock-header/{symbol}")
    def stock_header(symbol: str):
        symbol = public.require_enabled_symbol(symbol)
        identity = repository.stock_identities({symbol}).get(symbol)
        name, identity_status, _ = stock_identity(identity)
        result = {"symbol": symbol, "stock_name": name, "identity_status": identity_status,
                  "close": None, "trade_date": None, "price_status": "missing",
                  "previous_close": None, "change": None, "change_percent": None}
        persisted_rows = []
        try:
            page = query_core.page("ohlcv", symbol, limit=2, offset=0)
            persisted_rows = list(page.rows)
            if persisted_rows:
                row = persisted_rows[0]
                result.update(close=row.get("close"), trade_date=row.get("trade_date"),
                              price_status="persisted" if row.get("close") is not None else "missing")
        except (QueryValidationError, RuntimeError):
            pass
        if identity:
            prices, refresh, current, phase, authorized = resolve_prices({symbol: identity})
            quote = prices.get(symbol)
            if quote:
                result.update(
                    close=quote.get("price"),
                    trade_date=quote.get("price_date"),
                    price_status="stale" if quote.get("state") == "stale" else "available",
                    price_source=quote.get("source"),
                    quote_state=quote.get("state"),
                    quote_at=quote.get("quote_at"),
                    is_final=bool(quote.get("is_final")),
                    route_version=ROUTE_VERSION,
                    refresh_status="blocked" if not authorized else refresh.get("status", "idle"),
                    session=phase,
                    checked_at=current.isoformat(),
                )
        if persisted_rows and result.get("close") is not None:
            current_date = str(result.get("trade_date") or "")
            latest_date = str(persisted_rows[0].get("trade_date") or "")
            reference = (
                persisted_rows[1].get("close")
                if current_date and current_date == latest_date and len(persisted_rows) > 1
                else persisted_rows[0].get("close")
            )
            try:
                current_close = Decimal(str(result["close"]))
                previous_close = Decimal(str(reference))
                if current_close.is_finite() and previous_close.is_finite() and previous_close != 0:
                    change = current_close - previous_close
                    result.update(
                        previous_close=str(previous_close),
                        change=str(change),
                        change_percent=str(change / previous_close),
                    )
            except (InvalidOperation, TypeError, ValueError):
                pass
        return jsonable_encoder(result)

    def public_dataset(symbol: str, dataset_id: str, limit: int, offset: int) -> dict[str, Any]:
        symbol = public.require_enabled_symbol(symbol)
        try:
            page = query_core.page(dataset_id, symbol, limit=limit, offset=offset)
        except QueryValidationError:
            return {"data_status": "waiting", "dataset_id": dataset_id, "symbol": symbol.upper(),
                    "rows": [], "limit": limit, "offset": offset}
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail="public data unavailable") from error
        status_name = "available" if page.rows else "waiting"
        return jsonable_encoder({"data_status": status_name, "dataset_id": page.dataset_id,
                                 "symbol": page.symbol, "rows": page.rows,
                                 "limit": page.limit, "offset": page.offset})

    @public_router.get("/history/{symbol}", response_model=PublicDatasetOut)
    def public_history(symbol: str, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
        return public_dataset(symbol, "ohlcv", limit, offset)

    @public_router.get("/kline/{symbol}", response_model=PublicDatasetOut)
    def public_kline(symbol: str, limit: int = Query(200, ge=1, le=200), offset: int = Query(0, ge=0)):
        return public_dataset(symbol, "ohlcv", limit, offset)

    @public_router.get("/events/{symbol}", response_model=PublicDatasetOut)
    def public_events(symbol: str, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
        return public_dataset(symbol, "events", limit, offset)

    def core_summary(symbol: str):
        try:
            return jsonable_encoder(query_core.summary(symbol))
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail="core query unavailable") from error

    def core_page(symbol: str, dataset_id: str, limit: int = Query(50, ge=1, le=200),
                  offset: int = Query(0, ge=0)):
        try:
            page = query_core.page(dataset_id, symbol, limit=limit, offset=offset)
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail="core query unavailable") from error
        return jsonable_encoder({"dataset_id":page.dataset_id,"symbol":page.symbol,"rows":page.rows,
                                 "limit":page.limit,"offset":page.offset})

    admin.add_api_route("/core/{symbol}/summary", core_summary, methods=["GET"], response_model=CoreSummaryOut)
    admin.add_api_route("/core/{symbol}/datasets/{dataset_id}", core_page, methods=["GET"], response_model=CorePageOut)
    legacy_core.add_api_route("/{symbol}/summary", core_summary, methods=["GET"], response_model=CoreSummaryOut,
                              deprecated=True)
    legacy_core.add_api_route("/{symbol}/datasets/{dataset_id}", core_page, methods=["GET"],
                              response_model=CorePageOut, deprecated=True)

    @private.get("/profile")
    def profile(current: AuthenticatedUser = Depends(user)) -> dict[str, Any]:
        return {"user_id":current.user_id,"email":current.email}

    @private.get("/investment-profile", response_model=InvestmentProfileOut)
    def investment_profile(current: AuthenticatedUser = Depends(user)):
        return jsonable_encoder(repository.investment_profile(current.user_id))

    @private.get("/broker-profile")
    def broker_profile(current: AuthenticatedUser = Depends(user)):
        return jsonable_encoder(repository.broker_profile(current.user_id))

    @private.put("/broker-profile")
    def save_broker_profile(value: BrokerProfileIn, current: AuthenticatedUser = Depends(user),
                            idempotency_key: str = Depends(key)):
        return jsonable_encoder(repository.save_broker_profile(current.user_id,value,idempotency_key))

    @private.put("/investment-profile", response_model=InvestmentProfileOut)
    def update_investment_profile(value: InvestmentProfileIn, current: AuthenticatedUser = Depends(user),
                                  idempotency_key: str = Depends(key)):
        result=repository.save_investment_profile(current.user_id,value,idempotency_key)
        store.upsert("investment_profile_revisions",[{"user_id":current.user_id,**result}])
        return jsonable_encoder(result)

    @private.get("/ai-sources")
    def ai_sources(_current: AuthenticatedUser = Depends(user)):
        return {"items":contexts.sources()}

    @private.post("/journal/events", status_code=201)
    def add_ledger(value: LedgerEventIn, background_tasks: BackgroundTasks,
                   current: AuthenticatedUser = Depends(user), idempotency_key: str = Depends(key)):
        result = repository.add_ledger(current.user_id,value,idempotency_key)
        background_tasks.add_task(recalculate_private_mart_safely,current.user_id)
        return jsonable_encoder(result)

    @private.post("/journal/events/{event_id}/corrections", status_code=201)
    def correct_ledger(event_id: UUID,value:CorrectionIn,background_tasks:BackgroundTasks,
                       current:AuthenticatedUser=Depends(user),idempotency_key:str=Depends(key)):
        result=repository.correct_ledger(current.user_id,event_id,value.expected_version,value.replacement,idempotency_key)
        background_tasks.add_task(recalculate_private_mart_safely,current.user_id)
        return jsonable_encoder(result)

    @private.post("/journal/events/{event_id}/reversals", status_code=201)
    def reverse_ledger(event_id:UUID,value:LedgerReversalIn,background_tasks:BackgroundTasks,
                       current:AuthenticatedUser=Depends(user),idempotency_key:str=Depends(key)):
        """Append a reversal-only event; the original ledger row remains immutable for audit."""
        result=repository.reverse_ledger(current.user_id,event_id,value.expected_version,idempotency_key)
        background_tasks.add_task(recalculate_private_mart_safely,current.user_id)
        return jsonable_encoder(result)

    @private.post("/journal/recalculate", status_code=202)
    def recalculate_ledger(current: AuthenticatedUser = Depends(user)):
        try:
            result=recalculate_private_mart(current.user_id, "manual")
        except Exception as error:
            LOGGER.warning("manual private recalculation enqueue/dispatch failed: %s",type(error).__name__)
            raise HTTPException(status_code=503,detail="損益重新計算暫時無法使用") from error
        return jsonable_encoder({
            **result,
            "ledger_version":repository.latest_ledger_version(current.user_id),
        })

    @private.get("/journal/recalculation-status")
    def recalculation_status(current: AuthenticatedUser = Depends(user)):
        value = repository.recalculation_status(current.user_id)
        if not value:
            return {"status": "IDLE", "can_retry": True}
        return jsonable_encoder({
            "request_id": value["request_id"],
            "requested_ledger_version": value["requested_ledger_version"],
            "status": value["status"],
            "trigger_source": value["trigger_source"],
            "error_code": value.get("error_code"),
            "message": value.get("safe_message"),
            "requested_at": value.get("requested_at"),
            "started_at": value.get("started_at"),
            "finished_at": value.get("finished_at"),
            "can_retry": value["status"] in {"SUCCEEDED","FAILED","CANCELLED"},
        })

    @private.get("/journal/history")
    def history(symbol: str|None=None,year:int|None=Query(None,ge=1900,le=9999),current:AuthenticatedUser=Depends(user)):
        rows=repository.ledger_history(current.user_id,symbol,year)
        symbols={str(row.get("symbol")) for row in rows if row.get("symbol")}
        identities=repository.stock_identities(symbols) if symbols else {}
        enriched=[]
        for row in rows:
            identity=identities.get(str(row.get("symbol")))
            stock_name,identity_status,identity_missing_reason=stock_identity(identity)
            enriched.append({**row,"stock_name":stock_name,"identity_status":identity_status,
                "identity_missing_reason":identity_missing_reason,
                "net_cash_flow":ledger_net_cash_flow(row)})
        return jsonable_encoder(enriched)

    @private.get("/journal/positions")
    def positions(current:AuthenticatedUser=Depends(user)):
        operational = None
        try:
            reader = getattr(repository, "positions", None)
            operational = reader(current.user_id) if reader is not None else None
        except Exception as error:
            LOGGER.warning("operational positions unavailable; falling back to Private Mart: %s", type(error).__name__)
            operational = None

        if operational is None:
            summaries=store.mart("mart_user_portfolio_summary",current.user_id)
            if not summaries: return []
            anchors={(str(row.get("valuation_date")),int(row.get("ledger_version",0))) for row in summaries}
            if len(anchors)!=1: return []
            valuation_date,ledger_version=next(iter(anchors))
            snapshot={"valuation_date":valuation_date,"ledger_version":ledger_version}
            rows=store.mart("mart_user_positions",current.user_id,**snapshot)
            missing_names={str(row.get("symbol")) for row in rows
                           if row.get("symbol") and not str(row.get("stock_name") or "").strip()}
            identities=repository.stock_identities(missing_names) if missing_names else {}
            unrealized={(row.get("symbol"),row.get("currency")):row for row in
                        store.mart("mart_user_unrealized_pnl",current.user_id,**snapshot)}
            result=[]
            for row in rows:
                detail=unrealized.get((row.get("symbol"),row.get("currency")),{})
                identity=identities.get(str(row.get("symbol")))
                fallback_name,fallback_status,fallback_reason=stock_identity(identity)
                stock_name=str(row.get("stock_name") or fallback_name or "").strip() or None
                identity_status=(fallback_status if identity else row.get("identity_status") or fallback_status)
                result.append({**row,"unrealized_pnl":detail.get("unrealized_pnl"),
                    "unrealized_return":detail.get("unrealized_return"),
                    "stock_name":stock_name,"identity_status":identity_status,
                    "identity_missing_reason":fallback_reason if identity else row.get("identity_missing_reason") or fallback_reason,
                    "price_status":row.get("price_status") or detail.get("price_status","missing"),
                    "price_date":row.get("price_date") or detail.get("price_date"),
                    "missing_reason":row.get("missing_reason") or detail.get("missing_reason")})
            return jsonable_encoder(result)

        if not operational:
            return []
        latest_version=max(int(row.get("ledger_version",0)) for row in operational)
        identities=repository.stock_identities({str(row["symbol"]) for row in operational})
        canonical_positions={}
        canonical_unrealized={}
        summaries=store.mart("mart_user_portfolio_summary",current.user_id)
        anchors={(str(row.get("valuation_date")),int(row.get("ledger_version",0))) for row in summaries}
        if len(anchors)==1:
            valuation_date,canonical_version=next(iter(anchors))
            if canonical_version==latest_version:
                snapshot={"valuation_date":valuation_date,"ledger_version":canonical_version}
                canonical_positions={(row.get("symbol"),row.get("currency")):row for row in
                                     store.mart("mart_user_positions",current.user_id,**snapshot)}
                canonical_unrealized={(row.get("symbol"),row.get("currency")):row for row in
                                      store.mart("mart_user_unrealized_pnl",current.user_id,**snapshot)}
        result=[]
        for row in operational:
            key_=(row.get("symbol"),row.get("currency"))
            priced=canonical_positions.get(key_,{})
            detail=canonical_unrealized.get(key_,{})
            identity=identities.get(str(row.get("symbol")))
            stock_name,identity_status,identity_missing_reason=stock_identity(identity)
            has_canonical=bool(priced)
            result.append({**row,
                "stock_name":stock_name,"identity_status":identity_status,
                "identity_missing_reason":identity_missing_reason,
                "valuation_date":priced.get("valuation_date"),
                "market_price":priced.get("market_price"),"market_value":priced.get("market_value"),
                "unrealized_pnl":detail.get("unrealized_pnl"),
                "unrealized_return":detail.get("unrealized_return"),
                "price_status":priced.get("price_status") or detail.get("price_status") or "pending",
                "price_date":priced.get("price_date") or detail.get("price_date"),
                "missing_reason":priced.get("missing_reason") or detail.get("missing_reason") or
                                 (None if has_canonical else "private_mart_pending")})
        return jsonable_encoder(result)

    def resolved_portfolio_quotes(current: AuthenticatedUser, *, force: bool = False):
        rows = repository.positions(current.user_id)
        latest_version = repository.latest_ledger_version(current.user_id) if rows else 0
        if rows and any(int(row.get("ledger_version", 0)) != latest_version for row in rows):
            raise HTTPException(status_code=409, detail="交易已儲存，等待投資組合批次更新")
        identities = repository.stock_identities({str(row["symbol"]) for row in rows}) if rows else {}
        rows = [{**row, "stock_name": stock_identity(identities.get(str(row["symbol"])))[0]} for row in rows]
        try:
            prices, refresh, current_time, phase, authorized = resolve_prices(identities, force=force)
        except Exception as error:
            LOGGER.warning("latest price resolver unavailable: %s", type(error).__name__)
            raise HTTPException(status_code=503, detail="最後行情讀取暫時無法使用") from error
        # One bounded PostgreSQL query across the owner's eligible holdings;
        # never issue a Core/Iceberg reader request per symbol on page load.
        price_dates = {
            symbol: str(quote.get("price_date") or "")[:10]
            for symbol, quote in prices.items()
            if quote.get("state") in {"intraday", "closing_pending_eod", "eod_final"}
            and str(quote.get("price_date") or "")[:10].count("-") == 2
        }
        previous = {}
        if price_dates:
            try:
                reader = getattr(repository, "official_previous_closes", None)
                if reader is not None:
                    previous = reader(price_dates)
            except Exception as error:
                LOGGER.warning("official previous close unavailable: %s", type(error).__name__)
        result = value_holdings(rows, prices, current_time, previous_closes=previous)
        result["market_open"] = phase == "regular"
        result.update(
            route_version=ROUTE_VERSION,
            refresh_status="blocked" if not authorized else refresh.get("status", "idle"),
            session=phase,
            fallback="persistent_last_success" if prices else "missing",
        )
        return jsonable_encoder(result)

    @private.get("/portfolio/quotes")
    def portfolio_quotes(current: AuthenticatedUser = Depends(user)):
        return resolved_portfolio_quotes(current)

    @private.post("/portfolio/quotes/refresh")
    def refresh_portfolio_quotes(current: AuthenticatedUser = Depends(user)):
        return resolved_portfolio_quotes(current, force=True)

    @private.get("/journal/pnl")
    def pnl(year:int=Query(...,ge=1900,le=9999),current:AuthenticatedUser=Depends(user)):
        rows=store.mart("mart_user_annual_pnl",current.user_id,year=year)
        if rows and max(row.get("ledger_version",0) for row in rows)!=repository.latest_ledger_version(current.user_id):
            rows=[]
        return jsonable_encoder(rows)

    @private.get("/journal/monthly-summary", response_model=MonthlyLedgerSummaryOut)
    def monthly_ledger_summary(year:int=Query(...,ge=1900,le=9999),current:AuthenticatedUser=Depends(user)):
        rows=store.mart("mart_user_monthly_ledger_summary",current.user_id,year=year)
        if rows and max(row.get("ledger_version",0) for row in rows)!=repository.latest_ledger_version(current.user_id):
            rows=[]
        return {"items":jsonable_encoder(rows)}

    @private.get("/journal/symbol-summary")
    def symbol_ledger_summary(year:int=Query(...,ge=1900,le=9999),current:AuthenticatedUser=Depends(user)):
        rows=store.mart("mart_user_symbol_ledger_summary",current.user_id,year=year)
        if rows and max(row.get("ledger_version",0) for row in rows)!=repository.latest_ledger_version(current.user_id):
            rows=[]
        return {"items":jsonable_encoder(rows)}

    def portfolio_mart(table: str, current: AuthenticatedUser, **filters: Any) -> dict[str, Any]:
        rows=jsonable_encoder(store.mart(table,current.user_id,**filters))
        if table=="mart_user_exposure":
            for row in rows:
                row["symbols"]=json.loads(row["symbols"]); row["membership_snapshot"]=json.loads(row["membership_snapshot"])
        if table=="mart_user_portfolio_summary":
            for row in rows:
                missing=int(row.get("missing_price_count") or 0); stale=int(row.get("stale_price_count") or 0)
                affected=bool(missing or stale)
                row.setdefault("aggregate_status","withheld" if affected else "available")
                raw=row.get("affected_symbols",[])
                row["affected_symbols"]=json.loads(raw) if isinstance(raw,str) else list(raw or [])
                row.setdefault("affected_symbol_count",len(row["affected_symbols"]))
                row.setdefault("unrealized_return",None)
                if row["aggregate_status"]=="withheld":
                    row["market_value"]=None; row["unrealized_pnl"]=None; row["unrealized_return"]=None
        return {"items":rows}

    @private.get("/portfolio/summary", response_model=PortfolioSummaryOut)
    def portfolio_summary(current: AuthenticatedUser = Depends(user)):
        return portfolio_mart("mart_user_portfolio_summary",current)

    @private.get("/portfolio/exposure", response_model=PortfolioExposureOut)
    def portfolio_exposure(current: AuthenticatedUser = Depends(user)):
        return portfolio_mart("mart_user_exposure",current)

    @private.get("/portfolio/performance", response_model=PortfolioPerformanceOut)
    def portfolio_performance(year:int=Query(...,ge=1900,le=9999),current:AuthenticatedUser=Depends(user)):
        return portfolio_mart("mart_user_annual_performance",current,year=year)

    @private.get("/portfolio/stress-tests", response_model=PortfolioStressOut)
    def portfolio_stress_tests(current: AuthenticatedUser = Depends(user)):
        return portfolio_mart("mart_user_stress_tests",current)

    @private.get("/analysis-feedback")
    def analysis_feedback(analysis_execution_id:UUID,scope_type:str=Query(...,pattern="^(market|industry|symbol)$"),
                          scope_id:str=Query(...,min_length=1,max_length=80),
                          current:AuthenticatedUser=Depends(user)):
        return jsonable_encoder(repository.analysis_feedback(
            current.user_id,analysis_execution_id,scope_type,scope_id))

    @private.put("/analysis-feedback")
    def save_analysis_feedback(value:AnalysisFeedbackIn,current:AuthenticatedUser=Depends(user),
                               idempotency_key:str=Depends(key)):
        return jsonable_encoder(repository.save_analysis_feedback(current.user_id,value,idempotency_key))

    @private.post("/notes",status_code=201)
    def add_note(value:NoteIn,current:AuthenticatedUser=Depends(user),idempotency_key:str=Depends(key)):
        repository.require_owned_trade(current.user_id,value.trade_event_id)
        note_id=uuid5(NAMESPACE_URL,f"janus-note:{current.user_id}:{idempotency_key}")
        ref=store.write_note(user_id=current.user_id,note_id=note_id,revision=1,**value.model_dump())
        return jsonable_encoder(repository.add_note(current.user_id,value,idempotency_key,ref,note_id))

    @private.put("/notes/{note_id}")
    def revise_note(note_id:UUID,value:NoteRevisionIn,current:AuthenticatedUser=Depends(user),idempotency_key:str=Depends(key)):
        payload=NoteIn.model_validate(value.model_dump(exclude={"expected_version"}))
        repository.require_owned_trade(current.user_id,payload.trade_event_id)
        ref=store.write_note(user_id=current.user_id,note_id=note_id,revision=value.expected_version+1,**payload.model_dump())
        return jsonable_encoder(repository.revise_note(current.user_id,note_id,value.expected_version,payload,idempotency_key,ref))

    @private.get("/notes")
    def notes(symbol:str|None=None,current:AuthenticatedUser=Depends(user)):
        return jsonable_encoder(store.read_notes(current.user_id,repository.notes(current.user_id,symbol)))

    @private.get("/watchlist/search")
    def watchlist_search(q: str = Query(..., min_length=1, max_length=80),
                         current: AuthenticatedUser = Depends(user)):
        return jsonable_encoder({"items": repository.search_watchlist_stocks(q.strip())})

    @private.get("/watchlist")
    def watchlist(current:AuthenticatedUser=Depends(user)):
        rows = repository.watchlist(current.user_id)
        identities = repository.stock_identities({str(row["symbol"]) for row in rows}) if rows else {}
        prices, _, _, _, _ = resolve_prices(identities)
        result = []
        for row in rows:
            quote = prices.get(str(row["symbol"]))
            if quote:
                row = {**row,
                       "market_price": quote.get("price"),
                       "price_date": quote.get("price_date"),
                       "price_status": "stale" if quote.get("state") == "stale" else "available",
                       "price_source": quote.get("source"),
                       "quote_state": quote.get("state"),
                       "quote_at": quote.get("quote_at"),
                       "is_final": bool(quote.get("is_final")),
                       "route_version": ROUTE_VERSION}
            result.append(row)
        return jsonable_encoder(result)

    @private.post("/watchlist",status_code=201)
    def follow(value:WatchlistIn,current:AuthenticatedUser=Depends(user),idempotency_key:str=Depends(key)):
        return jsonable_encoder(repository.follow(current.user_id,value,idempotency_key))

    @private.delete("/watchlist/{symbol}",status_code=204)
    def unfollow(symbol:str,current:AuthenticatedUser=Depends(user),idempotency_key:str=Depends(key)):
        repository.unfollow(current.user_id,symbol,idempotency_key); return Response(status_code=204)

    @private.put("/watchlist/order")
    def reorder(value:WatchlistOrderIn,current:AuthenticatedUser=Depends(user),idempotency_key:str=Depends(key)):
        return jsonable_encoder(repository.reorder(current.user_id,value.symbols,value.expected_version,idempotency_key))

    @private.get("/export")
    def export(current:AuthenticatedUser=Depends(user)):
        indexes=repository.notes(current.user_id)
        return jsonable_encoder({"journal":repository.ledger_history(current.user_id,None,None),
            "notes":store.read_notes(current.user_id,indexes),"watchlist":repository.watchlist(current.user_id),
            "investment_profile":repository.investment_profile(current.user_id),
            "broker_profile_revisions":repository.broker_profile_history(current.user_id),
            "positions":store.mart("mart_user_positions",current.user_id),
            "portfolio_summary":store.mart("mart_user_portfolio_summary",current.user_id),
            "portfolio_exposure":store.mart("mart_user_exposure",current.user_id),
            "portfolio_performance":store.mart("mart_user_annual_performance",current.user_id),
            "portfolio_stress_tests":store.mart("mart_user_stress_tests",current.user_id),
            "analysis_feedback":repository.analysis_feedback_export(current.user_id),
            "assistant":store.export_assistant(current.user_id)})

    @private.delete("/private-data",status_code=202)
    def delete_private_data(current:AuthenticatedUser=Depends(user),idempotency_key:str=Depends(key)):
        return jsonable_encoder(repository.request_deletion(current.user_id,idempotency_key))

    @private.get("/private-data/{request_id}")
    def deletion_status(request_id: UUID, current: AuthenticatedUser = Depends(user)):
        return jsonable_encoder(repository.deletion_request(current.user_id, request_id))

    def admin_actor(current: AuthenticatedAdmin = Depends(authenticate_admin)) -> str:
        return current.email

    @admin.get("/stocks")
    def admin_stocks(q: str = Query("", max_length=80), enabled: bool | None = Query(None),
                     limit: int = Query(10, ge=1, le=100), cursor: str | None = Query(None)):
        items = admin_service.stocks(q, enabled=enabled, limit=limit + 1, cursor=cursor)
        page = items[:limit]
        return jsonable_encoder({"items": page, "limit": limit,
                                 "next_cursor": page[-1]["symbol"] if len(items) > limit else None})

    @admin.post("/stocks")
    @admin.put("/stocks")
    def admin_upsert_stock(payload: dict[str, Any] = Body(...)):
        return jsonable_encoder(admin_service.upsert_stock(payload))

    @admin.patch("/stocks/{symbol}/enabled")
    def admin_set_stock_enabled(symbol: str, payload: dict[str, Any] = Body(...)):
        if not isinstance(payload.get("enabled"), bool):
            raise AdminValidationError("enabled must be a boolean")
        admin_service.set_stock_enabled(symbol, payload["enabled"])
        return {"symbol": symbol, "enabled": payload["enabled"]}

    @admin.get("/stocks/{symbol}/references")
    def admin_stock_references(symbol: str):
        return jsonable_encoder(admin_service.stock_references(symbol))

    @admin.delete("/stocks/{symbol}")
    def admin_delete_stock(symbol: str):
        admin_service.delete_stock(symbol)
        return {"symbol": symbol, "deleted": True}

    @admin.get("/stocks/{symbol}/status")
    def admin_stock_status(symbol: str):
        return jsonable_encoder(admin_service.stock_status(symbol))

    @admin.get("/executions")
    def admin_executions(limit: int = Query(10, ge=1, le=50), cursor: str | None = Query(None)):
        items = admin_service.executions(limit=limit + 1, cursor=cursor)
        page = items[:limit]
        next_cursor = f'{page[-1]["requested_at"]},{page[-1]["execution_id"]}' if len(items) > limit else None
        return jsonable_encoder({"items": page, "limit": limit, "next_cursor": next_cursor})

    @admin.get("/executions/{execution_id}")
    def admin_execution_details(execution_id: str):
        return jsonable_encoder(admin_service.execution_details(execution_id))

    @admin.post("/executions/{execution_id}/items/{item_key}/retry", status_code=202)
    def admin_retry_execution_item(execution_id: str, item_key: str):
        return jsonable_encoder(admin_service.retry_execution_item(execution_id, item_key))

    @admin.post("/executions/collection", status_code=202)
    def admin_enqueue_collection(payload: dict[str, Any] = Body(...)):
        config_id = payload.get("config_id")
        if not isinstance(config_id, str) or not config_id.strip():
            raise AdminValidationError("config_id is required")
        symbols = tuple(payload["symbols"]) if isinstance(payload.get("symbols"), list) else None
        return jsonable_encoder(admin_service.enqueue_collection(
            config_id, symbols, request_options=payload.get("options") or {},
        ))

    @admin.post("/executions/analysis", status_code=202)
    def admin_enqueue_analysis(payload: dict[str, Any] = Body(...)):
        config_id = payload.get("config_id")
        if not isinstance(config_id, str) or not config_id.strip():
            raise AdminValidationError("config_id is required")
        symbols = tuple(payload["symbols"]) if isinstance(payload.get("symbols"), list) else None
        return jsonable_encoder(admin_service.enqueue_analysis(config_id, symbols))

    @admin.get("/mart-reports")
    def admin_mart_reports(analysis_as_of: str = Query("", max_length=10), scope_type: str = Query(""),
                           scope_id: str = Query(""), role: str = Query(""), prompt_version: str = Query(""),
                           analysis_outcome: str = Query(""), publication_status: str = Query(""),
                           limit: int = Query(50, ge=1, le=100)):
        return jsonable_encoder({"items": admin_service.mart_reports(
            analysis_as_of=analysis_as_of, scope_type=scope_type, scope_id=scope_id, role=role,
            prompt_version=prompt_version, analysis_outcome=analysis_outcome,
            publication_status=publication_status, limit=limit), "limit": limit})

    @admin.patch("/mart-reports/{execution_id}/{scope_type}/{scope_id}/publication")
    def admin_review_mart_report(execution_id: str, scope_type: str, scope_id: str,
                                 payload: dict[str, Any] = Body(...), actor: str = Depends(admin_actor)):
        return jsonable_encoder(admin_service.review_mart_report(
            execution_id, scope_type, scope_id, payload.get("action", ""), payload.get("reason", ""), actor,
        ))

    @admin.get("/source-health")
    def admin_source_health(limit: int = Query(200, ge=1, le=200), cursor: str | None = Query(None)):
        items = admin_service.source_health(limit=limit + 1, cursor=cursor)
        page = items[:limit]
        next_cursor = f'{page[-1]["source_id"]},{page[-1]["dataset_id"]}' if len(items) > limit else None
        return jsonable_encoder({"items": page, "limit": limit, "next_cursor": next_cursor})

    @admin.get("/memberships/{coverage_tier}")
    def admin_membership(coverage_tier: str):
        return jsonable_encoder(admin_service.membership_snapshot(coverage_tier))

    @admin.get("/market-universe")
    def admin_market_universe():
        return jsonable_encoder(admin_service.liquid_500_snapshot())

    @admin.get("/batches")
    def admin_batches(days: int = Query(3, ge=1, le=31),
                      until: datetime | None = None, limit: int = Query(100, ge=1, le=100),
                      before_id: str | None = Query(None, max_length=200)):
        return jsonable_encoder(admin_service.batches(days=days, until=until, limit=limit, before_id=before_id))

    @admin.get("/data-governance")
    def admin_data_governance():
        return jsonable_encoder(admin_service.data_governance())

    @admin.post("/market-universe/swap")
    def admin_swap_market_universe(payload: dict[str, Any] = Body(...),
                                   actor: str = Depends(admin_actor)):
        expected = payload.get("expected_version")
        if isinstance(expected, bool) or not isinstance(expected, int) or expected < 1:
            raise AdminValidationError("expected_version is required")
        return jsonable_encoder(admin_service.swap_liquid_500(
            remove_symbol=str(payload.get("remove_symbol") or "").strip(),
            add_symbol=str(payload.get("add_symbol") or "").strip(),
            reason=str(payload.get("reason") or "").strip(), expected_version=expected,
            actor=actor,
        ))

    @admin.put("/memberships/{coverage_tier}")
    def admin_save_membership(coverage_tier: str, payload: MembershipEditIn,
                              actor: str = Depends(admin_actor)):
        return jsonable_encoder(admin_service.set_membership(
            coverage_tier, tuple(payload.symbols), effective_from=payload.effective_from,
            reason=payload.reason, owner=actor, expected_version=payload.expected_version,
        ))

    @admin.get("/source-catalog")
    def admin_source_catalog(limit: int = Query(200, ge=1, le=200), cursor: str | None = Query(None)):
        items = admin_service.collection_configs(limit=limit + 1, cursor=cursor)
        page = items[:limit]
        return jsonable_encoder({"items": page, "limit": limit,
                                 "next_cursor": page[-1]["config_id"] if len(items) > limit else None})

    @admin.post("/source-catalog")
    @admin.put("/source-catalog")
    def admin_save_source_catalog(payload: dict[str, Any] = Body(...), actor: str = Depends(admin_actor)):
        return jsonable_encoder(admin_service.save_collection_config(payload, actor=actor))

    @admin.get("/source-reviews/{adapter_id}")
    def admin_source_review(adapter_id: str):
        return jsonable_encoder(admin_service.source_review(adapter_id))

    @admin.post("/source-reviews/{adapter_id}")
    @admin.put("/source-reviews/{adapter_id}")
    def admin_save_source_review(adapter_id: str, payload: dict[str, Any] = Body(...), actor: str = Depends(admin_actor)):
        expected = payload.get("expected_version")
        if isinstance(expected, bool) or not isinstance(expected, int) or expected < 0:
            raise AdminValidationError("expected_version is required")
        return jsonable_encoder(admin_service.save_source_review(
            adapter_id, payload.get("value"), actor=actor, expected_version=expected,
        ))

    @admin.get("/private-recalculations")
    def admin_private_recalculations(limit: int = Query(50, ge=1, le=100)):
        rows = repository.admin_recalculations(limit)
        configured = admin_service.setting("private_recalc_workers").get("value") or {"workers": 2}
        workers = int(configured.get("workers", 2)) if isinstance(configured, dict) else 2
        return jsonable_encoder({
            "workers": workers,
            "running": sum(1 for row in rows if row["status"] in {"RUNNING","CANCEL_REQUESTED"}),
            "queued": sum(1 for row in rows if row["status"] == "QUEUED"),
            "items": rows,
        })

    @admin.post("/private-recalculations/{request_id}/cancel")
    def admin_cancel_private_recalculation(
        request_id: UUID,
        payload: dict[str, Any] = Body(default={}),
        actor: str = Depends(admin_actor),
    ):
        message = str(payload.get("reason") or "管理員要求中止")
        return jsonable_encoder(repository.admin_cancel_recalculation(request_id, message, actor))

    @admin.post("/private-recalculations/{request_id}/fail")
    def admin_fail_private_recalculation(
        request_id: UUID,
        payload: dict[str, Any] = Body(...),
        actor: str = Depends(admin_actor),
    ):
        reason = str(payload.get("reason") or "").strip()
        if not reason:
            raise HTTPException(status_code=422, detail="失敗原因不可為空白")
        return jsonable_encoder(repository.admin_fail_recalculation(request_id, reason, actor))

    @admin.get("/settings/{setting_key}")
    def admin_setting(setting_key: str):
        return jsonable_encoder(admin_service.setting(setting_key))

    @admin.get("/data-quality/runbook")
    def admin_data_quality_runbook():
        document = Path(__file__).resolve().parents[2] / "doc" / "runbook-data-supplement.md"
        return {"title": "資料補充與週六檢核操作", "content": document.read_text(encoding="utf-8")}

    @admin.post("/settings/{setting_key}")
    @admin.put("/settings/{setting_key}")
    def admin_save_setting(setting_key: str, payload: dict[str, Any] = Body(...), actor: str = Depends(admin_actor)):
        expected = payload.get("expected_version")
        if expected is not None and (isinstance(expected, bool) or not isinstance(expected, int) or expected < 0):
            raise AdminValidationError("expected_version must be a non-negative integer")
        return jsonable_encoder(admin_service.save_setting(
            setting_key, payload.get("value"), actor=actor, expected_version=expected,
        ))

    @admin.get("/governance/{governance_key}/history")
    def admin_governance_history(governance_key: str, limit: int = Query(50, ge=1, le=50)):
        return jsonable_encoder({"items": admin_service.governance_history(governance_key, limit=limit), "limit": limit})

    @admin.post("/governance/{governance_key}/diff")
    def admin_governance_diff(governance_key: str, payload: GovernanceDiffIn):
        return jsonable_encoder(admin_service.governance_diff(governance_key, payload.value))

    @admin.get("/governance/{governance_key}")
    def admin_governance(governance_key: str):
        return jsonable_encoder(admin_service.governance(governance_key))

    @admin.put("/governance/{governance_key}")
    def admin_save_governance(governance_key: str, payload: GovernanceEditIn, actor: str = Depends(admin_actor)):
        return jsonable_encoder(admin_service.save_governance(
            governance_key, payload.value, actor=actor, reason=payload.reason,
            status=payload.status, expected_version=payload.expected_version,
        ))

    @admin.get("/audit")
    def admin_audit(limit: int = Query(50, ge=1, le=50)):
        return jsonable_encoder({"items": admin_service.audit(limit=limit)})

    api.include_router(public_router)
    api.include_router(private)
    api.include_router(admin)
    api.include_router(legacy_core)
    return api


app = create_app()
