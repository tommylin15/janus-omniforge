import json
import sys
import unittest
from io import BytesIO
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from apps.web.auth import AuthConfigurationError, GoogleAuthMiddleware, SESSION_COOKIE


class _App:
    def __call__(self, environ, start_response):
        payload = json.dumps({"email": environ.get("JANUS_AUTH_EMAIL")}).encode()
        start_response("200 OK", [("Content-Type", "application/json"), ("Content-Length", str(len(payload)))])
        return [payload]


class GoogleAuthMiddlewareTests(unittest.TestCase):
    def setUp(self):
        self.now = 1_800_000_000
        self.claims = {"email": "tommylin15@gmail.com", "email_verified": True, "sub": "google-sub", "exp": self.now + 3600}
        self.auth = GoogleAuthMiddleware(
            _App(), client_id="client.apps.googleusercontent.com", session_secret="s" * 32,
            allowed_emails=frozenset({"tommylin15@gmail.com"}), public_base_url="https://example.run.app",
            verifier=lambda token, audience: self.claims, clock=lambda: self.now,
        )

    def request(self, path, *, method="GET", form=None, cookie="", csrf_header=""):
        encoded = urlencode(form or {}).encode()
        environ = {
            "PATH_INFO": path, "REQUEST_METHOD": method, "CONTENT_LENGTH": str(len(encoded)),
            "CONTENT_TYPE": "application/x-www-form-urlencoded", "wsgi.input": BytesIO(encoded), "HTTP_COOKIE": cookie,
            "HTTP_X_JANUS_CSRF": csrf_header,
        }
        response = {}
        body = b"".join(self.auth(environ, lambda status, headers, exc_info=None: response.update(status=status, headers=headers)))
        return response["status"], dict(response["headers"]), body

    def test_login_page_is_public_and_admin_redirects(self):
        status, headers, body = self.request("/login")
        self.assertEqual(status, "200 OK")
        self.assertIn(b"client.apps.googleusercontent.com", body)
        self.assertIn(b"handleGoogleCredential", body)
        self.assertIn(b"X-Janus-CSRF", body)
        self.assertIn("accounts.google.com", headers["Content-Security-Policy"])
        status, headers, _ = self.request("/admin/stocks")
        self.assertEqual(status, "303 See Other")
        self.assertEqual(headers["Location"], "/login")

    def test_api_rejects_missing_session(self):
        status, _, body = self.request("/api/v1/admin/stocks")
        self.assertEqual(status, "401 Unauthorized")
        self.assertIn(b"authentication required", body)

    def test_allowed_google_account_gets_signed_session(self):
        csrf = self.auth._encode_login_csrf()
        status, _, body = self.request(
            "/auth/google", method="POST", csrf_header=csrf,
            form={"g_csrf_token": csrf, "credential": "valid-token"},
        )
        self.assertEqual(status, "200 OK")
        handoff = json.loads(body)["handoff"]
        status, headers, _ = self.request(
            "/auth/google", method="POST", form={"handoff": handoff},
        )
        self.assertEqual(status, "200 OK")
        self.assertTrue(headers["Set-Cookie"].startswith(f"{SESSION_COOKIE}="))
        self.assertIn("Strict-Transport-Security", headers)
        self.assertIn(b"/admin/stocks", _)
        session_cookie = headers["Set-Cookie"].split(";", 1)[0]
        status, _, body = self.request("/admin/stocks", cookie=session_cookie)
        self.assertEqual(status, "200 OK")
        self.assertIn(b"tommylin15@gmail.com", body)

    def test_wrong_account_and_csrf_are_rejected(self):
        self.claims["email"] = "other@gmail.com"
        csrf = self.auth._encode_login_csrf()
        status, _, _ = self.request(
            "/auth/google", method="POST", csrf_header=csrf,
            form={"g_csrf_token": csrf, "credential": "valid-token"},
        )
        self.assertEqual(status, "403 Forbidden")
        status, _, _ = self.request(
            "/auth/google", method="POST", csrf_header="one",
            form={"g_csrf_token": "two", "credential": "valid-token"},
        )
        self.assertEqual(status, "400 Bad Request")

    def test_tampered_session_is_rejected(self):
        csrf = self.auth._encode_login_csrf()
        status, _, body = self.request(
            "/auth/google", method="POST", csrf_header=csrf,
            form={"g_csrf_token": csrf, "credential": "valid-token"},
        )
        self.assertEqual(status, "200 OK")
        handoff = json.loads(body)["handoff"]
        status, headers, _ = self.request(
            "/auth/google", method="POST", form={"handoff": handoff},
        )
        self.assertEqual(status, "200 OK")
        session_cookie = headers["Set-Cookie"].split(";", 1)[0] + "x"
        status, _, _ = self.request("/admin/stocks", cookie=session_cookie)
        self.assertEqual(status, "303 See Other")

    def test_logout_requires_a_valid_session(self):
        status, headers, _ = self.request("/logout", method="POST")
        self.assertEqual(status, "303 See Other")
        self.assertEqual(headers["Location"], "/login")
        self.assertNotIn("Set-Cookie", headers)

    def test_configuration_fails_closed(self):
        with self.assertRaises(AuthConfigurationError):
            GoogleAuthMiddleware(
                _App(), client_id="", session_secret="short",
                allowed_emails=frozenset(), public_base_url="http://example.com",
            )


if __name__ == "__main__":
    unittest.main()
