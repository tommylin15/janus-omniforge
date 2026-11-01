"""Round-trip budgets and immutable-price safeguards for the cleanup."""
from contextlib import contextmanager
from io import BytesIO
import json

import pytest

from ingestion_core import stage
from services.api.repository import PostgresWorkspaceRepository
from services.api.tpex_quotes import TPEX_OFFICIAL_EOD_URL


def test_gcs_credentials_are_reused_and_refreshed_before_expiry(monkeypatch):
    now = [100.0]
    calls = []
    monkeypatch.setattr(stage, "monotonic", lambda: now[0])

    def metadata(request, **kwargs):
        calls.append(request)
        return BytesIO(json.dumps({"access_token": "synthetic", "expires_in": 120}).encode())

    monkeypatch.setattr(stage, "urlopen", metadata)
    store = stage.GcsObjectStore("test-bucket")
    assert store._token() == store._token() == "synthetic"
    assert len(calls) == 1
    now[0] = 160.0
    assert store._token() == "synthetic"
    assert len(calls) == 2


def test_missing_token_expiry_is_not_cached_and_refresh_errors_propagate(monkeypatch):
    calls = []

    def metadata(request, **kwargs):
        calls.append(request)
        if len(calls) == 3:
            raise TimeoutError
        return BytesIO(b'{"access_token":"synthetic"}')

    monkeypatch.setattr(stage, "urlopen", metadata)
    store = stage.GcsObjectStore("test-bucket")
    store._token()
    store._token()
    with pytest.raises(TimeoutError):
        store._token()
    assert len(calls) == 3


def quote(price="31.11", day="2026-10-30"):
    return {"price_date": day, "price": price, "source": "tpex_openapi_eod",
            "source_uri": TPEX_OFFICIAL_EOD_URL, "record_sha256": "a" * 64}


def repository(conflict=False):
    class Connection:
        calls = []
        rolled_back = False

        def execute(self, sql, values):
            self.calls.append((sql, values))
            return self

        def fetchone(self):
            return {"conflict": 1} if conflict else None

    connection = Connection()
    repo = PostgresWorkspaceRepository("synthetic")

    @contextmanager
    def connect():
        try:
            yield connection
        except Exception:
            connection.rolled_back = True
            raise

    repo._connection = connect
    return repo, connection


def test_official_history_uses_two_statements_for_a_full_batch():
    repo, connection = repository()
    history = {str(1000 + index): [quote(day=f"2026-10-{day:02}") for day in range(23, 31)]
               for index in range(250)}
    assert repo.save_official_eod_quotes(history) == 2000
    assert len(connection.calls) == 2
    assert len(connection.calls[0][1][0]) == 2000


def test_official_history_conflict_raises_inside_transaction():
    repo, connection = repository(conflict=True)
    with pytest.raises(ValueError, match="immutable price conflict"):
        repo.save_official_eod_quotes({"00719B": [quote()]})
    assert connection.rolled_back


def test_duplicate_conflict_and_invalid_price_fail_before_opening_database():
    repo, connection = repository()
    with pytest.raises(ValueError, match="immutable price conflict"):
        repo.save_official_eod_quotes({"00719B": [quote(), quote("32")]})
    with pytest.raises(ValueError, match="unverified"):
        repo.save_official_eod_quotes({"00719B": [quote("NaN")]})
    assert repo.save_official_eod_quotes({}) == 0
    assert connection.calls == []


def test_readiness_pushes_row_budget_into_scan_and_rejects_truncation():
    from types import SimpleNamespace
    from ingestion_core.readiness import _scan

    calls = []

    class Table:
        def schema(self):
            return SimpleNamespace(fields=[SimpleNamespace(name="symbol")])

        def current_snapshot(self):
            return SimpleNamespace(snapshot_id=1)

        def scan(self, **options):
            calls.append(options)
            return SimpleNamespace(to_arrow=lambda: SimpleNamespace(to_pylist=lambda: [{"symbol": "2330"}] * 3))

    core = SimpleNamespace(table_exists=lambda _: True, table_identifier=lambda v: v,
                           catalog=SimpleNamespace(load_table=lambda _: Table()))
    with pytest.raises(ValueError, match="bounded_scan_exceeded"):
        _scan(core, "ohlcv", ("symbol",), limit=2)
    assert calls == [{"snapshot_id": 1, "selected_fields": ("symbol",), "limit": 3}]


def test_shared_source_review_still_requires_every_approval_field():
    from ingestion_core.control import SOURCE_REVIEW_CHECKS, source_review_approved

    review = {"status": "approved_fallback", "checks": dict.fromkeys(SOURCE_REVIEW_CHECKS, True),
              "evidence_url": "https://example.com", "reviewer": "operator",
              "reason": "approved", "decided_at": "2026-11-01"}
    assert source_review_approved(review)
    for field in review:
        assert not source_review_approved({key: value for key, value in review.items() if key != field})
    for field in SOURCE_REVIEW_CHECKS:
        assert not source_review_approved({**review, "checks": {**review["checks"], field: False}})
