import re
import unittest
from urllib.parse import parse_qs, urlsplit

from fastapi import HTTPException

from services.api.mcp_oauth import (
    MCP_CLIENT_ID,
    MCP_REDIRECT_URI,
    InMemoryOAuthCodeStore,
    McpOAuth,
    OAuthSettings,
)


class McpOAuthTests(unittest.TestCase):
    def setUp(self):
        self.now = 1_700_000_000
        self.settings = OAuthSettings(
            issuer="https://api.example.test",
            resource="https://api.example.test/mcp",
            google_client_id="google-client",
            google_client_secret="google-secret",
            signing_key=b"k" * 32,
            allowed_emails=frozenset({"owner@example.com"}),
        )
        self.oauth = McpOAuth(
            self.settings, InMemoryOAuthCodeStore(), lambda _sub, _email: "owner-uuid",
            clock=lambda: self.now,
            google_exchange=lambda _code, _redirect: {"id_token": "id-token"},
            google_verify=lambda _token, _audience: {
                "iss": "https://accounts.google.com", "sub": "google-sub", "email": "owner@example.com",
                "email_verified": True, "exp": self.now + 600,
            },
        )

    def test_metadata_is_resource_bound_and_pkce_capable(self):
        protected = self.oauth.protected_resource_metadata()
        self.assertEqual(protected["resource"], self.settings.resource)
        metadata = self.oauth.authorization_server_metadata()
        self.assertEqual(metadata["issuer"], self.settings.issuer)
        self.assertEqual(metadata["code_challenge_methods_supported"], ["S256"])
        self.assertEqual(metadata["token_endpoint_auth_methods_supported"], ["none"])

    def test_authorization_requires_exact_resource_and_s256(self):
        with self.assertRaises(HTTPException):
            self.oauth.begin_authorization({"response_type": "code", "client_id": MCP_CLIENT_ID,
                                            "redirect_uri": MCP_REDIRECT_URI, "resource": "wrong",
                                            "scope": "janus.market.read", "code_challenge": "x" * 43,
                                            "code_challenge_method": "S256", "state": "state"})
        with self.assertRaises(HTTPException):
            self.oauth.begin_authorization({"response_type": "code", "client_id": MCP_CLIENT_ID,
                                            "redirect_uri": MCP_REDIRECT_URI, "resource": self.settings.resource,
                                            "scope": "janus.market.read", "code_challenge": "x" * 43,
                                            "code_challenge_method": "plain", "state": "state"})

    def test_pkce_code_is_one_time_and_access_token_has_binding(self):
        verifier = "v" * 64
        response = self.oauth.begin_authorization({
            "response_type": "code", "client_id": MCP_CLIENT_ID, "redirect_uri": MCP_REDIRECT_URI,
            "resource": self.settings.resource, "scope": "janus.market.read",
            "code_challenge": self.oauth._pkce(verifier), "code_challenge_method": "S256", "state": "state",
        })
        google_state = parse_qs(urlsplit(response.headers["location"]).query)["state"][0]
        consent = self.oauth.google_callback({"state": google_state, "code": "google-code"})
        token = re.search(r"name='token' value='([^']+)'", consent.body.decode()).group(1)
        redirect = self.oauth.complete_authorization(token, True)
        query = parse_qs(urlsplit(redirect.headers["location"]).query)
        access = self.oauth.exchange_token({
            "grant_type": "authorization_code", "client_id": MCP_CLIENT_ID, "redirect_uri": MCP_REDIRECT_URI,
            "resource": self.settings.resource, "code": query["code"][0], "code_verifier": verifier,
        })
        claims = self.oauth.verify_access_token(access["access_token"], "janus.market.read")
        self.assertEqual(claims["sub"], "owner-uuid")
        with self.assertRaises(HTTPException):
            self.oauth.exchange_token({
                "grant_type": "authorization_code", "client_id": MCP_CLIENT_ID, "redirect_uri": MCP_REDIRECT_URI,
                "resource": self.settings.resource, "code": query["code"][0], "code_verifier": verifier,
            })

    def test_repository_code_challenge_field_is_accepted(self):
        verifier = "repository-verifier"
        code = "repository-shaped-code"
        self.oauth.code_store.create(self.oauth._hash(code), {
            "user_id":"owner-uuid", "client_id":MCP_CLIENT_ID, "redirect_uri":MCP_REDIRECT_URI,
            "resource":self.settings.resource, "scope":"janus.market.read",
            "code_challenge":self.oauth._pkce(verifier),
        }, self.now + 600)
        token = self.oauth.exchange_token({
            "grant_type":"authorization_code", "client_id":MCP_CLIENT_ID, "redirect_uri":MCP_REDIRECT_URI,
            "resource":self.settings.resource, "code":code, "code_verifier":verifier,
        })
        self.assertEqual(self.oauth.verify_access_token(token["access_token"], "janus.market.read")["sub"], "owner-uuid")

    def test_consent_page_csp_allows_chatgpt_form_action(self):
        verifier = "v" * 64
        response = self.oauth.begin_authorization({
            "response_type": "code", "client_id": MCP_CLIENT_ID, "redirect_uri": MCP_REDIRECT_URI,
            "resource": self.settings.resource, "scope": "janus.sources.read",
            "code_challenge": self.oauth._pkce(verifier), "code_challenge_method": "S256", "state": "state",
        })
        google_state = parse_qs(urlsplit(response.headers["location"]).query)["state"][0]
        consent = self.oauth.google_callback({"state": google_state, "code": "google-code"})
        csp = consent.headers["Content-Security-Policy"]

        self.assertIn("form-action 'self' https://chatgpt.com", csp)
        self.assertNotIn("form-action 'self';", csp)
        self.assertIn("default-src 'none'", csp)
        self.assertIn("style-src 'unsafe-inline'", csp)
        self.assertIn("base-uri 'none'", csp)
        self.assertIn(b"action='/oauth/authorize/complete'", consent.body)


if __name__ == "__main__":
    unittest.main()
