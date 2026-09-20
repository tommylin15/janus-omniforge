from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import sys
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

ROOT=Path(__file__).parents[1]
sys.path.insert(0,str(ROOT))

import services.api.app as app_module
from services.api.app import create_app


USER_ID=UUID("00000000-0000-0000-0000-000000000001")


class Repository:
    def __init__(self): self.calls=[]; self.emails=[]; self.mcp=[]; self.feedback=None; self.profile={"risk_tolerance":None,"investment_horizon":None,"primary_goal":None,"minimum_cash_ratio":None,"ai_context_opt_in":False,"version":0,"updated_at":None}
    def resolve_user(self,sub,email): self.emails.append((sub,email)); return USER_ID
    def require_owned_trade(self,user_id,event_id): self.calls.append(("ownership",user_id,event_id))
    def add_ledger(self,user_id,value,key): self.calls.append((user_id,value,key)); return {"user_id":user_id,"event_type":value.event_type,"ledger_version":1}
    def ledger_history(self,user_id,symbol,year): return [{"user_id":user_id,"symbol":symbol or "2330"}]
    def watchlist(self,user_id): return [{"user_id":user_id,"symbol":"2330"}]
    def follow(self,user_id,value,key): self.calls.append((user_id,value,key)); return {"user_id":user_id,"symbol":value.symbol}
    def unfollow(self,user_id,symbol,key): self.calls.append((user_id,symbol,key))
    def notes(self,user_id,symbol=None): return [{"user_id":user_id,"artifact_ref":"private.note_revisions/n/1"}]
    def add_note(self,user_id,value,key,ref,note_id=None): self.calls.append((user_id,value,key,ref,note_id)); return {"user_id":user_id,"artifact_ref":ref,"note_id":note_id}
    def request_deletion(self,user_id,key): self.calls.append((user_id,key)); return {"user_id":user_id,"status":"QUEUED"}
    def mcp_servers(self,user_id): return [{**item,"user_id":user_id} for item in self.mcp]
    def replace_mcp_servers(self,user_id,items):
        self.mcp=[item.model_dump() for item in items]
        return self.mcp_servers(user_id)
    def investment_profile(self,user_id): return self.profile
    def save_investment_profile(self,user_id,value,key):
        self.calls.append((user_id,value,key))
        self.profile={**value.model_dump(exclude={"expected_version"}),"version":value.expected_version+1,"updated_at":"2026-09-13T00:00:00Z"}
        return self.profile
    def analysis_feedback(self,user_id,execution_id,scope_type,scope_id):
        self.calls.append(("feedback-read",user_id,execution_id,scope_type,scope_id))
        return self.feedback
    def analysis_feedback_export(self,user_id): return [self.feedback] if self.feedback else []
    def save_analysis_feedback(self,user_id,value,key):
        self.calls.append(("feedback-write",user_id,value,key))
        self.feedback={**value.model_dump(),"version":1,"updated_at":"2026-09-14T00:00:00Z"}
        return self.feedback


class Store:
    def __init__(self): self.writes=[]; self.contexts={}; self.upserts=[]; self.mart_calls=[]
    def upsert(self,table,rows): self.upserts.append((table,rows))
    def write_note(self,**value): self.writes.append(value); return "private.note_revisions/n/1"
    def read_notes(self,user_id,indexes): return [{**indexes[0],"body":"private"}]
    def mart(self,table,user_id,**filters):
        self.mart_calls.append((table,user_id,filters))
        common={"user_id":str(user_id),"ledger_version":1,"valuation_date":"2026-09-05"}
        rows={
          "mart_user_portfolio_summary":{**common,"currency":"TWD","market_value":"1200","cost_basis":"1000","unrealized_pnl":"200","missing_price_count":0,"cash_safety_status":"insufficient_data","cash_ratio":None,"minimum_cash_ratio":"0.1"},
          "mart_user_exposure":{**common,"currency":"TWD","industry":"semiconductor","market_value":"1200","portfolio_ratio":"1","allocation_method":"equal_weight_per_membership_v1","symbols":"[\"2330\"]","membership_snapshot":"[]","membership_snapshot_hash":"sha256:"+"0"*64},
          "mart_user_annual_performance":{**common,"year":filters.get("year",2026),"currency":"TWD","xirr_status":"available","xirr":.1,"cash_flow_count":2,"method":"xirr_actual_365_v1"},
          "mart_user_stress_tests":{**common,"currency":"TWD","scenario_id":"broad_market_down_20","shock":"-0.2","portfolio_value_before":"1200","portfolio_value_after":"960","loss":"-240","cash_safety_status":"insufficient_data","cash_ratio":None,"minimum_cash_ratio":"0.1","valuation_status":"available","method":"deterministic_parallel_shock_v1"},
        }
        return [rows.get(table,{**common,"table":table,"artifact_ref":"private/hidden",**filters})]
    def write_context_snapshot(self,**value): self.contexts[(str(value["user_id"]),value["context_id"])]=value; return "private.context/hidden"
    def read_context_snapshot(self,user_id,context_id): return self.contexts.get((str(user_id),context_id))


class Core:
    def page(self,dataset,symbol,limit):
        return [{"symbol":symbol,"trade_date":"2026-09-05","close":"100","source_id":"twse",
                 "provenance_id":"prov-1","gcs_uri":"gs://hidden"}]


class Public:
    def require_enabled_symbol(self, symbol): return symbol.upper()

    def report(self, scope_type, scope_id, *, analysis_as_of=""):
        return {"execution_id":"11111111-1111-1111-1111-111111111111",
                "scope_type": scope_type, "scope_id": scope_id,
                "analysis_as_of": analysis_as_of or "2026-09-12", "data_status": "published",
                "confidence": .8, "completeness": .9, "schema_version": "1", "model_version": "1",
                "governance_snapshot_version": "gov-1", "data": {"score": 80}}


class ExplodingPublic:
    def report(self, *_args, **_kwargs):
        raise RuntimeError("password=top-secret traceback=private")


class QueryCore:
    def summary(self, symbol):
        return {"symbol": symbol, "datasets": {}}

    def page(self, dataset_id, symbol, *, limit, offset):
        return type("Page", (), {"dataset_id": dataset_id, "symbol": symbol, "rows": (),
                                 "limit": limit, "offset": offset})()


class Mcp:
    def __init__(self): self.calls=[]
    def discover(self,owner_id,server_id,config_ref,tool_grants=None):
        self.calls.append((owner_id,server_id,config_ref,tool_grants))
        return {"serverId":server_id,"configRef":config_ref,"transport":"stdio","tools":[
            {"name":f"{server_id}__echo","description":"Echo","inputSchema":{"type":"object"}}]}
    def disconnect(self,owner_id,server_id): self.calls.append(("disconnect",owner_id,server_id))


def client(claims=None,service_claims=None,public=None,query_core=None,raise_server_exceptions=True):
    repo,store,mcp=Repository(),Store(),Mcp()
    values=claims or {"iss":"https://accounts.google.com","aud":"user-client","sub":"google-a","email":"old@example.com","email_verified":True,"exp":1_900_000_000}
    service_claims=service_claims or {"iss":"https://accounts.google.com","aud":"assistant-internal","sub":"service-1",
                                      "email":"gateway@example.iam.gserviceaccount.com","email_verified":True,"exp":1_900_000_000}
    admin_claims={"iss":"https://accounts.google.com","aud":"admin-client","sub":"admin-1",
                  "email":"admin@example.com","email_verified":True,"exp":1_900_000_000}
    def verify_admin(token, _audience):
        if token == "valid-admin-token": return admin_claims
        if token == "other-admin-token": return {**admin_claims,"email":"other@example.com"}
        return values
    app=create_app(repo,store,lambda _token,_audience:values,audience="user-client",core=Core(),
                   query_core=query_core,
                   admin_verifier=verify_admin,admin_audience="admin-client",
                   admin_emails=frozenset({"admin@example.com"}),
                   internal_verifier=lambda _token,_audience:service_claims,
                   internal_audience="assistant-internal",
                   internal_callers=frozenset({"gateway@example.iam.gserviceaccount.com"}),mcp=mcp,public=public)
    return TestClient(app, raise_server_exceptions=raise_server_exceptions),repo,store


def auth(): return {"Authorization":"Bearer valid-user-token"}
def admin_auth(): return {"Authorization":"Bearer valid-admin-token"}


def test_health_is_public_and_private_routes_require_bearer():
    api,_,_=client()
    assert api.get("/health").json()=={"status":"ok"}
    response=api.get("/api/v1/me/profile")
    assert response.status_code==401
    assert response.json()=={"detail":"authentication required"}


def test_usefulness_feedback_acceptance_page_is_served():
    api,_,_=client()
    response=api.get("/usefulness-feedback-acceptance.html")
    assert response.status_code==200
    assert "google.accounts.id.initialize" in response.text


def test_public_report_route_is_unauthenticated_and_uses_persisted_service():
    api,_,_=client(public=Public())
    response=api.get("/api/v1/public/reports/symbol/2330?analysis_as_of=2026-09-12")
    assert response.status_code==200
    assert response.json()["data"]=={"score":80}

    unavailable=client()[0].get("/api/v1/public/reports/symbol/2330")
    assert unavailable.status_code==503
    assert unavailable.json()=={"detail":"public reports unavailable"}


def test_public_report_route_uses_default_runtime_factory(monkeypatch):
    monkeypatch.setattr(app_module, "build_public_service", lambda: Public())
    api,_,_=client()
    response=api.get("/api/v1/public/reports/symbol/2330")
    assert response.status_code==200
    assert response.json()["data"]=={"score":80}


def test_unhandled_error_response_and_log_do_not_leak_secret(caplog):
    api,_,_=client(public=ExplodingPublic(),raise_server_exceptions=False)
    response=api.get("/api/v1/public/reports/symbol/2330")
    assert response.status_code==503
    assert response.json()=={"detail":"service unavailable"}
    assert "top-secret" not in response.text
    assert "top-secret" not in caplog.text
    assert "RuntimeError" in caplog.text


def test_core_routes_require_admin_audience_and_preserve_legacy_contract():
    api,_,_=client(query_core=QueryCore())
    assert api.get("/api/v1/admin/core/2330/summary").status_code==401
    assert api.get("/api/v1/admin/core/2330/summary",headers=auth()).status_code==401
    assert api.get("/api/v1/admin/core/2330/summary",headers={"Authorization":"Bearer other-admin-token"}).status_code==403
    assert api.get("/api/v1/admin/core/2330/summary",headers=admin_auth()).json()=={
        "symbol":"2330","datasets":{}
    }
    page=api.get("/api/v1/core/2330/datasets/ohlcv?limit=10&offset=2",headers=admin_auth())
    assert page.status_code==200
    assert page.json()=={"dataset_id":"ohlcv","symbol":"2330","rows":[],"limit":10,"offset":2}


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


def test_investment_profile_and_portfolio_routes_are_typed_and_owner_scoped():
    api,repo,store=client()
    empty=api.get("/api/v1/me/investment-profile",headers=auth())
    assert empty.json()["version"]==0
    payload={"risk_tolerance":"moderate","investment_horizon":"long","primary_goal":"growth",
             "minimum_cash_ratio":"0.15","ai_context_opt_in":True,"expected_version":0}
    saved=api.put("/api/v1/me/investment-profile",headers={**auth(),"Idempotency-Key":"profile-1"},json=payload)
    assert saved.status_code==200 and saved.json()["version"]==1
    assert repo.calls[-1][0]==USER_ID
    assert store.upserts[0][0]=="investment_profile_revisions" and store.upserts[0][1][0]["user_id"]==USER_ID
    for path,table in (("summary","mart_user_portfolio_summary"),("exposure","mart_user_exposure"),
                       ("performance?year=2026","mart_user_annual_performance"),("stress-tests","mart_user_stress_tests")):
        result=api.get(f"/api/v1/me/portfolio/{path}",headers=auth())
        assert result.status_code==200 and len(result.json()["items"])==1
        assert store.mart_calls[-1][0:2]==(table,USER_ID)
        assert "user_id" not in result.json()["items"][0] and "artifact_ref" not in result.json()["items"][0]


def test_investment_profile_rejects_unknown_fields_and_unbounded_cash_ratio():
    api,_,_=client()
    base={"risk_tolerance":"moderate","investment_horizon":"long","primary_goal":"growth",
          "minimum_cash_ratio":"0.15","ai_context_opt_in":False,"expected_version":0}
    for payload in ({**base,"user_id":str(uuid4())},{**base,"minimum_cash_ratio":"1.1"}):
        assert api.put("/api/v1/me/investment-profile",headers={**auth(),"Idempotency-Key":"profile-2"},json=payload).status_code==422


def test_analysis_feedback_is_bounded_and_scoped_to_authenticated_owner():
    api,repo,_=client()
    payload={"analysis_execution_id":"11111111-1111-1111-1111-111111111111",
             "scope_type":"symbol","scope_id":"2330","feedback":"useful","reason":"discovered_risk"}
    saved=api.put("/api/v1/me/analysis-feedback",headers={**auth(),"Idempotency-Key":"feedback-1"},json=payload)
    assert saved.status_code==200 and saved.json()["feedback"]=="useful"
    assert repo.calls[-1][0:2]==("feedback-write",USER_ID)
    query="analysis_execution_id=11111111-1111-1111-1111-111111111111&scope_type=symbol&scope_id=2330"
    assert api.get(f"/api/v1/me/analysis-feedback?{query}",headers=auth()).json()["reason"]=="discovered_risk"
    assert api.put("/api/v1/me/analysis-feedback",headers={**auth(),"Idempotency-Key":"feedback-2"},
                   json={**payload,"feedback":"great"}).status_code==422


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


def test_context_preview_is_bounded_opaque_and_owner_thread_bound():
    api,_,store=client()
    sources=api.get("/api/v1/me/ai-sources",headers=auth()).json()["items"]
    assert {item["source_id"] for item in sources}=={"janus-core","janus-private-core","janus-private-mart"}
    assert all(item["quota"]["max_records"]==20 for item in sources)

    response=api.post("/api/v1/me/chats/thread-a/context-preview",headers=auth(),json={"selector":{
        "source_id":"janus-core","resource":"ohlcv","symbol":"2330","limit":1}})
    assert response.status_code==200
    preview=response.json()
    assert preview["preview"]==[{"symbol":"2330","trade_date":"2026-09-05","close":"100","source_id":"twse","provenance_id":"prov-1"}]
    assert "thread-a" not in preview["context_ref"] and str(USER_ID) not in preview["context_ref"]
    assert preview["provenance"]==[{"context_source_id":"janus-core","source_id":"twse","provenance_id":"prov-1"}]
    assert all(ref != preview["context_ref"] for _,ref in store.contexts)

    payload={"owner_id":str(USER_ID),"thread_id":"thread-a","turn_id":"turn-a","context_refs":[preview["context_ref"]]}
    assert api.post("/internal/v1/assistant/context:resolve",json=payload).status_code==401
    resolved=api.post("/internal/v1/assistant/context:resolve",headers=auth(),json=payload)
    assert resolved.status_code==200
    assert resolved.json()["snapshots"][0]["records"]==preview["preview"]
    assert "artifact_ref" not in str(resolved.json()) and "gcs_uri" not in str(resolved.json())
    payload["thread_id"]="thread-b"
    assert api.post("/internal/v1/assistant/context:resolve",headers=auth(),json=payload).status_code==404
    payload["thread_id"]="thread-a"; payload["owner_id"]=str(uuid4())
    assert api.post("/internal/v1/assistant/context:resolve",headers=auth(),json=payload).status_code==404
    payload["owner_id"]=str(USER_ID)
    next(iter(store.contexts.values()))["expires_at"]=datetime.now(timezone.utc)-timedelta(seconds=1)
    assert api.post("/internal/v1/assistant/context:resolve",headers=auth(),json=payload).status_code==404


def test_investment_profile_context_requires_explicit_opt_in():
    api,repo,_=client()
    selector={"selector":{"source_id":"janus-private-mart","resource":"investment-profile","limit":1}}
    assert api.post("/api/v1/me/chats/thread-a/context-preview",headers=auth(),json=selector).status_code==422
    repo.profile={"risk_tolerance":"moderate","investment_horizon":"long","primary_goal":"growth",
                  "minimum_cash_ratio":Decimal("0.1"),"ai_context_opt_in":True,"version":1,"updated_at":None}
    response=api.post("/api/v1/me/chats/thread-a/context-preview",headers=auth(),json=selector)
    assert response.status_code==200 and response.json()["preview"][0]["risk_tolerance"]=="moderate"


def test_mcp_management_only_accepts_allowlisted_references_and_owner_scoped_grants():
    api,repo,_=client()
    payload={"items":[{"server_id":"research","config_ref":"approved-stdio","enabled":True,
                       "tool_grants":["research__echo"]}]}
    response=api.put("/api/v1/me/mcp/servers",headers=auth(),json=payload)
    assert response.status_code==200
    assert repo.mcp[0]["config_ref"]=="approved-stdio"
    tools=api.get("/api/v1/me/mcp/servers/research/tools",headers=auth()).json()["tools"]
    assert tools==[{"name":"research__echo","description":"Echo","inputSchema":{"type":"object"},"granted":True}]
    for forbidden in ({**payload,"user_id":str(uuid4())},
                      {"items":[{**payload["items"][0],"command":"curl attacker"}]},
                      {"items":[{**payload["items"][0],"url":"https://attacker.example"}]}):
        assert api.put("/api/v1/me/mcp/servers",headers=auth(),json=forbidden).status_code==422


def test_mcp_rejects_cross_server_or_unknown_tool_grants():
    api,_,_=client()
    wrong_namespace={"items":[{"server_id":"research","config_ref":"approved-stdio",
                               "tool_grants":["other__echo"]}]}
    assert api.put("/api/v1/me/mcp/servers",headers=auth(),json=wrong_namespace).status_code==422
    unavailable={"items":[{"server_id":"research","config_ref":"approved-stdio",
                            "tool_grants":["research__missing"]}]}
    assert api.put("/api/v1/me/mcp/servers",headers=auth(),json=unavailable).status_code==422

def test_context_selector_rejects_unknown_sources_sql_and_unbounded_ranges():
    api,_,_=client()
    for selector in (
        {"source_id":"unknown","resource":"ohlcv","symbol":"2330"},
        {"source_id":"janus-core","resource":"ohlcv","symbol":"2330","sql":"select *"},
        {"source_id":"janus-core","resource":"ohlcv","symbol":"2330","start_date":"2024-01-01","end_date":"2026-01-02"},
    ):
        response=api.post("/api/v1/me/chats/thread-a/context-preview",headers=auth(),json={"selector":selector})
        assert response.status_code==422


def test_internal_context_resolver_rejects_unapproved_service_account():
    claims={"iss":"https://accounts.google.com","aud":"assistant-internal","sub":"service-2",
            "email":"other@example.iam.gserviceaccount.com","email_verified":True,"exp":1_900_000_000}
    api,_,_=client(service_claims=claims)
    response=api.post("/internal/v1/assistant/context:resolve",headers=auth(),json={
        "owner_id":str(USER_ID),"thread_id":"thread-a","turn_id":"turn-a","context_refs":["x"*32]})
    assert response.status_code==403


def test_private_migration_has_decimal_append_only_and_user_leading_guards():
    sql=(ROOT/"infra/postgres/migrations/014_private_workspace.sql").read_text(encoding="utf-8")
    assert "numeric(20,8)" in sql and "numeric(20,4)" in sql
    assert "UPDATE ON private.ledger_events" not in sql
    assert "ledger_user_symbol_date_idx ON private.ledger_events(user_id, symbol" in sql
    note_sql=sql[sql.index("CREATE TABLE IF NOT EXISTS private.note_index"):sql.index("CREATE TABLE IF NOT EXISTS private.watchlist")]
    assert "body" not in note_sql
    repository=(ROOT/"services/api/repository.py").read_text(encoding="utf-8")
    assert "pg_advisory_xact_lock" in repository and "count(DISTINCT symbol)" in repository
    assert "ledger_events WHERE user_id=%s AND event_id=%s FOR UPDATE" not in repository
    assert "ON CONFLICT(user_id,idempotency_key) DO NOTHING" in repository
    assert 'sslmode="require"' in repository


def test_investment_profile_migration_is_bounded_owner_scoped_and_minimally_granted():
    sql=(ROOT/"infra/postgres/migrations/024_private_investment_profile.sql").read_text(encoding="utf-8")
    assert "PRIMARY KEY REFERENCES private.users(user_id)" in sql
    assert "minimum_cash_ratio BETWEEN 0 AND 1" in sql
    assert "ai_context_opt_in" in sql and "version integer" in sql
    assert "GRANT SELECT, INSERT, UPDATE ON private.investment_profiles TO janus_private_api" in sql
    assert "GRANT SELECT, DELETE ON private.investment_profiles TO janus_private_pipeline" in sql


def test_deletion_removes_oauth_codes_before_users():
    repository=(ROOT/"services/api/repository.py").read_text(encoding="utf-8")
    deletion=repository[repository.index("def complete_deletion"):repository.index("    @staticmethod", repository.index("def complete_deletion"))]
    assert deletion.index('"mcp_oauth_codes"') < deletion.index('"users"')
    migration=(ROOT/"infra/postgres/migrations/026_mcp_oauth_codes.sql").read_text(encoding="utf-8")
    assert "GRANT SELECT, DELETE ON private.mcp_oauth_codes TO janus_private_pipeline" in migration


def test_watchlist_demand_history_is_deidentified_append_only_and_quota_bounded():
    sql=(ROOT/"infra/postgres/migrations/019_core_mart_integration.sql").read_text(encoding="utf-8")
    assert "deep_tracking_membership_events" in sql
    assert "last_unfollow" in sql and "demand_count" in sql
    assert "REVOKE UPDATE, DELETE, TRUNCATE" in sql
    assert "user_id" not in sql[sql.index("CREATE TABLE IF NOT EXISTS control.deep_tracking_membership_events"):sql.index("CREATE INDEX IF NOT EXISTS deep_tracking_membership_history")]
    repository=(ROOT/"services/api/repository.py").read_text(encoding="utf-8")
    assert repository.count("record_deep_tracking_demand") == 2
    assert "global_count>=50" in repository
