# WBS-8-PILOT-RELEASE-BASELINE — completed 2026-09-17

The existing immutable Mart pipeline already provided the requested simple
`material_change` baseline／epoch mechanism. It records git SHA, immutable image
digest, governance／prompt／schema／feature／signal revisions, model／provider and
source／config revision. The lineage digest derives the baseline ID; re-registering
conflicting metadata fails, and existing execution manifests／Mart publication
linkage reject changes to the historical Core／Mart or baseline identity.

驗收結果：

- `python -m unittest tests/test_pilot_readiness.py`：**4 passed**。
- Existing GCP dev `janus-postgres-dev` guard：`e2-micro`、30 GB `pd-standard`、private IP、無 external IP。
- Existing `scripts/gcp/pilot-readiness-acceptance.sql`：migration `025_pilot_readiness`、lineage columns／relations、bounded role privileges、baseline registration 全部通過；transaction 以 `ROLLBACK` 結束，未留下 fixture。
- Existing `janus-intelligence-mart` Cloud Run Job 使用 immutable image digest `sha256:b497e6ee00792d0caf1f65584674f6bf5fa66ba2ed8facb3b7e392d9c002dd8c`，並設定 matching `JANUS_IMAGE_DIGEST` 與 `JANUS_GIT_SHA=b965410e3fb180a06d20728d3dad0be4306a2a79`。
- Artifact Registry retention 未調整；未部署 production、未建立新付費 GCP 資源、未呼叫 Artifact Analysis／Container Scanning／occurrence API。

Baseline implementation was reused as-is; no duplicate release system was added.
