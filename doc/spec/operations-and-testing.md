# Operations and testing

最新驗證日期：2026-09-11

## Secret bundle consolidation checkpoint（未驗證）

已取得人工安全 gate，同意以較大的 workload IAM blast radius 換取較少的 Secret
版本與管理項目。目標由 8 個 container 收斂為 `janus-postgres-api-bundle`（API／Web／
Pipeline）、`janus-agent-provider-bundle`（Agent／Mart／Ingestion）及
`janus-codex-owners-bundle`（owner UUID keyed auth）三個。2026-09-11 唯讀盤點顯示
現有 6 個 enabled versions；若同一 billing account 沒有其他 project 的 active
versions，依 6-version 免費額度，當下 active-version 儲存費預估為 US$0。收斂主要
降低未來 version 成本與操作負擔，不代表目前已有節費。

程式、向後相容欄位 loader、部署順序與 phased GCP migration／cleanup 腳本已修改；
依使用者要求，本 checkpoint 尚未執行任何 test、lint、shell syntax、build、GCP 寫入、
部署或 runtime acceptance，也未刪除 legacy Secret。下一步必須先完成本機 targeted
驗證，再執行 dev prepare／部署／A-B owner entry isolation 與 runtime probes；全部通過
後才能執行 cleanup。

## WBS-3-ADMIN-POLISH 驗證（2026-09-11）

Admin status／execution item 改為安全結構化欄表格，支援 sticky header、排序、篩選、分頁、欄位顯示與按需子表；source health／collection config 讀取改為 repository-level bounded keyset cursor。股票刪除 guard 現在會檢查 collection config、execution、market、report、fundamental 五類引用，提供結構化 references endpoint、409 引用摘要與 UI 阻擋原因。完整 `python -m pytest -q tests` 為 154 passed，`npm.cmd run test:unit` 為 18 passed，Admin Playwright 為 9 passed。`npm.cmd run build` 的 typecheck 通過，但 lint 被既有 `.tmp` urllib3 worker 與 `services/agent-gateway/dist` 生成檔 56 個 `no-undef` 阻擋；未修改或清理該生成物。未部署 production、未建立付費資源。

最新完整本機驗證：本次 private-pipeline bundle loader targeted tests 為 6 passed；
`git diff --check` passed。WSL／Windows bash 在本環境回傳 `E_ACCESSDENIED`，因此
未能執行 `bash -n`；未以此宣稱 shell syntax 已驗證。

## WBS-3-ACCEPTANCE GCP dev checkpoint（2026-09-11）

唯讀 baseline：project `gen-lang-client-0593591102`／`us-central1`；唯一 Compute
instance `janus-postgres-dev` 為 `e2-micro`、30 GB `pd-standard`、private IP
`10.42.0.5`、無 external IP；無 Cloud Router／NAT／snapshot／VPC connector。Direct
VPC subnet `10.42.0.0/24` 的 firewall 只允許 target tag `janus-postgres-db` 的
`5432`。Cloud Billing API 已啟用；project 已綁定 `open=true` 的 billing account，
現有 budget `tommyGCP_limitAmt` 為 TWD 100。Google API 沒有直接回報此帳戶的
e2-micro／region 剩餘資格沒有逐項額度 API；依本輪驗收判定，billing／Free Tier
dev guard **通過**。此判定不等同 GCP 對帳單為 US$0 的保證。

PostgreSQL acceptance：兩個並行 transaction 對固定 rollback fixture 執行
`FOR UPDATE SKIP LOCKED`，僅一個 worker claim 成功，fixture 已刪除；35 個短暫連線
中 30 成功、5 個收到 `too many clients already`，釋放後 probe 成功。VM reset
後回到 `RUNNING`，`pg_isready` accepting connections，控制面保留 18 executions。

Secret runtime 修正：GCP metadata 重讀確認目前 8 個 Secret，詳見
[`doc/secret_list.md`](../secret_list.md)。ingestion／mart／private-pipeline 已
分別切換至既有 bundle；private-pipeline API image build
`b7d47342-906c-44c0-8eea-cceda10898c7` SUCCESS，digest
`sha256:dcfe5857e6cd95ce6d576a8394ee0f061530e6e03f6ff756115e5b8f1b28a4be`。
Bundle runtime probes：ingestion idle `janus-ingestion-core-2zhhj`、完整 smoke
`janus-ingestion-core-n8mh2`、mart `janus-intelligence-mart-j2hgn`、private
pipeline `janus-private-pipeline-rvmct` 均 Completed=True；完整 ingestion smoke
為 5 檔、12 items、0 failed、1 個合法 sparse empty。

Canary 證據：既有三個成功 execution（`3fb8c93e...`、`29cabcc3...`、
`89a60703...`）各為 5 檔、12 items、0 failed；bundle 修正後手動觸發既有
Scheduler 的 Cloud Run execution `janus-ingestion-core-j5qbv` 及 control execution
`53d7b34d-85a1-45af-ae1a-3ce6245622ee` 亦成功，5 檔、12 items、0 failed、1 個
合法 sparse empty、5 個 source IDs。這次是 scheduler smoke，不計入連續 3 個交易日；
2026-09-11 07:30（Asia/Taipei）的自動排程 execution
`janus-ingestion-core-4zft5` 成功完成資料日 2026-09-10，control execution
`aa86076c-942e-4f2a-8fa9-2455f3753b5f` 為 5 檔、expected 12 items、received 12、
missing 0、158 received rows、0 failed、0 retries，8 個核准 source／dataset health
均為 `success`；Core 為
143 created、0 reused、8 updated。單次 task 約 4 分 31 秒，既有 job 維持 1 task、
1 vCPU、1 GiB、900 秒 timeout、maxRetries 1，未建立或擴大任何資源。post-fix scheduled
canary 目前為 **1/3**；後續只計 distinct 有效資料日 2026-09-11、2026-09-14，對應
Scheduler 執行日 2026-09-12、2026-09-15，週末重複資料日不重複計數。三日完成後再彙整
expected／received／missing、Core hash/date/null profile 與完整成本摘要。

Negative VPC／identity evidence：workstation 對 private IP `10.42.0.5:5432`
的 TCP probe 為 `False`；暫時移除 PostgreSQL VM 的 `janus-postgres-db` target tag
後，Cloud Run execution `janus-ingestion-core-kjsl4` 已確認 `Started=True` 並以
exit code 1 結束，tag 隨即恢復且 VM 仍 `RUNNING`。`janus-private-pipeline` identity
在 ingestion bundle IAM policy 中沒有 `secretAccessor`。第一次未等 task 啟動即恢復
tag 的 execution `janus-ingestion-core-2hz9h` 不列為負向證據。

## P0 WBS 4C acceptance implementation checkpoint（2026-09-10）

本地完成 Gateway handle contract 與 Chat API 串接：Codex 使用
`turn:start`／`turn:events`／`approval`／`turn:cancel`，保存 opaque handle，綁定
owner、logical/native thread、logical/native turn、request 與 params digest；terminal、
expiry、cancel、process error 會清理 App Server、MCP 與 sandbox，部分失敗保留
`CLEANUP_PENDING` 可重試。Chat API 將 gateway event 以既有 Private Storage／event
index 冪等落盤，建立 approval index，SSE 依 gateway cursor 增量同步；OpenRouter／
Gemini 舊同步路徑保留。

本地驗證：`python -m pytest -q tests` 為 150 passed；`npm.cmd run test:unit` 為
17 passed；`npm.cmd run typecheck`、`npm.cmd run build:agent-gateway`、Python
compile 與 `git diff --check` 通過。新增 Chat API contract test 覆蓋 Codex handle、
approval 落盤與 terminal continuation。Flutter 3.47.3／Dart 3.13.3 已準備完成，
`dart format lib test`、`flutter analyze`（無 error，20 個既有 info）與
`flutter test test/widget_test.dart`（2 passed）通過。

GCP dev 已部署既有服務：Gateway revision `janus-agent-gateway-00041-fn`，image
digest `sha256:8c1d0f3f1da04e1f4a336eec0ab97c088afdeb692f4c5a2957001e1ba2aa846b`；
API revision `janus-api-00048-x6x`。Gateway 仍為 `min=0`、`max=1`、
`concurrency=2`、`timeout=300`；本 revision 僅增加 dev-only
`CODEX_SANDBOX_MODE=read-only`，預設 `workspace-write` 與 OpenRouter／Gemini 舊路徑
保留。Gateway image build `0ec796ff-4bc6-4704-aa44-d18e703d9e23` SUCCESS。

owner B `auth_mode=chatgpt` 已重新登入，本機 App Server
`account/read(refreshToken=true)` 回傳 account，並上傳至既有
`janus-codex-owner-b` enabled version 7；owner A 版本全數 destroyed。新 revision
Codex approval live probe `cc5fecfa-b0e4-46f8-be22-391b96e2e15d` SUCCESS：產生真實
`approval_request`、錯誤 native-turn binding 被拒絕、accept 後 command completed、
decline 後沒有 completed command。此前安全 workspace command 直接
`turn_completed` 的 probes 僅作 root-cause evidence，不作 approval evidence。
probe 後 Cloud Build worker 臨時 IAM 已清空，暫存 probe 檔案已刪除。

獨立的 `google-user-client-id` Secret 不存在，但既有
`janus-postgres-api-bundle` 內已有 `google_user_client_id`；bundle 內目前沒有
`google_user_client_secret`，因此 Chat API 的真人 Google OAuth E2E 尚未完成。
OpenRouter/Gemini live build `7d661ef6-3ac5-4dd3-9f69-080966746ad0` SUCCESS；MCP
allowlist 後的 job 仍只有 readiness、未留下 application log，故本次 MCP execution
與完整整合仍未宣稱通過。Private Storage broad Cloud Build 因安全審核拒絕整個
workspace upload 而未重跑，保留本機 150 tests 證據；SSE reconnect 仍待 Chat API
真人 OAuth 路徑驗證。

## P0 WBS 4C acceptance checkpoint（2026-09-09）

Provider live probe Cloud Build `fd435461-71fc-4b8f-86bf-e583431900c5` SUCCESS：
GCP dev gateway signed OpenRouter `openrouter/free` 與 Gemini `gemini-2.5-flash`
dispatch、continuation metadata 與事件中的 API key redaction 均通過；worker
temporary IAM 已清理。

Grounding-enabled gateway revision `janus-agent-gateway-00034-g7l`（digest
`sha256:cf488f313aaa0c598034aecca679a141d0f1cf8024e357bc6487292727b68d98`）完成
部署；Cloud Build `31b2f8ac-25fa-4bbb-aca2-46c2ea3210aa` SUCCESS，實際驗證
OpenRouter streaming 與 Gemini Google Search Grounding citations／usage。
Approval／quota／stream contract Cloud Build `7960f7b5-e1fe-4b63-86cb-50d4b878a8fd`
SUCCESS，涵蓋 Agent Gateway、Gemini、OpenRouter 與 engine-security tests。

Private Storage／privacy／delete contract regression Cloud Build
`275ec264-0dde-46d7-b755-c49ad90b870e` SUCCESS，沿用 containerized API image
執行 `tests.test_assistant_storage`。

GCP dev Cloud Build `a4b5179a-81c2-4688-8558-19656d15ef91`（context sources）、
`115d9d6b-271d-4bf5-b85b-5d3210aa6b57`（Private Storage／Skills）與
`4e481c84-ac3f-4e78-8dad-6758c549cfa7`（Web bundle）均 SUCCESS。MCP transports
在 gateway revision `janus-agent-gateway-00032-k8r` 的 dev-only concurrency=2
驗收中 stdio／Streamable HTTP／legacy SSE、dynamic tools、redaction、timeout、
cancel、disconnect 全部通過；驗收後已恢復 concurrency=1，Job `janus-mcp-acceptance`
已刪除。Gateway 最終 revision `janus-agent-gateway-00033-22h`，acceptance image
digest `sha256:ac1139d7ab5c848c1d5f313069789530303cea1e78faaf95f654e16c6640ce8d`。

Codex managed-auth retry deployed gateway revision `janus-agent-gateway-00035-xtq`
with `@openai/codex@0.153.4` (Cloud Build `75fa29cf-7dfb-4176-9235-0c2ca5a9f0b5`
SUCCESS). Live POC build `ca212276-2dde-4ce1-bbdf-6982c3d943a2` still returned
HTTP 400 `Google API request failed (400)`. A fresh dev device-code probe
`e7b91774-8682-4077-8f5d-d50054d9640d` reached the gateway but returned HTTP 400
`failed to request device code: error sending request for url
(https://auth.openai.com/api/accounts/deviceauth/usercode)`, so no verification code
was produced for the required human approval step. Managed-auth／approval live flow
therefore remains blocked by the upstream auth request; temporary IAM was removed
after both probes.

Follow-up GCP dev diagnostics narrowed this to the Codex Linux App Server rather
than general egress: Cloud Build `6b838dc2-faa2-4eb3-aa3d-594ae02d852a` resolved
and reached the endpoint (GET 405), and `9a251707-c075-40d2-9f32-a6c75eb11023`
received a valid POST device code (`200`). Direct App Server probe
`eff86a80-a94a-44da-af76-0f1efccef287` on Linux `0.153.4` still returned the same
request error. No auth workaround or API-key fallback was introduced; the remaining
action is an upstream Codex CLI/device-auth compatibility fix or an approved newer
runtime release.
An isolated alpha probe of `0.154.0-alpha.10.2` (`e04655d7-28bd-47fa-9a28-8fa98bf61358`)
reproduced the same App Server error, so it was not adopted.
OpenRouter／Gemini 既有成功 probe 仍可參照前述 runtime dispatch evidence。為配合
2026-09-09 approval-handle remediation deployed revision `janus-agent-gateway-00038-j78`
(`sha256:74d2d17903b75ec5540a0150a3f00eb7cbb4a5496888c153c31ce59bcff33f05`) with
`concurrency=2`, `maxScale=1`, and `minScale=0`. Live owner-B turn on the dev
service returned an opaque `turnHandle` and a real shell `approval_request`; the
human-approved `accept` was routed back to the same Codex bridge, produced
`approval_resolved`, command `exitCode=0`, and `turn_completed`. The side effect
created `approved.txt` containing `JANUS_APPROVAL_SIDE_EFFECT`. An initial binding
mismatch was safely rejected, then fixed by separating Janus and Codex native thread
ids before the successful rerun. This validates the dev-only live approval flow;
the in-memory handle remains process-bound and is not a production durability claim.
現行 provider bundle，MCP acceptance 改讀 `mcp_owner_signing_key` 欄位，不建立新
Secret。

2026-09-09 device-auth remediation：Gateway runtime image 已安裝
`ca-certificates` 並設定 `CODEX_CA_CERTIFICATE=/etc/ssl/certs/ca-certificates.crt`；
`verificationUrl` 亦納入 login-start 安全回傳欄位。Cloud Build
`0baeea94-9174-4ceb-9acd-b968e50759dd` SUCCESS，image digest
`sha256:d4cc395510db6216ca518946c167767b9a1ef1679c405dae9c06f910e2192845`，
Cloud Run revision `janus-agent-gateway-00036-2s6`。真人 device-code login
Cloud Build `a98d47f9-508a-4fd6-ae80-4f6c6831d39a` SUCCESS，回報
`device login authenticated`；既有 bridge live verify Cloud Build
`8d3e76c9-7025-442d-ab4c-e9b6dde8db17` SUCCESS，checkpoint reconnect、
cancellation、logout／destroy 通過。驗收後已移除暫時 Cloud Build Secret accessor
與 invoker impersonation IAM。Approval 的真人 side-effect turn 尚未執行，WBS
4C 整合驗收仍未結案。

## P0 WBS 4C Skills（2026-09-06）

GCP dev Cloud Build `262243c4-1323-4eea-80a5-48d1c631be7b` 使用既有
`scripts/gcp/cloudbuild-private-storage-verify.yaml`，在 containerized API image
內執行完整 `python -m unittest tests.test_assistant_storage`，結果 SUCCESS。
驗證涵蓋 Skill manifest validation／credential fail-closed、assistant event
owner isolation／delete、PostgreSQL index contract 與 Codex deletion cleanup
guard；未部署 Cloud Run、未建立新資源，亦未呼叫 Artifact Analysis／Container
Scanning／occurrence API。

## P0 WBS 4C Codex auth lifecycle checkpoint（2026-09-06）

GCP dev Cloud Build `a44a6463-3e76-4d31-b784-84337ea9af88` 通過 Agent Gateway
TypeScript build 與 targeted Vitest；`f1ee3054-7d2f-4bdf-ae61-6f82b0ccfdf3`
通過 private-storage/deletion contract；修正後 `d5301537-af3f-42ac-876a-4587f916b493`
再通過 Gateway build、Vitest 與 Bash syntax。

本次使用 A/B owner Secret 部署 revision `janus-agent-gateway-00026-s8h`，image
digest `sha256:ee1bfd630b6ac2fb1912b764030ef0e866c41c078c60040799e51041d0345db0`，
設定為 `min=0`、`max=1`、`concurrency=1`。Cloud Build
`b131ee1a-cea5-44d2-97f8-04e0d04ef183`（A）與
`7c478c2a-7a5b-4f38-b7f3-146fbad2d237`（B）均 SUCCESS，完成各自 owner-bound
managed-auth load／refresh、cancellation、checkpoint replay、logout／session
eviction 與 destroy retry；兩個 owner Secret version 最終均 destroyed，證明
A/B Secret isolation。互動式 device-code login 的真人瀏覽器流程尚未驗收。

人工 gate 通過後建立 `janus-codex-owner-a`／`janus-codex-owner-b`（各自
`us-central1`、僅保留 dev fixture），並部署 Gateway revision
`janus-agent-gateway-00019-qvv`，image digest
`sha256:dc28e2f4abc51bdad685afea7dcbc6e89f525fdc4cc02f50f6d39d84c5a25daa`。
Live Cloud Build `9f7da474-8a16-457e-a84c-510c06fddb88`（A）與
`a3ef9a23-bd83-482b-ad40-d0802090b129`（B）通過 owner-bound run、cancellation、
GCS checkpoint replay；`eb45609e-e101-4b2c-8349-7d2b233d0b31` 通過 A destroy
兩次冪等後，`c5e69d10-2427-4cf7-af03-935d286ca53c` 證明 B 仍可獨立執行。
更新 logout endpoint 後部署 revision `janus-agent-gateway-00019-qvv`，
Cloud Build `1084498e-0d2f-481f-aa9a-762e1c5ca033` 通過 B run、logout／session
eviction 與 destroy retry；A／B Secret 版本最後均為 `DESTROYED`。Gateway 維持
`concurrency=1`、`maxScale=1`、`minScale=0`。

## P0 WBS 4C runtime dispatch acceptance (2026-09-09)

GCP dev Gateway revision `janus-agent-gateway-00029-5hk` 完成 OpenRouter／Gemini
signed dispatch live probe；Cloud Build `20050302-861a-4c84-84ad-c96f21903776`
結果為 `openrouter dispatch passed`、`gemini dispatch passed`、`DONE`。Codex
既有 POC bridge 由 Cloud Build `9dec1039-0052-420d-9ef1-6719ed46991a`
完成 health、owner-bound login／checkpoint reconnect、logout／session eviction、
destroy retry；checkpoint 為 `60ddd412-f367-4ac9-a5c6-8bbcd6f29e08`。

驗收期間暫時授予 Cloud Build provider bundle accessor 與 dev invoker
Token Creator，完成後均已移除；Gateway 維持 `min=0`、`max=1`、
`concurrency=1`。目前證據包含 Codex POC checkpoint、OpenRouter／Gemini
gateway probe，以及 `tests/test_chat_api.py::test_codex_message_round_trips_gateway_continuation`
的 message → gateway → 下一 turn continuation contract evidence。GCP dev 的
三-runtime 整合重跑仍屬 WBS-4C-ACCEPTANCE，不在本切片宣稱完成。

## P0 WBS 4C MCP Host implementation (2026-09-06)

GCP dev PostgreSQL migration `015_private_mcp_servers` 已套用並以
`private.mcp_servers` 存在性驗證。新增 Secret Manager secret
`janus-mcp-owner-signing-key`，僅授予 `janus-agent-gateway` 與 `janus-user-api`
runtime accessor；未輸出 secret payload。

Cloud Build `fe522ef7-0aed-4739-b7cd-a6fdd5b00c1f` 成功建置 Agent Gateway；最終
dev revision `janus-agent-gateway-00011-d78` 使用 immutable image digest
`sha256:a9e0aad9746c2144368b9808ed3b250e26309e268ab4f805c3049e8e2bbc2d78`。
API Cloud Build `1a0151d4-1ad6-479b-9179-dcbab72cf02e` 成功建置；dev revision
`janus-api-00018-jm9` 使用 image digest
`sha256:ad6ef02c255be4c7666db8869879f6745c75a8c0c3a0760639aaf004a99a3894`。

GCP dev fixture 為私有 Cloud Run `janus-mcp-fixture`，最終 revision
`janus-mcp-fixture-00008-zn5`、image digest
`sha256:7c1258a509c773b1e8b64b3573024033d7a26e36a6a9183a7bfa15c6c7124b3e`，維持
`maxScale=1`、`concurrency=80`、scale-to-zero；gateway 維持 `maxScale=1`、
`concurrency=2`、scale-to-zero。正式 acceptance 在 GCP dev Cloud Run Job
`janus-mcp-acceptance-p7kpf` 通過，Job 完成後已自動刪除。

Acceptance Cloud Build `2bad0afc-ca51-4eb7-abfb-fa05a4a38440` 建置 runner；結果：
stdio `discover=modern/call=ok`、Streamable HTTP `discover=modern/call=ok`、legacy
SSE `discover=legacy/call=ok`、secret structured-content redaction、timeout、
`tools/list_changed`、並行 cancel 與 disconnect 均為 `ok`。有效 HMAC、owner-scoped
tool grants、invalid config／credential boundary 亦已驗證；secret payload 從未輸出。

## P0 WBS 4C Context Sources（2026-09-06）

GCP dev Cloud Build `92131984-c36e-4755-9c20-9f37ba3cea12` 成功完成 source list、
Janus Core／Private Mart preview、opaque context reference、owner/thread isolation、
resolve 與 invalid selector/SQL 驗收。API 最終為 revision `janus-api-00016-4bv`，image
digest `sha256:3e702dac14143d478b7eb11925c8bff4c40c8826f28b4b0907d4228ab55871f9`。

驗收腳本在 Cloud Build worker 內建立的兩個暫時 Token Creator binding 已清理；
`janus-user-api` 對既有 Core catalog password Secret 的 dev read-only accessor 依授權保留。
本機新增 API 測試因 host 缺少 FastAPI runtime 未能 collection；既有 targeted tests 為
13 passed、1 項因 host 缺少 `zoneinfo`／`pytz` 而失敗。腳本 `bash -n` 與 `git diff --check`
通過。

## P0 WBS 4C Cloud Runtime POC（2026-09-06）

Agent Gateway image 使用 immutable digest
`sha256:3aada7f674da8f18d7362b4b02b99c435a78154006ad648b0bb2e5e240bb39e1`。
GCP dev Cloud Run service `janus-agent-gateway` 的 acceptance revision
`janus-agent-gateway-00005-gxb` 通過 100% traffic 驗收；完成後為恢復成本設定建立
`janus-agent-gateway-00006-fj5`，目前為 `min-instances=0`、`max-instances=1`、
`concurrency=1`。

Cloud Build `bfbe9024-6a24-4452-8ca7-a717314813da` 在 GCP worker 內完成 health、
Codex managed auth、workspace-write sandbox、turn cancellation、process stop、
Private GCS checkpoint 與 cursor reconnect。POC response 為 Codex `0.153.0`、
`authRotated=false`、checkpoint
`b36ed5c5-c833-40d0-994f-8c06f8f1862a`、`cancelled=true`、
`process=stopped-after-response`；checkpoint replay 與空 cursor replay 均通過。

驗收期間只暫時授予 Cloud Build identity 對專用
`janus-agent-poc-invoker` 的 `roles/iam.serviceAccountTokenCreator`，build 完成後已
移除；本機未直接呼叫 Cloud Run URL 或使用 proxy。此前為處理 GFE 間歇性 500，驗收
worker 的 health warm-up 改為最多 10 分鐘；最終以 `min-instances=1`、`max-instances=2`
驗收成功後，已回復為上述 scale-to-zero 設定。Codex App Server 仍屬 POC，未宣稱
production-ready。

## P0 WBS 4J 個人工作台實作（2026-09-05）

新增最小 FastAPI User service、獨立 Google User OIDC audience boundary、以 Google
`sub` 對應 UUID 的私人 PostgreSQL repository，以及 journal／notes／watchlist／export／
deletion typed endpoints；client `user_id`、錯誤 issuer／audience／expiry 均拒絕。
Ledger 為固定精度 append-only event，修正使用 reversal／replacement；筆記正文直接寫
Private Iceberg，PostgreSQL 只留索引與 artifact reference。

Private pipeline 依 persisted checkpoint 批次 upsert ledger、note reference、watchlist
與四個 user Mart；移動平均成本納入費稅，缺價保持 null，Iceberg 全部成功後才推進
checkpoint。另加入獨立 private bucket lifecycle、runtime service accounts／PostgreSQL
roles、50-symbol 全域 guard 與 Iceberg-first 可重試刪除流程。最小 Flutter 啟用關注、
記帳／筆記與我的，不加入券商、自動下單、排行榜或 FIFO。

Cloud Build `aa011f3a-b96d-42da-a99e-7bd445eb4a92` 驗證 bash syntax；
`c8a1d829-6898-4bf3-8f08-50c24b94a258` 在一次性 PostgreSQL 16 套用 001–014；
`4f85bf89-ef44-4cab-b8bf-76a448b6bd0c` 通過 Flutter analyze 與 widget test。
Dev migration `014_private_workspace` 已套用，PostgreSQL image digest 為
`sha256:28989610fdf7ce9e379df0554c224b5fe13e7c36b5c32c4fc9522aa528cff0c8`。
User API build `edf6fa7e-cab7-4432-b1cf-3f6c7580daf3` 成功，dev revision
`janus-api-00004-p4q` 使用 image digest
`sha256:487cf1a2824a8126679b9d4eb6b2cff03b86572c4c87805c666c43bdff34ff75`；
`/health` 200、無 bearer 與錯誤 audience 均 401。

兩個 Google OAuth 測試帳號完成真人登入，取得不同內部 `user_id`；A 建立 2330
watchlist 後，B 看不到該列、刪除收到 404，A 仍可讀。PostgreSQL 只讀驗證為 2 users／
2 distinct `google_sub`／2 distinct `user_id`，active watchlist 僅屬 1 user。OAuth client
ID 與 private DSN 的 BOM 已移除；dev DB API 密碼已輪替，Secret 第 1 版已停用，Cloud
Run 固定使用第 2 版。真人 journal／note／Private Iceberg artifact 完整交易情境已由下方
GCP dev acceptance 完成；公開 `mart_scoped_analysis` 尚未產生，個人化 overlay 維持未啟用。
未部署 production。

## WBS 4J complete transaction acceptance (2026-09-05)

GCP dev Web revision `janus-web-00057-h52` served the A/B acceptance page. Two
Google User OAuth subjects resolved to distinct internal users. The acceptance
covered idempotent BUY replay, reversal/replacement correction, cross-year BUY／SELL,
fees／taxes, CASH_DIV／STOCK_DIV, oversell rejection (409), note revision, and
cross-user history／note／correction／revision isolation (B returned 0 rows and 404).

Private pipeline execution `janus-private-pipeline-srmnn` advanced checkpoint 23→46;
the subsequent batch `janus-private-pipeline-kmc7m` advanced it to 54. Metadata
hashes changed for all seven private tables after the latest batch. Deletion request
`cffb8921-1f22-411b-8497-70bfdf8dad85` completed in
`janus-private-pipeline-n7ml8`; PostgreSQL reported `COMPLETED`, A's user／ledger／note
rows were absent, and B's user row remained. No public catalog tables were modified.

## P0 Admin 股票資料狀態（2026-09-03）

股票資料狀態表已顯示 Core 最新日期、精確 row count、coverage 比例、逐欄 null
count／ratio、既有 DQ、來源、snapshot 與 quarantine 摘要；Core reader 使用 bounded
aggregate 計數，不再把最多 200 筆的明細頁誤當總筆數。沒有 persisted quarantine
計數時明示未提供，未新增或校準 DQ 規則。Collection 操作改為「選取股票 → 加入收集
佇列 → 最近執行」，成功送出會清除暫存選取並切至 execution 追蹤。

Targeted Python 48/48、Vitest 2/2、Playwright 6/6、TypeScript typecheck、ESLint、
Web production build 與 `git diff --check` passed；未操作 GCP、未部署。

## P0 五檔 Scheduler canary 觀察（2026-09-03）

Cloud Scheduler `janus-ingestion-daily` 維持 `ENABLED`、`30 7 * * *`、
`Asia/Taipei`。2026-09-03 07:30（Asia/Taipei）準時觸發 Cloud Run execution
`janus-ingestion-core-8mvg4`，使用既有 immutable image
`sha256:673d74bd2da1798f7d581e45e1142deb986ed284950a4ea7f8ffe63642aa1186`；兩次 task
attempt 均失敗，persisted execution IDs 為
`629adfdc-63c5-4608-92e3-bc8cb6e0108f` 與
`74aeeff7-fd33-43bc-b6e7-d8cead2b0ad8`。五檔仍為
`1102／2327／2330／2381／4958`；`twse-valuation`、`twse-institutional` 收到 HTTP
307，`mops`、`twse-events` 收到 HTML，整體正確標記 failed，未誤報成功。retry 的
freshness guard 略過已完成的 7 項，未重複寫入 Core。

相同 image 的前一日 Scheduler execution `janus-ingestion-core-485bg` 於
2026-09-02 07:30 成功；四個官方 endpoint 在 2026-09-03 11:02 再次唯讀檢查時已回
HTTP 200，故目前記為上游排程時段異常，不修改程式或手動補跑。連續成功計數重置為
0/3，下一個交易日繼續觀察；尚未產生可結案的三日 expected／received／missing、
8 來源、Core profile 與成本摘要。

## P0 WBS 3 第一個可獨立驗收切片（2026-09-02）

Web build `311b584b-82f7-4b4b-9277-1737d9f159f9` 成功；dev revision
`janus-web-00037-g25` 使用 immutable image
`sha256:90dd2684a4b23c7d14c91b9113b9bd9c57c0550b07bbcc9e3405aa56555b5d44`，
實際 URL `https://janus-web-2oo7qbkd5q-uc.a.run.app`。2026-09-02
10:47–11:40（Asia/Taipei）以短效合成 session 完成 live Playwright：390px
responsive、恰有七個資料營運 tabs、Collection 可見，Analysis action／Mart／AI
Prompt 不存在；Analysis API 回 400 且 execution IDs 前後不變。HTML／Admin API responses 未出現 raw payload、object
URI、secret、完整 upstream error 或 traceback。Admin status／execution／source
health 查詢前後 persisted source health 完全相同，證明查詢未呼叫上游。

ingestion dev image 為
`sha256:673d74bd2da1798f7d581e45e1142deb986ed284950a4ea7f8ffe63642aa1186`。
五檔 `1102／2327／2330／2381／4958` 的 2026-08-28 單日 backfill execution
`312bcec0-453f-46eb-9caf-2bd633d23edb` 由 Cloud Run execution
`janus-ingestion-core-g26kr` claim，4m32.71s 後 succeeded：8 個來源、11 個 Stage
payload、11 metadata、11 manifest、0 quarantine、1 Core commit fence，
`failed=0／empty=1／created=0／updated=114／reused=289`。Admin detail 為 12 個
success／fallback／合法 empty items，安全訊息只包含 `Core committed` 或
`source returned no rows`；五檔股票 status 均可查，2381 當次 persisted row count
為 0，未在 UI 補值或誤報成功。

同日 replay execution `ac61b175-01cf-456b-982a-6c5e33fa9b53` 由
`janus-ingestion-core-8cvrh` claim，4m58.22s 後 succeeded；Stage／fence 數量相同，
`created=0／updated=0／reused=403`，證明 replay 未增加 natural-key rows。null 不覆蓋
有效值由完整 pytest 的 null-preserving merge regression 通過。受控 failure execution
`cfd83043-c8aa-4ce8-bff9-8cc3ab34b881` 經既有一次 retry 後為 `failed`、
`retry_count=2`、`error_code=COLLECTION_FAILED`，Admin response 無 traceback 或完整
error，未誤標成功；partial item 狀態由 framework regression 驗證。

Stage cleanup 於 2026-09-02 15:47–15:50（Asia/Taipei）以相同 immutable ingestion
image 執行；Cloud Run execution `janus-ingestion-core-fvltp` 與 persisted execution
`4e134da7-2a6d-488f-a704-b9c78b1cb87d` 均 succeeded。retention 經 Admin API 與 audit
由 30 天暫改 1 天後，三個 cleanup items 分別刪除 18／9／18 個 Stage objects；清理後
三個 Stage prefix 均為 0 objects，三個 `core-commit.json` immutable fence 均保留。
既有 failed execution `cfd83043-c8aa-4ce8-bff9-8cc3ab34b881` 未成為 cleanup candidate，
狀態維持 failed。retention 已透過相同 API 恢復 30 天、`cleanup_enabled=true`、version
3，兩次異動均由 `tommylin15@gmail.com` 留下 audit。

Web 設定維持 `minScale=0`；Cloud Monitoring 04:02Z 顯示 final revision 的 active／
idle instance 均為 0，實際 scale-to-zero 通過。本切片已完成；下一項為連續 3 個交易日
Scheduler 驗收，完整 DQ 校準與其他 WBS 仍未宣稱完成。
未部署 production、未建立新資源或提高限額，且未呼叫 Artifact Analysis／
Container Scanning／occurrence API。

## P0 Iceberg schema evolution tests (2026-08-31)

Core Iceberg regression 驗證 additive nullable 欄位會取得新 field ID，既有 field
IDs 保持穩定；舊 rows 對新增欄位回傳 null，既有 snapshot 保留且仍可讀。
不相容型別變更會在 commit 前被拒絕，不產生新 snapshot 或改寫既有資料；欄位語意
或單位改變仍依契約建立新 table version。Iceberg targeted pytest 5/5、完整
`python -m pytest -q tests` 98/98、適用的 Python compileall 與
`git diff --check` passed；本切片未操作 GCP。

## P0 2330 Source → Stage → Core → Admin integration (2026-08-31)

本機 integration regression 以 injected 2330 TWSE source fixture 建立 persisted
collection execution，驗證 raw／quarantine Stage objects、Core materialization 與
Admin HTTP status query。Admin 結果涵蓋 latest Core date、dataset coverage、row
count、DQ warning count、quarantine count，以及 persisted execution／provenance
關聯；response 不含 raw payload、object URI、secret、完整 upstream error 或
traceback，Admin query 期間 source adapter 呼叫數不增加。

同日 replay 維持單一 Core natural-key row 與相同 content hash，且 incoming null
close 未覆蓋既有有效值。Targeted pytest 11/11、完整 `python -m pytest -q tests`
96/96 與適用的 Python compileall passed；未操作 GCP，既有 dev migration
`009_admin_cursor_indexes` 未重複套用。

## P0 Admin cursor dev migration (2026-08-31)

PostgreSQL migration `009_admin_cursor_indexes` 已套用至既有 dev VM
`janus-postgres-dev`。`control.schema_migrations` 已記錄該 version；
`control.executions_admin_page_idx` 的實際定義為
`CREATE INDEX executions_admin_page_idx ON control.executions USING btree (requested_at DESC, execution_id DESC)`。
PostgreSQL readiness 回報 accepting connections，VM／container 暫存 migration 檔案均已清除。

套用前後的唯讀資源盤點一致：project `gen-lang-client-0593591102` 只有既有
`us-central1-a` `e2-micro` VM 與單一 30 GB `pd-standard` boot disk，VM 只有
private IP `10.42.0.5`、無 external IP；snapshot 與 Cloud Router／NAT 清單為空。
未重建 image、未重啟 PostgreSQL container、未建立額外雲端資源，且未部署
production 或呼叫 Artifact Analysis／Container Scanning／occurrence API。

## P0 Mart runtime connectivity (2026-08-31)

PostgreSQL build `36823a97-1ef1-4046-9700-37223be1bdf0` 產生 immutable digest
`sha256:6fe7049c87c07429ab4eb8563a704ff9d54951dbe28338e1ac657b2ae50ebd51`；
migration `008_mart_runtime_roles.sql` 已建立 non-superuser／non-createdb／
non-createrole／non-replication 的 `janus_mart_catalog` 與
`janus_mart_publication`，HBA 僅允許 `10.42.0.0/24` TLS 連線。

Mart 修正版 build `9a94e089-a89b-4e44-9351-3c9fb166b569` 產生 digest
`sha256:cbd336ace6629c1a78769673ad5415f0d6475a42766510f9b9ef2ea7d24fd007`。
Cloud Run Job `janus-intelligence-mart` 使用專用 service account、Direct VPC
`private-ranges-only`、`janus-intelligence-mart` network tag、固定 Secret version 1、
1 CPU／1 GiB／300 秒 timeout／1 retry。Execution
`janus-intelligence-mart-hd86r` 成功；catalog／publication 皆回報 private address、
bounded privileges `ok`。第一次 execution `janus-intelligence-mart-rpwjj` 只因
PostgreSQL 回傳 CIDR 形式 `172.17.0.2/32` 被驗證器誤判，已以 `ip_interface` 修正並
留下 regression test。臨時 VM Secret IAM 已撤銷，local／VM credential temp files
均已清除。

Cloud Scheduler `janus-ingestion-daily` 目前只呼叫 `janus-ingestion-core:run`；Mart
尚未排程。WBS／todo 已要求 ingestion DQ／Core commit 成功後由
`core.dataset.ready.v1` workflow／event 觸發 Mart，不得以同時獨立排程取代依賴。

Google login handoff 在驗證 ID token 後，以短效簽章 handoff 完成同源 POST；第二段
回應使用 `303 See Other`，在同一 response 設定 HttpOnly session cookie 並導向
`/admin/stocks`。不得使用零秒 meta refresh，以免瀏覽器在 cookie 提交前先載入
Admin、被誤判未登入而退回 `/login`。Auth 專項 7/7 與全套 78/78 tests passed。

## P0 Web runtime deployment (2026-08-30)

PostgreSQL migration `007_web_runtime_roles.sql` 已套用至 dev，Web control role
對明確列出的 control tables 使用一致的 SELECT／INSERT／UPDATE／DELETE 權限；
catalog role 對 catalog metadata 為 SELECT-only，且
`default_transaction_read_only=on`。實機權限查詢結果為
`catalog_write_tables=0`、`control_dml_missing=0`。兩個 role 均不是 superuser、
createdb、createrole 或 replication role。

PostgreSQL build `da62fdb1-f3f5-4436-bc28-0a18edd4e9ac` 的 immutable image digest
為 `sha256:f81ef216a81b003edd6b319cb2ab04f65b453c34c1fae09d8cf7f44e9de993b7`。
Web build `5d919396-ad8a-490e-a07c-30c33c3060bb` 的 immutable image digest 為
`sha256:1be0cb5e7cb5056fc2805de3eb9f44214cb969d13e991186872ad39cb32e8123`；
Cloud Run revision `janus-web-00023-ccj` ready 且承接全部 dev traffic。

Cloud Run 保持 `allUsers` invoker，由 application middleware 執行 allowlist session
驗證。未登入 smoke：`/health` 與 `/login` 回 200、`/admin/stocks` 轉址至
`/login`、Core API 回 401；短效合成簽章 session smoke 對 Admin 與
`/api/v1/core/2330/summary` 均回 200。revision ERROR log 查詢無結果，證明 Web
runtime 已透過 Direct VPC private path 使用專用 control/catalog credential。

Web catalog Secret 目前只保留 version 3 enabled，先前版本已 disabled；Web session
Secret 只保留 raw-byte 驗證為 48-byte ASCII、無 BOM 的 version 4 enabled，versions
1–3 均 disabled。Secret 值沒有寫入 repository 或正式驗證輸出；後續輪替必須依
`doc/runbook-dev-deploy.md` 的 raw-byte、runtime、disable-old-version 順序執行。

## Dev delivery automation and artifact retention (2026-08-28)

Terraform is no longer a repository or deployment dependency. Dev bootstrap is
performed by the explicitly authorized, idempotent
`scripts/gcp/provision-dev.sh`; it verifies the fixed PostgreSQL Free Tier shape
and does not create a missing PostgreSQL VM automatically.

Automatic runtime deployment is owned by three regional GCP Cloud Build
Developer Connect triggers, all restricted to branch `^main$` and component
paths:

- `janus-ingestion-core` (`5e201f5a-c206-4006-92b9-40a53c4155ed`):
  `jobs/ingestion-core/**`, contracts, observability, and `cloudbuild.yaml`.
- `janus-intelligence-mart` (`b8215cb9-1823-401d-b293-65fbdf73ce30`):
  `jobs/intelligence-mart/**`, contracts, observability, and `cloudbuild.yaml`.
- `janus-web` (`c08067dd-5c44-414f-9e8d-9d94e89b4089`): `apps/web/**` and
  `cloudbuild.yaml`.

Documentation-only and `scripts/gcp/**` changes do not trigger runtime builds.
The former two triggers were deleted before these three current triggers were
created. `.github/workflows/deploy-dev.yml` is manual-only (`workflow_dispatch`)
and restricted to `main`; its repository variables are
`GCP_WIF_PROVIDER` and `GCP_CI_SERVICE_ACCOUNT`. No long-lived service-account
JSON key is used. A path-matching push has not yet been used as end-to-end
evidence for the new trigger set; automatic trigger acceptance remains pending.

The last directly verified runtime deployments remain Cloud Build
`baf5b915-ee80-477b-8ec8-dc1e981fc23a` for ingestion-core at
`sha256:16248df5e95afea4cc099016c4c6e1722eade307b53d2065514f7d517f596e8e`
and `e021a691-2a0e-42eb-bffd-b25c2ee2ead2` for web at
`sha256:6746d5985e60781bda04b1965d980e0651c82dd30e7026344e1b30908221cd74`.
The `janus-intelligence-mart` trigger and Cloud Run Job now exist. Manual build,
immutable deployment, Direct VPC, Secret Manager, and database smoke acceptance
passed; a path-matching automatic trigger run remains pending.

Artifact Registry repositories `janusai-poc` and `janus-postgres` use the same
active cleanup policy with dry-run disabled: each image package keeps only its
most recent version, while older tagged and untagged versions are eligible for
deletion after one second. The old untagged PostgreSQL digest
`sha256:8dfe6976ca822f87a6ba42743bb0f841d4bee3352a66816d663f2bc0961f7c4e`
was permanently deleted; `postgres:16.15` remains at
`sha256:6fe7049c87c07429ab4eb8563a704ff9d54951dbe28338e1ac657b2ae50ebd51`.
Artifact Analysis and Container Scanning remain disabled and were not called.

## P0 Admin follow-up (2026-08-28)

Admin now has persisted settings and immutable audit metadata in SQLite and
PostgreSQL migration `006_admin_settings_audit.sql`, with optimistic version
checks. The source catalog API/UI exposes cadence, coverage tier, retention,
authorization status, and max-symbol quota; candidate/blocked enabled configs
are rejected. Stock status details expose the aggregate Core summary,
including latest date, row count, DQ warnings, and quarantine count when the
read-only Core runtime is connected. The existing Direct VPC Web Cloud Run
service has access to the control/catalog Secret Manager containers; no secret
values are committed or invented.

Frontend Vitest and Playwright configurations/tests were added. Dependencies
were not installed in this restricted environment because the npm registry
request stalled; browser discovery returned no available in-app browser.
Local HTTP smoke returned 200 for `/health`, `/admin/stocks`, and the Admin JS
asset. Python discovery ran 63 tests successfully; Python compileall,
JavaScript syntax, and git diff checks passed. Terraform is no longer part of
the repository or validation path.

## P0 Query／Admin application layer (2026-08-28)

`packages.web_api.CoreQueryService` is the read-only Core application boundary.
Dataset identifiers are allowlisted, symbol/date values are parameterized, and
pagination is bounded. It exposes row count, latest date, null profile, and
quality flags without returning Stage payloads. `apps.web.server` provides a
Cloud Run-compatible WSGI boundary with safe 4xx/5xx responses and a health
endpoint; runtime database wiring remains an explicit deployment configuration.

`packages.admin_api.AdminService` provides bounded stock search, enabled/delete
operations, queued collection/analysis triggers, recent execution/detail views,
and effective-time membership views. It delegates FK/reference protection,
candidate/blocked source rejection, and core-50 limits to the control plane;
collection work is never executed in the request path.

`/admin/stocks` now provides the first responsive Admin Data Operations UI:
10-row stock pages, cross-page selection, separate collection/analysis enqueue,
the latest 50 persisted executions with on-demand safe details, persisted source
health, and effective-time core membership editing. Runtime PostgreSQL wiring,
typed schedule/source authorization editing, audit/optimistic concurrency, and
browser interaction coverage remain open acceptance conditions.

UI acceptance may run against a local browser/Playwright environment or against
the existing GCP dev Cloud Run service when a real runtime is required. After
the manual billing gate has been satisfied, the existing dev service may be
started on demand without separate per-run approval. The cloud path must verify
the actual dev URL, responsive and interaction behavior, Admin API/runtime
connectivity, and safe output; evidence records the Cloud Run revision,
immutable image digest, test URL/time, and scale-to-zero state. This authorization
does not cover production deployment, higher resource limits, or new paid GCP
resources.

Source health summaries are now available from both SQLite reference and
PostgreSQL control adapters. Migration `005_source_health_telemetry.sql` adds
bounded aggregate coverage, cache, fallback, schema-drift, and tier fields;
raw upstream payloads remain excluded.

Validation for this change: 10 focused Admin/API tests passed; JavaScript syntax,
Python compileall, and diff checks passed. Full discovery ran 58 tests: 56 passed
and only the two existing PyIceberg tests failed to import because `pyiceberg` is
not installed. Browser discovery returned no available local browser; visual
interaction remains pending and may be completed through the authorized GCP dev
Cloud Run acceptance path above. No cloud deployment or paid resource was
created.

## PostgreSQL dev/MVP topology

Development PostgreSQL is a self-managed Compute Engine `e2-micro`
VM in `us-central1`, with private networking, no external IP, at most 30 GB
Standard Persistent Disk, and IAP／OS Login. The dev VM is provisioned at private
IP `10.42.0.5`. Free Tier mode does not create scheduled snapshots, backups, HA,
or replicas and is not a production HA decision. Cloud SQL is not part of the
selected dev topology.

The Free Tier target also limits outbound data to 1 GB/month. Eligibility is
evaluated by billing account and region; the resource limits do not guarantee a
zero bill.

## PostgreSQL control integration

`PostgreSQLControlPlane` is the production repository for control metadata. It
uses injected bounded connections, transaction-scoped writes, server-side
statement/idle timeouts, transition checks, and `FOR UPDATE SKIP LOCKED` queue
leases. Response cache payloads remain in GCS; PostgreSQL stores only URI,
hash, TTL, observed time, and state. The migration is idempotent and includes
expiry/health indexes and pruning support. Ingestion private-IP authentication
and control-symbol reads are validated; Web and Mart paths remain pending. The
Trino replacement is complete in the development runtime. No production
deployment was performed.

Provisioning gate: PostgreSQL VM, PostgreSQL repository/migration, private
connectivity, control/catalog schema bootstrap, and PostgreSQL readiness must
pass before a Cloud Run DuckDB runtime deployment is attempted.

DuckDB runs embedded in the Cloud Run ingestion Job and reads/writes Iceberg
data and metadata in GCS. PostgreSQL remains the control DB and SQL catalog
metadata store; it does not store Iceberg data files. The VM has only 1 GiB RAM
and is reserved for PostgreSQL control/catalog metadata.

The source control contract separates `market_wide`, `core_focus`, and
`market_macro` coverage. Collection configs persist cadence, scope,
authorization status, retention class, PII, republishing permission, and a
maximum symbol count. Historical coverage membership is append-only with
effective timestamps; `core_focus` is capped at 50 symbols. Candidate or blocked
sources are rejected before queueing, while source IDs remain available in the
contract for later approval review.

Artifact Registry cost guard: image push/pull, immutable digest, metadata and
cleanup only. Artifact Analysis API, Container Scanning API, vulnerability
scanning and occurrence APIs are prohibited; no scanning API was called during
this change.

## P0 資料控制面與 Ingestion Framework

- Python unit/contract tests：42 targeted tests passed；`compileall` passed；`git diff --check` passed。Full discovery remains blocked only by the local environment missing `pyiceberg` for two existing DuckDB/Iceberg tests。
- Python compileall：passed。
- Control schema：SQLite reference implementation covers stock master with
  collection-reference protection, dataset collection config, separate
  collection/analysis queue commands, persisted execution/items, response
  cache, incremental cursors, and source-health telemetry.
- Execution statuses：queued、running、retrying、succeeded、partial、failed。
- Item availability：success、empty、partial、fallback、stale、unavailable、
  schema_drift、failed。
- Adapter framework：sync/async `SourceAdapter`, bounded timeout, exponential
  backoff, retry-after support, per-source rate limiting, exact schema-drift
  detection, safe error taxonomy, and no raw upstream error persistence.
- Cache/incremental：market-scope responses share one market/day batch key;
  symbol-scope responses retain the exact start boundary; successful primary
  observations advance a cursor with configured overlap. Partial/fallback/stale
  responses are not promoted to successful cache entries.

## P0 Stage／Core

- Python unit/contract tests：39 passed（含 Stage/Core、DuckDB/Iceberg、framework/control、contract、DB session timeout 與 sparse-empty semantics）。
- Python compileall：passed。
- gcloud bootstrap guard：PostgreSQL `e2-micro`、30 GB、固定 zone 驗證通過。
- GCP Developer Connect triggers：三個 component trigger 已建立；新的 path-matching push acceptance 尚待驗證。
- Artifact Registry：兩個 repositories 均啟用 keep-latest-1 cleanup policy，dry-run disabled。
- Cloud Build images：`d6f62619-eba6-47b2-b238-c1057774a611` 與
  `fcbae728-f254-458e-8475-0c69b3e5a34f` 均成功。

Stage writer 使用 immutable create-if-absent、SHA-256 content hash、受控 ID、
去敏 source URL、execution manifest 與 quarantine sidecar。Core DQ 覆蓋
required key、type、date、duplicate、unit、range、schema drift、null-preserving
merge、欄位語意 zero 與極端漲跌保留警示。

2330 Stage → Core closed loop：`ingestion_core.sources` 提供 TWSE／TPEx OHLCV
normalisation；`pipeline.run_2330` 建立 persisted collection execution，將 raw
payload／sidecar／quarantine 寫入 Stage，使用 Core DQ materialise deterministic
OHLCV rows，並透過 event sink 發出 `core.dataset.ready.v1`。Core summary 保存
row count、content hash、date coverage、null profile、warning/quarantine count
與 provenance ID。重跑使用 Stage create-if-absent 與 null-preserving merge；真實
Cloud Run／VM restart smoke、GCS production object 與 PostgreSQL workload connectivity
仍待 runtime deployment 後驗證，未在本次變更中宣稱完成。

排程 Stage lifecycle 已加入 execution-scoped 模式：payload、sidecar 與 manifest
置於 `executions/{execution_id}/stage/`；Core 成功後以 immutable
`executions/{execution_id}/core-commit.json` 作為清理 fence。清理只接受已有
commit marker 的指定 execution，未 commit 的失敗／重試資料不會被刪除。Cloud
entrypoint 預設啟用此模式，並可用 `PREVIOUS_STAGE_EXECUTION_ID` 指定要清理的前次
成功 execution；Scheduler runtime 與雲端清理 smoke 已完成，詳如下方驗收紀錄。

2026-08-26 runtime smoke 已完成：Cloud Run executions
`janus-ingestion-core-6w8v9` 與 `janus-ingestion-core-vxtcp` 成功；前者輸出
8/8 sources、0 failure、Core reused 79,262，後者以前者的 commit fence 完成
Stage cleanup，前次 `core-commit.json` 保留。Cloud Scheduler
`janus-ingestion-daily` 現為 `ENABLED`，`30 7 * * *`、`Asia/Taipei`。Admin UI／
control DB settings 維護介面仍待後續；完整 incremental merge 已由 DuckDB
runtime 驗收。

DB-backed 五檔 runtime smoke `janus-ingestion-core-nbql7` 成功：從 control DB
讀取 `1102`、`2327`、`2330`、`2381`、`4958`，8 個來源產生 10 個 Stage
objects，`failed=0`、`core_created=0`、`core_reused=419`。FinMind 的 `2381`
與 TWSE events 在該窗口無資料，明確保存為 2 個合法 `empty`，不掩蓋 HTTP／
解析等真正失敗。Direct VPC ingress firewall 使用 private subnet
`10.42.0.0/24` 作 source range，只開放 target tag `janus-postgres-db` 的 5432；
Scheduler 驗收後恢復為 `ENABLED`。

2026-08-28 Trino → DuckDB cutover completed in development. Clean-image
canary `janus-ingestion-core-lngkm` completed in 4m38s with `failed=0`,
`core_created=0`, `core_reused=420`, and `core_updated=0`; the preceding
functional canary `janus-ingestion-core-89q6z` completed with `failed=0` and
`core_created=420`. Both runs read the five configured symbols
(`1102`, `2327`, `2330`, `2381`, `4958`) from the control DB and used the GCS
Iceberg warehouse `gs://gen-lang-client-0593591102-dev-core/warehouse/`.
The final image is
`ingestion-core@sha256:2e72c2a4e39188577e505a215557ebba797e8c5a08d3832243637be8b4fe64af`.
The SQL catalog migration creates the `janus_control.catalog` tables and
PyIceberg-compatible public updatable views; catalog Secret version 3 was
byte-verified against the private `janus_catalog` connection. Trino service,
build trigger, image, rollback tag, and old ingestion digest were removed;
Artifact Registry cleanup is active with dry-run disabled.

Job 亦支援 `INGESTION_DATE` 單日 replay，或以
`BACKFILL_START_DATE`／`BACKFILL_END_DATE` 執行最多 367 個日曆日的 bounded
range replay；`INGESTION_DATASETS` 可限制資料源。每次 replay 都使用新的 execution
ID，並沿用相同 Stage → Core commit fence。

2026-08-28 Web dev deployment：Cloud Build
`fd229529-e8c0-44c4-b0c3-2ef03c1aa691` 使用最小 build context 成功建立並 push
Web image，digest 為
`sha256:a42178256596da6bc0403f9f1bda45bac486da1788c3339ed78a98c2a085be40`。
Cloud Run revision `janus-web-00001-dvz` 已在 `us-central1` ready，使用
`web-runtime`、Direct VPC `private-ranges-only`、`janus-web` network tag，且未
開放匿名存取。Web runtime 已具備可選 PostgreSQL／Iceberg wiring；因尚未配置
Web 專用 control/catalog credential，該 revision 目前使用 safe fallback，DB
connected Web/Admin smoke、Mart Job runtime 與 authenticated HTTP 驗收未宣稱完成。

本機 Python 3.12 已安裝 `duckdb==1.5.5`；`python -m unittest discover -s tests`
結果為 59 tests passed，`compileall` 與 `git diff --check` 通過。

同日 authenticated HTTP smoke 已完成：Cloud SDK `cloud-run-proxy` 已安裝，
`janus-web-00002-472` custom audience 更新後，direct URL 與 localhost proxy
對 `/health`、`/admin/stocks`、`/assets/admin.css` 均回 HTTP 200。Cloud Run
仍為 user Invoker-only，未開放匿名；Token Creator 暫時 binding 已撤銷。

## P0 Core 第一批資料源

`ingestion_core.first_batch` 提供可重播的 credential-free JSON adapter，涵蓋
TAIEX／TPEx benchmark、PE／PB、法人、MOPS／FinMind financials、公司事件與
market activity（融資融券、借券、當沖、注意／處置、issued shares、turnover
等以 metric／unit 表示）。Normalizer 會保留 null 與原始單位，不對缺資料推算；
benchmark collection 與個股行情 collection 分離。`effective_trading_day` 對週末、
休市日與盤前執行回看最近有效交易日。所有 adapter transport 可注入 fixture，
raw payload 仍由 Stage/GCS 層保存，control database 僅保存 cache metadata；SQLite
reference 與 PostgreSQL adapter 均提供 bounded prune。第一批資料源的線上 upstream
API smoke 與實機 workload connectivity 仍需部署後執行。

Cloud Run ingestion Job 已以官方 TWSE／TPEx／MOPS OpenAPI 與 FinMind request
完成第一批 8 個來源的 Stage → Core 雲端 smoke；目前由 embedded DuckDB
寫入 GCS Iceberg。Execution
`janus-ingestion-core-n88jc` 為 8／8 Stage、0 failure，建立／重用合計 79,262
個 natural-key rows，並以來源／觀測日聚合成 8 個 Core partition objects（27.38
MiB）。同日 replay `janus-ingestion-core-nxmwc` 為 `core_created=0`、
`core_reused=79,262`，object count 維持 8，證明 create-if-absent partition commit
不產生重複資料。07:30 `Asia/Taipei` Scheduler 已 ENABLED；前次 Stage cleanup smoke
已完成。

## 2026-08-31 — P0 schedule／backfill／retention dev 驗收

GCP Cloud Build 驗證通過：Python 101 tests；Web Vitest 2、Playwright 5、typecheck、
ESLint 與 production build；PostgreSQL transaction／migration targeted build
`af628b6f-354d-4d68-93df-8c616976f11a`。全程未啟動 WSL。

dev migration `010_execution_runtime_options`、`011_control_settings_ownership` 與
`012_first_batch_source_ids` 已套用。`janus_control` 擁有 `admin_settings`、
`admin_audit` 與其 identity sequence，仍為 bounded non-superuser role；
`first-batch.source_ids` 使用 canonical provenance IDs。

scheduled execution `janus-ingestion-core-jmh8d` 成功，control execution
`dd8ad090-1daf-4522-94a9-6fc5bb8c9862` 為 `succeeded`，正式來源 items 保存
`Core committed`。指定 `2026-08-28`、`2330`、`twse` 的 queue backfill execution
`7362712f-5acf-4c5e-afd8-45fa33268c9e` 經 `janus-ingestion-core-kt9mq` 完成；
valuation 1 row、institutional 3 rows、market-activity 3 rows 已 commit，events 為
合法 empty。ingestion image digest 為
`sha256:ad00a77389beb4a636088e0b6ec9e0ba4fc2b371216d547865b97a599fd9342a`。

實機 smoke 同時發現並修正 PostgreSQL read transaction 在 upstream I/O 期間觸發
10 秒 idle-in-transaction timeout 的問題；repository 現以 autocommit 處理 reads，
write paths 仍使用 explicit transaction。Web dev `/admin/stocks` 未登入回 303 並導向
`/login`。Cloud Scheduler 維持 `30 7 * * *`、`Asia/Taipei`、enabled；Admin 變更
排程時間的自動 Scheduler reconciliation 仍列為後續工作。

## 2026-09-03 — Admin 狀態、來源、排程、版本與登入

Admin 股票資料狀態已改為 bounded aggregate；資料源設定提供 typed edit，並由後端
拒絕啟用 `candidate`／`blocked` 來源及以 authenticated actor 留下 audit。排程設定
成功同步既有 Cloud Scheduler 後才提交 control DB 版本。`/health` 回傳 Cloud Run
revision 並顯示於 Admin；Google 登入可解析 Google GSI 與 Janus session 並存的
cookie，登入期間顯示可存取的 loading 狀態，成功後不保留登入頁 history。

核心 50 使用 `coverage_membership_versions` 保存單調版本與 effective time，membership
rows 保留不可變更歷史 interval；PUT 以 expected version 防止 lost update，actor 只取
authenticated Google email，audit 保存原因與 added／removed diff。UI 會把下一版最低
生效時間推進一分鐘，避免重送相同 effective time；51 檔輸入在 live UI 被拒絕且版本
維持 v3。

GCP dev PostgreSQL build `04fdc438-e079-4182-9b1f-6a77675f06ca` 成功，migration
`013_membership_versions` 已套用既有 private PostgreSQL。Web build
`2873d608-74b3-4409-9c11-e4cf3638b800` 成功；revision `janus-web-00049-ws5` 使用
immutable digest `sha256:5c7db6bbb62b97105113d50f72cb5b494fd38fa61350b6a9c601ac10232c384d`。
真人 Google login 後依序建立 v1 `2330`、v2 新增 `2327`、v3 移除 `2330`；三版
effective interval、`tommylin15@gmail.com` actor、原因、版本與 audit diff 均由
PostgreSQL 實查確認。

dev-only `core-focus-smoke` 沒有固定 collection symbols；Cloud Run execution
`janus-ingestion-core-t72bf` 使用既有 ingestion digest
`sha256:b8840e7c456c3cafe3fee340c8ec3ebbee032c50c5be7ce9a74450bc7f0fea54` 成功。
persisted execution `9ffb6fb9-345f-47ac-a45d-0fdf7f12d8e5` 的
`requested_symbols=["2327"]`、status `succeeded`，MOPS financials 收到 28 rows 並
`Core committed`，證明 worker 依 v3 最新有效名單執行；smoke config 驗收後已 disabled。

驗收後資源 guard 仍為單一 `us-central1-a` `e2-micro`、30 GB `pd-standard`、private
IP、無 external IP；未部署 production、未建立新 VM／disk／snapshot／NAT，亦未呼叫
Artifact Analysis、Container Scanning 或 occurrence API。

## P0 WBS 4C Private Storage (2026-09-06)

Cloud Build contract `2b49fbbc-1dde-4091-9664-7ba33447f2ac` succeeded. PostgreSQL
image build `96ec69fc-5c1a-4b65-97de-cda22b57cba6` produced digest
`sha256:b7f927ea03656eda2c311d77004078efa8379242a3b7fa3ff413c9ec153a1216`;
IAP migration on `janus-postgres-dev` passed migration 016, A/B owner isolation,
event replay, role privilege and credential-column checks in a rolled-back test
transaction. Existing private-pipeline execution `janus-private-pipeline-wwxtl`
passed real GCS/Iceberg event／Skill isolation and cleanup using random owners.

The temporary Job image was restored to the existing `janus-api` digest
`sha256:ad6ef02c255be4c7666db8869879f6745c75a8c0c3a0760639aaf004a99a3894` and the
acceptance flag was removed. Codex managed-auth cleanup remains explicitly
`CLEANUP_PENDING` until an owner-scoped external credential cleaner exists.
