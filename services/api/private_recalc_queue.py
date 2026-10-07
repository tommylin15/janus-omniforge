"""Owner-scoped Private Mart recalculation queue and Cloud Run dispatcher."""

from __future__ import annotations

import os
from typing import Any, Callable

from .private_pipeline import RecalculationCancelled


class PrivateRecalcTriggerError(RuntimeError):
    pass


class CloudRunPrivateRecalcTrigger:
    def __init__(
        self,
        project: str,
        region: str,
        job: str = "janus-private-pipeline",
        container: str = "janus-private-pipeline",
        *,
        post: Callable[..., Any] | None = None,
    ) -> None:
        if not project or not region or not job or not container:
            raise ValueError("private recalculation trigger configuration is incomplete")
        self.project = project
        self.region = region
        self.job = job
        self.container = container
        self._post = post

    @classmethod
    def from_env(cls) -> "CloudRunPrivateRecalcTrigger":
        return cls(
            os.getenv("GCP_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT") or "",
            os.getenv("GCP_REGION", "us-central1"),
            os.getenv("PRIVATE_PIPELINE_JOB", "janus-private-pipeline"),
            os.getenv("PRIVATE_PIPELINE_CONTAINER", "janus-private-pipeline"),
        )

    def _request(self, url: str, **kwargs: Any) -> Any:
        if self._post is not None:
            return self._post(url, **kwargs)
        import google.auth
        from google.auth.transport.requests import AuthorizedSession

        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        return AuthorizedSession(credentials).post(url, **kwargs)

    def start(self, workers: int) -> dict[str, Any]:
        if not 2 <= int(workers) <= 8:
            raise ValueError("private recalculation workers must be between 2 and 8")
        url = (
            f"https://run.googleapis.com/v2/projects/{self.project}/locations/"
            f"{self.region}/jobs/{self.job}:run"
        )
        payload = {
            "overrides": {
                "taskCount": int(workers),
                "containerOverrides": [{
                    "name": self.container,
                    "env": [{"name": "PRIVATE_RECALC_QUEUE_MODE", "value": "true"}],
                }],
            }
        }
        response = self._request(url, json=payload, timeout=10)
        if not 200 <= int(response.status_code) < 300:
            raise PrivateRecalcTriggerError(
                f"private recalculation trigger failed with status {response.status_code}"
            )
        body = response.json() if hasattr(response, "json") else {}
        return {"status": "dispatched", "operation": body.get("name") if isinstance(body, dict) else None}


class QueuedPrivateRecalculator:
    """Enqueue one owner and start at most one shared queue execution."""

    def __init__(
        self,
        repository: Any,
        worker_count: Callable[[], int],
        trigger: CloudRunPrivateRecalcTrigger,
    ) -> None:
        self.repository = repository
        self.worker_count = worker_count
        self.trigger = trigger

    def run_user(self, user_id: Any, trigger_source: str = "manual") -> dict[str, Any]:
        request = self.repository.enqueue_recalculation(user_id, trigger_source)
        if request.get("should_dispatch"):
            try:
                self.trigger.start(self.worker_count())
            except Exception as error:
                self.repository.fail_recalculation_dispatch(
                    request["request_id"],
                    type(error).__name__.upper()[:80],
                    "損益重算服務啟動失敗，可重新嘗試",
                )
                raise
        return {
            "request_id": request["request_id"],
            "status": request["status"],
            "requested_ledger_version": request["requested_ledger_version"],
            "already_active": bool(request.get("already_active")),
        }


def run_queue_worker(repository: Any, pipeline: Any) -> dict[str, int]:
    """Drain owner requests on one Cloud Run task; claims are SKIP LOCKED."""
    execution = os.getenv("CLOUD_RUN_EXECUTION") or None
    task_index = int(os.getenv("CLOUD_RUN_TASK_INDEX", "0"))
    processed = succeeded = failed = cancelled = 0

    while True:
        request = repository.claim_recalculation(execution, task_index)
        if request is None:
            repository.release_recalculation_dispatch_if_idle()
            break

        processed += 1
        request_id = request["request_id"]
        lease = request["lease_token"]

        def stop() -> bool:
            repository.heartbeat_recalculation(request_id, lease)
            return repository.recalculation_should_stop(request_id, lease)

        try:
            computed = pipeline.run_user(
                request["user_id"],
                stop=stop,
                write_guard=repository.private_mart_write_lock,
            )
            result = repository.finish_recalculation(
                request_id,
                lease,
                succeeded=True,
                processed_ledger_version=int(computed["ledger_version"]),
            )
            if result and result.get("status") == "SUCCEEDED":
                succeeded += 1
            elif result and result.get("status") == "CANCELLED":
                cancelled += 1
        except RecalculationCancelled:
            result = repository.finish_recalculation(
                request_id,
                lease,
                succeeded=False,
                error_code="CANCELLED",
                safe_message="管理員已中止本次重算",
            )
            if result and result.get("status") == "CANCELLED":
                cancelled += 1
        except Exception as error:
            repository.finish_recalculation(
                request_id,
                lease,
                succeeded=False,
                error_code=type(error).__name__.upper()[:80],
                safe_message="損益重算執行失敗；已停止本次工作，可重新嘗試",
            )
            failed += 1

    return {
        "processed": processed,
        "succeeded": succeeded,
        "failed": failed,
        "cancelled": cancelled,
    }
