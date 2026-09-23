# Janus／omniAgent Hard Split 狀態

更新：2026-09-23。Phase 0–5 遷移檢查點已完成；Janus source hard split 已本機驗證。GCP dev runtime acceptance、專用舊 runtime 清理與最終 Phase 9 驗收仍待完成。

## Source 已完成

- 移除 `services/agent-gateway/`、generic MCP fixture、Janus Chat／Agent API routes、assistant storage runtime、generic provider／Codex bridge、相關測試與專用部署／驗證腳本。
- API image 改由 `apps/user_app` 原始碼建置 Flutter Web；移除固定 `legacy-user-app-web.tar.gz`。Web build 使用 `GOOGLE_USER_CLIENT_ID` 與 `GOOGLE_ADMIN_CLIENT_ID`。
- 保留 `services/api/mcp_adapter.py`、`services/api/mcp_oauth.py`、`/mcp` 與 OAuth routes、bounded context、Janus domain APIs 及已套用 migrations（包括 `016_private_assistant_storage.sql`、`026_mcp_oauth_codes.sql`）。不搬移或刪除歷史私人資料。
- 共用 `janus-agent-provider-bundle` 仍供 ingestion／mart 使用，不得視為 dedicated Agent resource 刪除。
- 開始時已有的 `scripts/gcp/cloudbuild-admin-flutter-acceptance.yaml` 與 `scripts/gcp/cloudbuild-public-api-verify.yaml` 使用者變更已保留，並將 legacy Chat 預期改為不存在。

## 本機驗證

`python -m pytest -q`: **241 passed**；TypeScript typecheck／lint 通過、unit tests **3 passed**；Flutter analyze **0 errors**（20 個既有 info notices）、widget tests **15 passed**；Git Bash `bash -n scripts/gcp/deploy-dev.sh` 與 `git diff --check` 通過。

Source commits：`4371487d241c53a2541d9d2a5552e8b96e693fd1` 與 `dadc10eea02f6be673053f16289934360afc31e3`。推送時因 `origin/main` 新增兩個文件提交而非 fast-forward；已 fetch，未 force-push，現正保留遠端變更並整合。

## 後續驗收 gates

### Phase 6B — GCP dev runtime acceptance

推送後以 immutable image build 部署既有 dev `janus-api`，記錄 build ID、digest、revision 與設定。驗證 health、User/Admin UI、domain API、workloads、MCP metadata／initialize／tools/list、未授權 guard、OAuth 及可行的 authenticated tool call；確認 Chat/Agent routes 不再提供。ChatGPT app UI invocation 若無法實測，獨立標示。不得用 localhost 或本機 proxy 代替。

### Phase 7 — GCP 專用 runtime cleanup

只有 Janus dev acceptance 通過後才清理。先盤點 caller 與 ownership，再移除 dedicated `janus-agent-gateway`、generic MCP fixture、暫停的 omniAgent candidate runtime，以及確認專屬的 IAM／Secret／service account。共用或 ownership 不明資源先列出，不猜測刪除；不得刪 migration 或歷史資料。

### Phase 8 — 文件與 stale-reference gate

README、active SPEC／WBS／TODO／UI、runbook 與此狀態文件已對齊 source ownership；runtime acceptance 後補記實際證據並再次掃描。舊 Phase 5、Agent Gateway 與 Chat runtime 驗收文件保留作歷史紀錄，不得當成目前 Janus 契約。

### Phase 9 — 最終驗收

再次驗證 Janus runtime、MCP、歷史資料完整性與清理結果。只有 source、runtime、MCP、歷史完整性都實際通過，才能標記 `JANUS / OMNIAGENT HARD SOURCE AND RUNTIME SPLIT COMPLETE`。omniAgent 自身 live runtime／Chat acceptance 獨立標示，不因 Janus cleanup 宣稱完成。

## GCP 唯讀盤點

截至 2026-09-23，dev `janus-api` 仍是舊 Chat revision，並帶有 `INTERNAL_ASSISTANT_AUDIENCE`、`ASSISTANT_SERVICE_ACCOUNTS`、`MCP_GATEWAY_URL`；部署腳本已設定移除這些變數。`janus-agent-gateway`、`janus-mcp-fixture`、`omniagent-agent-gateway` 與 `omniagent-chat` 仍存在。只做唯讀查詢，尚未 build、部署、刪除 GCP 資源或更動資料。
