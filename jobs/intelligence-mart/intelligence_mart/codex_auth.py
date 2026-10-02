"""Serialize account refreshes and save credentials only in the approved dev Secret."""

from base64 import b64decode, b64encode
from contextlib import contextmanager
import json
import os
import re
from urllib.request import Request, urlopen

from .codex_worker import CodexCLIProvider


class SecretAuth:
    def __init__(self):
        project = os.environ.get("GCP_PROJECT_ID", "")
        if os.environ.get("MART_CODEX_AUTH_SECRET") != "janus-mart-codex-auth" or not re.fullmatch(r"[a-z][a-z0-9-]+", project):
            raise ValueError("only the approved Mart auth Secret is supported")
        self.resource = f"projects/{project}/secrets/janus-mart-codex-auth"
        self.version = None
        self.initial_version = None
        self.saved = ""
        self.reason = None
        self.rotations_saved = 0
        self.connection = None

    def _request(self, suffix, data=None):
        from ingestion_core.stage import GcsObjectStore
        token = GcsObjectStore(os.environ["MART_BUCKET"])._token()
        endpoint = self.resource + (suffix if suffix.startswith(":") else "/" + suffix)
        request = Request(f"https://secretmanager.googleapis.com/v1/{endpoint}",
                          data=json.dumps(data).encode() if data is not None else None,
                          headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        with urlopen(request, timeout=15) as response:
            return json.load(response)

    def load(self, version="latest"):
        response = self._request(f"versions/{version}:access")
        name = response["name"]
        project = self.resource.split("/")[1]
        if not re.fullmatch(r"projects/(?:" + re.escape(project) + r"|[0-9]+)/secrets/janus-mart-codex-auth/versions/[0-9]+", name):
            raise ValueError("unexpected auth Secret version")
        self.resource = name.rsplit("/versions/", 1)[0]  # API returns the canonical project number.
        raw = b64decode(response["payload"]["data"], validate=True).decode()
        os.environ.pop("CODEX_ACCESS_TOKEN", None)
        os.environ["MART_CODEX_AUTH_JSON"] = raw
        if CodexCLIProvider()._auth() != ("auth_cache", None):
            os.environ.pop("MART_CODEX_AUTH_JSON", None)
            raise ValueError("invalid ChatGPT auth cache")
        self.saved, self.version = raw, name
        if self.initial_version is None:
            self.initial_version = name

    def checkpoint(self):
        if self.reason:
            return self.reason
        try:
            if self.connection is not None:
                with self.connection.cursor() as cursor:
                    cursor.execute("SELECT 1")  # Stop if the account lock's session was lost.
        except Exception:
            self.reason = "auth_lock_lost"
            return self.reason
        raw = os.environ.get("MART_CODEX_AUTH_JSON", "")
        if raw == self.saved:
            return None
        if CodexCLIProvider()._auth() != ("auth_cache", None):
            self.reason = "invalid_refreshed_auth_cache"
            return self.reason
        try:
            # No blind retry: addVersion has no idempotency fence.
            created = self._request(":addVersion", {"payload": {"data": b64encode(raw.encode()).decode()}})
            name = created["name"]
            if not re.fullmatch(re.escape(self.resource) + r"/versions/[0-9]+", name):
                raise ValueError("unexpected auth Secret version")
            self.load(name.rsplit("/", 1)[1])
            if self.saved != raw:
                raise ValueError("auth Secret readback mismatch")
            self.rotations_saved += 1
        except Exception:
            self.reason = "auth_persistence_failed"
        return self.reason

    def metadata(self):
        return {"storage": "dedicated_secret", "initial_version": self.initial_version,
                "latest_version": self.version, "rotations_saved": self.rotations_saved,
                "status": "blocked" if self.reason else "ready", "reason": self.reason,
                "required_user_action": bool(self.reason)}


@contextmanager
def auth_session():
    """Hold a separate autocommit connection, never a transaction across model I/O."""
    import psycopg
    state = SecretAuth()
    os.environ.pop("CODEX_ACCESS_TOKEN", None)
    os.environ.pop("MART_CODEX_AUTH_JSON", None)
    settings = {key.lower(): os.environ[f"PUBLICATION_DB_{key}"] for key in ("HOST", "NAME", "USER", "PASSWORD")}
    with psycopg.connect(host=settings["host"], dbname=settings["name"], user=settings["user"],
                         password=settings["password"], autocommit=True, connect_timeout=5,
                         sslmode=os.environ.get("PUBLICATION_DB_SSLMODE", "require"),
                         options="-c statement_timeout=15000") as connection:
        state.connection = connection
        # ponytail: one account lock, use per-account keys if multiple accounts are approved.
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_try_advisory_lock(1835102836, 1)")
            locked = cursor.fetchone()[0]
        try:
            if not locked:
                state.reason = "auth_batch_busy"
            else:
                try:
                    state.load()
                except Exception:
                    state.reason = "auth_secret_unavailable"
            yield state
        finally:
            os.environ.pop("MART_CODEX_AUTH_JSON", None)
            if locked:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_advisory_unlock(1835102836, 1)")
