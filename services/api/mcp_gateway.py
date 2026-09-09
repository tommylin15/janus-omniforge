"""Authenticated service-to-service client for the Cloud Run MCP Host."""

from __future__ import annotations

from hashlib import sha256
import hmac
import json
import os
import time
from typing import Any, Callable


class McpGatewayError(ValueError): pass


class McpGatewayClient:
    def __init__(self, url: str, signing_key: str, *, requester: Callable[..., Any] | None = None,
                 token_provider: Callable[[str], str] | None = None) -> None:
        if not url.startswith("https://") or len(signing_key) < 32:
            raise ValueError("MCP gateway URL or signing key is invalid")
        self.url, self.signing_key = url.rstrip("/"), signing_key.encode()
        self.requester, self.token_provider = requester, token_provider

    @classmethod
    def from_env(cls) -> "McpGatewayClient":
        return cls(os.getenv("MCP_GATEWAY_URL", ""), os.getenv("MCP_OWNER_SIGNING_KEY", ""))

    def discover(self, owner_id: Any, server_id: str, config_ref: str,
                 tool_grants: list[str] | None = None) -> dict[str, Any]:
        return self._post("discover", {"ownerId":str(owner_id), "serverId":server_id,
            "configRef":config_ref, "toolGrants":tool_grants or []})

    def disconnect(self, owner_id: Any, server_id: str) -> None:
        self._post("disconnect", {"ownerId":str(owner_id), "serverId":server_id})

    def destroy_codex_auth(self, owner_id: Any) -> None:
        self._post("auth:destroy", {"ownerId":str(owner_id)}, prefix="codex")

    def logout_codex_session(self, owner_id: Any) -> None:
        self._post("session:logout", {"ownerId":str(owner_id)}, prefix="codex")

    def start_codex_login(self, owner_id: Any) -> dict[str, Any]:
        return self._post("session:login-start", {"ownerId":str(owner_id)}, prefix="codex")

    def codex_login_status(self, owner_id: Any) -> dict[str, Any]:
        return self._post("session:login-status", {"ownerId":str(owner_id)}, prefix="codex")

    def dispatch_assistant_turn(self, owner_id: Any, *, thread_id: str, turn_id: str,
                                runtime: str, model: str, messages: list[dict[str, Any]],
                                continuation: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._post("turn", {"ownerId":str(owner_id), "threadId":thread_id, "turnId":turn_id,
            "runtime":runtime, "model":model, "messages":messages, "continuation":continuation or {}}, prefix="assistant")

    def _post(self, operation: str, payload: dict[str, Any], prefix: str = "mcp") -> dict[str, Any]:
        body=json.dumps(payload,separators=(",",":"),sort_keys=True).encode()
        timestamp=str(int(time.time()*1000))
        signature=hmac.new(self.signing_key,timestamp.encode()+b"."+body,sha256).hexdigest()
        if self.requester is None or self.token_provider is None:
            from google.auth.transport.requests import Request
            from google.oauth2.id_token import fetch_id_token
            import requests
            requester=self.requester or requests.post
            token_provider=self.token_provider or (lambda audience: fetch_id_token(Request(),audience))
        else:
            requester,token_provider=self.requester,self.token_provider
        try:
            response=requester(f"{self.url}/internal/v1/{prefix}/{operation}",data=body,timeout=65,
                headers={"Authorization":f"Bearer {token_provider(self.url)}","Content-Type":"application/json",
                         "X-Janus-Timestamp":timestamp,"X-Janus-Signature":f"v1={signature}"})
            if not response.ok: raise McpGatewayError(f"MCP gateway request failed ({response.status_code})")
            value=response.json()
        except McpGatewayError: raise
        except Exception: raise McpGatewayError("MCP gateway is unavailable") from None
        if not isinstance(value,dict): raise McpGatewayError("MCP gateway returned an invalid response")
        return value
