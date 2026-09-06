# Agent Gateway dev POC

Private Cloud Run service for the `WBS-4C-CLOUD-RUNTIME` feasibility check. It
starts pinned Codex App Server `0.153.0` over stdio JSONL, refreshes managed
auth from Secret Manager, uses a bounded in-memory turn sandbox, and proves
cursor reconnect from an external Private GCS checkpoint.

The POC endpoints are Cloud Run IAM-only and additionally require
`CODEX_POC_ENABLED=true`. They are not the chat API or the later Codex bridge.
Use `scripts/gcp/deploy-agent-gateway-dev.sh` and
`scripts/gcp/verify-agent-gateway-dev.sh`; never place `auth.json` in this repo.

The same private service now contains the MCP Host. `MCP_SERVER_CONFIGS` is a
server-owned JSON map of immutable config references to `stdio`,
`streamable-http`, or explicit legacy `sse` transports. User payloads contain
only a config reference and namespaced tool grants. Internal discover, call,
cancel, and disconnect routes require Cloud Run IAM plus an HMAC signed owner
claim; raw commands, URLs, images, and credentials are never accepted from the
client.

`CodexBridge` upgrades the POC client to the bidirectional App Server protocol:
owner-bound threads/turns, item and delta events, device-code login, bounded
request-scoped approvals, cancellation, and dynamic tools dispatched through
the same `McpHost` grant checks. Chat routes and durable private thread storage
remain separate later WBS slices.

Bridge contract/build checks and the live managed-auth/cancellation/reconnect
probe run only in GCP dev through `verify-agent-gateway-dev.sh`.
