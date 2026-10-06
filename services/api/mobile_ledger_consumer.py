"""Consume the private mobile ledger queue into the canonical Janus ledger."""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any

from pydantic import ValidationError

from packages.mobile_ledger_queue import MobileLedgerQueue, MobileLedgerQueueError
from .models import LedgerEventIn
from .repository import ConflictError, OversellError


_REQUEST_ID = re.compile(r"^mobile-[A-Za-z0-9._:-]{8,121}$")


def _optional(value: str) -> str | None:
    value = value.strip()
    return value or None


def _ledger_value(row: dict[str, str]) -> LedgerEventIn:
    if row.get("source", "").strip() != "chatgpt-mobile":
        raise ValueError("mobile ledger source is invalid")
    created_at = datetime.fromisoformat(row.get("created_at", "").strip().replace("Z", "+00:00"))
    if created_at.tzinfo is None:
        raise ValueError("mobile ledger created_at must include timezone")
    if not row.get("fee", "").strip() or not row.get("tax", "").strip():
        raise ValueError("fee and tax must be explicit")
    return LedgerEventIn.model_validate({
        "event_type": row.get("event_type", "").strip(),
        "trade_date": row.get("trade_date", "").strip(),
        "symbol": row.get("symbol", "").strip().upper(),
        "shares": _optional(row.get("shares", "")),
        "price": _optional(row.get("price", "")),
        "cash_amount": _optional(row.get("cash_amount", "")),
        "fee": row.get("fee", "").strip(),
        "tax": row.get("tax", "").strip(),
        "currency": row.get("currency", "").strip().upper() or "TWD",
        "memo": _optional(row.get("memo", "")),
    })


def probe_mobile_ledger_consumer(
    repository: Any,
    *,
    queue: MobileLedgerQueue | None = None,
) -> dict[str, Any]:
    queue = queue or MobileLedgerQueue.from_adc(write=True)
    queue_file = queue.locate()
    repository.user_id_for_email(queue_file.owner_email)
    return {
        "status": "available",
        "pending": queue.has_pending(queue_file),
        "writable": queue_file.can_edit,
        "owner_bound": True,
    }


def process_mobile_ledger_queue(
    repository: Any,
    *,
    queue: MobileLedgerQueue | None = None,
    limit: int = 20,
    now: datetime | None = None,
) -> dict[str, int]:
    """Persist bounded PENDING rows; provider/infrastructure failures remain retryable."""
    queue = queue or MobileLedgerQueue.from_adc(write=True)
    queue_file = queue.locate()
    owner_id = repository.user_id_for_email(queue_file.owner_email)
    pending = queue.pending(queue_file, limit=limit)
    processed = errors = 0
    timestamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()

    for row in pending:
        request_id = row.get("request_id", "").strip()
        row_number = int(row["_row_number"])
        try:
            if _REQUEST_ID.fullmatch(request_id) is None:
                raise ValueError("invalid request id")
            value = _ledger_value(row)
            persisted = repository.add_ledger(owner_id, value, request_id)
            queue.mark(
                queue_file,
                row_number,
                status="PROCESSED",
                processed_at=timestamp,
                ledger_version=persisted.get("ledger_version"),
                event_id=persisted.get("event_id"),
            )
            processed += 1
        except (ValidationError, ValueError, ConflictError, OversellError) as error:
            code = {
                OversellError: "OVERSELL",
                ConflictError: "CONFLICT",
                ValidationError: "VALIDATION",
                ValueError: "VALIDATION",
            }.get(type(error), "VALIDATION")
            queue.mark(
                queue_file,
                row_number,
                status="ERROR",
                processed_at=timestamp,
                error_code=code,
            )
            errors += 1

    return {"pending": len(pending), "processed": processed, "errors": errors}


__all__ = ["MobileLedgerQueueError", "probe_mobile_ledger_consumer", "process_mobile_ledger_queue"]
