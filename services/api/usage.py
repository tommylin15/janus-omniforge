"""Bounded, optional product telemetry. Never accepts identity or free text."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import Field, model_validator

from .models import StrictModel
from .repository import NotFoundError


class UsageBodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope['path'] not in (
                '/api/v1/me/usage/batches','/api/v1/admin/usage/self/batches'):
            return await self.app(scope, receive, send)
        from starlette.responses import JSONResponse
        body = bytearray()
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            body.extend(message.get('body', b''))
            if len(body) > 16384:
                return await JSONResponse({'detail':'usage batch too large'},status_code=413)(scope,receive,send)
            if not message.get('more_body'):
                break
        delivered = False
        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {'type':'http.request','body':bytes(body),'more_body':False}
            return await receive()
        await self.app(scope,replay,send)

FEATURES = ('today', 'watchlist', 'journal', 'notes', 'profile', 'stock_detail',
            'admin_overview', 'admin_batches', 'admin_quality', 'admin_settings')
ACTIONS = ('open', 'save', 'remove', 'recalculate', 'refresh', 'analyse')
TAIPEI = ZoneInfo('Asia/Taipei')


class UsageEvent(StrictModel):
    schema_version: Literal['usage-event.v1'] = 'usage-event.v1'
    event_id: UUID
    session_id: UUID
    feature_id: Literal[*FEATURES]
    event_type: Literal['page_view', 'feature_action', 'action_result', 'active_interval']
    action_key: Literal[*ACTIONS] = 'open'
    outcome: Literal['unknown', 'success', 'failed'] = 'unknown'
    client_time: datetime
    active_duration_ms: int = Field(default=0, ge=0, le=60000, strict=True)

    @model_validator(mode='after')
    def valid_interval(self):
        if self.client_time.tzinfo is None:
            raise ValueError('client_time must include timezone')
        if self.event_type != 'active_interval' and self.active_duration_ms:
            raise ValueError('duration requires active_interval')
        return self


class UsageBatch(StrictModel):
    batch_id: UUID
    events: list[UsageEvent] = Field(min_length=1, max_length=20)

    @model_validator(mode='after')
    def bounded(self):
        now = datetime.now(timezone.utc)
        for event in self.events:
            if not now - timedelta(days=7) <= event.client_time <= now + timedelta(minutes=5):
                raise ValueError('event time outside accepted window')
            start = event.client_time - timedelta(milliseconds=event.active_duration_ms)
            if start.astimezone(TAIPEI).date() != event.client_time.astimezone(TAIPEI).date():
                raise ValueError('split active intervals at Taipei midnight')
        if len({e.event_id for e in self.events}) != len(self.events):
            raise ValueError('duplicate event_id')
        if sum(e.active_duration_ms for e in self.events) > 60000:
            raise ValueError('batch active time exceeds 60 seconds')
        return self


class UsagePreference(StrictModel):
    enabled: bool = Field(strict=True)


class UsageService:
    def __init__(self, repository):
        self.repository = repository

    def preference(self, user_id, enabled=None):
        with self.repository._connection() as db:
            if enabled is not None:
                # Serialize opt-out/deletion with in-flight telemetry writes.
                db.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s::text,0))', (user_id,))
                if not db.execute('SELECT user_id FROM private.users WHERE user_id=%s',(user_id,)).fetchone():
                    raise NotFoundError('user unavailable')
                db.execute('''INSERT INTO private.usage_preferences(user_id,enabled) VALUES (%s,%s)
                    ON CONFLICT(user_id) DO UPDATE SET enabled=EXCLUDED.enabled,updated_at=now()''', (user_id, enabled))
            row = db.execute('SELECT enabled FROM private.usage_preferences WHERE user_id=%s', (user_id,)).fetchone()
        return {'enabled': bool(row and row['enabled']), 'policy_version': 'usage.v1',
                'recent_days': 7, 'daily_days': 180, 'completeness': 'partial'}

    def ingest(self, user_id, batch: UsageBatch):
        with self.repository._connection() as db:
            db.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s::text,0))', (user_id,))
            pref = db.execute('SELECT enabled FROM private.usage_preferences WHERE user_id=%s', (user_id,)).fetchone()
            if not pref or not pref['enabled']:
                return {'status': 'disabled', 'accepted': 0}
            if db.execute('SELECT batch_id FROM private.usage_ingest_receipts WHERE user_id=%s AND batch_id=%s',
                          (user_id,batch.batch_id)).fetchone():
                return {'status': 'duplicate', 'accepted': 0}
            recent = db.execute('''SELECT count(*) AS n FROM private.usage_ingest_receipts
                WHERE user_id=%s AND received_at>now()-interval '1 minute' ''',(user_id,)).fetchone()
            if recent['n'] >= 6:
                return {'status': 'rate_limited', 'accepted': 0}
            count = db.execute('''SELECT count(*) AS n FROM private.usage_recent_events
                WHERE user_id=%s AND received_at>now()-interval '1 day' ''',(user_id,)).fetchone()
            if count['n'] + len(batch.events) > 10000:
                return {'status': 'rate_limited', 'accepted': 0}
            active = db.execute('''SELECT coalesce(sum(active_duration_ms),0) AS n
                FROM private.usage_recent_events WHERE user_id=%s
                AND received_at>now()-interval '1 minute' ''',(user_id,)).fetchone()
            if active['n'] + sum(e.active_duration_ms for e in batch.events) > 60000:
                return {'status': 'rate_limited', 'accepted': 0}
            receipt = db.execute('''INSERT INTO private.usage_ingest_receipts(user_id,batch_id)
                VALUES (%s,%s) ON CONFLICT DO NOTHING RETURNING batch_id''', (user_id, batch.batch_id)).fetchone()
            if not receipt:
                return {'status': 'duplicate', 'accepted': 0}
            accepted = 0
            for event in sorted(batch.events, key=lambda e: (e.feature_id,e.client_time,e.event_id.hex)):
                saved = db.execute('''INSERT INTO private.usage_recent_events
                    (user_id,event_id,session_id,feature_id,event_type,action_key,outcome,client_time,active_duration_ms)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING event_id''',
                    (user_id,event.event_id,event.session_id,event.feature_id,event.event_type,event.action_key,
                     event.outcome,event.client_time,event.active_duration_ms)).fetchone()
                if not saved:
                    continue
                accepted += 1
                session = db.execute('''INSERT INTO private.usage_daily_sessions(user_id,day,feature_id,session_id)
                    VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING session_id''',
                    (user_id,event.client_time.astimezone(TAIPEI).date(),event.feature_id,event.session_id)).fetchone()
                db.execute('''INSERT INTO private.usage_user_feature_daily
                    (user_id,day,feature_id,page_views,actions,successes,failures,active_duration_ms,last_event_at,sessions)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT(user_id,day,feature_id) DO UPDATE SET
                    page_views=usage_user_feature_daily.page_views+EXCLUDED.page_views,
                    actions=usage_user_feature_daily.actions+EXCLUDED.actions,
                    successes=usage_user_feature_daily.successes+EXCLUDED.successes,
                    failures=usage_user_feature_daily.failures+EXCLUDED.failures,
                    sessions=usage_user_feature_daily.sessions+EXCLUDED.sessions,
                    active_duration_ms=usage_user_feature_daily.active_duration_ms+EXCLUDED.active_duration_ms,
                    last_event_at=greatest(usage_user_feature_daily.last_event_at,EXCLUDED.last_event_at)''',
                    (user_id,event.client_time.astimezone(TAIPEI).date(),event.feature_id,
                     int(event.event_type=='page_view'),int(event.event_type=='feature_action'),
                     int(event.event_type=='action_result' and event.outcome=='success'),
                     int(event.event_type=='action_result' and event.outcome=='failed'),
                     event.active_duration_ms,event.client_time,int(session is not None)))
                db.execute('''INSERT INTO private.usage_monthly_summary(month,feature_id,actions,active_duration_ms)
                    VALUES (%s,%s,%s,%s) ON CONFLICT(month,feature_id) DO UPDATE SET
                    actions=usage_monthly_summary.actions+EXCLUDED.actions,
                    active_duration_ms=usage_monthly_summary.active_duration_ms+EXCLUDED.active_duration_ms''',
                    (event.client_time.astimezone(TAIPEI).date().replace(day=1),event.feature_id,
                     int(event.event_type=='feature_action'),event.active_duration_ms))
        return {'status': 'accepted', 'accepted': accepted, 'completeness': 'partial'}

    def purge(self):
        with self.repository._connection() as db:
            db.execute("DELETE FROM private.usage_recent_events WHERE received_at<now()-interval '7 days' OR client_time<now()-interval '7 days'")
            for table, column, days in (('usage_ingest_receipts','received_at',7),
                                       ('usage_user_feature_daily','day',180),
                                       ('usage_daily_sessions','day',180),
                                       ('usage_access_audit','accessed_at',180)):
                db.execute(f'DELETE FROM private.{table} WHERE {column}<now()-(%s * interval \'1 day\')', (days,))
            db.execute("DELETE FROM private.usage_monthly_summary WHERE month < date_trunc('month',now())-interval '11 months'")

    def delete(self, user_id):
        with self.repository._connection() as db:
            db.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s::text,0))', (user_id,))
            db.execute('''INSERT INTO private.usage_preferences(user_id,enabled)
                SELECT user_id,false FROM private.users WHERE user_id=%s
                ON CONFLICT(user_id) DO UPDATE SET enabled=false,updated_at=now()''', (user_id,))
            for table in ('usage_recent_events','usage_ingest_receipts','usage_user_feature_daily','usage_daily_sessions'):
                db.execute(f'DELETE FROM private.{table} WHERE user_id=%s', (user_id,))
        return {'status': 'deleted', 'enabled': False}

    def read(self, *, actor, days=7, user_id=None, recent=False, query=None, grain='day'):
        # Queries are bounded at the API and again here for non-HTTP callers.
        if days not in (7,30,90) or grain not in ('day','week','month') or (query is not None and len(query)>100):
            raise ValueError('usage query outside bounds')
        with self.repository._connection() as db:
            db.execute('INSERT INTO private.usage_access_audit(actor,target_user_id,view) VALUES (%s,%s,%s)',
                       (actor,user_id,'users' if query is not None else 'recent' if recent else 'daily'))
            if query is not None:
                rows = db.execute('''SELECT u.user_id,u.display_email,max(d.last_event_at) AS last_event_at,
                    sum(d.actions) AS actions,sum(d.active_duration_ms) AS active_duration_ms
                    FROM private.users u LEFT JOIN private.usage_user_feature_daily d
                      ON d.user_id=u.user_id AND d.day >= (now() AT TIME ZONE 'Asia/Taipei')::date-6
                    WHERE position(lower(%s) in lower(u.display_email))>0 OR u.user_id::text=%s
                    GROUP BY u.user_id,u.display_email ORDER BY max(d.last_event_at) DESC NULLS LAST,u.user_id LIMIT 50''',
                    (query,query)).fetchall()
            elif recent:
                rows = db.execute('''SELECT client_time,feature_id,event_type,action_key,outcome
                    FROM private.usage_recent_events WHERE user_id=%s AND client_time>=now()-interval '7 days'
                    ORDER BY client_time DESC,event_id DESC LIMIT 100''',(user_id,)).fetchall()
            else:
                rows = db.execute('''SELECT date_trunc(%s,day)::date AS day,feature_id,count(DISTINCT user_id) AS active_users,
                    sum(page_views) AS page_views,sum(actions) AS actions,sum(successes) AS successes,
                    sum(failures) AS failures,sum(sessions) AS sessions,sum(active_duration_ms) AS active_duration_ms,max(last_event_at) AS last_event_at
                    FROM private.usage_user_feature_daily
                    WHERE day >= (now() AT TIME ZONE 'Asia/Taipei')::date-(%s-1)
                      AND (%s::uuid IS NULL OR user_id=%s)
                    GROUP BY 1,2 ORDER BY 1 DESC,2 LIMIT 900''',(grain,days,user_id,user_id)).fetchall()
            daily = []
            if query is None and not recent:
                daily = db.execute('''SELECT day,count(DISTINCT user_id) AS active_users FROM private.usage_user_feature_daily
                    WHERE day >= (now() AT TIME ZONE 'Asia/Taipei')::date-(%s-1)
                    AND (%s::uuid IS NULL OR user_id=%s) GROUP BY day ORDER BY day DESC LIMIT 90''', (days,user_id,user_id)).fetchall()
        return {'status': 'partial' if rows else 'no_data', 'items': rows,
                'daily_active_users': daily, 'grain': grain,
                'completeness': 'unknown', 'duration_basis': 'estimated', 'days': 7 if recent else days}
