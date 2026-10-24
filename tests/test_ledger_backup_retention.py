"""Controller only observes; the VM owns generation-fenced GCS cleanup."""
from datetime import datetime
from unittest.mock import MagicMock
import pytest
from ingestion_core.ledger_backup import poll_backup


@pytest.mark.parametrize("retention,status", [("pending","running"),("succeeded","succeeded"),("failed","failed")])
def test_backup_and_cleanup_status_are_independent(retention, status):
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value.fetchone.return_value = (
        "succeeded", 1024000, "a"*64, datetime(2026,10,24,2), None, retention)
    result = poll_backup(connection, {"backup_date":"2026-10-24"})
    assert result["status"] == status
    assert result["backup_status"] == "succeeded"
    assert result["retention_cleanup"]["status"] == retention
    assert result["size_bytes"] == 1024000


def test_invalid_completed_receipt_never_becomes_success():
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value.fetchone.return_value = (
        "succeeded", 0, "bad", None, None, "succeeded")
    with pytest.raises(ValueError):
        poll_backup(connection, {"backup_date":"2026-10-24"})
