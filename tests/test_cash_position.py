"""Owner-declared cash and asset valuation: independent of delayed PnL Mart."""
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from services.api.app import create_app
from services.api.models import CashPositionIn
from services.api.repository import ConflictError, PostgresWorkspaceRepository

OWNER = UUID("00000000-0000-0000-0000-000000000010")


class CashRepo:
    def __init__(self):
        self.balance = None
        self.version = 0
        self.calls = []
        self.saved = {}

    def resolve_user(self, sub, email):
        return OWNER

    def cash_position(self, owner):
        self.calls.append(("read", owner))
        return {"cash_status": "not_configured" if self.balance is None else "available",
                "cash_balance": self.balance, "cash_version": self.version,
                "currency": "TWD", "anchor_ledger_version": 35}

    def set_cash_position(self, owner, value, key):
        self.calls.append(("write", owner, key))
        if key in self.saved:
            if self.saved[key] != (value.amount, value.expected_version):
                raise ConflictError("idempotency mismatch")
            return self.cash_position(owner)
        if value.expected_version != self.version:
            raise ConflictError("version conflict")
        self.saved[key] = (value.amount, value.expected_version)
        self.balance = value.amount
        self.version += 1
        return self.cash_position(owner)


class Store:
    pass


def api_client():
    repo = CashRepo()
    claims = {"iss": "https://accounts.google.com", "aud": "user-client",
              "sub": "test-owner", "email": "test@example.com",
              "email_verified": True, "exp": 1900000000}
    api = create_app(repo, Store(), lambda _token, _audience: claims,
                     audience="user-client", private_recalculator=object())
    return TestClient(api, raise_server_exceptions=False), repo


def test_cash_balance_is_owner_scoped_explicit_and_can_be_reanchored():
    api, repo = api_client()
    endpoint = "/api/v1/me/cash-position"
    auth = {"Authorization": "Bearer user-token"}
    assert api.get(endpoint).status_code == 401
    assert api.put(endpoint, json={"amount": "2000", "expected_version": 0},
                   headers={"Idempotency-Key": "cash-00001"}).status_code == 401

    missing = api.get(endpoint, headers=auth)
    assert missing.status_code == 200
    assert missing.json()["cash_balance"] is None
    assert missing.json()["cash_status"] == "not_configured"

    payload = {"amount": "2000.5000", "expected_version": 0}
    created = api.put(endpoint, json=payload,
                      headers={**auth, "Idempotency-Key": "cash-00001"})
    assert created.status_code == 200, created.text
    assert Decimal(created.json()["cash_balance"]) == Decimal("2000.5000")
    assert created.json()["cash_version"] == 1
    replay = api.put(endpoint, json=payload,
                     headers={**auth, "Idempotency-Key": "cash-00001"})
    assert replay.status_code == 200
    conflict = api.put(endpoint, json={"amount": "5000", "expected_version": 0},
                       headers={**auth, "Idempotency-Key": "cash-00002"})
    assert conflict.status_code == 409
    # Human can simply overwrite current cash without explaining deposits.
    edited = api.put(endpoint, json={"amount": "800", "expected_version": 1},
                     headers={**auth, "Idempotency-Key": "cash-00003"})
    assert edited.status_code == 200 and edited.json()["cash_version"] == 2
    assert repo.calls[-1][1] == OWNER


def test_cash_rejects_forged_owner_nonfinite_or_overprecise_amounts():
    api, _ = api_client()
    endpoint = "/api/v1/me/cash-position"
    auth = {"Authorization": "Bearer user-token", "Idempotency-Key": "cash-00004"}
    for payload in (
        {"amount": "-1", "expected_version": 0},
        {"amount": "NaN", "expected_version": 0},
        {"amount": "1.00001", "expected_version": 0},
        {"amount": "100", "expected_version": 0, "user_id": str(OWNER)},
    ):
        assert api.put(endpoint, json=payload, headers=auth).status_code == 422
    with pytest.raises(ValidationError):
        CashPositionIn(amount=Decimal("1.99999"), expected_version=0)


class DbConnection:
    def __init__(self, checkpoint, delta, version=42):
        self.checkpoint = checkpoint
        self.delta = delta
        self.version = version
        self.queries = []

    def execute(self, statement, args):
        self.queries.append((statement, args))
        self.last = statement
        return self

    def fetchone(self):
        if "cash_balance_snapshots" in self.last:
            return self.checkpoint
        return {"delta": self.delta, "current_ledger_version": self.version}


def test_cash_snapshot_is_strict_ledger_anchor_and_trade_net_flow():
    time = datetime(2026, 10, 16, tzinfo=timezone.utc)
    connection = DbConnection({"version": 3, "amount": Decimal("100000"),
                               "anchor_ledger_version": 35, "updated_at": time},
                              delta=Decimal("-28920.50"))
    result = PostgresWorkspaceRepository._cash_position_in_tx(connection, OWNER)
    assert result["cash_balance"] == Decimal("71079.50")
    assert result["anchor_ledger_version"] == 35
    assert result["current_ledger_version"] == 42
    sql, args = connection.queries[-1]
    assert args == (35, OWNER)
    for guard in ("ledger_version > %s", "event_action='REVERSAL'",
                  "WHEN 'BUY'", "WHEN 'SELL'", "WHEN 'CASH_DIV'",
                  "COALESCE(fee,0)", "COALESCE(tax,0)", "currency='TWD'"):
        assert guard in sql
    missing = PostgresWorkspaceRepository._cash_position_in_tx(DbConnection(None, 0), OWNER)
    assert missing["cash_balance"] is None
    assert missing["cash_status"] == "not_configured"


def test_schema_is_immutable_owner_only_and_migration_ready():
    from pathlib import Path
    root = Path(__file__).parents[1]
    ddl = (root / "infra/postgres/migrations/062_owner_cash_balance_snapshots.sql").read_text()
    assert "user_id uuid NOT NULL," in ddl
    assert "REFERENCES private.users" not in ddl
    assert "PRIMARY KEY (user_id, version)" in ddl
    assert "UNIQUE (user_id, idempotency_key)" in ddl
    assert "GRANT SELECT, INSERT ON private.cash_balance_snapshots TO janus_private_api" in ddl
    assert "GRANT SELECT, DELETE ON private.cash_balance_snapshots TO janus_private_pipeline" in ddl
    assert "-- PHASE: acceptance" in ddl
    assert "062_owner_cash_balance_snapshots" in ddl


def test_owner_deletion_also_removes_cash_snapshots():
    from pathlib import Path
    root=Path(__file__).parents[1]
    code=(root / "services/api/repository.py").read_text()
    assert '"cash_balance_snapshots","current_positions","ledger_events","users"' in code
