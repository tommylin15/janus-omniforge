# TODO 完成紀錄（2026-09-06）

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
