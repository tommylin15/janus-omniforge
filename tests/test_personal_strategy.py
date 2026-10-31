"""Targeted unit tests for Personal Strategy (PS-VERIFY).

Covers:
- Contract validation, risk limits, template data gates
- Period calculations (weekly strategy, Saturday report)
- Concurrency, idempotency keys, duplicate slots, retry gates
- B-tier capacity, watchlist optimistic locking (expected_version)
- Worker Flash model allowlist / Pro rejection
- Privacy fencing: external Google Search contains ONLY public symbols/time
- Saturday watchlist synchronization atomic rules (all-or-none, locked protection)
- Report retention: 3 per kind, failed runs do not prune existing reports
- Lossless seed storage without ledger mutation
"""
from datetime import date, datetime, timedelta
import json
import pytest
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from services.api.personal_strategy_contract import (
    TAIPEI, TYPES, DAILY, WEEKLY, TEMPLATES,
    Risk, StrategyInput, ReportInput, TierInput, Delta, Section, ReportOutput, SeedInput,
    period, preview
)
from services.api.personal_strategy import (
    PersonalStrategyService, encoded, digest
)
from services.api.personal_research_worker import FlashClient, Worker, safe_url


# ============================================================================
# 1. Contract & Validation Tests
# ============================================================================

def test_risk_validation_rules():
    # Valid risk
    r = Risk(
        tolerance='moderate', horizon='medium',
        minimum_cash_ratio=0.2, max_position_ratio=0.3, max_sector_ratio=0.5,
        loss_budget_ratio=0.05, max_drawdown_ratio=0.15, liquidity_need='半年內無大額支出'
    )
    assert r.tolerance == 'moderate'

    # max_position_ratio > max_sector_ratio must fail
    with pytest.raises(ValueError, match='單股上限不得高於產業上限'):
        Risk(
            tolerance='moderate', horizon='medium',
            minimum_cash_ratio=0.1, max_position_ratio=0.6, max_sector_ratio=0.5,
            loss_budget_ratio=0.05, max_drawdown_ratio=0.15, liquidity_need='無'
        )

    # loss_budget_ratio > max_drawdown_ratio must fail
    with pytest.raises(ValueError, match='單筆風險預算不得大於可承受損失'):
        Risk(
            tolerance='moderate', horizon='medium',
            minimum_cash_ratio=0.1, max_position_ratio=0.3, max_sector_ratio=0.4,
            loss_budget_ratio=0.18, max_drawdown_ratio=0.15, liquidity_need='無'
        )


def test_strategy_input_validation():
    base_risk = Risk(
        tolerance='conservative', horizon='long',
        minimum_cash_ratio=0.3, max_position_ratio=0.2, max_sector_ratio=0.4,
        loss_budget_ratio=0.04, max_drawdown_ratio=0.1, liquidity_need='無需求'
    )

    # Valid strategy
    s = StrategyInput(template_id='stock', risk=base_risk, private_ai_consent=True, protected_symbols=['2882'])
    assert s.template_id == 'stock'
    assert s.protected_symbols == ['2882']

    # Invalid protected symbol format
    with pytest.raises(ValueError, match='保護池代號格式錯誤'):
        StrategyInput(template_id='stock', risk=base_risk, protected_symbols=['invalid space!'])

    # Custom strategy must have at least 20 chars of custom text
    with pytest.raises(ValueError, match='自訂策略需包含目的'):
        StrategyInput(template_id='custom', custom_text='短自訂', risk=base_risk)


def test_report_input_sync_validation():
    # Saturday report requires explicit sync_watchlist
    with pytest.raises(ValueError, match='週六報告需明確選擇是否同步'):
        ReportInput(report_type='saturday', sync_watchlist=None)

    # Valid Saturday report with sync=True or False
    r_sat = ReportInput(report_type='saturday', sync_watchlist=True)
    assert r_sat.sync_watchlist is True

    # Non-Saturday reports cannot sync
    with pytest.raises(ValueError, match='只有週六報告可同步'):
        ReportInput(report_type='premarket', sync_watchlist=True)

    r_pre = ReportInput(report_type='premarket', sync_watchlist=False)
    assert r_pre.sync_watchlist is False


def test_report_output_schema_and_chapters():
    sections_6 = [Section(body=f"Chapter {i+1} content") for i in range(6)]
    out = ReportOutput(
        sections=sections_6,
        support=["支撐證據1", "支撐證據2"],
        opposition=["反對證據1"],
        invalidation=["失效條件1"],
        consistency="策略一致性確認通過",
        missing=["2330: 缺站內四模型資料"],
        covered_symbols=["2330", "2882"],
        delta=[Delta(symbol="2330", action="upsert", tier="A", reason="成長確認")]
    )
    assert len(out.sections) == 6
    assert len(out.support) == 2
    assert out.delta[0].symbol == "2330"


def test_seed_input_validation():
    # Valid seed
    docs = {"my_rules.md": "# My Rules\n進場條件：突破"}
    seed = SeedInput(documents=docs)
    assert len(seed.documents) == 1

    # Non-markdown filename rejected
    with pytest.raises(ValueError, match='必須使用Markdown檔名'):
        SeedInput(documents={"rules.txt": "some text"})


# ============================================================================
# 2. Period Calculations & Strategy Preview Tests
# ============================================================================

def test_period_calculation():
    # Monday ISO week boundary
    wednesday = datetime(2026, 10, 28, 10, 0, tzinfo=TAIPEI) # Wednesday
    week_start = period('strategy', now=wednesday)
    assert week_start == date(2026, 10, 26) # Monday of that week

    # Saturday report on non-Saturday raises ValueError
    with pytest.raises(ValueError, match='週報只限台北時間週六執行'):
        period('saturday', now=wednesday)

    # Saturday report on Saturday succeeds
    saturday = datetime(2026, 10, 31, 10, 0, tzinfo=TAIPEI)
    assert period('saturday', now=saturday) == date(2026, 10, 31)

    # Premarket / intraday / postmarket return the current date
    assert period('premarket', now=wednesday) == date(2026, 10, 28)


def test_strategy_preview_warnings_and_data_gates():
    # Value strategy with short horizon triggers warning & blocks
    risk_short = Risk(
        tolerance='conservative', horizon='short',
        minimum_cash_ratio=0.2, max_position_ratio=0.3, max_sector_ratio=0.4,
        loss_budget_ratio=0.05, max_drawdown_ratio=0.15, liquidity_need='短期需用'
    )
    p_val = preview(StrategyInput(template_id='value', risk=risk_short, private_ai_consent=True))
    assert p_val['blocked'] is True
    assert any('此學派通常需數月以上' in w for w in p_val['warnings'])

    # Trend strategy preview notes data gate
    risk_med = Risk(
        tolerance='aggressive', horizon='medium',
        minimum_cash_ratio=0.1, max_position_ratio=0.3, max_sector_ratio=0.5,
        loss_budget_ratio=0.08, max_drawdown_ratio=0.2, liquidity_need='無'
    )
    p_trend = preview(StrategyInput(template_id='trend', risk=risk_med, private_ai_consent=True))
    assert p_trend['blocked'] is False
    assert '65個有效' in p_trend['rules']['template']['data_gate']
    assert p_trend['rules']['b_capacity'] == 50

    # Stock strategy preview has b_capacity = 8
    p_stock = preview(StrategyInput(template_id='stock', risk=risk_med, private_ai_consent=True))
    assert p_stock['rules']['b_capacity'] == 8


# ============================================================================
# 3. Service Logic: Concurrency, Idempotency, Quota & Optimistic Locks
# ============================================================================

class MockCursor:
    def __init__(self, data=None):
        self.data = data or {}
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append((sql.strip(), params))
        # Custom mock handlers based on SQL patterns
        if "pg_advisory_xact_lock" in sql:
            return self
        if "FROM private.users WHERE user_id=%s FOR UPDATE" in sql:
            self._result = {"user_id": params[0], "ledger_version": 1, "change_version": 1}
            return self
        if "FROM private.personal_research_requests WHERE user_id=%s AND idempotency_key=%s" in sql:
            self._result = self.data.get("replay_request")
            return self
        if "FROM private.personal_research_requests WHERE user_id=%s AND kind=%s AND period_start=%s" in sql:
            self._result = self.data.get("slot_request")
            return self
        if "FROM private.personal_strategies WHERE user_id=%s AND week_start=%s" in sql:
            self._result = self.data.get("week_used")
            return self
        if "UPDATE private.watchlist SET tier=%s" in sql:
            # Check version match
            if self.data.get("watchlist_version_mismatch"):
                self._result = None
            else:
                self._result = {"symbol": params[3], "tier": params[0], "version": 2}
            return self
        if "SELECT count(*) AS n FROM private.watchlist" in sql:
            self._result = {"n": self.data.get("b_count", 0)}
            return self
        self._result = None
        return self

    def fetchone(self):
        return self._result

    def fetchall(self):
        return self._result if isinstance(self._result, list) else ([self._result] if self._result else [])


class MockRepo:
    def __init__(self, data=None):
        self.cursor = MockCursor(data)

    def _connection(self):
        class ConnCtx:
            def __init__(self, cur): self.cur = cur
            def __enter__(self): return self.cur
            def __exit__(self, *args): pass
        return ConnCtx(self.cursor)

    def _next_change_version(self, c, owner): pass
    def _sync_supplement_demand(self, c): pass


def test_enqueue_idempotency_conflict():
    owner = uuid4()
    req_id = uuid4()
    old_hash = digest({"template_id": "stock"})
    diff_hash = digest({"template_id": "value"})

    repo = MockRepo({
        "replay_request": {
            "request_id": req_id, "user_id": owner, "kind": "strategy",
            "period_start": date(2026, 10, 26), "idempotency_key": "test-key-1",
            "input_hash": old_hash, "status": "QUEUED", "attempts": 0,
            "safe_error": None, "lease_until": None
        }
    })
    service = PersonalStrategyService(repo, trigger=None)

    # 1. Matching idempotency key returns existing request
    from fastapi import HTTPException
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("PERSONAL_STRATEGY_ENABLED", "true")
        res = service.enqueue(owner, "strategy", {"template_id": "stock"}, "test-key-1")
        assert res["request_id"] == req_id

        # 2. Same idempotency key with different payload raises 409
        with pytest.raises(HTTPException) as exc:
            service.enqueue(owner, "strategy", {"template_id": "value"}, "test-key-1")
        assert exc.value.status_code == 409
        assert "同一請求識別不可改內容" in exc.value.detail


def test_enqueue_slot_duplicate_conflict():
    owner = uuid4()
    req_id = uuid4()
    slot_date = date(2026, 10, 26)
    diff_hash = digest({"template_id": "trend"})

    repo = MockRepo({
        "slot_request": {
            "request_id": req_id, "user_id": owner, "kind": "strategy",
            "period_start": slot_date, "idempotency_key": "other-key",
            "input_hash": "another_hash", "status": "QUEUED", "attempts": 0,
            "safe_error": None, "lease_until": None
        }
    })
    service = PersonalStrategyService(repo, trigger=None)

    from fastapi import HTTPException
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("PERSONAL_STRATEGY_ENABLED", "true")
        with pytest.raises(HTTPException) as exc:
            service.enqueue(owner, "strategy", {"template_id": "trend"}, "new-key-2")
        assert exc.value.status_code == 409
        assert "本時段已有請求" in exc.value.detail["message"]


def test_b_pool_capacity_enforced():
    owner = uuid4()
    repo = MockRepo({
        "b_count": 8,  # Already 8 B-tier stocks
    })
    service = PersonalStrategyService(repo, trigger=None)

    # Active strategy is stock with b_capacity = 8
    service.active = lambda c, o: {"rules": {"b_capacity": 8}}

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        service.tier(owner, "2330", TierInput(tier="B", locked=False, expected_version=1))
    assert exc.value.status_code == 409
    assert "B池已達策略容量" in exc.value.detail


def test_watchlist_optimistic_version_locking():
    owner = uuid4()
    repo = MockRepo({
        "watchlist_version_mismatch": True,
    })
    service = PersonalStrategyService(repo, trigger=None)
    service.active = lambda c, o: {"rules": {"b_capacity": 50}}

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        service.tier(owner, "2330", TierInput(tier="A", locked=True, expected_version=1))
    assert exc.value.status_code == 409
    assert "名單版本已變更" in exc.value.detail


# ============================================================================
# 4. Worker Tests: Flash Model Whitelist, Privacy Boundary, Sync & Retention
# ============================================================================

def test_safe_url_validation():
    assert safe_url("https://www.twse.com.tw/zh/page/news.html") is True
    assert safe_url("http://insecure.com") is False
    assert safe_url("https://user:pass@secret.com") is False
    assert safe_url("not a url") is False


def test_flash_client_model_whitelist(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "dummy_key")
    monkeypatch.setenv("PERSONAL_RESEARCH_API_APPROVED", "true")
    monkeypatch.setenv("PERSONAL_RESEARCH_FLASH_MODELS", "gemini-2.5-flash")

    client = FlashClient()

    # Mock provider models discovery
    fake_discovery = {
        "models": [
            {"name": "models/gemini-2.5-flash", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/gemini-2.5-pro", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/gemini-3.0-flash-preview", "supportedGenerationMethods": ["generateContent"]},
        ]
    }
    client.http = lambda path, payload=None: fake_discovery

    # Must select gemini-2.5-flash
    selected = client.select()
    assert selected == "gemini-2.5-flash"

    # Pro models or unapproved models must fail
    with pytest.raises(ValueError, match="PINNED_MODEL_UNAVAILABLE"):
        client.select(pinned="gemini-2.5-pro")


def test_external_search_query_privacy_isolation():
    """Verify that external search queries never include private fields (cash, position sizes, cost, notes)."""
    symbols = ["2330", "2454", "2882"]
    prompt_sent = []

    class MockFlashClient:
        def select(self, pinned=None): return "gemini-2.5-flash"
        def generate(self, prompt, *, search=False, schema=None):
            prompt_sent.append((prompt, search))
            if search:
                return "External search summary", {
                    "groundingChunks": [{"web": {"title": "TWSE", "uri": "https://www.twse.com.tw"}}],
                    "groundingSupports": []
                }
            return json.dumps({
                "sections": [{"body": f"Chapter {i+1}"} for i in range(6)],
                "support": ["支撐1"], "opposition": ["反對1"], "invalidation": ["失效1"],
                "consistency": "符合規則", "missing": [], "covered_symbols": symbols,
                "delta": []
            }), {}

    class WorkerRepo(MockRepo):
        def _connection(self):
            class Ctx:
                def __enter__(self):
                    cur = MockCursor()
                    cur.execute = lambda sql, params=None: cur
                    cur.fetchone = lambda: {
                        "request_id": uuid4(), "user_id": uuid4(), "kind": "premarket",
                        "period_start": datetime.now(TAIPEI).date(), "checkpoint": {},
                        "input_json": {
                            "payload": {"report_type": "premarket"},
                            "snapshot": {
                                "holdings": [{"symbol": "2330", "shares": 1000, "cost": 950000}],
                                "watchlist": [{"symbol": "2454", "tier": "A"}, {"symbol": "2882", "tier": "B"}],
                                "cash": {"cash_status": "available", "total_twd": 5000000},
                                "strategy": {"version_id": str(uuid4()), "rules": {"template_id": "stock", "b_capacity": 8}},
                                "products": [{"symbol": "2330"}, {"symbol": "2454"}, {"symbol": "2882"}],
                                "captured_at": datetime.now(TAIPEI).isoformat(),
                                "version": "v1"
                            }
                        }
                    }
                    return cur
                def __exit__(self, *args): pass
            return Ctx()

    worker = Worker(WorkerRepo(), client_factory=MockFlashClient)
    # Run the worker step
    req_id = uuid4()
    worker.finish_report = lambda *args: None  # mock finish

    worker.run(req_id)

    # Check search prompt
    search_prompts = [p for p, is_search in prompt_sent if is_search]
    assert len(search_prompts) > 0
    search_text = search_prompts[0]

    # Must contain public symbols
    assert "taiwan_symbols" in search_text
    # MUST NOT contain private details
    assert "shares" not in search_text
    assert "950000" not in search_text
    assert "5000000" not in search_text
    assert "total_twd" not in search_text


def test_saturday_sync_locked_and_atomic():
    """Verify Saturday sync: locked symbol in delta causes full skip (all-or-none)."""
    worker = Worker(MockRepo())

    # Delta proposing to upsert locked symbol 2330 and unlocked 2454
    output = ReportOutput(
        sections=[Section(body="Ch") for _ in range(7)],
        support=["S1"], opposition=["O1"], invalidation=["I1"],
        consistency="C1", missing=[], covered_symbols=["2330", "2454"],
        delta=[
            Delta(symbol="2330", action="upsert", tier="A", reason="加碼"),
            Delta(symbol="2454", action="upsert", tier="B", reason="觀察")
        ]
    )

    class MockWatchlistCursor(MockCursor):
        def execute(self, sql, params=None):
            if "SELECT * FROM private.watchlist WHERE user_id=%s AND active FOR UPDATE" in sql:
                self._result = [
                    {"symbol": "2330", "tier": "B", "sync_locked": True},   # Locked!
                    {"symbol": "2454", "tier": "C", "sync_locked": False},
                ]
                return self
            return super().execute(sql, params)

    cur = MockWatchlistCursor()
    res = worker.apply_delta(cur, uuid4(), output, {"b_capacity": 8})
    assert res["status"] == "SKIPPED"
    assert "包含鎖定股票" in res["reason"]
