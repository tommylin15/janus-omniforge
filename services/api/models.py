"""Typed request contracts for the private workspace."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any
from uuid import UUID

from .engine_security import AgentRuntime, Capability

from pydantic import BaseModel, ConfigDict, Field, model_validator


Money = Annotated[Decimal, Field(max_digits=20, decimal_places=4, ge=0)]
Quantity = Annotated[Decimal, Field(max_digits=20, decimal_places=8, gt=0)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


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


class ContextSelector(StrictModel):
    source_id: Annotated[str, Field(pattern=r"^[a-z0-9-]{1,40}$")]
    resource: Annotated[str, Field(pattern=r"^[a-z0-9-]{1,40}$")]
    symbol: Annotated[str | None, Field(pattern=r"^[0-9A-Z._-]{1,20}$")] = None
    start_date: date | None = None
    end_date: date | None = None
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


class ContextPreviewIn(StrictModel):
    selector: ContextSelector


class ContextResolveIn(StrictModel):
    owner_id: UUID
    thread_id: Annotated[str, Field(min_length=1, max_length=128)]
    turn_id: Annotated[str, Field(min_length=1, max_length=128)]
    context_refs: Annotated[list[Annotated[str, Field(min_length=32, max_length=128)]], Field(min_length=1, max_length=10)]

    @model_validator(mode="after")
    def validate_refs(self) -> "ContextResolveIn":
        if len(self.context_refs) != len(set(self.context_refs)):
            raise ValueError("context_refs must be unique")
        return self


class McpServerIn(StrictModel):
    server_id: Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9-]{0,39}$")]
    config_ref: Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")]
    enabled: bool = True
    tool_grants: Annotated[list[Annotated[str, Field(pattern=r"^[A-Za-z0-9._:-]{1,192}$")]], Field(max_length=128)] = []

    @model_validator(mode="after")
    def validate_grants(self) -> "McpServerIn":
        if len(self.tool_grants) != len(set(self.tool_grants)):
            raise ValueError("tool_grants must be unique")
        if any(not grant.startswith(f"{self.server_id}__") for grant in self.tool_grants):
            raise ValueError("tool grants must use the server namespace")
        return self


class McpServersPutIn(StrictModel):
    items: Annotated[list[McpServerIn], Field(max_length=8)]

    @model_validator(mode="after")
    def validate_servers(self) -> "McpServersPutIn":
        if len({item.server_id for item in self.items}) != len(self.items):
            raise ValueError("server_id must be unique")
        return self


class SkillStep(StrictModel):
    tool: Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,191}$")]
    args: dict[str, Any] = Field(default_factory=dict)


class SkillDefinition(StrictModel):
    prompt: Annotated[str, Field(min_length=1, max_length=12_000)]
    required_tools: Annotated[list[Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,191}$")]], Field(max_length=32)] = Field(default_factory=list)
    workflow: Annotated[list[SkillStep], Field(max_length=32)] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_scope(self) -> "SkillDefinition":
        if len(self.required_tools) != len(set(self.required_tools)):
            raise ValueError("required_tools must be unique")
        required = set(self.required_tools)
        if any(step.tool not in required for step in self.workflow):
            raise ValueError("workflow tools must be declared in required_tools")
        return self


class SkillRevisionIn(StrictModel):
    skill_id: Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9-]{0,127}$")]
    revision: Annotated[int, Field(ge=1)]
    definition: SkillDefinition


class SkillStateIn(StrictModel):
    enabled: bool
    revision: Annotated[int | None, Field(ge=1)] = None


class RuntimeBindingIn(StrictModel):
    runtime: AgentRuntime
    model: Annotated[str, Field(min_length=1, max_length=128)]
    assistant_profile: Annotated[str, Field(min_length=1, max_length=128)]
    skill_profile: Annotated[str | None, Field(min_length=1, max_length=128)] = None
    model_capabilities: list[Capability] = Field(default_factory=list)


class ThreadCreateIn(RuntimeBindingIn):
    thread_id: Annotated[str | None, Field(min_length=1, max_length=128)] = None
    parent_thread_id: Annotated[str | None, Field(min_length=1, max_length=128)] = None


class ForkThreadIn(StrictModel):
    thread_id: Annotated[str | None, Field(min_length=1, max_length=128)] = None


class MessageIn(StrictModel):
    content: Annotated[str, Field(min_length=1, max_length=50_000)]
    turn_id: Annotated[str | None, Field(min_length=1, max_length=128)] = None
    context_artifact_ref: Annotated[str | None, Field(min_length=1, max_length=512)] = None
    skill_id: Annotated[str | None, Field(pattern=r"^[a-z0-9][a-z0-9-]{0,127}$")] = None
    skill_revision: Annotated[int | None, Field(ge=1)] = None
    continuation: dict[str, Any] = Field(default_factory=dict)


class ApprovalResponseIn(StrictModel):
    approved: bool
    params_digest: Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
