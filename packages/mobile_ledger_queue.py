"""Private Google Sheets queue used as a mobile-safe ChatGPT ledger bridge."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode


# This Sheet is a transport queue only; PostgreSQL remains the canonical ledger.
QUEUE_FILE_NAME = "Janus Mobile Ledger Queue"
QUEUE_SHEET_NAME = "Queue"
QUEUE_HEADERS = (
    "request_id",
    "created_at",
    "event_type",
    "trade_date",
    "symbol",
    "shares",
    "price",
    "cash_amount",
    "fee",
    "tax",
    "currency",
    "memo",
    "source",
    "status",
    "processed_at",
    "ledger_version",
    "event_id",
    "error_code",
)
_MAX_SCAN_ROWS = 999


class MobileLedgerQueueError(RuntimeError):
    pass


@dataclass(frozen=True)
class MobileLedgerQueueFile:
    file_id: str
    owner_email: str
    can_edit: bool


class MobileLedgerQueue:
    """Bounded Drive/Sheets adapter; never trusts a row-supplied owner."""

    DRIVE_FILES = "https://www.googleapis.com/drive/v3/files"
    SHEETS = "https://sheets.googleapis.com/v4/spreadsheets"

    def __init__(self, session: Any, *, require_edit: bool = False) -> None:
        self.session = session
        self.require_edit = require_edit

    @classmethod
    def from_adc(cls, *, write: bool = False) -> "MobileLedgerQueue":
        import google.auth
        from google.auth.transport.requests import AuthorizedSession

        scopes = [
            "https://www.googleapis.com/auth/drive.metadata.readonly",
            "https://www.googleapis.com/auth/spreadsheets.readonly",
        ]
        if write:
            scopes[-1] = "https://www.googleapis.com/auth/spreadsheets"
        try:
            credentials, _ = google.auth.default(scopes=tuple(scopes))
            return cls(AuthorizedSession(credentials), require_edit=write)
        except Exception as error:
            raise MobileLedgerQueueError("mobile ledger queue credential unavailable") from error

    def _json(self, method: str, url: str, *, stage: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = self.session.request(method, url, timeout=15, **kwargs)
            if response.status_code != 200:
                raise MobileLedgerQueueError(f"{stage}_http_{response.status_code}")
            value = response.json()
        except MobileLedgerQueueError:
            raise
        except Exception as error:
            raise MobileLedgerQueueError(f"{stage}_transport") from error
        if not isinstance(value, dict):
            raise MobileLedgerQueueError(f"{stage}_invalid_response")
        return value

    def locate(self) -> MobileLedgerQueueFile:
        escaped = QUEUE_FILE_NAME.replace("'", "\\'")
        query = f"name = '{escaped}' and mimeType = 'application/vnd.google-apps.spreadsheet' and trashed = false"
        params = urlencode({
            "q": query,
            "spaces": "drive",
            "pageSize": 2,
            "fields": "files(id,name,owners(emailAddress),capabilities(canEdit))",
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
        })
        files = self._json("GET", f"{self.DRIVE_FILES}?{params}", stage="drive_metadata").get("files", [])
        if not isinstance(files, list) or len(files) != 1:
            raise MobileLedgerQueueError("mobile ledger queue must resolve to exactly one shared spreadsheet")
        value = files[0]
        owners = value.get("owners") or []
        emails = {str(owner.get("emailAddress", "")).strip().lower()
                  for owner in owners if isinstance(owner, dict) and owner.get("emailAddress")}
        if len(emails) != 1:
            raise MobileLedgerQueueError("mobile ledger queue owner is unavailable")
        can_edit = bool((value.get("capabilities") or {}).get("canEdit"))
        if self.require_edit and not can_edit:
            raise MobileLedgerQueueError("mobile ledger queue is not writable by this runtime")
        file_id = str(value.get("id", "")).strip()
        if not file_id:
            raise MobileLedgerQueueError("mobile ledger queue file identity is unavailable")
        return MobileLedgerQueueFile(file_id=file_id, owner_email=next(iter(emails)), can_edit=can_edit)

    def rows(self, queue_file: MobileLedgerQueueFile) -> list[dict[str, str]]:
        values = self._json(
            "GET",
            f"{self.SHEETS}/{queue_file.file_id}/values/{QUEUE_SHEET_NAME}!A1:R{_MAX_SCAN_ROWS + 1}",
            stage="sheet_read",
        ).get("values", [])
        if not values or tuple(str(value).strip() for value in values[0]) != QUEUE_HEADERS:
            raise MobileLedgerQueueError("mobile ledger queue header contract mismatch")
        rows: list[dict[str, str]] = []
        for row_number, raw in enumerate(values[1:], start=2):
            cells = [str(value).strip() for value in raw]
            cells.extend([""] * (len(QUEUE_HEADERS) - len(cells)))
            record = dict(zip(QUEUE_HEADERS, cells[:len(QUEUE_HEADERS)]))
            record["_row_number"] = str(row_number)
            rows.append(record)
        return rows

    def pending(self, queue_file: MobileLedgerQueueFile, *, limit: int = 20) -> list[dict[str, str]]:
        if not 1 <= limit <= 20:
            raise ValueError("mobile ledger queue limit must be 1..20")
        return [row for row in self.rows(queue_file) if row.get("status") == "PENDING"][:limit]

    def has_pending(self, queue_file: MobileLedgerQueueFile | None = None) -> bool:
        queue_file = queue_file or self.locate()
        return any(row.get("status") == "PENDING" for row in self.rows(queue_file))

    def mark(
        self,
        queue_file: MobileLedgerQueueFile,
        row_number: int,
        *,
        status: str,
        processed_at: str,
        ledger_version: int | str | None = None,
        event_id: Any | None = None,
        error_code: str = "",
    ) -> None:
        if status not in {"PROCESSED", "ERROR"}:
            raise ValueError("unsupported mobile ledger queue status")
        values = [[
            status,
            processed_at,
            "" if ledger_version is None else str(ledger_version),
            "" if event_id is None else str(event_id),
            error_code,
        ]]
        self._json(
            "PUT",
            f"{self.SHEETS}/{queue_file.file_id}/values/{QUEUE_SHEET_NAME}!N{row_number}:R{row_number}?valueInputOption=RAW",
            stage="sheet_write",
            json={"range": f"{QUEUE_SHEET_NAME}!N{row_number}:R{row_number}", "majorDimension": "ROWS", "values": values},
        )


def probe_mobile_ledger_queue(*, write: bool = False) -> dict[str, Any]:
    queue = MobileLedgerQueue.from_adc(write=write)
    queue_file = queue.locate()
    return {"status": "available", "pending": queue.has_pending(queue_file), "writable": queue_file.can_edit}
