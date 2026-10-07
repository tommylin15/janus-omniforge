from uuid import UUID

import pytest

from ingestion_core.private_recalc_acceptance import run_private_recalc_acceptance


REQUEST = "11111111-1111-4111-8111-111111111111"


class Store:
    def __init__(self):
        self.calls = []

    def seed(self, request_id):
        self.calls.append(("seed", request_id))
        return {
            "component": "ingestion-core",
            "status": "succeeded",
            "operation": "private_recalc_acceptance_seed",
            "request_id": str(request_id),
            "requested_ledger_version": 164,
            "workers": 2,
            "duplicate_owner_guard": "passed",
        }

    def verify(self, request_id, execution):
        self.calls.append(("verify", request_id, execution))
        return {
            "component": "ingestion-core",
            "status": "succeeded",
            "operation": "private_recalc_acceptance_verify",
            "request_id": str(request_id),
            "requested_ledger_version": 164,
            "attempt_count": 1,
            "worker_task_index": 1,
            "worker_execution": execution,
        }

    def cleanup(self, request_id):
        self.calls.append(("cleanup", request_id))
        return {
            "component": "ingestion-core",
            "status": "succeeded",
            "operation": "private_recalc_acceptance_cleanup",
            "request_id": str(request_id),
            "active_request_failed": True,
        }


def test_acceptance_seed_is_bounded_and_does_not_expose_owner_content():
    store = Store()
    result = run_private_recalc_acceptance("seed", REQUEST, store=store)
    assert store.calls == [("seed", UUID(REQUEST))]
    assert result["workers"] == 2
    assert result["duplicate_owner_guard"] == "passed"
    rendered = repr(result).lower()
    assert "user_id" not in rendered
    assert "symbol" not in rendered
    assert "trade" not in rendered


def test_acceptance_verify_requires_expected_execution_and_returns_worker_evidence():
    store = Store()
    result = run_private_recalc_acceptance(
        "verify",
        REQUEST,
        expected_execution="janus-private-pipeline-canary",
        store=store,
    )
    assert result["attempt_count"] == 1
    assert result["worker_task_index"] == 1
    assert result["worker_execution"] == "janus-private-pipeline-canary"
    assert store.calls == [
        (
            "verify",
            UUID(REQUEST),
            "janus-private-pipeline-canary",
        )
    ]


def test_acceptance_cleanup_is_explicit_and_uuid_is_canonical():
    store = Store()
    result = run_private_recalc_acceptance("cleanup", REQUEST, store=store)
    assert result["active_request_failed"] is True
    with pytest.raises(ValueError):
        run_private_recalc_acceptance("seed", "not-a-uuid", store=store)
    with pytest.raises(ValueError):
        run_private_recalc_acceptance("unknown", REQUEST, store=store)
