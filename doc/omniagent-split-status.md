# Janus／omniAgent Hard Split 狀態

更新：2026-09-23。本機 source 驗證通過，尚未完成 GCP runtime／Phase 9 驗收。

## 已修改的 source

- 移除 `services/agent-gateway/`、generic MCP fixture、Janus Chat／Agent API routes、assistant storage runtime、generic provider／Codex bridge、專用測試與部署／驗證腳本。
- API image 改由 `apps/user_app` 原始碼建置 Flutter Web；移除固定的 `legacy-user-app-web.tar.gz`。Web build 需要 `GOOGLE_USER_CLIENT_ID` 與 `GOOGLE_ADMIN_CLIENT_ID` 兩個公開 OAuth client ID。
- 保留 `services/api/mcp_adapter.py`、`services/api/mcp_oauth.py`、`/mcp` 與 OAuth routes、bounded context 讀取、Janus domain APIs 及 migrations（包含 `016_private_assistant_storage.sql`、`026_mcp_oauth_codes.sql`）。既有歷史資料未操作。既有共用 `janus-agent-provider-bundle` 仍供 ingestion／mart 使用，不可當成 dedicated Agent resource 刪除。
- `scripts/gcp/cloudbuild-admin-flutter-acceptance.yaml` 與 `scripts/gcp/cloudbuild-public-api-verify.yaml` 在開始時已有使用者未提交修改；本次保留其 Admin OAuth／public data 檢查，將 legacy Chat 預期改成不存在。

## 驗證與待續 gate

本機驗證：`python -m pytest -q` 241 passed；TypeScript typecheck/lint 通過，unit tests 3 passed；Flutter analyze 0 errors（20 個既有 style info），widget tests 15 passed；`git diff --check` 通過。測試中修正 private pipeline 殘留縮排、保留筆記 idempotency 所需的 `uuid5` import，並更新 contract registry 測試以要求 generic Agent schemas 不存在。

1. `/ponytail-review` 已執行，未發現可再簡化的必要 diff；commit/push `main` 並記錄 source SHA。建 immutable Janus image、部署既有 GCP dev `janus-api`，記錄 Cloud Build ID、digest、revision 與設定。
3. 從 GCP dev runtime／Cloud Build worker 驗 Janus health、User/Admin UI、domain APIs、workloads、MCP metadata、initialize、tools/list、未授權 guard、OAuth 與可行的 authenticated tool call。ChatGPT app UI invocation 若無法實測，獨立標示。
4. cleaned Janus 驗收通過後，盤點 caller 與 resource ownership，再刪 dedicated `janus-agent-gateway`、generic MCP fixture、暫停的 omniAgent candidate runtime 及其專用 IAM／Secret／SA。共用或 ownership 不明的資源先列出，不猜測刪除。
5. 再跑 Janus runtime smoke，更新 README、SPEC／WBS／TODO／UI、runbook、operations evidence 與本文件；再次 `/ponytail-review` 後提交文件 checkpoint。只有 source、runtime、MCP、歷史完整性都實際通過，才能標記 `JANUS / OMNIAGENT HARD SOURCE AND RUNTIME SPLIT COMPLETE`；omniAgent live acceptance 仍 deferred。

目前未執行 production build、commit、push、GCP 操作或資料異動。舊 GCP dev revision 仍提供 generic Chat；Phase 9 狀態為待驗收。
