"""Minimal Cloud Scheduler reconciliation using the Cloud Run service identity."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class CloudSchedulerSync:
    def __init__(self, project: str, location: str, job: str, *, timezone: str = "Asia/Taipei", timeout: int = 10) -> None:
        values = (project, location, job)
        if any(not re.fullmatch(r"[A-Za-z0-9._:-]+", value) for value in values):
            raise ValueError("scheduler resource name is invalid")
        self.name = f"projects/{project}/locations/{location}/jobs/{job}"
        self.timezone = timezone
        self.timeout = timeout

    def __call__(self, value: dict[str, Any]) -> dict[str, str]:
        hour, minute = value["time"].split(":")
        cron = f"{int(minute)} {int(hour)} * * *"
        current = self._request("GET", f"{self._url()}?fields=state")
        updated = self._request(
            "PATCH", f"{self._url()}?updateMask=schedule,timeZone",
            {"name": self.name, "schedule": cron, "timeZone": self.timezone},
        )
        if updated.get("state") == "UPDATE_FAILED":
            updated = self._request(
                "PATCH", f"{self._url()}?updateMask=schedule,timeZone",
                {"name": self.name, "schedule": cron, "timeZone": self.timezone},
            )
        state = updated.get("state", current.get("state"))
        if value.get("enabled", True) and state == "PAUSED":
            state = self._request("POST", f"{self._url()}:resume", {}).get("state", "ENABLED")
        elif not value.get("enabled", True) and state == "ENABLED":
            state = self._request("POST", f"{self._url()}:pause", {}).get("state", "PAUSED")
        expected = "ENABLED" if value.get("enabled", True) else "PAUSED"
        if state != expected:
            raise RuntimeError("Cloud Scheduler did not reach the requested state")
        return {"name": self.name, "schedule": cron, "time_zone": self.timezone, "state": state}

    def _url(self) -> str:
        return f"https://cloudscheduler.googleapis.com/v1/{self.name}"

    def _request(self, method: str, url: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        token_request = Request(
            "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token",
            headers={"Metadata-Flavor": "Google"},
        )
        try:
            with urlopen(token_request, timeout=self.timeout) as response:
                token = json.load(response)["access_token"]
            data = None if body is None else json.dumps(body).encode("utf-8")
            request = Request(url, data=data, method=method, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
            with urlopen(request, timeout=self.timeout) as response:
                return json.load(response)
        except (HTTPError, URLError, KeyError, ValueError) as error:
            raise RuntimeError("Cloud Scheduler sync failed") from error
