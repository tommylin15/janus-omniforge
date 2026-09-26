"""Typed request contracts for the private workspace."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, RootModel, model_validator


Money = Annotated[Decimal, Field(max_digits=20, decimal_places=4, ge=0)]
Quantity = Annotated[Decimal, Field(max_digits=20, decimal_places=8, gt=0)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GovernanceDiffIn(StrictModel):
    value: dict[str, Any]


class GovernanceEditIn(StrictModel):
    value: dict[str, Any]
    status: Literal["approved", "development-default", "pending"] = "pending"
    reason: Annotated[str, Field(min_length=1, max_length=2000)]
    expected_version: Annotated[int, Field(ge=0)]


class MembershipEditIn(StrictModel):
    symbols: Annotated[list[Annotated[str, Field(pattern=r"^[0-9A-Z.-]{1,16}$")]], Field(max_length=50)]
    effective_from: datetime
    reason: Annotated[str, Field(min_length=1, max_length=2000)]
    expected_version: Annotated[int, Field(ge=0)]


class CorePageOut(BaseModel):
    dataset_id: str
    symbol: str
    rows: list[dict[str, Any]]
    limit: int
    offset: int


class CoreSummaryOut(BaseModel):
    symbol: str
    datasets: dict[str, dict[str, Any]]


class PublicReportOut(BaseModel):
    execution_id: UUID
    analysis_as_of: str
    scope_type: str
    scope_id: str
    data_status: str
    confidence: float
    completeness: float
    schema_version: str
    model_version: str
    governance_snapshot_version: str
    data: dict[str, Any]


class PublicWaitingOut(BaseModel):
    analysis_as_of: str = ""
    scope_type: Literal["symbol"] = "symbol"
    scope_id: str
    data_status: Literal["waiting"] = "waiting"
    data: dict[str, Any] = Field(default_factory=dict)


class HealthOut(BaseModel):
    status: Literal["ok"]


class PublicReportListOut(BaseModel):
    items: list[PublicReportOut]


class PublicDatasetOut(BaseModel):
    data_status: Literal["available", "waiting"]
    dataset_id: str
    symbol: str
    rows: list[dict[str, Any]]
    limit: int
    offset: int


class PrivateResponseOut(RootModel[dict[str, Any] | list[Any] | None]):
    """Named OpenAPI boundary for owner-scoped responses with varied domain shapes."""


class AdminResponseOut(RootModel[dict[str, Any] | list[Any] | None]):
    """Named OpenAPI boundary for admin responses with varied domain shapes."""


class LedgerType(StrEnum):
    BUY = "BUY"
    SELL = "SELL"
    CASH_DIV = "CASH_DIV"
    STOCK_DIV = "STOCK_DIV"


class LedgerEventIn(StrictModel):
    event_type: LedgerType
    trade_date: date
    symbol: Annotated[str, Field(pattern=r"^[0-9A-Z.-]{1,16}$")]
    shares: Quantity | None = None
    price: Money | None = None
    cash_amount: Money | None = None
    fee: Money = Decimal("0")
    tax: Money = Decimal("0")
    currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")] = "TWD"
    memo: Annotated[str | None, Field(max_length=500)] = None

    @model_validator(mode="after")
    def validate_type_fields(self) -> "LedgerEventIn":
        required = {
            LedgerType.BUY: ("shares", "price"),
            LedgerType.SELL: ("shares", "price"),
            LedgerType.CASH_DIV: ("cash_amount",),
            LedgerType.STOCK_DIV: ("shares",),
        }[self.event_type]
        if any(getattr(self, field) is None for field in required):
            raise ValueError(f"{self.event_type} requires {', '.join(required)}")
        allowed = set(required) | {"fee", "tax"}
        supplied = {name for name in ("shares", "price", "cash_amount") if getattr(self, name) is not None}
        if supplied - allowed:
            raise ValueError(f"{self.event_type} contains unrelated fields")
        return self
class CorrectionIn(StrictModel):
    expected_version: Annotated[int, Field(ge=1)]
    replacement: LedgerEventIn


class NoteIn(StrictModel):
    body: Annotated[str, Field(min_length=1, max_length=50_000)]
    symbol: Annotated[str | None, Field(pattern=r"^[0-9A-Z.-]{1,16}$")] = None
    trade_event_id: UUID | None = None
    needs_follow_up: bool = False


class NoteRevisionIn(NoteIn):
    expected_version: Annotated[int, Field(ge=1)]


class WatchlistIn(StrictModel):
    symbol: Annotated[str, Field(pattern=r"^[0-9A-Z.-]{1,16}$")]
    target_price: Money | None = None


class WatchlistOrderIn(StrictModel):
    symbols: Annotated[list[str], Field(max_length=50)]
    expected_version: Annotated[int, Field(ge=1)]


class InvestmentProfileIn(StrictModel):
    risk_tolerance: Literal["conservative", "moderate", "aggressive"]
    investment_horizon: Literal["short", "medium", "long"]
    primary_goal: Literal["capital_preservation", "income", "growth", "retirement"]
    minimum_cash_ratio: Annotated[Decimal, Field(ge=0, le=1, max_digits=5, decimal_places=4)]
    ai_context_opt_in: bool = False
    expected_version: Annotated[int, Field(ge=0)]


class InvestmentProfileOut(BaseModel):
    risk_tolerance: Literal["conservative", "moderate", "aggressive"] | None = None
    investment_horizon: Literal["short", "medium", "long"] | None = None
    primary_goal: Literal["capital_preservation", "income", "growth", "retirement"] | None = None
    minimum_cash_ratio: Decimal | None = None
    ai_context_opt_in: bool = False
    version: int = 0
    updated_at: datetime | None = None


class AnalysisFeedbackIn(StrictModel):
    analysis_execution_id: UUID
    scope_type: Literal["market", "industry", "symbol"]
    scope_id: Annotated[str, Field(min_length=1, max_length=80, pattern=r"^[0-9A-Za-z_.:-]+$")]
    feedback: Literal["useful", "neutral", "misleading"]
    reason: Literal[
        "discovered_risk", "useful_context", "already_known", "too_generic", "stale",
        "missing_data", "wrong_interpretation", "other",
    ] | None = None


class PortfolioSummaryItem(BaseModel):
    currency: str
    market_value: Decimal | None
    cost_basis: Decimal
    unrealized_pnl: Decimal | None
    unrealized_return: Decimal | None = None
    aggregate_status: Literal["available", "withheld"]
    affected_symbol_count: int
    affected_symbols: list[str]
    missing_price_count: int
    stale_price_count: int = 0
    valuation_status: Literal["available", "partial", "stale"] | None = None
    cash_safety_status: Literal["available", "insufficient_data"]
    cash_ratio: Decimal | None
    minimum_cash_ratio: Decimal | None
    ledger_version: int
    valuation_date: date


class PortfolioSummaryOut(BaseModel):
    items: list[PortfolioSummaryItem]


class MonthlyLedgerSummaryItem(BaseModel):
    year: int
    month: int = Field(ge=1, le=12)
    currency: str
    purchase_outflow: Decimal
    sale_proceeds: Decimal
    cash_dividends: Decimal
    realized_pnl: Decimal
    fees: Decimal
    taxes: Decimal
    transaction_count: int
    valuation_date: date


class MonthlyLedgerSummaryOut(BaseModel):
    items: list[MonthlyLedgerSummaryItem]


class PortfolioExposureItem(BaseModel):
    currency: str
    industry: str
    market_value: Decimal
    portfolio_ratio: Decimal | None
    allocation_method: Literal["equal_weight_per_membership_v1"]
    symbols: list[str]
    membership_snapshot: list[dict[str, Any]]
    membership_snapshot_hash: str
    ledger_version: int
    valuation_date: date


class PortfolioExposureOut(BaseModel):
    items: list[PortfolioExposureItem]


class PortfolioPerformanceItem(BaseModel):
    year: int
    currency: str
    xirr_status: Literal["available", "insufficient_data", "no_root", "multiple_roots"]
    xirr: float | None
    cash_flow_count: int
    method: Literal["xirr_actual_365_v1"]
    ledger_version: int
    valuation_date: date


class PortfolioPerformanceOut(BaseModel):
    items: list[PortfolioPerformanceItem]


class PortfolioStressItem(BaseModel):
    currency: str
    scenario_id: Literal["broad_market_down_20", "sector_shock_down_30", "liquidity_shock_down_15"]
    shock: Decimal
    portfolio_value_before: Decimal
    portfolio_value_after: Decimal
    loss: Decimal
    cash_safety_status: Literal["available", "insufficient_data"]
    cash_ratio: Decimal | None
    minimum_cash_ratio: Decimal | None
    valuation_status: Literal["available", "partial", "stale"]
    method: Literal["deterministic_parallel_shock_v1"]
    ledger_version: int
    valuation_date: date


class PortfolioStressOut(BaseModel):
    items: list[PortfolioStressItem]


class ContextSelector(StrictModel):
    source_id: Annotated[str, Field(pattern=r"^[a-z0-9-]{1,40}$")]
    resource: Annotated[str, Field(pattern=r"^[a-z0-9-]{1,40}$")]
    symbol: Annotated[str | None, Field(pattern=r"^[0-9A-Z._-]{1,20}$")] = None
    start_date: date | None = None
    end_date: date | None = None
    year: Annotated[int | None, Field(ge=1900, le=9999)] = None
    limit: Annotated[int, Field(ge=1, le=20)] = 10

    @model_validator(mode="after")
    def validate_dates(self) -> "ContextSelector":
        if (self.start_date is None) != (self.end_date is None):
            raise ValueError("start_date and end_date must be supplied together")
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date cannot be after end_date")
        if self.start_date and self.end_date and (self.end_date - self.start_date).days > 366:
            raise ValueError("context date range cannot exceed 366 days")
        return self
