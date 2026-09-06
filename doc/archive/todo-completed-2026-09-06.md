# TODO 完成紀錄（2026-09-06）

## WBS-4C-CONTEXT-SOURCES

完成 read-only context sources：Janus Core、Private Core、Private Mart；加入
owner/thread scope、日期與 limit quota、provenance disclosure、opaque short-lived
context reference，以及 fail-closed 的外部 source allowlist。新增 source list、preview
與 internal resolve API，並將 context snapshot 以 owner/context ID 隔離寫入 Private Iceberg。

GCP dev 驗收由 Cloud Build `92131984-c36e-4755-9c20-9f37ba3cea12` 通過，涵蓋 source
list、Core／Private Mart preview、opaque reference、owner/thread isolation、resolve 與
invalid selector/SQL。API 最終 revision 為 `janus-api-00016-4bv`，immutable image digest
為 `sha256:3e702dac14143d478b7eb11925c8bff4c40c8826f28b4b0907d4228ab55871f9`。

驗收期間的兩個暫時 `roles/iam.serviceAccountTokenCreator` binding 已由腳本自動移除；
依授權保留 dev 中 `janus-user-api` 對既有 Core catalog password Secret 的 read-only
`roles/secretmanager.secretAccessor`。未部署 production，未新增付費 GCP 資源。

## WBS-4C-CLOUD-RUNTIME

完成 Cloud Run Agent Gateway POC：

- Service：`janus-agent-gateway`
- Acceptance revision：`janus-agent-gateway-00005-gxb`
- Restored dev revision：`janus-agent-gateway-00006-fj5`
- Image digest：`sha256:3aada7f674da8f18d7362b4b02b99c435a78154006ad648b0bb2e5e240bb39e1`
- Cloud Build acceptance：`bfbe9024-6a24-4452-8ca7-a717314813da`
- Checkpoint：`b36ed5c5-c833-40d0-994f-8c06f8f1862a`

GCP dev acceptance 通過 managed auth、Codex App Server stdio、workspace-write
sandbox、turn cancellation、process stop、Private GCS checkpoint 與 cursor reconnect。
Codex `0.153.0`、`authRotated=false`、`cancelled=true`、
`process=stopped-after-response`。

驗收後已將 service 回復為 `min-instances=0`、`max-instances=1`、`concurrency=1`。
Cloud Build 對專用 invoker 的暫時 `roles/iam.serviceAccountTokenCreator` 已移除；
未執行本機到 Cloud Run URL 或 proxy 驗收。Codex App Server 僅作 POC，未宣稱
production-ready。
