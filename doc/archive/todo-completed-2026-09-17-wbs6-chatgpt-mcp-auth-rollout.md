# WBS-6 ChatGPT MCP OAuth dev rollout — completed 2026-09-17

- Existing `janus-api` revision `janus-api-mcp-oauth3-config` was deployed with no production traffic and the `mcp-oauth` dev tag.
- API bundle `janus-postgres-api-bundle` version 16 contains the required OAuth client secret and signing key fields; the explicit dev user allowlist is `tommylin15@gmail.com`.
- PostgreSQL migration `026_mcp_oauth_codes` was applied to the existing `janus-postgres-dev` VM using immutable image `sha256:c635d2fd249cb9e0c66db313011bcd3bd52fd44f63be108bd868fd0683490733`.
- GCP dev VM/IAP checks passed: protected-resource metadata 200, authorization-server metadata 200, incomplete token exchange 400, missing-S256 authorize request 400, and valid-S256 authorize request 302 to Google upstream.
- The revision remains tagged/no-traffic; Google OAuth must have the exact callback `https://janus-api-2oo7qbkd5q-uc.a.run.app/oauth/google/callback` configured before a real browser login. MCP adapter implementation and connector acceptance remain the next WBS.
