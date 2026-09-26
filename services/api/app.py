"""FastAPI boundary for the WBS 4J private workspace."""

from __future__ import annotations

import json
from hashlib import sha256
import logging
import os
from pathlib import Path
from threading import Lock
from time import monotonic
from typing import Any, Callable
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from fastapi import APIRouter, Body, Depends, FastAPI, Header, HTTPException, Query, Request, Response, status
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
from .models import (AdminResponseOut, AnalysisFeedbackIn, CorePageOut, CoreSummaryOut,
                     CorrectionIn, HealthOut, InvestmentProfileIn, InvestmentProfileOut, LedgerEventIn,
                     MonthlyLedgerSummaryOut,
                     NoteIn, NoteRevisionIn, PortfolioExposureOut, PortfolioPerformanceOut,
                     PortfolioStressOut, PortfolioSummaryOut,
                     PrivateResponseOut, PublicDatasetOut, PublicReportListOut, PublicReportOut, PublicWaitingOut,
                     WatchlistIn, WatchlistOrderIn,
                     GovernanceDiffIn, GovernanceEditIn, MembershipEditIn)
from .repository import ConflictError, NotFoundError, OversellError, repository_from_env
from .private_pipeline import ledger_net_cash_flow
from .public_runtime import build_admin_service, build_core_service, build_pipeline_service, build_public_service
from .store import PrivateIcebergStore


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
               oauth_facade: Any | None = None) -> FastAPI:
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
    repository = repository or _Lazy(repository_from_env)
    store = store or _Lazy(PrivateIcebergStore.from_env)
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
        response, response_status, headers = McpAdapter(contexts, oauth_service()).handle(
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

    _coop_headers = {"Cross-Origin-Opener-Policy": "unsafe-none"}

    @api.get("/", include_in_schema=False)
    def web_root():
        return RedirectResponse("/app")

    @api.get("/app", include_in_schema=False)
    def flutter_app_root():
        return FileResponse(flutter_dir / "index.html", headers=_coop_headers)

    @api.get("/app/{path:path}", include_in_schema=False)
    def flutter_app(path: str):
        candidate = flutter_dir / path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(flutter_dir / "index.html", headers=_coop_headers)

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
    def add_ledger(value: LedgerEventIn, current: AuthenticatedUser = Depends(user), idempotency_key: str = Depends(key)):
        return jsonable_encoder(repository.add_ledger(current.user_id,value,idempotency_key))

    @private.post("/journal/events/{event_id}/corrections", status_code=201)
    def correct_ledger(event_id: UUID,value:CorrectionIn,current:AuthenticatedUser=Depends(user),idempotency_key:str=Depends(key)):
        return jsonable_encoder(repository.correct_ledger(current.user_id,event_id,value.expected_version,value.replacement,idempotency_key))

    @private.get("/journal/history")
    def history(symbol: str|None=None,year:int|None=Query(None,ge=1900,le=9999),current:AuthenticatedUser=Depends(user)):
        rows=repository.ledger_history(current.user_id,symbol,year)
        symbols={str(row.get("symbol")) for row in rows if row.get("symbol")}
        identities=repository.stock_identities(symbols) if symbols else {}
        enriched=[]
        for row in rows:
            identity=identities.get(str(row.get("symbol")))
            stock_name=str(identity.get("name") or "").strip() if identity else ""
            identity_status=("available" if stock_name and identity and identity.get("enabled") is True else
                             "disabled" if stock_name and identity else "missing")
            enriched.append({**row,"stock_name":stock_name or None,"identity_status":identity_status,
                "identity_missing_reason":"stock_master_not_found" if identity_status=="missing" else None,
                "net_cash_flow":ledger_net_cash_flow(row)})
        return jsonable_encoder(enriched)

    @private.get("/journal/positions")
    def positions(current:AuthenticatedUser=Depends(user)):
        summaries=store.mart("mart_user_portfolio_summary",current.user_id)
        if not summaries: return []
        anchors={(str(row.get("valuation_date")),int(row.get("ledger_version",0))) for row in summaries}
        if len(anchors)!=1: return []
        valuation_date,ledger_version=next(iter(anchors))
        snapshot={"valuation_date":valuation_date,"ledger_version":ledger_version}
        rows=store.mart("mart_user_positions",current.user_id,**snapshot)
        unrealized={(row.get("symbol"),row.get("currency")):row for row in
                    store.mart("mart_user_unrealized_pnl",current.user_id,**snapshot)}
        result=[]
        for row in rows:
            detail=unrealized.get((row.get("symbol"),row.get("currency")),{})
            result.append({**row,"unrealized_pnl":detail.get("unrealized_pnl"),
                "unrealized_return":detail.get("unrealized_return"),
                "price_status":row.get("price_status") or detail.get("price_status","missing"),
                "price_date":row.get("price_date") or detail.get("price_date"),
                "missing_reason":row.get("missing_reason") or detail.get("missing_reason")})
        return jsonable_encoder(result)

    @private.get("/journal/pnl")
    def pnl(year:int=Query(...,ge=1900,le=9999),current:AuthenticatedUser=Depends(user)):
        return jsonable_encoder(store.mart("mart_user_annual_pnl",current.user_id,year=year))

    @private.get("/journal/monthly-summary", response_model=MonthlyLedgerSummaryOut)
    def monthly_ledger_summary(year:int=Query(...,ge=1900,le=9999),current:AuthenticatedUser=Depends(user)):
        rows=store.mart("mart_user_monthly_ledger_summary",current.user_id,year=year)
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

    @private.get("/watchlist")
    def watchlist(current:AuthenticatedUser=Depends(user)): return jsonable_encoder(repository.watchlist(current.user_id))

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

    @admin.get("/settings/{setting_key}")
    def admin_setting(setting_key: str):
        return jsonable_encoder(admin_service.setting(setting_key))

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
