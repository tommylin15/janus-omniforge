"""Owner-scoped research persistence and HTTP contract. No in-process AI tasks."""
import hashlib
import json
import os
from datetime import datetime, timedelta
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import Field
from .personal_strategy_contract import (TAIPEI, TYPES, TEMPLATES, StrategyInput, ReportInput,
    TierInput, SeedInput, Strict, period, preview)


def encoded(value):
    return json.dumps(jsonable_encoder(value), ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def digest(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


class PersonalStrategyService:
    def __init__(self, repository, trigger=None):
        self.repo = repository
        self.trigger = trigger or PersonalResearchTrigger()

    def lock(self, c, owner):
        # Same order as legacy follow/reorder; serializes quota and pool writes.
        c.execute("SELECT pg_advisory_xact_lock(hashtext('private-watchlist-symbol-limit'))")
        row = c.execute('SELECT user_id,ledger_version,change_version FROM private.users WHERE user_id=%s FOR UPDATE', (owner,)).fetchone()
        if not row:
            raise HTTPException(404, '找不到個人資料')
        return row

    def active(self, c, owner):
        return c.execute('''SELECT p.*,s.paused FROM private.personal_strategy_state s
            JOIN private.personal_strategies p ON p.version_id=s.active_version AND p.user_id=s.user_id
            WHERE s.user_id=%s''', (owner,)).fetchone()

    def summary(self, owner):
        week = period('strategy')
        today = datetime.now(TAIPEI).date()
        with self.repo._connection() as c:
            active = self.active(c, owner)
            requests = c.execute('''SELECT request_id,kind,status,period_start,attempts,safe_error,lease_until
                FROM private.personal_research_requests WHERE user_id=%s
                AND ((kind='strategy' AND period_start=%s) OR (kind<>'strategy' AND period_start=%s))
                ORDER BY requested_at DESC''', (owner, week, today)).fetchall()
            used = c.execute('SELECT 1 FROM private.personal_strategies WHERE user_id=%s AND week_start=%s', (owner, week)).fetchone()
        return {'active': active, 'requests': requests, 'strategy_locked': bool(used),
                'next_change_at': f'{week+timedelta(days=7)}T00:00:00+08:00',
                'saturday': today.weekday()==5,
                'enabled': os.getenv('PERSONAL_STRATEGY_ENABLED', 'false') == 'true'}

    def snapshot(self, c, owner):
        user = c.execute('SELECT ledger_version,change_version FROM private.users WHERE user_id=%s', (owner,)).fetchone()
        holdings = c.execute('SELECT * FROM private.current_positions WHERE user_id=%s AND shares>0 ORDER BY symbol,currency', (owner,)).fetchall()
        watchlist = c.execute('SELECT * FROM private.watchlist WHERE user_id=%s AND active ORDER BY sort_order,symbol', (owner,)).fetchall()
        active = self.active(c, owner)
        cash = self.repo._cash_position_in_tx(c, owner)
        # Explicitly exclude email, identifiers, notes and secrets from model context.
        positions = [{k:v for k,v in r.items() if k not in ('user_id',)} for r in holdings]
        watches = [{k:v for k,v in r.items() if k not in ('user_id','idempotency_key')} for r in watchlist]
        symbols = sorted({r['symbol'] for r in positions+watches})
        stocks = c.execute('SELECT symbol,name,market FROM control.stock_master WHERE symbol=ANY(%s)', (symbols,)).fetchall() if symbols else []
        quotes = c.execute('''SELECT symbol,price,quote_at,received_at FROM control.operational_last_quotes
            WHERE symbol=ANY(%s)''',(symbols,)).fetchall() if symbols else []
        protected = set(active['rules'].get('protected_symbols',[])) if active else set()
        for p in positions:
            p['pool'] = 'protected' if p['symbol'] in protected else 'general'
            p['status'] = 'S'
        products = c.execute('''SELECT DISTINCT ON(symbol) symbol,analysis_as_of,payload_json
            FROM private.specialist_product WHERE symbol=ANY(%s) ORDER BY symbol,analysis_as_of DESC,created_at DESC''', (symbols,)).fetchall() if symbols else []
        version = {'user':dict(user), 'watch':watches, 'cash_version':cash.get('cash_version'),
                   'active':str(active['version_id']) if active else None, 'paused':bool(active and active['paused'])}
        return jsonable_encoder({'version': digest(version), 'holdings':positions, 'watchlist':watches,
            'cash':cash, 'strategy':active, 'stocks':stocks, 'products':products, 'last_quotes':quotes,
            'trend_signal_status':'not_computed: no verified adjusted daily series supplied',
            'captured_at':datetime.now(TAIPEI)})

    def enqueue(self, owner, kind, payload, key):
        if os.getenv('PERSONAL_STRATEGY_ENABLED', 'false') != 'true':
            raise HTTPException(503, '個人策略尚未啟用；請完成部署設定')
        slot = period(kind)
        input_hash = digest(payload)
        with self.repo._connection() as c:
            self.lock(c, owner)
            replay = c.execute('SELECT * FROM private.personal_research_requests WHERE user_id=%s AND idempotency_key=%s', (owner,key)).fetchone()
            if replay:
                if replay['input_hash'] != input_hash or replay['kind'] != kind:
                    raise HTTPException(409, '同一請求識別不可改內容')
                return self.public_request(replay)
            existing = c.execute('SELECT * FROM private.personal_research_requests WHERE user_id=%s AND kind=%s AND period_start=%s', (owner,kind,slot)).fetchone()
            if existing and existing['input_hash'] == input_hash:
                return self.public_request(existing)
            if existing:
                raise HTTPException(409, {'message':'本時段已有請求，請查狀態或重試原請求', 'request_id':str(existing['request_id'])})
            if kind == 'strategy':
                value = StrategyInput.model_validate(payload)
                prepared = preview(value)
                if prepared['blocked']:
                    raise HTTPException(422, prepared['warnings'])
                if not value.private_ai_consent:
                    raise HTTPException(422, '需同意將必要私人資料送Gemini分析')
                if c.execute('SELECT 1 FROM private.personal_strategies WHERE user_id=%s AND week_start=%s', (owner,slot)).fetchone():
                    raise HTTPException(409, '本週已產出策略')
                context = {'prepared':prepared}
            else:
                current = self.active(c, owner)
                if not current:
                    raise HTTPException(409, '請先產出個人策略')
                context = {'snapshot':self.snapshot(c, owner)}
                if not current['rules'].get('private_ai_consent'):
                    raise HTTPException(409, '尚未同意私人AI分析')
            request_id = uuid4()
            row = c.execute('''INSERT INTO private.personal_research_requests
                (request_id,user_id,kind,period_start,idempotency_key,input_hash,status,input_json)
                VALUES(%s,%s,%s,%s,%s,%s,'QUEUED',%s::jsonb) RETURNING *''',
                (request_id,owner,kind,slot,key,input_hash,encoded({'payload':payload,**context}))).fetchone()
        self.dispatch(owner, request_id)
        return self.public_request(row)

    @staticmethod
    def public_request(row):
        return {k:row[k] for k in ('request_id','kind','status','period_start','attempts','safe_error','lease_until')}

    def dispatch(self, owner, request_id):
        try:
            self.trigger.start(request_id)
        except Exception:
            # An ambiguous dispatch may still have reached Cloud Run. Claim is
            # conditional; a running worker must never be failed by this path.
            with self.repo._connection() as c:
                c.execute("UPDATE private.personal_research_requests SET status='FAILED',safe_error='派送未確認，可重試原請求' WHERE request_id=%s AND user_id=%s AND status='QUEUED'", (request_id,owner))

    def status(self, owner, request_id):
        with self.repo._connection() as c:
            row = c.execute('SELECT * FROM private.personal_research_requests WHERE request_id=%s AND user_id=%s', (request_id,owner)).fetchone()
        if not row:
            raise HTTPException(404, '找不到請求')
        return self.public_request(row)

    def retry(self, owner, request_id):
        with self.repo._connection() as c:
            self.lock(c, owner)
            row = c.execute('SELECT * FROM private.personal_research_requests WHERE request_id=%s AND user_id=%s FOR UPDATE', (request_id,owner)).fetchone()
            if not row:
                raise HTTPException(404, '找不到請求')
            if row['period_start'] != period(row['kind']):
                raise HTTPException(409, '已跨日／跨週，不可重試舊請求')
            if row['attempts'] >= 2:
                raise HTTPException(409, '已達重試上限')
            if row['status'] in ('READY','PARTIAL'):
                return self.public_request(row)
            if row['lease_until'] and row['lease_until'] > datetime.now(TAIPEI):
                raise HTTPException(409, '工作仍在執行')
            if row['status']=='QUEUED' and datetime.now(TAIPEI)-row['requested_at'] < timedelta(minutes=2):
                raise HTTPException(409, '派送中，請稍候')
            c.execute("UPDATE private.personal_research_requests SET status='QUEUED',lease_token=NULL,lease_until=NULL,safe_error=NULL WHERE request_id=%s", (request_id,))
        self.dispatch(owner, request_id)
        return self.status(owner, request_id)

    def tier(self, owner, symbol, value):
        with self.repo._connection() as c:
            self.lock(c, owner)
            active = self.active(c, owner)
            if active and value.tier=='B':
                count=c.execute("SELECT count(*) AS n FROM private.watchlist WHERE user_id=%s AND active AND tier='B' AND symbol<>%s", (owner,symbol)).fetchone()['n']
                if count >= active['rules']['b_capacity']:
                    raise HTTPException(409, 'B池已達策略容量')
            row = c.execute('''UPDATE private.watchlist SET tier=%s,tier_confirmed=true,sync_locked=%s,
                version=version+1,updated_at=now() WHERE user_id=%s AND symbol=%s AND active AND version=%s RETURNING *''',
                (value.tier,value.locked,owner,symbol,value.expected_version)).fetchone()
            if not row:
                raise HTTPException(409, '名單版本已變更，請重新整理')
            self.repo._next_change_version(c,owner)
            return row

    def pause(self, owner, paused):
        with self.repo._connection() as c:
            self.lock(c, owner)
            c.execute('''INSERT INTO private.personal_strategy_state(user_id,paused) VALUES(%s,%s)
                ON CONFLICT(user_id) DO UPDATE SET paused=EXCLUDED.paused,updated_at=now()''',(owner,paused))
        return {'paused':paused}

    def reports(self, owner, kind):
        if kind not in TYPES:
            raise HTTPException(422, '報告類型錯誤')
        with self.repo._connection() as c:
            return {'items':c.execute('SELECT * FROM private.personal_reports WHERE user_id=%s AND kind=%s ORDER BY created_at DESC,report_id DESC LIMIT 3', (owner,kind)).fetchall()}

    def seed(self, owner, value, apply=False):
        # Lossless import; interpretation is explicitly separate from ledger writes.
        result = {'content_hash':digest(value.documents),'files':list(value.documents),
                  'unparsed':list(value.documents),'note':'完整保留私人原文；不自動修改帳本、名單或生效策略。可複製策略條文至設定預覽。'}
        if apply:
            with self.repo._connection() as c:
                self.lock(c,owner)
                existing=c.execute('SELECT content_hash FROM private.personal_strategy_seeds WHERE user_id=%s',(owner,)).fetchone()
                if existing and existing['content_hash'] != result['content_hash']:
                    raise HTTPException(409,'已匯入不同種子；保留原資料，不覆寫')
                c.execute('INSERT INTO private.personal_strategy_seeds(user_id,documents,content_hash) VALUES(%s,%s::jsonb,%s) ON CONFLICT(user_id) DO NOTHING', (owner,encoded(value.documents),result['content_hash']))
        return result

    def export(self, owner):
        with self.repo._connection() as c:
            active=self.active(c,owner)
            seed=c.execute('SELECT documents FROM private.personal_strategy_seeds WHERE user_id=%s',(owner,)).fetchone()
            reports=c.execute('SELECT kind,markdown,created_at FROM private.personal_reports WHERE user_id=%s ORDER BY created_at DESC LIMIT 12',(owner,)).fetchall()
        return {'strategy':active,'seed_documents':seed['documents'] if seed else {},'reports':reports}


class PersonalResearchTrigger:
    def start(self, request_id):
        from .private_recalc_queue import CloudRunPrivateRecalcTrigger
        trigger=CloudRunPrivateRecalcTrigger.from_env()
        response=trigger._request(f'https://run.googleapis.com/v2/projects/{trigger.project}/locations/{trigger.region}/jobs/{trigger.job}:run',
            json={'overrides':{'taskCount':1,'containerOverrides':[{'name':trigger.container,'env':[
                {'name':'PERSONAL_RESEARCH_REQUEST_ID','value':str(request_id)},
                {'name':'PRIVATE_RECALC_QUEUE_MODE','value':'false'}, {'name':'MOBILE_LEDGER_ONLY','value':'false'}]}]}}, timeout=10)
        if not 200<=response.status_code<300:
            raise RuntimeError('personal research dispatch unavailable')


def router(repository, user_dependency, trigger=None):
    service=PersonalStrategyService(repository,trigger)
    routes=APIRouter(prefix='/api/v1/me/personal-strategy',tags=['personal-strategy'])
    def key(value:str=Header(alias='Idempotency-Key',min_length=8,max_length=128)): return value
    @routes.get('/templates')
    def templates(current=Depends(user_dependency)):
        return {'items':[{'id':k,**v} for k,v in TEMPLATES.items()]}
    @routes.get('')
    def summary(current=Depends(user_dependency)): return jsonable_encoder(service.summary(current.user_id))
    @routes.post('/preview')
    def draft(value:StrategyInput,current=Depends(user_dependency)): return preview(value)
    @routes.post('/generate',status_code=202)
    def generate(value:StrategyInput,current=Depends(user_dependency),token=Depends(key)):
        return jsonable_encoder(service.enqueue(current.user_id,'strategy',value.model_dump(),token))
    @routes.post('/reports',status_code=202)
    def request_report(value:ReportInput,current=Depends(user_dependency),token=Depends(key)):
        try: return jsonable_encoder(service.enqueue(current.user_id,value.report_type,value.model_dump(),token))
        except ValueError as e: raise HTTPException(422,str(e)) from None
    @routes.get('/reports/{kind}')
    def reports(kind:str,current=Depends(user_dependency)): return jsonable_encoder(service.reports(current.user_id,kind))
    @routes.get('/requests/{request_id}')
    def request_status(request_id:UUID,current=Depends(user_dependency)): return jsonable_encoder(service.status(current.user_id,request_id))
    @routes.post('/requests/{request_id}/retry',status_code=202)
    def retry(request_id:UUID,current=Depends(user_dependency)):
        try: return jsonable_encoder(service.retry(current.user_id,request_id))
        except ValueError as e: raise HTTPException(422,str(e)) from None
    @routes.put('/watchlist/{symbol}')
    def tier(symbol:str,value:TierInput,current=Depends(user_dependency)): return jsonable_encoder(service.tier(current.user_id,symbol,value))
    class Pause(Strict):
        paused: bool
    @routes.put('/pause')
    def pause(value:Pause,current=Depends(user_dependency)): return service.pause(current.user_id,value.paused)
    @routes.post('/seed/preview')
    def seed_preview(value:SeedInput,current=Depends(user_dependency)): return service.seed(current.user_id,value)
    @routes.post('/seed/apply')
    def seed_apply(value:SeedInput,current=Depends(user_dependency)): return service.seed(current.user_id,value,True)
    @routes.get('/export')
    def export(current=Depends(user_dependency)): return jsonable_encoder(service.export(current.user_id))
    return routes
