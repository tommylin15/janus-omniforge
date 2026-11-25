"""AI-REF-05 單元測試：/changes 與 /today-changes Additive v2 擴充與零 Page-Load LLM 呼叫。"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, timezone

from packages.ai_insight_contracts import (
    AIAnalysisInput,
    AnalysisMeta,
    DeterministicFact,
    DeterministicReview,
    ExternalEstimates,
    LLMInsightDraft,
    LLMPrimaryInsightDraft,
    QualityGate,
    Summary30s,
    build_stock_insight_v2,
)
from packages.analysis_product import content_hash
from services.api.analysis import AnalysisService
from tests.test_change_analysis import fact, observe


def _sample_v2_dict(symbol: str = "2330") -> dict:
    inp = AIAnalysisInput(
        meta=AnalysisMeta(
            canonical_symbol=symbol,
            company_name="台積電",
            market="TWSE",
            security_type="common_stock",
            as_of_date=date(2026, 11, 25),
            price_as_of_date=date(2026, 11, 25),
            session="post_market",
        ),
        deterministic_review=DeterministicReview(review_status="OK", triggered_rules=[]),
        deterministic_facts=[
            DeterministicFact(
                evidence_id="fact_1",
                category="price",
                metric="close",
                label="還原收盤價",
                value=1050.0,
                display_value="1,050.0 元",
                currency="TWD",
                source_name="TWSE_CORE",
                as_of=date(2026, 11, 25),
                deep_link=f"/stock/{symbol}?tab=price",
            )
        ],
        recent_events=[],
        external_estimates=ExternalEstimates(status="not_covered", items=[]),
        previous_insights=[],
    )
    draft = LLMInsightDraft(
        summary_30s=Summary30s(current_state="收盤報 1,050.0 元", key_delta="無重大變化", top_watch="月底營收"),
        primary_insights=[
            LLMPrimaryInsightDraft(
                previous_id=None,
                statement_type="confirmed_fact",
                category="price",
                state="new",
                rank_reason="price_volume_anomaly",
                headline="還原收盤價 1,050.0 元",
                meaning=None,
                next_check="觀察後續成交量",
                invalidation_condition="公布新收盤價",
                evidence_ids=["fact_1"],
            )
        ],
    )
    return build_stock_insight_v2(
        inp,
        draft,
        mode="ai_synthesis",
        model_id="gemini-hydrogen",
        prompt_version="v2.1.0",
        generated_at=datetime(2026, 11, 25, 8, 0, tzinfo=timezone.utc),
        source_status="available",
        quality_gate=QualityGate(status="PASS", error_count=0, warning_count=0),
        secondary_insights=[{"headline": "補充事實"}],
    ).model_dump(mode="json")


class _StubConnection:
    def __init__(self, product: dict) -> None:
        self.product = product

    def execute(self, sql: str, args=None):
        self._sql = sql
        self._args = args
        return self

    def fetchall(self):
        if "membership GROUP BY" in self._sql:
            return [{"symbol": "2330", "priority": 0}]
        return [{"symbol": self.product["symbol"], "payload_json": self.product}]


class _StubRepo:
    def __init__(self, snapshots: dict[str, dict]) -> None:
        product = {
            "symbol": "2330",
            "change_analysis": {
                "postmarket": {
                    "cutoff_at": "2026-11-25T08:00:00Z",
                    "observations": observe([fact(valid_until="2099-08-01T00:00:00Z")]),
                }
            },
        }
        product["content_hash"] = content_hash(product)
        self.conn = _StubConnection(product)
        self.snapshots = snapshots
        self.loaded_calls: list[tuple[list[str], str]] = []

    @contextmanager
    def _connection(self):
        yield self.conn

    def list_latest_insight_v2(self, symbols: list[str], session: str = "postmarket") -> dict[str, dict]:
        self.loaded_calls.append((list(symbols), session))
        return {s: self.snapshots[s] for s in symbols if s in self.snapshots}


def test_changes_and_today_changes_attach_insight_v2_additively():
    v2_2330 = _sample_v2_dict("2330")
    repo = _StubRepo({"2330": v2_2330})
    service = AnalysisService(repo)

    detail = service.changes("2330", "postmarket")
    assert "observations" in detail
    assert detail["insight_v2"]["schema_version"] == "insight.v2"
    assert detail["insight_v2"]["more_count"] == 1

    # 非母體個股（無持久化快照）僅回傳 waiting / fallback，絕不呼叫 LLM
    uncovered = service.changes("9999", "postmarket")
    assert uncovered["status"] == "waiting"
    assert "insight_v2" not in uncovered

    today = service.today_changes("owner-a", "postmarket")
    assert len(today["items"]) == 1
    preview = today["items"][0]["insight_v2_preview"]
    assert preview["schema_version"] == "insight.v2"
    assert preview["review_status"] == "OK"
    assert preview["more_count"] == 1
    assert preview["primary_insight"]["headline"] == "還原收盤價 1,050.0 元"
