"""Small OAuth authorization facade for the external Janus MCP resource."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from hashlib import sha256
import hmac
import html
import json
import os
import secrets
import time
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Protocol
from urllib.parse import urlencode, urlsplit
from urllib.request import Request as UrlRequest, urlopen

from fastapi import HTTPException, Request, Response, status

from .auth import GOOGLE_ISSUERS


MCP_CLIENT_ID = "https://chatgpt.com/oauth/client.json"
MCP_REDIRECT_URI = "https://chatgpt.com/connector_platform_oauth_redirect"
MCP_SCOPES = frozenset({"janus.sources.read", "janus.market.read", "janus.private.read", "offline_access"})
_GOOGLE_AUTHORIZE = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"


class OAuthCodeStore(Protocol):
    def create(self, code_hash: str, value: Mapping[str, Any], expires_at: int) -> None: ...
    def consume(self, code_hash: str, now: int) -> Mapping[str, Any] | None: ...
    def create_refresh(self, token_hash: str, value: Mapping[str, Any], expires_at: int) -> None: ...
    def rotate_refresh(self, old_hash: str, new_hash: str, client_id: str, resource: str,
                       now: int, expires_at: int) -> Mapping[str, Any] | None: ...
    def revoke_refresh(self, token_hash: str, client_id: str) -> None: ...


@dataclass(frozen=True)
class OAuthSettings:
    issuer: str
    resource: str
    google_client_id: str
    google_client_secret: str
    signing_key: bytes
    allowed_emails: frozenset[str]
    authorization_ttl: int = 600
    access_ttl: int = 900
    refresh_ttl: int = 90 * 24 * 60 * 60

    @classmethod
    def from_env(cls) -> "OAuthSettings":
        values = {name: os.getenv(name, "").strip() for name in (
            "MCP_OAUTH_ISSUER", "MCP_RESOURCE_URL", "GOOGLE_USER_CLIENT_ID",
            "GOOGLE_USER_CLIENT_SECRET", "MCP_OAUTH_SIGNING_KEY",
        )}
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise ValueError(f"MCP OAuth configuration missing: {','.join(missing)}")
        for name in ("MCP_OAUTH_ISSUER", "MCP_RESOURCE_URL"):
            parsed = urlsplit(values[name])
            if parsed.scheme != "https" or not parsed.netloc or parsed.query or parsed.fragment:
                raise ValueError(f"{name} must be an HTTPS URL without query or fragment")
        emails = frozenset(value.strip().lower() for value in os.getenv("GOOGLE_USER_ALLOWED_EMAILS", "").split(",") if value.strip())
        if not emails:
            raise ValueError("GOOGLE_USER_ALLOWED_EMAILS is required for MCP OAuth")
        key = values["MCP_OAUTH_SIGNING_KEY"].encode("utf-8")
        if len(key) < 32:
            raise ValueError("MCP_OAUTH_SIGNING_KEY must be at least 32 bytes")
        return cls(values["MCP_OAUTH_ISSUER"].rstrip("/"), values["MCP_RESOURCE_URL"].rstrip("/"),
                   values["GOOGLE_USER_CLIENT_ID"], values["GOOGLE_USER_CLIENT_SECRET"], key, emails)


class InMemoryOAuthCodeStore:
    """Test-only store; production uses the PostgreSQL implementation."""

    def __init__(self) -> None:
        self._items: dict[str, tuple[dict[str, Any], int, bool]] = {}
        self._refresh: dict[str, tuple[dict[str, Any], int]] = {}

    def create(self, code_hash: str, value: Mapping[str, Any], expires_at: int) -> None:
        self._items[code_hash] = (dict(value), expires_at, False)

    def consume(self, code_hash: str, now: int) -> Mapping[str, Any] | None:
        item = self._items.get(code_hash)
        if item is None or item[1] <= now or item[2]:
            return None
        self._items[code_hash] = (item[0], item[1], True)
        return dict(item[0])

    def create_refresh(self, token_hash: str, value: Mapping[str, Any], expires_at: int) -> None:
        self._refresh[token_hash] = (dict(value), expires_at)

    def rotate_refresh(self, old_hash: str, new_hash: str, client_id: str, resource: str,
                       now: int, expires_at: int) -> Mapping[str, Any] | None:
        item = self._refresh.pop(old_hash, None)
        if item is None or item[1] <= now or item[0]["client_id"] != client_id or item[0]["resource"] != resource:
            if item is not None:
                self._refresh[old_hash] = item
            return None
        self._refresh[new_hash] = (item[0], expires_at)
        return dict(item[0])

    def revoke_refresh(self, token_hash: str, client_id: str) -> None:
        item = self._refresh.get(token_hash)
        if item is not None and item[0]["client_id"] == client_id:
            del self._refresh[token_hash]


class RepositoryOAuthCodeStore:
    def __init__(self, repository: Any) -> None:
        self.repository = repository

    def create(self, code_hash: str, value: Mapping[str, Any], expires_at: int) -> None:
        self.repository.create_mcp_oauth_code(code_hash, dict(value), expires_at)

    def consume(self, code_hash: str, now: int) -> Mapping[str, Any] | None:
        return self.repository.consume_mcp_oauth_code(code_hash, now)

    def create_refresh(self, token_hash: str, value: Mapping[str, Any], expires_at: int) -> None:
        self.repository.create_mcp_oauth_refresh_token(token_hash, dict(value), expires_at)

    def rotate_refresh(self, old_hash: str, new_hash: str, client_id: str, resource: str,
                       now: int, expires_at: int) -> Mapping[str, Any] | None:
        return self.repository.rotate_mcp_oauth_refresh_token(
            old_hash, new_hash, client_id, resource, now, expires_at)

    def revoke_refresh(self, token_hash: str, client_id: str) -> None:
        self.repository.revoke_mcp_oauth_refresh_token(token_hash, client_id)


class McpOAuth:
    def __init__(
        self,
        settings: OAuthSettings,
        code_store: OAuthCodeStore,
        resolve_user: Callable[[str, str], Any],
        *,
        clock: Callable[[], float] = time.time,
        google_exchange: Callable[[str, str], Mapping[str, Any]] | None = None,
        google_verify: Callable[[str, str], Mapping[str, Any]] | None = None,
    ) -> None:
        self.settings = settings
        self.code_store = code_store
        self.resolve_user = resolve_user
        self.clock = clock
        self.google_exchange = google_exchange or self._exchange_google_code
        self.google_verify = google_verify or self._verify_google_token

    def protected_resource_metadata(self) -> dict[str, Any]:
        return {
            "resource": self.settings.resource,
            "authorization_servers": [self.settings.issuer],
            "scopes_supported": sorted(MCP_SCOPES),
        }

    def authorization_server_metadata(self) -> dict[str, Any]:
        base = self.settings.issuer
        return {
            "issuer": base,
            "authorization_response_iss_parameter_supported": True,
            "authorization_endpoint": f"{base}/oauth/authorize",
            "token_endpoint": f"{base}/oauth/token",
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "revocation_endpoint": f"{base}/oauth/revoke",
            "revocation_endpoint_auth_methods_supported": ["none"],
            "client_id_metadata_document_supported": True,
            "token_endpoint_auth_methods_supported": ["none"],
            "code_challenge_methods_supported": ["S256"],
            "scopes_supported": sorted(MCP_SCOPES),
        }

    def begin_authorization(self, params: Mapping[str, str]) -> Response:
        client_id = params.get("client_id", "")
        redirect_uri = params.get("redirect_uri", "")
        scope = " ".join(dict.fromkeys((*self._scope(params.get("scope", "")).split(), "offline_access")))
        if params.get("response_type") != "code":
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "response_type must be code")
        if not params.get("state"):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "state is required")
        if not self._valid_client(client_id) or not self._valid_redirect(redirect_uri):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "OAuth client or redirect URI is not allowed")
        if params.get("resource") != self.settings.resource:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "resource is required")
        challenge = params.get("code_challenge", "")
        if params.get("code_challenge_method") != "S256" or not self._valid_challenge(challenge):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "S256 PKCE code challenge is required")
        state = self._sign({
            "kind": "google", "client_id": client_id, "redirect_uri": redirect_uri,
            "resource": self.settings.resource, "scope": scope, "challenge": challenge,
            "state": params.get("state", ""), "exp": self._now() + self.settings.authorization_ttl,
            "nonce": secrets.token_urlsafe(24),
        })
        query = urlencode({
            "client_id": self.settings.google_client_id,
            "redirect_uri": f"{self.settings.issuer}/oauth/google/callback",
            "response_type": "code", "scope": "openid email", "access_type": "online",
            "prompt": "select_account", "state": state,
        })
        return Response(status_code=status.HTTP_302_FOUND, headers={"Location": f"{_GOOGLE_AUTHORIZE}?{query}"})

    def google_callback(self, query: Mapping[str, str]) -> Response:
        state = self._unsigned(query.get("state", ""), "google")
        if query.get("error"):
            return self._client_error(state, query["error"])
        code = query.get("code", "")
        if not code:
            return self._client_error(state, "invalid_request")
        try:
            tokens = dict(self.google_exchange(code, f"{self.settings.issuer}/oauth/google/callback"))
            claims = dict(self.google_verify(str(tokens.get("id_token", "")), self.settings.google_client_id))
            if str(claims.get("iss", "")) not in GOOGLE_ISSUERS or claims.get("email_verified") is not True:
                raise ValueError("unverified Google identity")
            if int(claims.get("exp", 0)) <= self._now():
                raise ValueError("expired Google identity")
            subject, email = str(claims.get("sub", "")).strip(), str(claims.get("email", "")).strip().lower()
            if not subject or email not in self.settings.allowed_emails:
                raise ValueError("Google account is not allowed")
            state = dict(state)
            state["user_id"] = str(self.resolve_user(subject, email))
            state["email"] = email
            state["exp"] = self._now() + self.settings.authorization_ttl
            return Response(content=self._consent_page(self._sign(state)), media_type="text/html", headers={
                "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
                "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; form-action 'self' https://chatgpt.com; base-uri 'none'",
            })
        except Exception:
            return self._client_error(state, "access_denied")

    def complete_authorization(self, token: str, approved: bool) -> Response:
        state = self._unsigned(token, "google")
        if not approved:
            return self._client_error(state, "access_denied")
        code = secrets.token_urlsafe(48)
        expires = self._now() + self.settings.authorization_ttl
        self.code_store.create(self._hash(code), {
            "user_id": state["user_id"], "client_id": state["client_id"],
            "redirect_uri": state["redirect_uri"], "resource": state["resource"],
            "scope": state["scope"], "challenge": state["challenge"],
        }, expires)
        query = {"code": code, "state": state.get("state", ""), "iss": self.settings.issuer}
        return Response(status_code=status.HTTP_302_FOUND, headers={"Location": f"{state['redirect_uri']}?{urlencode(query)}"})

    def exchange_token(self, form: Mapping[str, str]) -> dict[str, Any]:
        if not self._valid_client(form.get("client_id", "")):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "OAuth client is not allowed")
        grant_type = form.get("grant_type")
        if grant_type == "authorization_code" and not self._valid_redirect(form.get("redirect_uri", "")):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "OAuth redirect URI is not allowed")
        if form.get("resource") != self.settings.resource:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "resource is required")
        now = self._now()
        if grant_type == "authorization_code":
            code = form.get("code", "")
            record = self.code_store.consume(self._hash(code), now) if code else None
            if not record or any(record.get(name) != form.get(name) for name in ("client_id", "redirect_uri", "resource")):
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid authorization code")
            verifier = form.get("code_verifier", "")
            challenge = self._pkce(verifier)
            if not verifier or not hmac.compare_digest(challenge, str(record.get("code_challenge", record.get("challenge", "")))):
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid PKCE verifier")
            refresh_token = None
            if "offline_access" in str(record["scope"]).split():
                refresh_token = secrets.token_urlsafe(48)
                self.code_store.create_refresh(self._hash(refresh_token), {
                    "user_id": record["user_id"], "client_id": record["client_id"],
                    "resource": record["resource"], "scope": record["scope"],
                }, now + self.settings.refresh_ttl)
        elif grant_type == "refresh_token":
            presented = form.get("refresh_token", "")
            replacement = secrets.token_urlsafe(48)
            record = self.code_store.rotate_refresh(
                self._hash(presented), self._hash(replacement), form["client_id"], form["resource"],
                now, now + self.settings.refresh_ttl) if presented else None
            if not record:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid refresh token")
            refresh_token = replacement
        else:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "unsupported grant_type")
        payload = {"iss": self.settings.issuer, "sub": str(record["user_id"]), "aud": self.settings.resource,
                   "scope": str(record["scope"]), "iat": now, "exp": now + self.settings.access_ttl,
                   "jti": secrets.token_urlsafe(18)}
        result = {"access_token": self._sign(payload), "token_type": "Bearer", "expires_in": self.settings.access_ttl,
                  "scope": payload["scope"]}
        if refresh_token:
            result["refresh_token"] = refresh_token
        return result

    def revoke_token(self, form: Mapping[str, str]) -> None:
        client_id = form.get("client_id", "")
        if not self._valid_client(client_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "OAuth client is not allowed")
        token = form.get("token", "")
        if token and form.get("token_type_hint", "refresh_token") == "refresh_token":
            self.code_store.revoke_refresh(self._hash(token), client_id)

    def verify_access_token(self, token: str, required_scope: str) -> Mapping[str, Any]:
        payload = self._unsigned(token, "access")
        if payload.get("iss") != self.settings.issuer or payload.get("aud") != self.settings.resource:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid MCP access token")
        if int(payload.get("exp", 0)) <= self._now() or required_scope not in str(payload.get("scope", "")).split():
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "insufficient MCP scope")
        if not str(payload.get("sub", "")):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid MCP subject")
        return payload

    def _client_error(self, state: Mapping[str, Any], error: str) -> Response:
        params = {"error": error, "state": state.get("state", ""), "iss": self.settings.issuer}
        return Response(status_code=status.HTTP_302_FOUND, headers={"Location": f"{state['redirect_uri']}?{urlencode(params)}"})

    def _consent_page(self, token: str) -> str:
        safe = html.escape(token, quote=True)
        return f"<!doctype html><meta charset='utf-8'><title>Janus MCP authorization</title><main><h1>Janus MCP authorization</h1><p>允許 ChatGPT 讀取已核准的 Janus 市場與私人資料，並在短效存取憑證到期後自動續期？此授權閒置 90 天後失效；你可隨時在 ChatGPT 解除連結或撤銷。</p><form method='post' action='/oauth/authorize/complete'><input type='hidden' name='token' value='{safe}'><button name='approved' value='true'>允許</button><button name='approved' value='false'>拒絕</button></form></main>"

    def _sign(self, payload: Mapping[str, Any]) -> str:
        encoded = self._b64(json.dumps(dict(payload), separators=(",", ":"), sort_keys=True).encode())
        signature = self._b64(hmac.new(self.settings.signing_key, encoded.encode(), sha256).digest())
        return f"{encoded}.{signature}"

    def _unsigned(self, token: str, kind: str) -> dict[str, Any]:
        try:
            encoded, supplied = token.rsplit(".", 1)
            expected = self._b64(hmac.new(self.settings.signing_key, encoded.encode(), sha256).digest())
            payload = json.loads(self._unb64(encoded))
            if not hmac.compare_digest(supplied, expected) or not isinstance(payload, dict) or int(payload.get("exp", 0)) <= self._now():
                raise ValueError("invalid signed token")
            if kind == "google" and payload.get("kind") != "google":
                raise ValueError("invalid state")
            if kind == "access" and payload.get("iss") != self.settings.issuer:
                raise ValueError("invalid access token")
            return payload
        except Exception as error:
            raise HTTPException(status.HTTP_400_BAD_REQUEST if kind == "google" else status.HTTP_401_UNAUTHORIZED, "invalid OAuth token") from error

    def _exchange_google_code(self, code: str, redirect_uri: str) -> Mapping[str, Any]:
        body = urlencode({"code": code, "client_id": self.settings.google_client_id, "client_secret": self.settings.google_client_secret,
                          "redirect_uri": redirect_uri, "grant_type": "authorization_code"}).encode()
        request = UrlRequest(_GOOGLE_TOKEN, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
        with urlopen(request, timeout=10) as response:
            return json.loads(response.read(16 * 1024))

    @staticmethod
    def _verify_google_token(token: str, audience: str) -> Mapping[str, Any]:
        from google.auth.transport import requests
        from google.oauth2 import id_token
        return id_token.verify_oauth2_token(token, requests.Request(), audience)

    def _scope(self, raw: str) -> str:
        values = tuple(dict.fromkeys(raw.split()))
        if not values or any(value not in MCP_SCOPES for value in values):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "scope is not allowlisted")
        return " ".join(values)

    @staticmethod
    def _valid_client(value: str) -> bool:
        return value == MCP_CLIENT_ID or (value.startswith("https://chatgpt.com/oauth/") and value.endswith("/client.json"))

    @staticmethod
    def _valid_redirect(value: str) -> bool:
        return value == MCP_REDIRECT_URI or (value.startswith("https://chatgpt.com/connector/oauth/") and "?" not in value and "#" not in value)

    @staticmethod
    def _valid_challenge(value: str) -> bool:
        return 43 <= len(value) <= 128 and all(char.isalnum() or char in "-_" for char in value)

    @staticmethod
    def _pkce(verifier: str) -> str:
        return McpOAuth._b64(sha256(verifier.encode()).digest())

    def _now(self) -> int:
        return int(self.clock())

    @staticmethod
    def _hash(value: str) -> str:
        return sha256(value.encode()).hexdigest()

    @staticmethod
    def _b64(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).rstrip(b"=").decode()

    @staticmethod
    def _unb64(value: str) -> bytes:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def parse_form(request: Request, body: bytes) -> dict[str, str]:
    from urllib.parse import parse_qs
    values = parse_qs(body.decode("utf-8"), keep_blank_values=True)
    return {key: items[0] for key, items in values.items() if items}
