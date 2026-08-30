"""Google Sign-In protection for the externally reachable Web service."""

from __future__ import annotations

import base64
from http.cookies import SimpleCookie
import hashlib
import hmac
import html
import json
import logging
import os
import time
from typing import Any, Callable, Mapping
from urllib.parse import parse_qs, urlsplit


LOGGER = logging.getLogger(__name__)
SESSION_COOKIE = "__Host-janus_session"
MAX_LOGIN_BYTES = 16 * 1024


class AuthConfigurationError(RuntimeError):
    """Raised when authentication is required but incompletely configured."""


class GoogleAuthMiddleware:
    """Verify Google ID tokens once, then use a short-lived signed session."""

    def __init__(
        self,
        app: Callable[..., Any],
        *,
        client_id: str,
        session_secret: str,
        allowed_emails: frozenset[str],
        public_base_url: str,
        verifier: Callable[[str, str], Mapping[str, Any]] | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if not client_id.strip():
            raise AuthConfigurationError("GOOGLE_CLIENT_ID is required")
        normalized_secret = session_secret.strip()
        if len(normalized_secret.encode("utf-8")) < 32:
            raise AuthConfigurationError("JANUS_SESSION_SECRET must be at least 32 bytes")
        if not allowed_emails:
            raise AuthConfigurationError("GOOGLE_ALLOWED_EMAILS is required")
        base = public_base_url.strip().rstrip("/")
        parsed = urlsplit(base)
        if parsed.scheme != "https" or not parsed.netloc or parsed.path:
            raise AuthConfigurationError("PUBLIC_BASE_URL must be an HTTPS origin")
        self.app = app
        self.client_id = client_id.strip()
        self.session_secret = normalized_secret.encode("utf-8")
        self.allowed_emails = frozenset(email.strip().lower() for email in allowed_emails)
        self.public_base_url = base
        self.verifier = verifier or self._verify_google_token
        self.clock = clock

    def __call__(self, environ: dict[str, Any], start_response: Callable[..., Any]):
        path = urlsplit(environ.get("PATH_INFO", "/")).path.rstrip("/") or "/"
        method = environ.get("REQUEST_METHOD", "GET").upper()

        if path == "/health":
            return self.app(environ, self._secure_start_response(start_response))
        if path == "/login" and method == "GET":
            session = self._session(environ)
            if session is not None:
                return self._redirect(start_response, "/admin/stocks")
            return self._html(start_response, self._login_page())
        if path == "/auth/google" and method == "POST":
            return self._google_callback(environ, start_response)
        session = self._session(environ)
        if session is None:
            if path.startswith("/api/"):
                return self._json(start_response, {"error": "authentication required"}, "401 Unauthorized")
            return self._redirect(start_response, "/login")
        if path == "/logout" and method == "POST":
            return self._redirect(start_response, "/login", clear_cookie=True)
        environ["JANUS_AUTH_EMAIL"] = session["email"]
        environ["JANUS_AUTH_SUB"] = session["sub"]
        return self.app(environ, self._secure_start_response(start_response))

    def _google_callback(self, environ: dict[str, Any], start_response: Callable[..., Any]):
        try:
            form = self._request_form(environ)
            csrf_cookie = self._cookie(environ, "g_csrf_token")
            csrf_body = form.get("g_csrf_token", [""])[0]
            if not csrf_cookie or not csrf_body or not hmac.compare_digest(csrf_cookie, csrf_body):
                return self._json(start_response, {"error": "invalid login request"}, "400 Bad Request")
            credential = form.get("credential", [""])[0]
            if not credential:
                return self._json(start_response, {"error": "missing Google credential"}, "400 Bad Request")
            claims = dict(self.verifier(credential, self.client_id))
            email = str(claims.get("email", "")).strip().lower()
            subject = str(claims.get("sub", "")).strip()
            if claims.get("email_verified") is not True or not subject:
                return self._json(start_response, {"error": "Google account is not verified"}, "403 Forbidden")
            if email not in self.allowed_emails:
                return self._json(start_response, {"error": "account is not allowed"}, "403 Forbidden")
            google_expiry = int(claims.get("exp", 0))
            expiry = min(google_expiry, int(self.clock()) + 3600)
            if expiry <= int(self.clock()):
                return self._json(start_response, {"error": "Google credential has expired"}, "401 Unauthorized")
            session = self._encode_session({"email": email, "sub": subject, "exp": expiry})
            return self._redirect(start_response, "/admin/stocks", session=session, max_age=expiry - int(self.clock()))
        except ValueError:
            return self._json(start_response, {"error": "invalid Google credential"}, "401 Unauthorized")
        except Exception as error:  # Keep network/library details out of the response and logs.
            LOGGER.warning("Google authentication unavailable: %s", type(error).__name__)
            return self._json(start_response, {"error": "authentication unavailable"}, "503 Service Unavailable")

    @staticmethod
    def _verify_google_token(token: str, client_id: str) -> Mapping[str, Any]:
        from google.auth.transport import requests
        from google.oauth2 import id_token

        return id_token.verify_oauth2_token(token, requests.Request(), client_id)

    @staticmethod
    def _request_form(environ: dict[str, Any]) -> dict[str, list[str]]:
        if not environ.get("CONTENT_TYPE", "").lower().startswith("application/x-www-form-urlencoded"):
            raise ValueError("login request must be form encoded")
        length = int(environ.get("CONTENT_LENGTH") or 0)
        if length <= 0 or length > MAX_LOGIN_BYTES:
            raise ValueError("login request size is invalid")
        stream = environ.get("wsgi.input")
        if stream is None:
            raise ValueError("login request body is unavailable")
        return parse_qs(stream.read(length).decode("utf-8"), keep_blank_values=True)

    def _session(self, environ: dict[str, Any]) -> dict[str, Any] | None:
        value = self._cookie(environ, SESSION_COOKIE)
        if not value:
            return None
        try:
            encoded, supplied = value.rsplit(".", 1)
            expected = self._b64(hmac.new(self.session_secret, encoded.encode("ascii"), hashlib.sha256).digest())
            if not hmac.compare_digest(supplied, expected):
                return None
            payload = json.loads(self._unb64(encoded).decode("utf-8"))
            email = str(payload.get("email", "")).lower()
            if email not in self.allowed_emails or int(payload.get("exp", 0)) <= int(self.clock()):
                return None
            if not str(payload.get("sub", "")):
                return None
            return payload
        except (ValueError, TypeError, json.JSONDecodeError):
            return None

    def _encode_session(self, payload: dict[str, Any]) -> str:
        encoded = self._b64(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
        signature = self._b64(hmac.new(self.session_secret, encoded.encode("ascii"), hashlib.sha256).digest())
        return f"{encoded}.{signature}"

    @staticmethod
    def _cookie(environ: dict[str, Any], name: str) -> str | None:
        cookie = SimpleCookie()
        try:
            cookie.load(environ.get("HTTP_COOKIE", ""))
        except Exception:
            return None
        morsel = cookie.get(name)
        return morsel.value if morsel else None

    @staticmethod
    def _b64(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")

    @staticmethod
    def _unb64(value: str) -> bytes:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))

    def _login_page(self) -> str:
        client_id = html.escape(self.client_id, quote=True)
        login_uri = html.escape(f"{self.public_base_url}/auth/google", quote=True)
        return f"""<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Janus Admin 登入</title><script src="https://accounts.google.com/gsi/client" async defer></script>
<style>html{{color-scheme:dark}}body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#07101d;color:#edf5ff;font-family:system-ui,sans-serif}}main{{width:min(28rem,calc(100% - 2rem));padding:2rem;border:1px solid #263950;border-radius:18px;background:#0d1929;box-shadow:0 24px 70px #0008}}.brand{{letter-spacing:.18em;color:#63d3ff;font-weight:700}}h1{{margin:.8rem 0}}p{{color:#a9b9ca;line-height:1.6}}.signin{{margin-top:1.5rem;min-height:44px}}</style></head>
<body><main><div class="brand">JANUS</div><h1>Data Operations</h1><p>請使用已授權的 Google 帳號登入。</p>
<div id="g_id_onload" data-client_id="{client_id}" data-login_uri="{login_uri}" data-auto_prompt="false"></div>
<div class="g_id_signin signin" data-type="standard" data-shape="rectangular" data-theme="filled_blue" data-text="signin_with" data-size="large"></div>
</main></body></html>"""

    def _secure_start_response(self, start_response: Callable[..., Any]):
        def secure(status: str, headers: list[tuple[str, str]], exc_info: Any = None):
            names = {name.lower() for name, _ in headers}
            if "cache-control" not in names:
                headers.append(("Cache-Control", "no-store"))
            headers.extend(self._security_headers())
            return start_response(status, headers, exc_info)

        return secure

    def _html(self, start_response: Callable[..., Any], body: str):
        payload = body.encode("utf-8")
        headers = [("Content-Type", "text/html; charset=utf-8"), ("Content-Length", str(len(payload))), ("Cache-Control", "no-store")]
        headers.extend(self._security_headers(login=True))
        start_response("200 OK", headers)
        return [payload]

    def _json(self, start_response: Callable[..., Any], body: dict[str, Any], status: str):
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers = [("Content-Type", "application/json; charset=utf-8"), ("Content-Length", str(len(payload))), ("Cache-Control", "no-store")]
        headers.extend(self._security_headers())
        start_response(status, headers)
        return [payload]

    def _redirect(self, start_response: Callable[..., Any], location: str, *, session: str | None = None, max_age: int = 0, clear_cookie: bool = False):
        headers = [("Location", location), ("Content-Length", "0"), ("Cache-Control", "no-store")]
        if session is not None:
            headers.append(("Set-Cookie", f"{SESSION_COOKIE}={session}; Path=/; Max-Age={max(1, max_age)}; HttpOnly; Secure; SameSite=Lax"))
        elif clear_cookie:
            headers.append(("Set-Cookie", f"{SESSION_COOKIE}=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Lax"))
        headers.extend(self._security_headers())
        start_response("303 See Other", headers)
        return [b""]

    @staticmethod
    def _security_headers(*, login: bool = False) -> list[tuple[str, str]]:
        script = "'self' https://accounts.google.com/gsi/client" if login else "'self'"
        frame = "https://accounts.google.com/gsi/" if login else "'none'"
        connect = "'self' https://accounts.google.com/gsi/" if login else "'self'"
        return [
            ("X-Content-Type-Options", "nosniff"),
            ("Strict-Transport-Security", "max-age=31536000; includeSubDomains"),
            ("Referrer-Policy", "no-referrer"),
            ("Permissions-Policy", "camera=(), microphone=(), geolocation=()"),
            ("Content-Security-Policy", f"default-src 'none'; script-src {script}; style-src 'self' 'unsafe-inline'; img-src 'self' data: https://*.googleusercontent.com; frame-src {frame}; connect-src {connect}; base-uri 'none'; form-action 'self' https://accounts.google.com"),
        ]


def protect_with_google(app: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap the app when JANUS_AUTH_REQUIRED is explicitly enabled."""
    required = os.environ.get("JANUS_AUTH_REQUIRED", "false").strip().lower() == "true"
    if not required:
        return app
    allowed = frozenset(value.strip() for value in os.environ.get("GOOGLE_ALLOWED_EMAILS", "").split(",") if value.strip())
    return GoogleAuthMiddleware(
        app,
        client_id=os.environ.get("GOOGLE_CLIENT_ID", ""),
        session_secret=os.environ.get("JANUS_SESSION_SECRET", ""),
        allowed_emails=allowed,
        public_base_url=os.environ.get("PUBLIC_BASE_URL", ""),
    )
