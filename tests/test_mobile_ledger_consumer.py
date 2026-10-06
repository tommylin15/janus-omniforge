from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID

from services.api.mobile_ledger_consumer import (
    probe_mobile_ledger_consumer,
    process_mobile_ledger_queue,
)
from services.api.repository import OversellError


OWNER = UUID("00000000-0000-0000-0000-000000000001")


class Queue:
    def __init__(self, rows):
        self.rows = rows
        self.marks = []
        self.file = SimpleNamespace(owner_email="owner@example.com", can_edit=True)

    def locate(self):
        return self.file

    def pending(self, queue_file, *, limit=20):
        assert queue_file is self.file
        return self.rows[:limit]

    def has_pending(self, queue_file):
        assert queue_file is self.file
        return bool(self.rows)

    def mark(self, queue_file, row_number, **values):
        assert queue_file is self.file
        self.marks.append((row_number, values))


class Repository:
    def __init__(self):
        self.lookups = []
        self.added = []
        self.by_key = {}

    def user_id_for_email(self, email):
        self.lookups.append(email)
        return OWNER

    def add_ledger(self, owner_id, value, key):
        self.added.append((owner_id, value, key))
        if key not in self.by_key:
            self.by_key[key] = {
                "event_id": "11111111-1111-1111-1111-111111111111",
                "ledger_version": 25,
            }
        return self.by_key[key]


def valid_row(**updates):
    row = {
        "_row_number": "2",
        "request_id": "mobile-12345678",
        "created_at": "2026-10-06T12:00:00+08:00",
        "event_type": "BUY",
        "trade_date": "2026-10-06",
        "symbol": "2330",
        "shares": "1000",
        "price": "100",
        "cash_amount": "",
        "fee": "10",
        "tax": "0",
        "currency": "TWD",
        "memo": "手機補登",
        "source": "chatgpt-mobile",
    }
    row.update(updates)
    return row


def test_consumer_binds_owner_from_drive_and_uses_request_id_for_idempotency():
    queue = Queue([valid_row()])
    repository = Repository()
    result = process_mobile_ledger_queue(
        repository,
        queue=queue,
        now=datetime(2026, 10, 6, 4, tzinfo=timezone.utc),
    )
    assert result == {"pending": 1, "processed": 1, "errors": 0}
    assert repository.lookups == ["owner@example.com"]
    owner, event, key = repository.added[0]
    assert owner == OWNER and key == "mobile-12345678"
    assert event.symbol == "2330" and str(event.shares) == "1000"
    assert str(event.fee) == "10" and str(event.tax) == "0"
    assert queue.marks[0][1]["status"] == "PROCESSED"
    assert queue.marks[0][1]["ledger_version"] == 25

    # A provider retry reuses the exact canonical idempotency key.
    retry = Queue([valid_row()])
    again = process_mobile_ledger_queue(repository, queue=retry)
    assert again["processed"] == 1
    assert repository.added[-1][2] == "mobile-12345678"
    assert repository.by_key["mobile-12345678"]["ledger_version"] == 25


def test_consumer_requires_explicit_fee_and_tax_instead_of_guessing_missing_values():
    queue = Queue([valid_row(fee="")])
    repository = Repository()
    result = process_mobile_ledger_queue(repository, queue=queue)
    assert result == {"pending": 1, "processed": 0, "errors": 1}
    assert repository.added == []
    assert queue.marks == [(2, {
        "status": "ERROR",
        "processed_at": queue.marks[0][1]["processed_at"],
        "error_code": "VALIDATION",
    })]


def test_consumer_sanitizes_oversell_without_leaking_domain_message():
    class OversellRepository(Repository):
        def add_ledger(self, owner_id, value, key):
            raise OversellError("private holdings detail")

    queue = Queue([valid_row(event_type="SELL")])
    result = process_mobile_ledger_queue(OversellRepository(), queue=queue)
    assert result["errors"] == 1
    assert queue.marks[0][1]["error_code"] == "OVERSELL"
    assert "private holdings detail" not in str(queue.marks)


def test_probe_verifies_writer_and_existing_owner_binding_without_exposing_identity():
    queue = Queue([])
    repository = Repository()
    result = probe_mobile_ledger_consumer(repository, queue=queue)
    assert result == {"status": "available", "pending": False, "writable": True, "owner_bound": True}
    assert repository.lookups == ["owner@example.com"]
    assert "owner@example.com" not in str(result)
    assert str(OWNER) not in str(result)
