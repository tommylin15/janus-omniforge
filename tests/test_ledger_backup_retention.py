"""Tests for ledger backup retention cleanup."""
from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest


def test_cleanup_skipped_when_minimum_backups():
    """Should not delete when 3 or fewer backups exist."""
    from ingestion_core.ledger_backup import cleanup_old_backups
    
    mock_blob = MagicMock()
    mock_blob.name = "pilot-ledger-backups/daily/2026-10-15.dump"
    
    mock_bucket = MagicMock()
    mock_bucket.list_blobs.return_value = [mock_blob]
    
    mock_client = MagicMock()
    mock_client.bucket.return_value = mock_bucket
    
    result = cleanup_old_backups(storage_client=mock_client)
    
    assert result["status"] == "skipped"
    assert result["reason"] == "minimum_retention"
    assert result["count"] == 1


def test_cleanup_keeps_seven_days():
    """Should keep 7 most recent backups and delete older ones."""
    from ingestion_core.ledger_backup import cleanup_old_backups
    
    # Create 10 mock blobs (dates 10/08 to 10/17)
    blobs = []
    for day in range(8, 18):
        blob = MagicMock()
        blob.name = f"pilot-ledger-backups/daily/2026-10-{day:02d}.dump"
        blobs.append(blob)
    
    mock_bucket = MagicMock()
    mock_bucket.list_blobs.return_value = blobs
    
    mock_client = MagicMock()
    mock_client.bucket.return_value = mock_bucket
    
    result = cleanup_old_backups(storage_client=mock_client)
    
    assert result["status"] == "completed"
    assert result["kept"] == 7
    # Should delete 10/08, 10/09, 10/10 (3 oldest)
    assert len(result["deleted"]) == 3
    assert "2026-10-08" in result["deleted"]
    assert "2026-10-09" in result["deleted"]
    assert "2026-10-10" in result["deleted"]


def test_cleanup_ignores_non_matching_files():
    """Should ignore files that don't match the daily backup pattern."""
    from ingestion_core.ledger_backup import cleanup_old_backups
    
    blobs = []
    # Valid backup
    blob1 = MagicMock()
    blob1.name = "pilot-ledger-backups/daily/2026-10-17.dump"
    blobs.append(blob1)
    # Invalid - wrong extension
    blob2 = MagicMock()
    blob2.name = "pilot-ledger-backups/daily/2026-10-16.sql"
    blobs.append(blob2)
    # Invalid - monthly backup
    blob3 = MagicMock()
    blob3.name = "pilot-ledger-backups/monthly/2026-10.dump"
    blobs.append(blob3)
    
    mock_bucket = MagicMock()
    mock_bucket.list_blobs.return_value = blobs
    
    mock_client = MagicMock()
    mock_client.bucket.return_value = mock_bucket
    
    result = cleanup_old_backups(storage_client=mock_client)
    
    # Only 1 valid backup, should skip
    assert result["status"] == "skipped"
    assert result["count"] == 1


def test_poll_backup_triggers_cleanup_on_success():
    """Cleanup should run after successful backup."""
    from ingestion_core.ledger_backup import poll_backup
    
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = (
        'succeeded',  # status
        1024000,      # size_bytes
        'a' * 64,     # sha256
        datetime(2026, 10, 17, 2, 0, 0),  # completed_at
        None,         # error_code
    )
    mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor.__exit__ = MagicMock(return_value=False)
    
    mock_connection = MagicMock()
    mock_connection.cursor.return_value = mock_cursor
    
    state = {
        'job': 'janus-batch-controller',
        'batch': 'ledger-backup',
        'status': 'running',
        'backup_date': '2026-10-17',
    }
    
    with patch("ingestion_core.ledger_backup.cleanup_old_backups") as mock_cleanup:
        mock_cleanup.return_value = {"status": "completed", "kept": 7, "deleted": []}
        result = poll_backup(mock_connection, state)
    
    assert result["status"] == "succeeded"
    assert "retention_cleanup" in result
    mock_cleanup.assert_called_once()
