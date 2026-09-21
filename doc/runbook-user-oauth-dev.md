# Dev User OAuth deployment runbook

This runbook covers the current Janus parallel-live `dev` environment. `dev` is the real personal-use Janus runtime, not a disposable POC sandbox. A capability that passes its auth, data, runtime, and integration acceptance may be used here with real owner data; it does not need a separate Production environment first.

Do not reuse the Admin OAuth client, deploy a separate future Production topology without an explicit decision, enable scanning APIs, or print secret payloads. The word `dev` in this runbook identifies the current environment and resource naming; it does not mean fake data, mock-only use, or “not allowed for real use.”

Mock OAuth, injected verifiers, and local pages are useful for deterministic regression tests, but they do not replace the real Google login／allowlisted owner／Cloud Run／persisted-data evidence required when a user-facing OAuth path is declared live accepted.

## OAuth and secrets

Create a Google Auth Platform Web client named `Janus User Dev`, with
`http://localhost` and `http://localhost:8080` as authorized JavaScript
origins. Put both acceptance accounts on the OAuth Audience test-user list where Google configuration requires it. These are real acceptance owners for the current dev path; do not treat their successful live login as sample-only evidence.

Download the client JSON as `google-user-oauth-dev.json`. The exact filename is
gitignored. Upload `web.client_id` and `web.client_secret` as new
versions of these Secret Manager secrets, verify both versions are enabled,
then delete the local JSON:

- `google-user-client-id`
- `google-user-client-secret`

The private runtime uses these additional secrets:

- `private-database-url`
- `postgres-private-api-password`
- `postgres-private-pipeline-password`

Never pass a secret value as a command argument. Pin Cloud Run secret refs to
an enabled numeric version, not `latest`. On Windows, write upload files with
`.NET` `UTF8Encoding(false)`; `Set-Content -Encoding utf8` in Windows
PowerShell can add a BOM that makes an OAuth client ID or PostgreSQL DSN
invalid. Before deployment, verify the first code point is the expected ASCII
character and delete the temporary file in `finally`.

For rotation, create the new Secret versions first, update the PostgreSQL role
password through an ACL-restricted temporary SQL file copied over IAP, pin
Cloud Run to the new numeric versions, verify the new revision, then disable
the old versions. The remote file must be mode `0600` and removed by a shell
trap; never place the password in a command argument or terminal output.

## Build contexts

`cloudbuild.yaml` uses the submitted directory as Docker build context:

- User API: submit repository root with `_DOCKERFILE=services/api/Dockerfile`
- PostgreSQL: submit `infra/postgres` with `_DOCKERFILE=Dockerfile`

Resolve each pushed tag to a digest and deploy only the digest. A repository-
root PostgreSQL build fails because its Dockerfile copies paths relative to
`infra/postgres`.

## PostgreSQL migration 014

1. Build and resolve the immutable PostgreSQL image as described above.
2. For an existing dev database, apply only
   `migrations/014_private_workspace.sql`; rerunning the non-idempotent role
   bootstrap from migration 001 will fail. Copy the migration and a temporary
   mode-`0600` variable file containing only the two private role passwords to
   `janus-postgres-dev` through IAP, execute them inside the PostgreSQL
   container, and remove both files with a trap.
3. Restart the PostgreSQL container with the resolved image digest and
   `--restart=always`. Local WSL, Windows gcloud, or Cloud Shell may be used;
   prefer the environment that can reliably preserve file permissions and
   cleanup.
4. Verify `control.schema_migrations` contains `014_private_workspace`, both
   private roles are non-privileged, readiness passes, and the running image is
   the new digest.

Do not use a remote `postgres` HBA rule or a long-lived migration service
account. If a temporary migration Job was created during diagnosis, delete it
and revoke all bootstrap/private secret grants before continuing.

Because the current dev database holds real personal-use data, migration success is not established by SQL completion alone: retain the migration marker, runtime readiness, owner isolation, and applicable rollback／rebuild evidence. Do not substitute a fixture database result for the live database acceptance when claiming this path complete.

## User API deployment

Deploy `janus-api` in `us-central1` with scale-to-zero, service account
`janus-user-api`, Direct VPC network `janusai-lake-poc`, subnet
`janusai-lake-poc-uscentral1`, and `private-ranges-only` egress. Configure:

- `GOOGLE_USER_CLIENT_ID=google-user-client-id:VERSION`
- `PRIVATE_DATABASE_URL=private-database-url:VERSION`
- `PRIVATE_CATALOG_PASSWORD=postgres-private-api-password:VERSION`
- `POSTGRES_HOST=10.42.0.5`, `POSTGRES_DB=janus_control`
- `PRIVATE_CATALOG_USER=janus_private_api`
- `PRIVATE_ICEBERG_WAREHOUSE=gs://PROJECT-dev-private/warehouse`
- `GCP_PROJECT_ID=PROJECT`
- `USER_CORS_ORIGINS=http://localhost:8080`

For the dev MCP OAuth facade (same `janus-api`, no new service), first prepare
the merged API bundle with `google_user_client_secret` and a fresh
`mcp_oauth_signing_key`, then deploy with:

- `MCP_OAUTH_ENABLED=true`
- `MCP_OAUTH_ISSUER=https://mcp-oauth---janus-api-2oo7qbkd5q-uc.a.run.app`
- `MCP_RESOURCE_URL=https://mcp-adapter---janus-api-2oo7qbkd5q-uc.a.run.app/mcp`
- `GOOGLE_USER_ALLOWED_EMAILS` set to the explicit current owner／acceptance allowlist

The Google Web client must allow the exact callback
`https://mcp-oauth---janus-api-2oo7qbkd5q-uc.a.run.app/oauth/google/callback`. The facade
issues short-lived Janus access tokens with the MCP resource in `aud` and
stores only hashed, one-time authorization codes in PostgreSQL. Enable it only after the bundle version and callback allowlist are verified in the current dev environment; that verification is a safety gate for the MCP OAuth capability, not a reason to keep unrelated Janus features in mock mode.

Grant the runtime account access only to those three runtime secrets and
`roles/storage.objectAdmin` only on the private bucket. Public invocation is
acceptable because `/health` is public and every `/api/v1/me/*` route enforces
the independent Google bearer audience.

## A/B live acceptance

For each real acceptance account, obtain a fresh ID token for the User client and
call `/api/v1/me/profile`. Record different internal `user_id` values. Then:

Serve `scripts/gcp` as the local HTTP root and open
`http://localhost:8080/user-ab-acceptance.html?client_id=...&api=...`. Select
the A or B slot before each Google sign-in; tokens remain only in page memory.
The local page is only an acceptance harness; the auth, Cloud Run API, PostgreSQL／Iceberg data, and owner isolation being verified are the real dev path.

1. A creates a journal row, note, and watchlist entry against the real dev backend.
2. B lists each collection and must see none of A's rows or artifact refs.
3. B attempts A's known event/note identifiers and must receive 404/409, never
   A's data.
4. A still sees its own data; Admin-client and wrong-audience tokens receive
   401; no bearer receives 401; `/health` receives 200.
5. Query PostgreSQL and Private Iceberg by internal `user_id` to confirm A/B
   partitioning, then record revision, image digest, execution IDs, and UTC
   timestamps in `doc/spec/operations-and-testing.md`.

A/B acceptance is complete only when the real OAuth journey and persisted owner isolation are both evidenced. Injected verifier tests, synthetic rows, or fixture-only results may supplement negative/error coverage but must not be reported as the live OAuth flow itself.