# Agent Gateway dev POC

Private Cloud Run service for the `WBS-4C-CLOUD-RUNTIME` feasibility check. It
starts pinned Codex App Server `0.153.0` over stdio JSONL, refreshes managed
auth from Secret Manager, uses a bounded in-memory turn sandbox, and proves
cursor reconnect from an external Private GCS checkpoint.

The POC endpoints are Cloud Run IAM-only and additionally require
`CODEX_POC_ENABLED=true`. They are not the chat API or the later Codex bridge.
Use `scripts/gcp/deploy-agent-gateway-dev.sh` and
`scripts/gcp/verify-agent-gateway-dev.sh`; never place `auth.json` in this repo.
