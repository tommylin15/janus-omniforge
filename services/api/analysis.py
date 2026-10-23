"""Owner-scoped analysis commands and bounded PostgreSQL read models."""
from __future__ import annotations

import json
import os
from typing import Literal
from uuid import uuid4

from fastapi import HTTPException
from pydantic import Field, model_validator

from packages.analysis_product import content_hash, freshness
from packages.analysis_models import DEFAULT_MODELS, MODEL_OPTIONS, validated_models
from .models import StrictModel
from .repository import ConflictError, NotFoundError


class CEORequestIn(StrictModel):
    profile_id: str = Field(default="default", pattern=r"^[a-z0-9-]{1,40}$")


class CEOCapabilityIn(StrictModel):
    email: str = Field(min_length=3, max_length=254)
    enabled: bool
    daily_quota: int = Field(ge=0, le=50)
    cooldown_seconds: int = Field(ge=60, le=86400)
    expected_version: int = Field(ge=0)
    reason: str = Field(min_length=1, max_length=500)


class CEOProfileIn(StrictModel):
    approved: bool
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=500)
    providers: list[Literal['codex_cli', 'openrouter', 'gemini']] = Field(
        default_factory=lambda: ['codex_cli', 'openrouter', 'gemini'], min_length=3, max_length=3)
    models: dict[str, str] = Field(default_factory=lambda: dict(DEFAULT_MODELS))

    @model_validator(mode='after')
    def complete_route(self):
        if len(set(self.providers)) != 3:
            raise ValueError('route must contain each approved provider exactly once')
        validated_models(self.models)
        return self


class AnalysisService:
    def __init__(self, repository, trigger=None):
        self.repository = repository
        self.trigger = trigger

    def changes(self, symbol, session='postmarket'):
        return self._changes([symbol], session).get(symbol, {'symbol': symbol,
            'session': session, 'status': 'waiting', 'observations': []})

    def _changes(self, symbols, session):
        from datetime import datetime, time, timedelta
        from zoneinfo import ZoneInfo
        from packages.change_analysis import session_view
        now = datetime.now(ZoneInfo('Asia/Taipei'))
        if session == 'premarket':
            cutoff = min(now, datetime.combine(now.date(), time(9), now.tzinfo))
        elif session == 'postmarket':
            cutoff = (datetime.combine(now.date(), time.min, now.tzinfo) - timedelta(microseconds=1)
                      if now.hour < 13 or (now.hour == 13 and now.minute < 30) else now)
        else:
            raise HTTPException(422, '不支援的盤前／盤後類型')
        with self.repository._connection() as connection:
            rows = connection.execute('''SELECT DISTINCT ON(symbol) symbol,payload_json
                FROM private.specialist_product WHERE symbol=ANY(%s)
                AND (payload_json->'change_analysis'->%s->>'cutoff_at')::timestamptz<=%s
                ORDER BY symbol,analysis_as_of DESC,created_at DESC''', (symbols, session, cutoff)).fetchall()
        result = {}
        for row in rows:
            value = row['payload_json']
            if value['content_hash'] != content_hash({k: v for k, v in value.items() if k != 'content_hash'}):
                raise HTTPException(503, '事實來源驗證失敗')
            result[row['symbol']] = session_view(value, session, cutoff_at=cutoff.isoformat())
        return result

    def today_changes(self, user_id, session='postmarket'):
        # Membership is private; the selected immutable public product is shared.
        with self.repository._connection() as connection:
            rows = connection.execute('''SELECT symbol,min(priority) AS priority FROM (
                SELECT symbol,0 AS priority FROM private.current_positions WHERE user_id=%s AND shares>0
                UNION ALL SELECT symbol,1 AS priority FROM private.watchlist WHERE user_id=%s AND active
                ) membership GROUP BY symbol ORDER BY priority,symbol''', (user_id, user_id)).fetchall()
        views = self._changes([r['symbol'] for r in rows], session) if rows else {}
        items = []
        from packages.change_analysis import instant
        kind_order = {'event': 0, 'operation': 1, 'price': 2, 'valuation': 3}
        for row in rows:
            view = views.get(row['symbol'], {})
            candidates = [i for i in view.get('observations', []) if i['state'] != 'expired'
                          and (i['state'] != 'ongoing' or i.get('changed'))]
            candidates.sort(key=lambda i: (kind_order[i['kind']], -instant(i['source_available_at']).timestamp(), i['identity']))
            if candidates:
                items.append({**candidates[0], 'session': session, 'cutoff_at': view['cutoff_at'],
                              'price_date': view['price_date'], 'membership_priority': row['priority']})
        items.sort(key=lambda i: (i['membership_priority'], kind_order[i['kind']],
                                  -instant(i['source_available_at']).timestamp(), i['symbol']))
        return {'session': session, 'items': [{k: v for k, v in i.items() if k != 'membership_priority'}
                                            for i in items[:3]], 'status':
                'available' if len(views) == len(rows) and all(v['status'] == 'available' for v in views.values())
                else 'partial', 'basis_note': '依已保存收盤與截止前公告；資料晚到時保留原日期。'}

    def baseline(self, symbol, execution_id=None):
        with self.repository._connection() as connection:
            row = connection.execute("""SELECT payload_json FROM private.specialist_product
                WHERE symbol=%s AND (%s::uuid IS NULL OR execution_id=%s::uuid)
                ORDER BY analysis_as_of DESC,created_at DESC LIMIT 1""",
                (symbol, execution_id, execution_id)).fetchone()
        if not row:
            return {"symbol": symbol, "data_status": "waiting", "specialists": [], "model_quality": "NOT_VERIFIED"}
        value = row["payload_json"]
        if value["content_hash"] != content_hash({k: v for k, v in value.items() if k != "content_hash"}):
            raise HTTPException(503, "分析來源驗證失敗")
        # Read-only ACTIVE overlay: a later deterministic Mart row must not
        # conceal the last immutable, still-current XGBoost Risk observation.
        # Never replace newer non-Risk specialists or rewrite persisted rows.
        risk_source = value if "risk_first_release_candidate" in value else None
        if risk_source is None and execution_id is None:
            with self.repository._connection() as connection:
                candidate = connection.execute("""SELECT payload_json FROM private.specialist_product
                    WHERE symbol=%s AND analysis_as_of<=%s
                      AND payload_json ? 'risk_first_release_candidate'
                    ORDER BY analysis_as_of DESC,created_at DESC LIMIT 1""",
                    (symbol, value["analysis_as_of"])).fetchone()
            if candidate:
                risk_source = candidate["payload_json"]
        if risk_source is not None:
            if (risk_source["content_hash"] != content_hash(
                    {k: v for k, v in risk_source.items() if k != "content_hash"})):
                raise HTTPException(503, "風險預測來源驗證失敗")
            # A previous valid model is reusable for at most the existing
            # seven-calendar-day freshness contract, never future-dated.
            from datetime import datetime
            from zoneinfo import ZoneInfo
            today = datetime.now(ZoneInfo("Asia/Taipei")).date()
            if freshness(risk_source, today) == "current":
                with self.repository._connection() as connection:
                    gate = connection.execute("""SELECT mode,model_sha256 FROM private.risk_model_activation
                        ORDER BY activation_id DESC LIMIT 1""").fetchone()
                if (gate and gate["mode"] == "ACTIVE"
                        and gate["model_sha256"] ==
                        "36c77d0168a1d667223ab915c9b08fd2c1c6608f9f7db2fc046204e922854044"):
                    from packages.analysis_product import (
                        approved_first_release_risk_projection, roll_forward_approved_risk)
                    approved = approved_first_release_risk_projection(
                        risk_source, risk_source["risk_first_release_candidate"])
                    value = (approved if risk_source is value
                             else roll_forward_approved_risk(value, approved))
            # API output is always a projection; never expose unpublished
            # first-release candidate bytes when inactive or expired.
            if "risk_first_release_candidate" in value:
                value = dict(value)
                value.pop("risk_first_release_candidate")
                value["content_hash"] = content_hash(
                    {k: v for k, v in value.items() if k != "content_hash"})
        with self.repository._connection() as connection:
            market = connection.execute('''SELECT payload_json,content_hash FROM private.market_screening_product
                WHERE symbol=%s AND analysis_as_of=%s AND core_snapshot_id=%s''',
                (symbol, value['analysis_as_of'], value.get('core_snapshot_id', ''))).fetchone()
        if market and content_hash(market['payload_json']) != market['content_hash']:
            raise HTTPException(503, '市場比較來源驗證失敗')
        # Attach only exact-date/Core public screening. Freeze this combined
        # view when a user requests CEO; never mutate the specialist projection.
        value = {**value, 'source_projection_hash': value['content_hash'],
                 'market_context': market['payload_json'] if market else None}
        value['content_hash'] = content_hash({k: v for k, v in value.items() if k != 'content_hash'})
        from datetime import datetime
        from zoneinfo import ZoneInfo
        return {**value, "data_status": "partial" if any(a["baseline_status"] != "available"
                for a in value["specialists"]) else "available",
                "freshness": freshness(value, datetime.now(ZoneInfo("Asia/Taipei")).date())}

    def capability(self, user_id):
        with self.repository._connection() as connection:
            row = connection.execute("""SELECT enabled,daily_quota,cooldown_seconds,version
                FROM private.ceo_capability_revisions WHERE user_id=%s ORDER BY version DESC LIMIT 1""",
                (user_id,)).fetchone()
            profile = connection.execute("""SELECT approved,version FROM private.ceo_profile_revisions
                WHERE profile_id='default' ORDER BY version DESC LIMIT 1""").fetchone()
        return {"can_request": bool(row and row["enabled"] and row["daily_quota"] > 0),
                "capability": dict(row) if row else None,
                "profile_approved": bool(profile and profile["approved"]),
                "profile_version": profile["version"] if profile else None}

    def history(self, user_id, symbol, limit=10):
        with self.repository._connection() as connection:
            rows = connection.execute("""SELECT request_id,symbol,status,profile_id,profile_version,
                baseline_hash,requested_at,started_at,finished_at,safe_reason,report_json,report_hash,audit_json
                FROM private.ceo_requests WHERE user_id=%s AND symbol=%s
                ORDER BY requested_at DESC,request_id DESC LIMIT %s""", (user_id, symbol, limit)).fetchall()
        baseline = self.baseline(symbol)
        current_hashes = {a["output_hash"] for a in baseline.get("specialists", [])}
        items = [self._public_request(dict(row)) for row in rows]
        for item in items:
            report = item.get("report_json")
            item["material_change"] = (set(report["output"]["validated_role_artifact_hashes"]) != current_hashes
                                       if report and current_hashes else None)
            item["specialist_freshness"] = baseline.get("freshness", "unavailable")
        return items

    def request_status(self, user_id, request_id):
        with self.repository._connection() as connection:
            row = connection.execute("""SELECT request_id,symbol,status,profile_id,profile_version,
                baseline_hash,requested_at,started_at,finished_at,safe_reason,report_json,report_hash,audit_json
                FROM private.ceo_requests WHERE user_id=%s AND request_id=%s""", (user_id, request_id)).fetchone()
        if not row:
            raise NotFoundError("analysis request not found")
        return self._public_request(dict(row))

    def compare(self, symbol):
        with self.repository._connection() as connection:
            rows = connection.execute('''SELECT payload_json FROM private.specialist_product
                WHERE symbol=%s ORDER BY analysis_as_of DESC,created_at DESC LIMIT 2''', (symbol,)).fetchall()
        values = [row['payload_json'] for row in rows]
        for value in values:
            if content_hash({k: v for k, v in value.items() if k != 'content_hash'}) != value['content_hash']:
                raise HTTPException(503, '比較來源驗證失敗')
        return {'symbol': symbol, 'versions': values, 'model_quality': 'NOT_VERIFIED',
                'comparison_status': 'available' if len(values) == 2 else 'insufficient_history',
                'llm_api_tokens': 0, 'promotion_allowed': False}

    @staticmethod
    def _public_request(row):
        if row.get("report_json") is not None and content_hash(row["report_json"]) != row["report_hash"]:
            raise HTTPException(503, "CEO 報告驗證失敗")
        return row

    def enqueue(self, user_id, symbol, profile_id, key):
        if not key or len(key) > 128:
            raise HTTPException(422, "Idempotency-Key 必須為 1–128 字元")
        # A retry of an existing command must work even if today's baseline or
        # capability changed. It never dispatches or consumes another quota.
        with self.repository._connection() as connection:
            replay = connection.execute('''SELECT request_id,symbol,profile_id FROM private.ceo_requests
                WHERE user_id=%s AND idempotency_key=%s''', (user_id, key)).fetchone()
        if replay:
            if replay['symbol'] != symbol or replay['profile_id'] != profile_id:
                raise ConflictError('analysis idempotency key already used')
            return {'request_id': replay['request_id'], 'already_requested': True}
        baseline = self.baseline(symbol)
        if not baseline.get("content_hash") or baseline.get("freshness") != "current":
            raise HTTPException(409, "分析基準尚未就緒或已過期")
        if any(a["status"] == "blocked" for a in baseline["specialists"]):
            raise HTTPException(409, "分析基準來源受阻")
        # Store the immutable projection, not presentation-only status fields.
        baseline = {k: v for k, v in baseline.items() if k not in {"data_status", "freshness"}}
        request_id = uuid4()
        with self.repository._connection() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"ceo-owner:{user_id}",))
            replay = connection.execute("""SELECT request_id,symbol,profile_id FROM private.ceo_requests
                WHERE user_id=%s AND idempotency_key=%s""", (user_id, key)).fetchone()
            if replay:
                if replay["symbol"] != symbol or replay["profile_id"] != profile_id:
                    raise ConflictError("analysis idempotency key already used")
                return {"request_id": replay["request_id"], "already_requested": True}
            cap = connection.execute("""SELECT enabled,daily_quota,cooldown_seconds FROM private.ceo_capability_revisions
                WHERE user_id=%s ORDER BY version DESC LIMIT 1""", (user_id,)).fetchone()
            if not cap or not cap["enabled"] or cap["daily_quota"] == 0:
                raise HTTPException(403, "無 CEO 分析權限")
            profile = connection.execute("""SELECT version,approved,route_json FROM private.ceo_profile_revisions
                WHERE profile_id=%s ORDER BY version DESC LIMIT 1""", (profile_id,)).fetchone()
            if not profile or not profile["approved"]:
                raise HTTPException(409, "CEO provider profile 尚未核准")
            if self.trigger is not None and hasattr(self.trigger, 'preflight'):
                self.trigger.preflight()
            state = connection.execute("""SELECT
                count(*) FILTER(WHERE status IN ('QUEUED','RUNNING','CANCEL_REQUESTED')) AS active,
                count(*) FILTER(WHERE (requested_at AT TIME ZONE 'Asia/Taipei')::date=
                    (now() AT TIME ZONE 'Asia/Taipei')::date) AS today,
                coalesce(max(requested_at)>now()-make_interval(secs => %s),false) AS cooling
                FROM private.ceo_requests WHERE user_id=%s""", (cap["cooldown_seconds"], user_id)).fetchone()
            if state["active"] or state["cooling"] or state["today"] >= cap["daily_quota"]:
                raise HTTPException(429, "已有執行中分析，或已達冷卻／每日額度限制")
            connection.execute("""INSERT INTO private.ceo_requests
                (request_id,user_id,symbol,profile_id,profile_version,route_json,baseline_json,baseline_hash,idempotency_key,status)
                VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,'QUEUED')""",
                (request_id, user_id, symbol, profile_id, profile["version"], json.dumps(profile["route_json"]),
                 json.dumps(baseline, ensure_ascii=False), baseline["content_hash"], key))
        if self.trigger is not None:
            try:
                self.trigger.start(request_id)
            except Exception:
                # A dispatch timeout may have started a Job. Preserve QUEUED;
                # never replay automatically or mark an unknown dispatch failed.
                return {"request_id": request_id, "status": "QUEUED", "dispatch_status": "unknown"}
        return {"request_id": request_id, "status": "QUEUED", "dispatch_status": "dispatched" if self.trigger else "pending"}

    def cancel(self, user_id, request_id):
        with self.repository._connection() as connection:
            row = connection.execute("""UPDATE private.ceo_requests SET status=CASE
                WHEN status='QUEUED' THEN 'CANCELLED' ELSE 'CANCEL_REQUESTED' END
                WHERE user_id=%s AND request_id=%s AND status IN ('QUEUED','RUNNING')
                RETURNING request_id,status""", (user_id, request_id)).fetchone()
        return dict(row) if row else self.request_status(user_id, request_id)

    def reconcile(self, user_id, request_id):
        with self.repository._connection() as connection:
            row = connection.execute('''SELECT status,worker_execution FROM private.ceo_requests
                WHERE user_id=%s AND request_id=%s FOR UPDATE''', (user_id, request_id)).fetchone()
            if not row:
                raise NotFoundError('analysis request not found')
            if row['status'] in {'RUNNING', 'CANCEL_REQUESTED'} and row['worker_execution']:
                if self.trigger and self.trigger.terminal_execution(row['worker_execution']):
                    connection.execute('''UPDATE private.ceo_requests SET status=%s,safe_reason=%s
                        WHERE user_id=%s AND request_id=%s''',
                        ('CANCELLED' if row['status'] == 'CANCEL_REQUESTED' else 'FAILED',
                         'worker_terminal_without_report', user_id, request_id))
        return self.request_status(user_id, request_id)

    def admin_summary(self):
        with self.repository._connection() as connection:
            profiles = connection.execute("""SELECT DISTINCT ON(profile_id) profile_id,version,approved,route_json,
                actor,reason,created_at FROM private.ceo_profile_revisions ORDER BY profile_id,version DESC""").fetchall()
            profile_history = connection.execute("""SELECT profile_id,version,approved,route_json,actor,reason,created_at
                FROM private.ceo_profile_revisions ORDER BY created_at DESC LIMIT 50""").fetchall()
            caps = connection.execute("""SELECT DISTINCT ON(c.user_id) c.user_id,u.display_email,c.enabled,c.daily_quota,c.cooldown_seconds,
                c.version,c.actor,c.reason,c.created_at FROM private.ceo_capability_revisions c
                JOIN private.users u ON u.user_id=c.user_id ORDER BY c.user_id,c.version DESC LIMIT 100""").fetchall()
            recent = connection.execute("""SELECT request_id,symbol,status,profile_id,profile_version,requested_at,
                finished_at,safe_reason,audit_json FROM private.ceo_requests ORDER BY requested_at DESC LIMIT 50""").fetchall()
            specialist = connection.execute("""SELECT DISTINCT ON(symbol) symbol,analysis_as_of,content_hash,
                payload_json FROM private.specialist_product ORDER BY symbol,analysis_as_of DESC,created_at DESC LIMIT 50""").fetchall()
        return {"profiles": [dict(r) for r in profiles], "capabilities": [dict(r) for r in caps],
                "profile_history": [dict(r) for r in profile_history],
                "executions": [dict(r) for r in recent], "specialists": [dict(r) for r in specialist],
                "provider_health": "NOT_VERIFIED", "model_options": MODEL_OPTIONS,
                "paid_api_enabled": False}

    def save_capability(self, value, actor):
        user_id = self.repository.user_id_for_email(value.email)
        with self.repository._connection() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"ceo-owner:{user_id}",))
            row = connection.execute("SELECT max(version) AS version FROM private.ceo_capability_revisions WHERE user_id=%s", (user_id,)).fetchone()
            version = int(row["version"] or 0)
            if version != value.expected_version:
                raise ConflictError("capability version changed")
            connection.execute("""INSERT INTO private.ceo_capability_revisions
                (user_id,version,enabled,daily_quota,cooldown_seconds,actor,reason) VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (user_id, version+1, value.enabled, value.daily_quota, value.cooldown_seconds, actor, value.reason))
        return {"user_id": user_id, "version": version+1}

    def save_profile(self, profile_id, value, actor):
        with self.repository._connection() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"ceo-profile:{profile_id}",))
            row = connection.execute("""SELECT version,route_json FROM private.ceo_profile_revisions
                WHERE profile_id=%s ORDER BY version DESC LIMIT 1""", (profile_id,)).fetchone()
            if not row or row["version"] != value.expected_version:
                raise ConflictError("profile version changed")
            connection.execute("""INSERT INTO private.ceo_profile_revisions
                (profile_id,version,approved,route_json,actor,reason) VALUES (%s,%s,%s,%s::jsonb,%s,%s)""",
                (profile_id, row["version"]+1, value.approved,
                 json.dumps({"providers": value.providers, "models": value.models, "version": row["version"]+1}), actor, value.reason))
        return {"profile_id": profile_id, "version": row["version"]+1}


class CEOJobTrigger:
    def preflight(self):
        import re
        project = os.getenv('GCP_PROJECT_ID', '')
        job = os.getenv('CEO_JOB_NAME', 'janus-ceo-analysis')
        if not project or not re.fullmatch(r'[a-z][a-z0-9-]{0,62}', job):
            raise HTTPException(503, 'CEO 執行環境尚未就緒')
        import google.auth
        from google.auth.transport.requests import AuthorizedSession
        try:
            credentials, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
            response = AuthorizedSession(credentials).get(
                f'https://run.googleapis.com/v2/projects/{project}/locations/{os.getenv("GCP_REGION", "us-central1")}/jobs/{job}', timeout=5)
            if response.status_code != 200:
                raise ValueError('worker unavailable')
            value = response.json()
            containers = value.get('template', {}).get('template', {}).get('containers', [])
            if (value.get('reconciling', False) or len(containers) != 1 or containers[0].get('name') != 'ceo'
                    or value.get('terminalCondition', {}).get('state') != 'CONDITION_SUCCEEDED'):
                raise ValueError('worker unavailable')
        except Exception:
            raise HTTPException(503, 'CEO 執行環境或派送權限尚未就緒') from None

    def terminal_execution(self, execution):
        import re
        import google.auth
        from google.auth.transport.requests import AuthorizedSession
        if not re.fullmatch(r'[a-z][a-z0-9-]{0,100}', execution):
            raise HTTPException(503, 'CEO execution identity 無法核對')
        try:
            credentials, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
            response = AuthorizedSession(credentials).get(
                f'https://run.googleapis.com/v2/projects/{os.environ["GCP_PROJECT_ID"]}/locations/'
                f'{os.getenv("GCP_REGION", "us-central1")}/jobs/{os.getenv("CEO_JOB_NAME", "janus-ceo-analysis")}/executions/{execution}', timeout=5)
            response.raise_for_status()
            value = response.json()
        except Exception:
            raise HTTPException(503, '雲端執行終態尚未確認；保留原狀態') from None
        completed = [c for c in value.get('conditions', []) if c.get('type') == 'Completed']
        return (not value.get('reconciling', False) and value.get('runningCount', 0) == 0
                and bool(value.get('completionTime')) and len(completed) == 1
                and completed[0].get('state') in {'CONDITION_SUCCEEDED', 'CONDITION_FAILED'}
                and completed[0].get('executionReason') not in {'JOB_STATUS_SERVICE_POLLING_ERROR', 'CANCELLING', 'DELAYED_START_PENDING'})

    def start(self, request_id):
        import google.auth
        from google.auth.transport.requests import AuthorizedSession
        project = os.environ.get("GCP_PROJECT_ID", "")
        if not project:
            raise ValueError("CEO dispatch unavailable")
        region = os.environ.get("GCP_REGION", "us-central1")
        job = os.environ.get('CEO_JOB_NAME', 'janus-ceo-analysis')
        if not job:
            raise ValueError('dedicated approved CEO worker unavailable')
        credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        response = AuthorizedSession(credentials).post(
            f"https://run.googleapis.com/v2/projects/{project}/locations/{region}/jobs/{job}:run",
            json={"overrides": {"taskCount": 1, "timeout": "480s", "containerOverrides": [{"name": "ceo", "env": [
                {"name": "MART_OPERATION", "value": "ceo-request"},
                {"name": "CEO_REQUEST_ID", "value": str(request_id)}]}]}}, timeout=10)
        if not 200 <= response.status_code < 300:
            raise RuntimeError("CEO dispatch unavailable")
