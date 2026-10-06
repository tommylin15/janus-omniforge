from types import SimpleNamespace

import pytest

from packages.mobile_ledger_queue import (
    MobileLedgerQueue,
    MobileLedgerQueueError,
    QUEUE_HEADERS,
)


class Session:
    def __init__(self, *, files=None, values=None, status=200):
        self.files = files if files is not None else [{
            "id": "sheet-1",
            "owners": [{"emailAddress": "Owner@Example.com"}],
            "capabilities": {"canEdit": True},
        }]
        self.values = values if values is not None else [list(QUEUE_HEADERS)]
        self.status = status
        self.calls = []

    def request(self, method, url, timeout, **kwargs):
        self.calls.append((method, url, kwargs))
        if self.status != 200:
            return SimpleNamespace(status_code=self.status, json=lambda: {"error": "secret provider detail"})
        if "drive/v3/files" in url:
            return SimpleNamespace(status_code=200, json=lambda: {"files": self.files})
        if method == "GET":
            return SimpleNamespace(status_code=200, json=lambda: {"values": self.values})
        return SimpleNamespace(status_code=200, json=lambda: {"updatedRows": 1})


def test_queue_discovers_one_owner_reads_bounded_pending_and_marks_status():
    row = [
        "mobile-12345678", "2026-10-06T12:00:00+08:00", "BUY", "2026-10-06", "2330",
        "1000", "100", "", "10", "0", "TWD", "test", "chatgpt-mobile", "PENDING",
    ]
    session = Session(values=[list(QUEUE_HEADERS), row])
    queue = MobileLedgerQueue(session, require_edit=True)
    queue_file = queue.locate()
    assert queue_file.owner_email == "owner@example.com"
    pending = queue.pending(queue_file)
    assert len(pending) == 1 and pending[0]["_row_number"] == "2"
    assert "A1:R1000" in session.calls[1][1]

    queue.mark(queue_file, 2, status="PROCESSED", processed_at="2026-10-06T04:01:00+00:00",
               ledger_version=25, event_id="event-1")
    method, url, kwargs = session.calls[-1]
    assert method == "PUT" and "N2:R2" in url
    assert kwargs["json"]["values"] == [[
        "PROCESSED", "2026-10-06T04:01:00+00:00", "25", "event-1", "",
    ]]


@pytest.mark.parametrize("files", [[], [
    {"id": "a", "owners": [{"emailAddress": "a@example.com"}], "capabilities": {"canEdit": True}},
    {"id": "b", "owners": [{"emailAddress": "b@example.com"}], "capabilities": {"canEdit": True}},
]])
def test_queue_fails_closed_when_exact_file_is_missing_or_ambiguous(files):
    with pytest.raises(MobileLedgerQueueError):
        MobileLedgerQueue(Session(files=files)).locate()


def test_queue_requires_one_owner_and_writer_capability():
    with pytest.raises(MobileLedgerQueueError):
        MobileLedgerQueue(Session(files=[{"id": "x", "owners": [], "capabilities": {"canEdit": True}}])).locate()
    with pytest.raises(MobileLedgerQueueError):
        MobileLedgerQueue(Session(files=[{
            "id": "x", "owners": [{"emailAddress": "owner@example.com"}],
            "capabilities": {"canEdit": False},
        }]), require_edit=True).locate()


def test_queue_rejects_header_drift_and_provider_errors_without_leaking_body():
    queue = MobileLedgerQueue(Session(values=[["wrong"]]))
    queue_file = queue.locate()
    with pytest.raises(MobileLedgerQueueError, match="header contract"):
        queue.rows(queue_file)

    with pytest.raises(MobileLedgerQueueError) as error:
        MobileLedgerQueue(Session(status=403)).locate()
    assert "secret provider detail" not in str(error.value)


def test_pending_is_bounded_and_requires_known_status():
    rows = [list(QUEUE_HEADERS)]
    for index in range(25):
        rows.append([
            f"request-{index:08d}", "", "BUY", "2026-10-06", "2330", "1", "1", "",
            "0", "0", "TWD", "", "chatgpt-mobile", "PENDING" if index < 24 else "PROCESSED",
        ])
    queue = MobileLedgerQueue(Session(values=rows))
    queue_file = queue.locate()
    assert len(queue.pending(queue_file)) == 20
    with pytest.raises(ValueError):
        queue.pending(queue_file, limit=21)
