"""Typed request contracts for the private workspace."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated
from uuid import UUID

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
