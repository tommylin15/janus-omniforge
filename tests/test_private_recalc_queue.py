from __future__ import annotations

from contextlib import contextmanager
from uuid import UUID, uuid4

from services.api.private_recalc_queue import (
    CloudRunPrivateRecalcTrigger,
    QueuedPrivateRecalculator,
    run_queue_worker,
)


USER = UUID("00000000-0000-0000-0000-000000000001")


def test_cloud_run_trigger_uses_bounded_parallel_tasks_without_owner_payload():
    calls = []

    class Response:
        status_code = 200
        def json(self):
            return {"name": "operations/recalc-1"}

    def post(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    trigger = CloudRunPrivateRecalcTrigger(
        "janus-dev", "us-central1", post=post
    )
    result = trigger.start(4)

    assert result["status"] == "dispatched"
    payload = calls[0][1]["json"]
    assert payload["overrides"]["taskCount"] == 4
    assert payload["overrides"]["containerOverrides"][0]["env"] == [
        {"name": "PRIVATE_RECALC_QUEUE_MODE", "value": "true"}
    ]
    assert str(USER) not in repr(calls)


def test_same_owner_active_request_is_not_dispatched_twice():
    class Repository:
        def __init__(self):
            self.calls = 0
        def enqueue_recalculation(self, user_id, trigger_source):
            self.calls += 1
            return {
                "request_id": uuid4(),
                "user_id": user_id,
                "requested_ledger_version": 9,
                "status": "RUNNING" if self.calls > 1 else "QUEUED",
                "should_dispatch": self.calls == 1,
                "already_active": self.calls > 1,
            }
        def fail_recalculation_dispatch(self, *_args):
            raise AssertionError("dispatch should not fail")

    class Trigger:
        def __init__(self):
            self.calls = []
        def start(self, workers):
            self.calls.append(workers)
            return {"status": "dispatched"}

    repository = Repository()
    trigger = Trigger()
    service = QueuedPrivateRecalculator(repository, lambda: 3, trigger)

    first = service.run_user(USER, "manual")
    second = service.run_user(USER, "manual")

    assert first["status"] == "QUEUED"
    assert second["status"] == "RUNNING"
    assert second["already_active"] is True
    assert trigger.calls == [3]


def test_queue_worker_claims_multiple_owners_but_serializes_write_guard(monkeypatch):
    monkeypatch.setenv("CLOUD_RUN_EXECUTION", "exec-1")
    monkeypatch.setenv("CLOUD_RUN_TASK_INDEX", "1")
    requests = [
        {
            "request_id": uuid4(),
            "lease_token": uuid4(),
            "user_id": USER,
        },
        {
            "request_id": uuid4(),
            "lease_token": uuid4(),
            "user_id": UUID("00000000-0000-0000-0000-000000000002"),
        },
    ]

    class Repository:
        def __init__(self):
            self.finished = []
            self.lock_depth = 0
            self.claim_meta = []
        def claim_recalculation(self, execution, task_index):
            self.claim_meta.append((execution, task_index))
            return requests.pop(0) if requests else None
        def heartbeat_recalculation(self, _request_id, _lease):
            return None
        def recalculation_should_stop(self, _request_id, _lease):
            return False
        @contextmanager
        def private_mart_write_lock(self):
            assert self.lock_depth == 0
            self.lock_depth += 1
            try:
                yield
            finally:
                self.lock_depth -= 1
        def finish_recalculation(self, request_id, lease, **kwargs):
            self.finished.append((request_id, lease, kwargs))
            assert kwargs["processed_ledger_version"] == 1
            return {"status": "SUCCEEDED"}
        def release_recalculation_dispatch_if_idle(self):
            return True

    class Pipeline:
        def __init__(self, repository):
            self.repository = repository
            self.users = []
        def run_user(self, user_id, *, stop, write_guard):
            self.users.append(user_id)
            assert stop() is False
            with write_guard():
                assert self.repository.lock_depth == 1
            return {"status": "updated", "ledger_version": 1}

    repository = Repository()
    pipeline = Pipeline(repository)
    result = run_queue_worker(repository, pipeline)

    assert result == {"processed": 2, "succeeded": 2, "failed": 0, "cancelled": 0}
    assert pipeline.users == [
        USER,
        UUID("00000000-0000-0000-0000-000000000002"),
    ]
    assert repository.claim_meta[0] == ("exec-1", 1)
