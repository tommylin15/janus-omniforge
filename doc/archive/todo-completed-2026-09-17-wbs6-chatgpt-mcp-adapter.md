# WBS-6-CHATGPT-MCP-ADAPTER — completed 2026-09-17

- Workspace source archive uploaded to the existing dev Cloud Build bucket with explicit user approval.
- Cloud Build `7d070e60-d8c1-4e7f-821f-5d8a54bd9196` succeeded through build and push; image digest `sha256:a9672d6ddfa8d81a483ea257deaf707cd7576998729bad8f1d5492a61053be01`.
- Cloud Run `janus-api-mcp-adapter3` and `janus-api-mcp-oauth4` are Ready, tagged `mcp-adapter`／`mcp-oauth`, and receive 0% traffic.
- GCP VM/IAP acceptance: initialize 200; tools/list 200 with three read-only tools and scopes; unauthenticated call 401 with MCP auth challenge; OAuth token exchange 200; authenticated sources and owner-scoped private trades calls 200; no `user_id` or `artifact_ref` disclosure.
- Temporary OAuth fixture was deleted and verified absent. No production traffic or new paid GCP resource was created.
- Local targeted tests: 32 passed; Python compile, Git Bash `bash -n`, and `git diff --check` passed.
