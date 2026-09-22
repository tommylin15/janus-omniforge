# omniAgent split status

Status date: 2026-09-22

## Closed migration checkpoints

The Janus → omniAgent split execution checkpoints Phase 0–5 are closed based on the accepted repository, CI and GCP dev evidence:

- **Phase 0 — Baseline / freeze:** completed.
- **Phase 1 — omniAgent skeleton / copy-first:** completed.
- **Phase 2 — contract / security ownership split:** completed.
- **Phase 3 — Janus ↔ omniAgent authenticated bounded wire boundary:** completed as a code/contract checkpoint. Real dev traffic validation belongs to Phase 6B.
- **Phase 4 — Chat API / assistant storage ownership:** completed as an ownership/schema/API checkpoint. Historical data copy, live database/write ownership and runtime dispatch belong to later deployment/cutover gates.
- **Phase 5 — UI extraction:** completed. Generic Chat source/widget tests are owned by omniAgent; Janus source keeps investment User/Admin UI. Janus API deployment safety is verified by the pinned pre-split Web artifact and canonical dev revision `janus-api-00154-74s`.

Closing Phase 0–5 does **not** mean the overall omniAgent split is complete or that live write ownership has moved away from Janus.

## Carry-forward phase ownership

### Phase 6 — Deployment Planning Gate

Planning only. Define the proposed Cloud Run, Cloud Build, Secret, service account, IAM, OAuth, environment, routing, service-to-service authentication, rollback and paid-resource changes. Classify each as existing-dev reuse, config change, new resource, or explicit-approval required. No deployment/security/cost change is executed in this phase.

### Phase 6B — Real Dev Deployment / Acceptance

After required approvals, use the real parallel-live dev environment for provider/runtime dispatch, Codex managed auth, Gemini/OpenRouter, MCP discovery/call, streaming, reconnect, cancellation, approvals, owner isolation, real omniAgent → Janus bounded API/MCP, and at least one real E2E path. ChatGPT → Janus MCP remains an independent path and must continue to work.

Historical owner mapping/export-copy-verify, live omniAgent storage application, write-routing cutover and post-cutover rollback belong here when required by the approved plan. Migration remains copy/verify-first and non-destructive until acceptance.

### Phase 7 — Janus Cleanup

Only after Phase 6B live acceptance and explicit cleanup approval. Remove only Janus generic assistant implementation that is demonstrably replaced by omniAgent. Preserve Janus domain/data/API/MCP/UI responsibilities and all applied migration history. Run Janus/omniAgent regression and stale import/path scans.

### Phase 8 — Documentation Migration / Stale-reference Gate

Align active README/WBS/spec/TODO/UI/runbooks/service/package documentation with the actual current ownership, paths and runtime. Archive/history keeps historical facts; current documents must not describe stale ownership as live architecture.

### Phase 9 — Final Acceptance

Re-check both repositories, tests, CI, deployment, live runtime, integration, UI, contracts, storage ownership, docs, stale references and rollback. Only a Phase 9 PASS may be labeled `OMNIAGENT SPLIT COMPLETE`.

## Current live boundary

Janus remains the live Chat writer and retains the applied Janus migration history and historical conversation/private data until an approved Phase 6B cutover. The pinned legacy Web artifact preserves the currently deployed Chat UI while the source ownership is already split. Remaining OAuth, runtime dispatch, real Janus integration, Skills/MCP integration, historical migration and live cutover are therefore carry-forward work, not unfinished Phase 3–5 checkpoint scope.
