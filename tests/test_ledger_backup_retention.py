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


def test_poll_backup_success_does_not_trigger_gcs_retention():
    """A successful VM backup transitions even if the GCS cleanup is unavailable."""
    from ingestion_core.ledger_backup import poll_backup

    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = (
        'succeeded', 1024000, 'a' * 64, datetime(2026, 10, 17, 2), None
    )
    mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor.__exit__ = MagicMock(return_value=False)
    mock_connection = MagicMock()
    mock_connection.cursor.return_value = mock_cursor
    state = {
        'job': 'janus-batch-controller', 'batch': 'ledger-backup',
        'status': 'running', 'backup_date': '2026-10-17',
    }

    with patch("ingestion_core.ledger_backup.cleanup_old_backups") as mock_cleanup:
        mock_cleanup.side_effect = PermissionError("GCS private backup bucket")
        result = poll_backup(mock_connection, state)

    assert result['status'] == 'succeeded'
    assert result['retention_cleanup'] == {'status': 'not_run_in_reconcile'}
    assert result['size_bytes'] == 1024000
    assert result['completion_time'] == '2026-10-17T02:00:00'
    mock_cleanup.assert_not_called()


def test_poll_backup_failed_and_missing_receipts_do_not_mark_succeeded():
    from ingestion_core.ledger_backup import poll_backup

    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = (
        'succeeded', 1024000, 'not-a-checksum', datetime(2026, 10, 17, 2), None
    )
    mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor.__exit__ = MagicMock(return_value=False)
    mock_connection = MagicMock()
    mock_connection.cursor.return_value = mock_cursor
    with pytest.raises(ValueError, match='invalid completed backup receipt'):
        poll_backup(mock_connection, {'status':'running','backup_date':'2026-10-17'})
    mock_cursor.fetchone.return_value = ('failed', None, None, None, 'BACKUP_FAILED')
    result = poll_backup(mock_connection, {'status':'running','backup_date':'2026-10-17'})
    assert result['status'] == 'failed'
