from datetime import date
from decimal import Decimal
from pathlib import Path
import sys
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

ROOT=Path(__file__).parents[1]
sys.path.insert(0,str(ROOT))

from services.api.app import create_app


USER_ID=UUID("00000000-0000-0000-0000-000000000001")


class Repository:
    def __init__(self): self.calls=[]; self.emails=[]
    def resolve_user(self,sub,email): self.emails.append((sub,email)); return USER_ID
    def require_owned_trade(self,user_id,event_id): self.calls.append(("ownership",user_id,event_id))
    def add_ledger(self,user_id,value,key): self.calls.append((user_id,value,key)); return {"user_id":user_id,"event_type":value.event_type,"ledger_version":1}
    def ledger_history(self,user_id,symbol,year): return [{"user_id":user_id,"symbol":symbol or "2330"}]
    def watchlist(self,user_id): return [{"user_id":user_id,"symbol":"2330"}]
    def follow(self,user_id,value,key): self.calls.append((user_id,value,key)); return {"user_id":user_id,"symbol":value.symbol}
    def unfollow(self,user_id,symbol,key): self.calls.append((user_id,symbol,key))
    def notes(self,user_id,symbol=None): return [{"user_id":user_id,"artifact_ref":"private.note_revisions/n/1"}]
    def add_note(self,user_id,value,key,ref): self.calls.append((user_id,value,key,ref)); return {"user_id":user_id,"artifact_ref":ref}
    def request_deletion(self,user_id,key): self.calls.append((user_id,key)); return {"user_id":user_id,"status":"QUEUED"}


class Store:
    def __init__(self): self.writes=[]
    def write_note(self,**value): self.writes.append(value); return "private.note_revisions/n/1"
    def read_notes(self,user_id,indexes): return [{**indexes[0],"body":"private"}]
    def mart(self,table,user_id,**filters): return [{"user_id":str(user_id),"table":table,**filters}]


def client(claims=None):
    repo,store=Repository(),Store()
    values=claims or {"iss":"https://accounts.google.com","aud":"user-client","sub":"google-a","email":"old@example.com","email_verified":True,"exp":1_900_000_000}
    app=create_app(repo,store,lambda _token,_audience:values,audience="user-client")
    return TestClient(app),repo,store


def auth(): return {"Authorization":"Bearer valid-user-token"}


def test_health_is_public_and_private_routes_require_bearer():
    api,_,_=client()
    assert api.get("/health").json()=={"status":"ok"}
    response=api.get("/api/v1/me/profile")
    assert response.status_code==401
    assert response.json()=={"detail":"authentication required"}


def test_oidc_rejects_admin_audience_expiry_and_untrusted_issuer():
    for changed in ({"aud":"admin-client"},{"exp":1},{"iss":"https://attacker.example"}):
        claims={"iss":"https://accounts.google.com","aud":"user-client","sub":"google-a","email":"a@example.com","email_verified":True,"exp":1_900_000_000,**changed}
        api,_,_=client(claims)
        assert api.get("/api/v1/me/profile",headers=auth()).status_code==401


def test_google_sub_owns_uuid_while_email_is_display_only():
    api,repo,_=client()
    first=api.get("/api/v1/me/profile",headers=auth())
    assert first.json()=={"user_id":str(USER_ID),"email":"old@example.com"}
    assert repo.emails==[("google-a","old@example.com")]


def test_resolver_failure_is_not_reported_as_invalid_google_credential():
    class BrokenRepository(Repository):
        def resolve_user(self, sub, email): raise RuntimeError("database unavailable")

    claims={"iss":"https://accounts.google.com","aud":"user-client","sub":"google-a",
            "email":"a@example.com","email_verified":True,"exp":1_900_000_000}
    api=TestClient(create_app(BrokenRepository(),Store(),lambda _token,_audience:claims,audience="user-client"))
    try: api.get("/api/v1/me/profile",headers=auth())
    except RuntimeError as error: assert str(error)=="database unavailable"
    else: raise AssertionError("resolver failure was swallowed")


def test_identity_cannot_be_supplied_by_client_and_routes_scope_to_authenticated_uuid():
    api,repo,_=client()
    payload={"event_type":"BUY","trade_date":"2026-09-04","symbol":"2330","shares":"10","price":"100","user_id":str(uuid4())}
    assert api.post("/api/v1/me/journal/events",headers={**auth(),"Idempotency-Key":"request-1"},json=payload).status_code==422
    payload.pop("user_id")
    response=api.post("/api/v1/me/journal/events",headers={**auth(),"Idempotency-Key":"request-1"},json=payload)
    assert response.status_code==201
    assert repo.calls[0][0]==USER_ID


def test_note_body_goes_to_private_store_not_repository_index():
    api,repo,store=client()
    response=api.post("/api/v1/me/notes",headers={**auth(),"Idempotency-Key":"note-key-1"},json={"body":"private"})
    assert response.status_code==201
    assert store.writes[0]["user_id"]==USER_ID
    assert store.writes[0]["body"]=="private"
    assert repo.calls[1][3].startswith("private.note_revisions/")


def test_ledger_contract_rejects_wrong_type_fields():
    api,_,_=client()
    response=api.post("/api/v1/me/journal/events",headers={**auth(),"Idempotency-Key":"request-2"},json={
        "event_type":"CASH_DIV","trade_date":"2026-09-04","symbol":"2330","shares":"1","currency":"TWD"})
    assert response.status_code==422


def test_private_deletion_is_authenticated_and_queued_for_the_same_user():
    api,repo,_=client()
    response=api.delete("/api/v1/me/private-data",headers={**auth(),"Idempotency-Key":"delete-key-1"})
    assert response.status_code==202
    assert repo.calls[-1]==(USER_ID,"delete-key-1")


def test_private_migration_has_decimal_append_only_and_user_leading_guards():
    sql=(ROOT/"infra/postgres/migrations/014_private_workspace.sql").read_text(encoding="utf-8")
    assert "numeric(20,8)" in sql and "numeric(20,4)" in sql
    assert "UPDATE ON private.ledger_events" not in sql
    assert "ledger_user_symbol_date_idx ON private.ledger_events(user_id, symbol" in sql
    note_sql=sql[sql.index("CREATE TABLE IF NOT EXISTS private.note_index"):sql.index("CREATE TABLE IF NOT EXISTS private.watchlist")]
    assert "body" not in note_sql
    repository=(ROOT/"services/api/repository.py").read_text(encoding="utf-8")
    assert "pg_advisory_xact_lock" in repository and "count(DISTINCT symbol)" in repository
