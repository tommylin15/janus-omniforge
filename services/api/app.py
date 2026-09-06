"""FastAPI boundary for the WBS 4J private workspace."""

from __future__ import annotations

import os
from typing import Any, Callable
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import APIRouter, Depends, FastAPI, Header, Query, Request, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware

from .auth import (AuthenticatedUser, GoogleServiceAuthenticator, GoogleUserAuthenticator,
                   allowed_assistant_callers, allowed_user_emails)
from .context_sources import (ContextReferenceNotFound, ContextSourceError, ContextSourceService,
                              CoreContextReader)
from .mcp_gateway import McpGatewayClient, McpGatewayError
from .models import (ContextPreviewIn, ContextResolveIn, CorrectionIn, LedgerEventIn, NoteIn,
                     McpServersPutIn, NoteRevisionIn, WatchlistIn, WatchlistOrderIn)
from .repository import ConflictError, NotFoundError, OversellError, repository_from_env
from .store import PrivateIcebergStore


class _Lazy:
    def __init__(self, factory: Callable[[], Any]) -> None:
        self.factory, self.value = factory, None

    def __getattr__(self, name: str) -> Any:
        if self.value is None: self.value = self.factory()
        return getattr(self.value, name)


def create_app(repository: Any | None = None, store: Any | None = None,
               verifier: Callable[..., Any] | None = None, *, audience: str | None = None,
               core: Any | None = None, internal_verifier: Callable[..., Any] | None = None,
               internal_audience: str | None = None,
               internal_callers: frozenset[str] | None = None,
               mcp: Any | None = None) -> FastAPI:
    repository = repository or _Lazy(repository_from_env)
    store = store or _Lazy(PrivateIcebergStore.from_env)
    core = core or _Lazy(CoreContextReader.from_env)
    mcp = mcp or _Lazy(McpGatewayClient.from_env)
    contexts = ContextSourceService(repository,store,core)
    auth = GoogleUserAuthenticator(audience or os.getenv("GOOGLE_USER_CLIENT_ID", ""), repository,
                                   allowed_emails=allowed_user_emails(), verifier=verifier)
    service_auth = GoogleServiceAuthenticator(
        internal_audience or os.getenv("INTERNAL_ASSISTANT_AUDIENCE", ""),
        internal_callers if internal_callers is not None else allowed_assistant_callers(),
        verifier=internal_verifier,
    )
    api = FastAPI(title="Janus User API", version="0.1.0", docs_url=None, redoc_url=None)
    origins=[value.strip() for value in os.getenv("USER_CORS_ORIGINS","").split(",") if value.strip()]
    if origins:
        api.add_middleware(CORSMiddleware,allow_origins=origins,allow_credentials=False,
                           allow_methods=["GET","POST","PUT","DELETE"],allow_headers=["Authorization","Content-Type","Idempotency-Key"])
    def authenticate(request: Request) -> AuthenticatedUser: return auth(request)
    def authenticate_service(request: Request) -> Any: return service_auth(request)
    private = APIRouter(prefix="/api/v1/me", dependencies=[Depends(authenticate)])

    def user(request_user: AuthenticatedUser = Depends(authenticate)) -> AuthenticatedUser: return request_user
    def key(value: str = Header(alias="Idempotency-Key", min_length=8, max_length=128)) -> str: return value

    async def conflict_handler(_request: Any, error: Exception):
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail":str(error)}, status_code=status.HTTP_409_CONFLICT)

    async def missing_handler(_request: Any, error: Exception):
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail":str(error)}, status_code=status.HTTP_404_NOT_FOUND)

    async def invalid_handler(_request: Any, error: Exception):
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail":str(error)}, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)

    api.add_exception_handler(ConflictError, conflict_handler)
    api.add_exception_handler(OversellError, conflict_handler)
    api.add_exception_handler(NotFoundError, missing_handler)
    api.add_exception_handler(ContextReferenceNotFound, missing_handler)
    api.add_exception_handler(ContextSourceError, invalid_handler)
    api.add_exception_handler(McpGatewayError, invalid_handler)

    @api.get("/health")
    def health() -> dict[str, str]: return {"status":"ok"}

    @private.get("/profile")
    def profile(current: AuthenticatedUser = Depends(user)) -> dict[str, Any]:
        return {"user_id":current.user_id,"email":current.email}

    @private.get("/ai-sources")
    def ai_sources(_current: AuthenticatedUser = Depends(user)):
        return {"items":contexts.sources()}

    @private.post("/chats/{conversation_id}/context-preview")
    def context_preview(conversation_id:str,value:ContextPreviewIn,current:AuthenticatedUser=Depends(user)):
        return jsonable_encoder(contexts.preview(current.user_id,conversation_id,value.selector))

    @private.get("/mcp/servers")
    def mcp_servers(current:AuthenticatedUser=Depends(user)):
        return jsonable_encoder({"items":repository.mcp_servers(current.user_id)})

    @private.put("/mcp/servers")
    def put_mcp_servers(value:McpServersPutIn,current:AuthenticatedUser=Depends(user)):
        for item in value.items:
            if not item.enabled: continue
            discovered=mcp.discover(current.user_id,item.server_id,item.config_ref)
            available={tool["name"] for tool in discovered.get("tools",[]) if isinstance(tool,dict) and isinstance(tool.get("name"),str)}
            if not set(item.tool_grants)<=available: raise ContextSourceError("MCP tool grant is not available from the configured server")
        previous={row["server_id"]:row for row in repository.mcp_servers(current.user_id)}
        result=repository.replace_mcp_servers(current.user_id,value.items)
        configured={item.server_id:item for item in value.items}
        for server_id,row in previous.items():
            item=configured.get(server_id)
            if item is None or not item.enabled or item.config_ref != row["config_ref"]:
                mcp.disconnect(current.user_id,server_id)
        return jsonable_encoder({"items":result})

    @private.get("/mcp/servers/{server_id}/tools")
    def mcp_tools(server_id:str,current:AuthenticatedUser=Depends(user)):
        server=next((item for item in repository.mcp_servers(current.user_id) if item["server_id"]==server_id),None)
        if not server or not server["enabled"]: raise NotFoundError("MCP server not found")
        discovered=mcp.discover(current.user_id,server_id,server["config_ref"])
        grants=set(server["tool_grants"])
        return jsonable_encoder({**discovered,"tools":[{**tool,"granted":tool["name"] in grants} for tool in discovered["tools"]]})

    @private.post("/journal/events", status_code=201)
    def add_ledger(value: LedgerEventIn, current: AuthenticatedUser = Depends(user), idempotency_key: str = Depends(key)):
        return jsonable_encoder(repository.add_ledger(current.user_id,value,idempotency_key))

    @private.post("/journal/events/{event_id}/corrections", status_code=201)
    def correct_ledger(event_id: UUID,value: CorrectionIn,current: AuthenticatedUser=Depends(user),idempotency_key: str=Depends(key)):
        return jsonable_encoder(repository.correct_ledger(current.user_id,event_id,value.expected_version,value.replacement,idempotency_key))

    @private.get("/journal/history")
    def history(symbol: str|None=None,year:int|None=Query(None,ge=1900,le=9999),current:AuthenticatedUser=Depends(user)):
        return jsonable_encoder(repository.ledger_history(current.user_id,symbol,year))

    @private.get("/journal/positions")
    def positions(current:AuthenticatedUser=Depends(user)):
        return jsonable_encoder(store.mart("mart_user_positions",current.user_id))

    @private.get("/journal/pnl")
    def pnl(year:int=Query(...,ge=1900,le=9999),current:AuthenticatedUser=Depends(user)):
        return jsonable_encoder(store.mart("mart_user_annual_pnl",current.user_id,year=year))

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
            "positions":store.mart("mart_user_positions",current.user_id)})

    @private.delete("/private-data",status_code=202)
    def delete_private_data(current:AuthenticatedUser=Depends(user),idempotency_key:str=Depends(key)):
        return jsonable_encoder(repository.request_deletion(current.user_id,idempotency_key))

    @api.post("/internal/v1/assistant/context:resolve",dependencies=[Depends(authenticate_service)])
    def resolve_context(value:ContextResolveIn):
        return jsonable_encoder(contexts.resolve(value.owner_id,value.thread_id,value.turn_id,value.context_refs))

    api.include_router(private)
    return api


app = create_app()
