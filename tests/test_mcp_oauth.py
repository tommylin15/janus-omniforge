import re
import unittest
from urllib.parse import parse_qs, urlsplit

from fastapi import HTTPException

from services.api.mcp_oauth import (
    CODEX_CLIENT_ID,
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
        self.assertEqual(metadata["grant_types_supported"], ["authorization_code", "refresh_token"])
        self.assertIn("offline_access", metadata["scopes_supported"])
        self.assertNotIn("janus.private.write", metadata["scopes_supported"])
        self.assertEqual(metadata["revocation_endpoint"], "https://api.example.test/oauth/revoke")
        self.assertEqual(metadata["revocation_endpoint_auth_methods_supported"], ["none"])
        self.assertEqual(self.settings.refresh_ttl, 90 * 24 * 60 * 60)
        self.assertEqual(metadata["response_types_supported"], ["code"])
        self.assertEqual(metadata["registration_endpoint"], self.settings.issuer + "/oauth/register")

    def test_google_clients_register_authorize_exchange_refresh_and_revoke(self):
        for callback in ("http://localhost:54321/oauth/callback", "http://127.0.0.1:7777/oauth/callback",
                         "https://antigravity.google/oauth-callback"):
            with self.subTest(callback=callback):
                registration = self.oauth.register_client({"redirect_uris": [callback]})
                client_id = registration["client_id"]
                self.assertLessEqual(len(client_id), 512)
                verifier = "google-client-verifier" * 3
                response = self.oauth.begin_authorization({
                    "response_type": "code", "client_id": client_id, "redirect_uri": callback,
                    "code_challenge": self.oauth._pkce(verifier), "code_challenge_method": "S256", "state": "google-client-state",
                })
                google_state = parse_qs(urlsplit(response.headers["location"]).query)["state"][0]
                consent = self.oauth.google_callback({"state": google_state, "code": "google-code"})
                origin = urlsplit(callback)
                self.assertIn(f"{origin.scheme}://{origin.netloc}", consent.headers["Content-Security-Policy"])
                token = re.search(r"name='token' value='([^']+)'", consent.body.decode()).group(1)
                redirect = self.oauth.complete_authorization(token, True)
                query = parse_qs(urlsplit(redirect.headers["location"]).query)
                self.assertEqual(query["iss"], [self.settings.issuer])
                self.assertEqual(query["state"], ["google-client-state"])
                access = self.oauth.exchange_token({
                    "grant_type": "authorization_code", "client_id": client_id, "redirect_uri": callback,
                    "code": query["code"][0], "code_verifier": verifier,
                })
                self.assertEqual(self.oauth.verify_access_token(access["access_token"], "janus.private.read")["sub"], "owner-uuid")
                renewed = self.oauth.exchange_token({"grant_type": "refresh_token", "client_id": client_id,
                                                     "refresh_token": access["refresh_token"]})
                self.oauth.revoke_token({"client_id": client_id, "token": renewed["refresh_token"]})
                with self.assertRaises(HTTPException):
                    self.oauth.exchange_token({"grant_type": "refresh_token", "client_id": client_id,
                                               "refresh_token": renewed["refresh_token"]})

    def test_registration_rejects_untrusted_redirects_and_confidential_clients(self):
        for metadata in ({"redirect_uris": ["https://evil.test/oauth-callback"]},
                         {"redirect_uris": ["https://antigravity.google.evil.test/oauth-callback"]},
                         {"redirect_uris": ["http://localhost:0/oauth/callback"]},
                         {"redirect_uris": ["http://localhost:65536/oauth/callback"]},
                         {"redirect_uris": ["http://localhost:7777/oauth/callback?next=evil"]},
                         {"redirect_uris": ["http://localhost:7777/oauth/callback\n"]},
                         {"redirect_uris": ["http://127.0.0.2:7777/oauth/callback"]},
                         {"redirect_uris": []}, {"redirect_uris": "http://localhost:7777/oauth/callback"},
                         {"redirect_uris": ["https://antigravity.google/oauth-callback"], "token_endpoint_auth_method": "client_secret_post"},
                         {"redirect_uris": ["https://antigravity.google/oauth-callback"], "scope": "janus.private.write"}):
            with self.subTest(metadata=metadata), self.assertRaises(HTTPException):
                self.oauth.register_client(metadata)

    def test_registered_client_cannot_change_callback_resource_or_signature(self):
        client_id = self.oauth.register_client({"redirect_uris": ["http://localhost:7777/oauth/callback"]})["client_id"]
        self.assertFalse(self.oauth._valid_client(client_id + "tampered"))
        self.assertFalse(self.oauth._valid_redirect("http://localhost:7778/oauth/callback", client_id))
        self.assertFalse(self.oauth._valid_redirect(MCP_REDIRECT_URI, client_id))
        for resource in ("https://evil.test/mcp", ""):
            with self.subTest(resource=resource), self.assertRaises(HTTPException):
                self.oauth.begin_authorization({"response_type": "code", "client_id": client_id,
                    "redirect_uri": "http://localhost:7777/oauth/callback", "resource": resource,
                    "code_challenge": "x" * 43, "code_challenge_method": "S256", "state": "state"})

    def test_registration_http_contract_and_path_discovery(self):
        from fastapi.testclient import TestClient
        from services.api.app import create_app
        from types import SimpleNamespace
        with TestClient(create_app(repository=SimpleNamespace(), oauth_facade=self.oauth)) as client:
            response = client.post("/oauth/register", json={"redirect_uris": ["https://antigravity.google/oauth-callback"]})
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.headers["cache-control"], "no-store")
            self.assertTrue(self.oauth._valid_client(response.json()["client_id"]))
            for body in ([], {"redirect_uris": ["https://evil.test"]}, {"scope": 7}, None):
                self.assertEqual(client.post("/oauth/register", json=body).status_code, 400)
            self.assertEqual(client.post("/oauth/register", content="x" * 4097).status_code, 400)
            self.assertEqual(client.get("/.well-known/oauth-protected-resource/mcp").json()["resource"], self.settings.resource)

    def test_registered_client_is_public_metadata_and_never_an_access_token(self):
        registration = self.oauth.register_client({"redirect_uris": ["https://antigravity.google/oauth-callback"],
                                                   "grant_types": ["authorization_code"]})
        clone = McpOAuth(self.settings, InMemoryOAuthCodeStore(), lambda *_: "owner-uuid")
        self.assertTrue(clone._valid_client(registration["client_id"]))
        with self.assertRaises(HTTPException):
            clone.verify_access_token(registration["client_id"].removeprefix("janus-dcr."), "janus.private.read")

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
        self.assertIn("offline_access", access["scope"].split())
        self.assertIn("refresh_token", access)
        with self.assertRaises(HTTPException):
            self.oauth.exchange_token({
                "grant_type": "authorization_code", "client_id": MCP_CLIENT_ID, "redirect_uri": MCP_REDIRECT_URI,
                "resource": self.settings.resource, "code": query["code"][0], "code_verifier": verifier,
            })

    def test_retired_write_scope_is_rejected(self):
        with self.assertRaises(HTTPException) as denied:
            self.oauth.begin_authorization({
                "response_type": "code", "client_id": MCP_CLIENT_ID, "redirect_uri": MCP_REDIRECT_URI,
                "resource": self.settings.resource, "scope": "janus.private.write",
                "code_challenge": self.oauth._pkce("verifier"), "code_challenge_method": "S256", "state": "state",
            })
        self.assertEqual(denied.exception.status_code, 400)

    def test_codex_loopback_authorization_and_exchange(self):
        for port in (59164, 61235):
            with self.subTest(port=port):
                callback = f"http://127.0.0.1:{port}/callback"
                verifier = "codex-verifier" * 5
                response = self.oauth.begin_authorization({
                    "response_type": "code", "client_id": CODEX_CLIENT_ID, "redirect_uri": callback,
                    "resource": self.settings.resource, "scope": "janus.private.read",
                    "code_challenge": self.oauth._pkce(verifier), "code_challenge_method": "S256", "state": "codex-state",
                })
                google_query = parse_qs(urlsplit(response.headers["location"]).query)
                self.assertEqual(google_query["redirect_uri"], [f"{self.settings.issuer}/oauth/google/callback"])
                consent = self.oauth.google_callback({"state": google_query["state"][0], "code": "google-code"})
                self.assertIn(f"form-action 'self' https://chatgpt.com http://127.0.0.1:{port};", consent.headers["Content-Security-Policy"])
                token = re.search(r"name='token' value='([^']+)'", consent.body.decode()).group(1)
                redirect = self.oauth.complete_authorization(token, True)
                self.assertTrue(redirect.headers["location"].startswith(callback + "?"))
                query = parse_qs(urlsplit(redirect.headers["location"]).query)
                self.assertEqual(query["state"], ["codex-state"])
                self.assertEqual(query["iss"], [self.settings.issuer])
                access = self.oauth.exchange_token({
                    "grant_type": "authorization_code", "client_id": CODEX_CLIENT_ID, "redirect_uri": callback,
                    "resource": self.settings.resource, "code": query["code"][0], "code_verifier": verifier,
                })
                self.assertEqual(self.oauth.verify_access_token(access["access_token"], "janus.private.read")["sub"], "owner-uuid")

    def test_loopback_rejects_other_clients_and_nonexact_urls(self):
        callbacks = (
            "http://localhost:59164/callback", "http://127.0.0.2:59164/callback",
            "http://127.0.0.1.evil.test:59164/callback", "https://127.0.0.1:59164/callback",
            "http://user@127.0.0.1:59164/callback", "http://127.0.0.1:59164/other",
            "http://127.0.0.1:59164/callback/", "http://127.0.0.1:59164/callback?next=evil",
            "http://127.0.0.1:59164/callback#fragment", "http://127.0.0.1:0/callback",
            "http://127.0.0.1:65536/callback", "http://127.0.0.1/callback",
            "http://127.0.0.1:59164/call%62ack", "http://127.0.0.1:59164/callback\n",
        )
        pairs = [(CODEX_CLIENT_ID, callback) for callback in callbacks]
        pairs += [(client, "http://127.0.0.1:59164/callback") for client in
                  (MCP_CLIENT_ID, "https://chatgpt.com/oauth/other/client.json", "https://evil.test/client.json")]
        for client, callback in pairs:
            with self.subTest(client=client, callback=callback):
                with self.assertRaises(HTTPException):
                    self.oauth.begin_authorization({
                        "response_type": "code", "client_id": client, "redirect_uri": callback,
                        "resource": self.settings.resource, "scope": "janus.private.read",
                        "code_challenge": "x" * 43, "code_challenge_method": "S256", "state": "state",
                    })
                with self.assertRaises(HTTPException):
                    self.oauth.exchange_token({
                        "grant_type": "authorization_code", "client_id": client, "redirect_uri": callback,
                        "resource": self.settings.resource, "code": "unused", "code_verifier": "v" * 64,
                    })

    def test_codex_code_remains_bound_to_port_and_pkce(self):
        verifier = "v" * 64
        for callback, supplied_verifier in (("http://127.0.0.1:59165/callback", verifier),
                                            ("http://127.0.0.1:59164/callback", "wrong-verifier")):
            with self.subTest(callback=callback, verifier=supplied_verifier):
                self.oauth.code_store.create(self.oauth._hash("codex-code"), {
                    "user_id": "owner-uuid", "client_id": CODEX_CLIENT_ID,
                    "redirect_uri": "http://127.0.0.1:59164/callback", "resource": self.settings.resource,
                    "scope": "janus.private.read", "challenge": self.oauth._pkce(verifier),
                }, self.now + 600)
                with self.assertRaises(HTTPException):
                    self.oauth.exchange_token({
                        "grant_type": "authorization_code", "client_id": CODEX_CLIENT_ID, "redirect_uri": callback,
                        "resource": self.settings.resource, "code": "codex-code", "code_verifier": supplied_verifier,
                    })


    def test_offline_access_refresh_rotates_once_and_revokes(self):
        verifier = "refresh-verifier"
        response = self.oauth.begin_authorization({
            "response_type": "code", "client_id": MCP_CLIENT_ID, "redirect_uri": MCP_REDIRECT_URI,
            "resource": self.settings.resource, "scope": "janus.market.read offline_access",
            "code_challenge": self.oauth._pkce(verifier), "code_challenge_method": "S256", "state": "state",
        })
        google_state = parse_qs(urlsplit(response.headers["location"]).query)["state"][0]
        consent = self.oauth.google_callback({"state": google_state, "code": "google-code"})
        token = re.search(r"name='token' value='([^']+)'", consent.body.decode()).group(1)
        redirect = self.oauth.complete_authorization(token, True)
        code = parse_qs(urlsplit(redirect.headers["location"]).query)["code"][0]
        original = self.oauth.exchange_token({
            "grant_type": "authorization_code", "client_id": MCP_CLIENT_ID, "redirect_uri": MCP_REDIRECT_URI,
            "resource": self.settings.resource, "code": code, "code_verifier": verifier,
        })
        self.assertIn("refresh_token", original)
        renewed = self.oauth.exchange_token({
            "grant_type": "refresh_token", "client_id": MCP_CLIENT_ID, "resource": self.settings.resource,
            "refresh_token": original["refresh_token"],
        })
        self.assertNotEqual(renewed["refresh_token"], original["refresh_token"])
        claims = self.oauth.verify_access_token(renewed["access_token"], "janus.market.read")
        self.assertEqual(claims["sub"], "owner-uuid")
        with self.assertRaises(HTTPException):
            self.oauth.exchange_token({
                "grant_type": "refresh_token", "client_id": MCP_CLIENT_ID, "resource": self.settings.resource,
                "refresh_token": original["refresh_token"],
            })
        self.oauth.revoke_token({"client_id": MCP_CLIENT_ID, "token": renewed["refresh_token"]})
        with self.assertRaises(HTTPException):
            self.oauth.exchange_token({
                "grant_type": "refresh_token", "client_id": MCP_CLIENT_ID, "resource": self.settings.resource,
                "refresh_token": renewed["refresh_token"],
            })

    def test_refresh_token_expiration_is_enforced(self):
        self.oauth.code_store.create_refresh(self.oauth._hash("expired-token"), {
            "user_id": "owner-uuid", "client_id": MCP_CLIENT_ID, "resource": self.settings.resource,
            "scope": "janus.market.read offline_access",
        }, self.now - 1)
        with self.assertRaises(HTTPException):
            self.oauth.exchange_token({
                "grant_type": "refresh_token", "client_id": MCP_CLIENT_ID, "resource": self.settings.resource,
                "refresh_token": "expired-token",
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
        self.assertNotIn(b"janus.private.write", consent.body)
        self.assertIn("MCP 不提供新增交易或股息紀錄功能".encode(), consent.body)
        self.assertIn("閒置 90 天後失效".encode(), consent.body)


if __name__ == "__main__":
    unittest.main()
