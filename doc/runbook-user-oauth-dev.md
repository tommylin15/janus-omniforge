# Dev User／MCP OAuth Runbook

本 runbook 只描述目前 Janus parallel-live `dev` 的 User OAuth、MCP OAuth 與 owner-isolation 驗收程序。`dev` 是真實個人使用環境，不是 disposable POC；實際 source、env、Secret reference 與部署參數執行前一律以 GitHub `main` 與 GCP runtime 查證。

最新 OAuth／MCP acceptance 狀態見 [`todo.md`](todo.md) 與 [`spec/operations-and-testing.md`](spec/operations-and-testing.md)。歷史 migration／舊 Secret 名稱／舊 revision 不在本文件保存。

## MCP 外掛功能與平台邊界

Janus Dev Private 與 Janus Dev Read-only v2 共用 Cloud Run MCP／OAuth tags。2026-10-09 使用者要求撤除 MCP 個人交易／股息寫入：server tools/list 只列三個 read tools，舊 `janus_private_ledger_append` 呼叫必須回 Unknown tool，新 `janus.private.write` 授權必須拒絕。外掛舊描述或 ledger-recording skill 不構成使用授權；需由原外掛來源更新／重新載入，不能只修改安裝 cache。

Cloud Run endpoint 是遠端服務；Codex 的本機外掛安裝不會自動讓 ChatGPT 網頁／手機 App 取得相同外掛。ChatGPT 網頁版應使用已設定的遠端 Read-only v2 連線。依 [OpenAI 官方平台限制](https://help.openai.com/en/articles/12584461-developer-mode-and-mcp-apps-in-chatgpt)，自訂 MCP apps 目前只支援網頁，不支援 ChatGPT 手機 App；手機瀏覽器的網頁操作仍需實機驗收。

## 1. 安全邊界

- User 與 Admin OAuth audience 必須分離；不得拿 Admin token 當 User token。
- MCP OAuth 只提供 Janus 已授權的 read-only domain context；typed selector、limit、date range、owner scope 由 server contract 限制，不接受任意 SQL、GCS URI、object path 或 client-supplied user identity。
- Secret payload 不得出現在 argv、shell trace、process listing、Cloud Build substitution、deployment metadata、UI 或 log。
- 真實 Google login、allowlisted owner、Cloud Run API、PostgreSQL／Iceberg owner isolation 才能構成 live acceptance；mock verifier／fixture 只補 deterministic regression 與 negative coverage。
- OAuth／MCP partial success 不得包裝成完整 acceptance。

## 2. Google OAuth client

User Web client 必須使用 Janus User audience，並包含目前實際 UI／callback 所需的 authorized origins／redirect URIs。不要從歷史文件複製固定 URL；執行前以目前 Cloud Run tagged URL、Flutter build config 與 Google Auth Platform 設定交叉確認。

公開 client ID 可作為 Flutter Web build-time configuration；client secret、MCP signing material、database credentials 必須走目前 Secret bundle，不寫入 source、README 或一般 config。

### Codex Desktop 的本機 MCP callback

Codex OAuth client 為 `https://chatgpt.com/oauth/codex/client.json`；本機 callback 為 `http://127.0.0.1:<port>/callback`，未固定設定時 port 由 OS 選擇。Janus 修正限定此精確 client 才可使用 IPv4 loopback callback，要求合法明確 port 與精確 `/callback`，拒絕其他 hostname、userinfo、query、fragment 與路徑。Authorization 與 token exchange 使用同一檢查，authorization code 仍綁定原始 callback／client／resource 與 S256 PKCE。

這個 loopback URL 是 Janus → Codex 回呼，**不加入 Google OAuth 的 redirect URIs**。Google → Janus 的 callback 仍為目前 issuer 加 `/oauth/google/callback`。發布前必須核准此 client callback allowlist 擴充；本機 tests 通過不代表 live 已支援。Consent CSP 只對這個已驗證的 Codex callback 加入該次精確 loopback origin，保留其他 CSP 限制。

MCP tag 修復使用 `.github/workflows/ghcr-mcp-route-dev.yml`，人工 dispatch 的 `release_run` 必須是候選 request 指定 SHA 的成功完整 GHCR publication run。此流程只將既有 `mcp-oauth`／`mcp-adapter` tag 指向既有 0% GHCR candidate，保留 canonical traffic 與其他 tag；透過共享 Actions concurrency 與 Git-ref lease 互斥，鎖內核對 Trigger disabled／無 ongoing builds、digest、Ready、min instances=0、build identity、Codex pre-login 302／非法 loopback 400／未授權 MCP 401。失敗時讀回原路由，回復不明則保留 lease；人工 recovery 使用該 run 的非敏感 routing artifact，禁止強制解鎖。這個 pre-login gate 不等於 owner consent／token exchange／private tool live PASS。

## 3. 目前 Secret 模型

目前 `scripts/gcp/deploy-dev.sh` 對 `janus-api` 使用整合後的 `janus-runtime-bundle`，以 `JANUS_API_POSTGRES_BUNDLE` 注入 runtime；Jobs 也使用同一 bundle 的對應 runtime env。不要再依照舊文件建立 `google-user-client-secret`、`private-database-url`、`postgres-private-api-password` 等分散 Secret 作為新的 canonical path。

Rotation／修改前：

1. 先從目前 Cloud Run／Job template 與 [`secret_list.md`](secret_list.md) 唯讀確認 bundle 名稱、enabled versions、consumer references。
2. 任何 bundle 變更都視為共享 runtime credential 變更；先評估 API、private pipeline、ingestion、mart 與 migration consumer 的影響。
3. 新 version 建立後，以 raw-byte／schema 方式驗證，不輸出 payload；候選 runtime 驗證成功後才停用舊 version。
4. 目前 deployment script 使用 `janus-runtime-bundle:latest`；若要改成 pin numeric version，屬於 runtime config／deployment 行為變更，須另開實作工作，不能只改本 runbook 假裝完成。

## 4. User API／MCP OAuth deployment

API deployment 走 [`runbook-dev-deploy.md`](runbook-dev-deploy.md) 與 `scripts/gcp/deploy-dev.sh api`。目前 script 要求 Flutter build-time `GOOGLE_USER_CLIENT_ID`、`GOOGLE_ADMIN_CLIENT_ID`，並可在 `MCP_OAUTH_ENABLED=true` 時要求：

- `MCP_OAUTH_ISSUER`
- `MCP_RESOURCE_URL`
- `GOOGLE_USER_ALLOWED_EMAILS`

OAuth issuer 必須使用目前 `mcp-oauth` tagged URL，MCP resource 必須使用目前 `mcp-adapter` tagged URL；不要在文件固定某次 revision。候選 deploy 使用 no-traffic／tag 路徑，先驗證 metadata、authorization challenge、MCP initialize／tool schema、negative guards 與受影響的 authenticated path，再切 canonical traffic。

部署或 allowlist 修正後，至少記錄 Git SHA、image digest、revision、UTC 時間與實際 acceptance result 到 [`spec/operations-and-testing.md`](spec/operations-and-testing.md)。

## 5. Refresh token acceptance

目前 contract 包含 `offline_access`、refresh-token rotation／revocation 與 inactivity expiry。驗收時不要讀 token 值；只驗證行為與 bounded metadata：

1. 新授權後能建立有效 refresh state。
2. access token 到期後，client 能透過 token endpoint refresh，而不重新進入 Google authorize flow。
3. rotation 後 active refresh state 不無界增加，舊 token 不再可重用。
4. revoke／expired／wrong client／wrong scope 等 negative path fail closed。
5. server log、DB query、tool output 不洩漏 token／secret payload。

## 6. A/B owner-isolation live acceptance

A/B acceptance 必須使用兩個真實 allowlisted Google owner，分別建立／登入各自 Janus identity。驗收目標是證明 authenticated private context 由 server-side owner identity 隔離，而不是由 client 傳 `user_id` 控制。

最小流程：

1. Owner A 登入，確認自己的 profile／private records／MCP private context 可讀。
2. Owner B 重新登入並建立自己的 Janus owner state；B 的 private API／MCP 只看到 B 的資料，不得看到 A 的 positions、performance、trades、profile 或其他 private artifacts。
3. 嘗試已知 A identifier 時，B 必須得到 404／403／bounded empty 等契約允許的隔離結果，不能洩漏 A payload。
4. 切回 A 再次確認 A 仍只看到 A 的資料。
5. wrong audience、unauthenticated、invalid selector／limit／date range 等 negative cases 照 contract fail closed。
6. 只記錄 internal owner IDs 的必要對照、revision／digest、UTC timestamp 與結果；不要記錄 bearer／refresh token 值。

目前是否完成這個 A/B gate，只看 `todo.md` 與最新 operations evidence，不因本 runbook 存在就視為完成。

## 7. Migration 與資料保留

OAuth／private schema 變更必須走 repository 的版本化 migration。不要重跑已被取代的 bootstrap migration，也不要從歷史 runbook 推測現在應套用哪個 migration number。

對 existing dev database：

- 先查 `control.schema_migrations`／目前 schema；
- 只執行尚未套用、且屬於本次核准 WBS 的 additive／approved migration；
- 執行後驗證 marker、role／constraint、runtime readiness 與 owner isolation；
- 不刪除歷史 private data 或已套用 migration，除非另有明確不可逆操作授權。
