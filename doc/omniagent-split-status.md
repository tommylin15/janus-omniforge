# Janus／omniAgent Hard Split 狀態

更新：2026-09-23。Janus source hard split、GCP dev runtime acceptance 與 Janus 專用 runtime cleanup 已完成。整體 omniAgent split 不標記 Phase 9 complete：未做互動式 authenticated MCP tool call；omniAgent gateway 仍有 live 請求並保留。

## Source 已完成

- 移除 `services/agent-gateway/`、generic MCP fixture、Janus Chat／Agent API routes、assistant storage runtime、generic provider／Codex bridge、相關測試與專用部署／驗證腳本。
- API image 改由 `apps/user_app` 原始碼建置 Flutter Web；移除固定 `legacy-user-app-web.tar.gz`。Web build 使用 `GOOGLE_USER_CLIENT_ID` 與 `GOOGLE_ADMIN_CLIENT_ID`。
- 保留 `services/api/mcp_adapter.py`、`services/api/mcp_oauth.py`、`/mcp` 與 OAuth routes、bounded context、Janus domain APIs 及已套用 migrations（包括 `016_private_assistant_storage.sql`、`026_mcp_oauth_codes.sql`）。不搬移或刪除歷史私人資料。
- 2026-09-23 已將剩餘三個 Janus bundles 合併為 `janus-runtime-bundle`，並更新所有 Janus API／Job／PostgreSQL migration build references；舊 bundles 已刪除，Codex owners bundle 原先已不存在。
- 開始時已有的 `scripts/gcp/cloudbuild-admin-flutter-acceptance.yaml` 與 `scripts/gcp/cloudbuild-public-api-verify.yaml` 使用者變更已保留，並將 legacy Chat 預期改為不存在。

## 本機驗證

`python -m pytest -q`: **241 passed**；TypeScript typecheck／lint 通過、unit tests **3 passed**；Flutter analyze **0 errors**（20 個既有 info notices）、widget tests **15 passed**；Git Bash `bash -n scripts/gcp/deploy-dev.sh` 與 `git diff --check` 通過。

Source/documentation commits `4371487d`、`dadc10ee` 與 acceptance config commit `f80f3c6` 已推送到 GitHub `main`；遠端原有文件提交經一般 merge 保留，未 force-push。

## 後續驗收 gates

### Phase 6B — GCP dev runtime acceptance（完成）

immutable image build `53aa871d-7805-4dd4-a8a9-c2eb9101204d`，digest `sha256:d1b9d7c2f3f5f05d142e514281cb36d791ef81b477ebf3ebadbf7fa310f591bf`，revision `janus-api-runtime-bundle` 已部署並承接 canonical 100% traffic。2026-09-23 三個剩餘 Janus bundles 無衝突合併為一個 28 欄位 `janus-runtime-bundle`；API 與三個 Cloud Run Job templates 均引用 `latest`，IAM 授權四個 runtime identities 與 Cloud Build default identity。候選 public API／MCP-OAuth／User-Admin UI acceptance builds `6ecc1a49`、`acf423f5`、`e29095b1` 均成功；切流量後 canonical builds `17dd3591`、`6a653e48`、`8fbe6d86` 均成功。Chat/internal routes removed、MCP metadata／initialize／tools/list 與未授權 tool-call guard 仍通過。未進行互動式 OAuth consent 與 authenticated tools/call，亦未執行 Job 或 PostgreSQL schema/data migration；未使用 localhost 或本機 proxy。

### Phase 7 — GCP 專用 runtime cleanup（Janus 部分完成）

Janus acceptance 後已刪 `janus-agent-gateway`、`janus-mcp-fixture`、無版本的 `janus-codex-owners-bundle`、`janus-agent-gateway`／`janus-agent-poc-invoker` service account，以及原有三個 Janus Secret bundles；唯一保留的 Janus bundle 是 `janus-runtime-bundle`。其欄位級存取隔離因使用者核准的單一資源設計而取消。omniAgent cleanup 未執行：`omniagent-agent-gateway` 當日仍有成功請求，`omniagent-chat` 仍是其 invoker identity，兩者可能有 owner 需求，故保留。

### Phase 8 — 文件與 stale-reference gate

README、active SPEC／WBS／TODO／UI、runbook、Secret 清單與此狀態文件已同步 source/runtime ownership 與實際驗收證據。舊 Phase 5、Agent Gateway 與 Chat runtime 驗收文件保留作歷史紀錄，不得當成目前 Janus 契約。

### Phase 9 — 最終驗收

Janus source/runtime/MCP smoke、已套用 migration 與歷史資料保留、Janus 專用 cleanup 均已驗收。最終 overall split label 仍 deferred，直到互動式 authenticated MCP tool call 可驗證，且 omniAgent owner 確認其 live gateway/chat runtime 的保留或清理決策。

## GCP 唯讀盤點

截至 2026-09-23，canonical `janus-api` 100% 指向 `janus-api-runtime-bundle`，`MCP_OAUTH_ENABLED=true`，三個 legacy Agent env vars 不存在。Secret Manager 僅剩 Janus `janus-runtime-bundle` 一個 container／enabled version。API 與三個 Job references 均為 `janus-runtime-bundle:latest`；Job `janus-ingestion-core`、`janus-intelligence-mart`、`janus-private-pipeline` 均 Ready。`omniagent-agent-gateway` 與 `omniagent-chat` 保留；gateway 在當日仍有成功 requests。
