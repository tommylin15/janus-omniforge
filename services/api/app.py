"""FastAPI boundary for the WBS 4J private workspace."""

from __future__ import annotations

import os
from typing import Any, Callable
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import APIRouter, Depends, FastAPI, Header, Query, Request, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware

from .auth import AuthenticatedUser, GoogleUserAuthenticator, allowed_user_emails
from .models import CorrectionIn, LedgerEventIn, NoteIn, NoteRevisionIn, WatchlistIn, WatchlistOrderIn
from .repository import ConflictError, NotFoundError, OversellError, repository_from_env
from .store import PrivateIcebergStore


class _Lazy:
    def __init__(self, factory: Callable[[], Any]) -> None:
        self.factory, self.value = factory, None

    def __getattr__(self, name: str) -> Any:
        if self.value is None: self.value = self.factory()
        return getattr(self.value, name)


def create_app(repository: Any | None = None, store: Any | None = None,
               verifier: Callable[..., Any] | None = None, *, audience: str | None = None) -> FastAPI:
    repository = repository or _Lazy(repository_from_env)
    store = store or _Lazy(PrivateIcebergStore.from_env)
    auth = GoogleUserAuthenticator(audience or os.getenv("GOOGLE_USER_CLIENT_ID", ""), repository,
                                   allowed_emails=allowed_user_emails(), verifier=verifier)
    api = FastAPI(title="Janus User API", version="0.1.0", docs_url=None, redoc_url=None)
    origins=[value.strip() for value in os.getenv("USER_CORS_ORIGINS","").split(",") if value.strip()]
    if origins:
        api.add_middleware(CORSMiddleware,allow_origins=origins,allow_credentials=False,
                           allow_methods=["GET","POST","PUT","DELETE"],allow_headers=["Authorization","Content-Type","Idempotency-Key"])
    def authenticate(request: Request) -> AuthenticatedUser: return auth(request)
    private = APIRouter(prefix="/api/v1/me", dependencies=[Depends(authenticate)])

    def user(request_user: AuthenticatedUser = Depends(authenticate)) -> AuthenticatedUser: return request_user
    def key(value: str = Header(alias="Idempotency-Key", min_length=8, max_length=128)) -> str: return value

    async def conflict_handler(_request: Any, error: Exception):
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail":str(error)}, status_code=status.HTTP_409_CONFLICT)

    async def missing_handler(_request: Any, error: Exception):
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail":str(error)}, status_code=status.HTTP_404_NOT_FOUND)

    api.add_exception_handler(ConflictError, conflict_handler)
    api.add_exception_handler(OversellError, conflict_handler)
    api.add_exception_handler(NotFoundError, missing_handler)

    @api.get("/health")
    def health() -> dict[str, str]: return {"status":"ok"}

    @private.get("/profile")
    def profile(current: AuthenticatedUser = Depends(user)) -> dict[str, Any]:
        return {"user_id":current.user_id,"email":current.email}

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

    api.include_router(private)
    return api


app = create_app()
