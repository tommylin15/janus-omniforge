# Janus CEO → omniAgent P0-V Gateway（獨立整合）

更新：2026-10-13。此工作只授權 Janus CEO 請求鏈；**不解除持股／Private Recalc P0 的 PAUSED BY USER**，不重啟四個排程 Jobs、不修改已存在的交易帳本、不切換正式 API／omniAgent Gateway 流量。

## 目標與實作

Janus 手動 CEO API 依既有 capability、profile、quota/cooldown、latest validated baseline 與 Specialist hashes 產生 `private.ceo_requests`。既有 `janus-ceo-analysis` Job（仍使用 `intelligence-mart@...` 身分，保留原有 PostgreSQL/GCS 存取）藉由 Google IAMCredentials **受限 impersonation** 取得專用 `omniagent-codex-market-client@gen-lang-client-0593591102.iam.gserviceaccount.com` 的 audience-bound ID token，向 omniAgent Gateway 0% 試驗標籤 `POST /v1/gemini/execute` 發起單次 `project=market-mart` 請求。Gateway 經已存在的 Gemini Flash-Lite 服務回傳文字。

Janus 只接受 HTTP 200、`status=completed`、相同 project/ownerId/requestId/model 和有界非空 text，並在 Janus 原有 `OUTPUT_MODELS.ceo` Pydantic JSON schema 解析後，**再執行原有 `validate_ceo_output` 的 five hashes、evidence/PIT/numeric claim 檢查**。成功才依原機制寫入 immutable GCS JSON、readback、再將 report/hash 寫入 `private.ceo_requests`；FAIL/BLOCKED 不產生報告。Gateway 沒有 canonical number／publication authority。

- Provider 實作：`jobs/intelligence-mart/intelligence_mart/provider_routing.py` 的 `OmniGatewayGeminiProvider`，只在 CEO bounded manual 且 `MART_CEO_GEMINI_ONLY=true` + `MART_CEO_GEMINI_VIA_OMNIAGENT=true` 使用；**不讀 Janus Gemini API key**；不影響正常 deterministic Specialist（0 LLM）。
- Job 設定：`scripts/gcp/ceo_worker_template.py`，既有 `janus-ceo-analysis`、1 CPU／1Gi、480 秒、maxRetries=0、無 Scheduler，pilot URL pinned；`ceo_worker_deploy.py` 僅允許這兩個環境變數的可審計增補，保留原有身分、網路、Secret 與 rollback。
- Gateway 固有硬限制：prompt UTF-8 **≤8192 bytes**、單次模型產生 **≤512 tokens**、回覆文字長度 **≤32000**；超過 prompt 閾值拒絕，**不能截去金融事實或數字**。512 tokens 不保證能產出完整 CEO JSON，未通過驗證不得稱 SUCCESS。缺少 response schema 原生強制能力是 upstream P0-V Gateway contract 限制，不宣稱本次已解。
- Fail-closed：身分不可 impersonate、錯誤 audience／project／owner／request/model、429／timeout／空文字／JSON 不符、baseline 過期／權限取消均不落有效報告；無自動重送 uncertain execution。只保存安全錯誤分類與 usage（如有），不存 Gateway provider text、Bearer、API key。
- Gemini model 固定 `gemini-3.5-flash-lite`；不新增付費模型／計費資源。Gateway 的 model 成功不等於帳單免費，需要獨立核對授權與用量。

## 驗收關卡（不要互相代替）

1. **程式與安全回歸**：`tests/test_mart_provider_routing.py`、`tests/test_ceo_worker_template.py`、`tests/test_analysis_product.py`。包含錯誤路由、偽造 response、schema、owner/request identity、超長 input、無 retry、傳統直接 Gemini 與 DB 不回歸。
2. **身分與 Gateway read-only preflight**：`.github/workflows/ceo-omniagent-p0v-preflight.yml`。檢查原 Job SA、target Gateway 0% tag、Gateway `roles/run.invoker` 與專用 market caller 的 `roles/iam.serviceAccountTokenCreator`。不需要新金鑰、不能靠 CI 自己 impersonation PASS 代替 Worker runtime 授權。
3. **GHCR 完整 Release**：原有 `ghcr-publish-dev.yml` 同 SHA Python/Flutter/full test，並建置專用 CEO image；失敗不進入 Job rollout。API 0% 候選必須遵守原 Release/lease、完整 SHA、GHCR digest 及自動 OAuth 負測。
4. **真實工作鏈**：先驗證 Mart Worker 實際 impersonation，僅從現有 capability 授權的新 `QUEUED` 手動 CEO request 執行一次；readback Worker final status、Gateway requestId、schema accepted、`report_hash`、immutable GCS 與 PG、錯誤無資料洩漏。未知終態**不得重送**，報告 `PARTIAL`（缺資料）也不能寫成全數 PASS。最後驗證 API 認證讀回同一 immutable history。
5. **部署邊界**：omniAgent pilot `gemini-p0v-b03e5f55` 是 **0%**，不是正式 route。因 Cloud Run Job 沒有 Service 0%-traffic candidate，只能做 digest-fenced 的無 Scheduler canary／受控更新及可復原路徑；未證實 IAM 不得更換既有 CEO Job image，未達 CEO E2E 不得正式切流量。

## 目前實證與 blocker

- 上游 omniAgent 同 Gateway 候選來源 `b03e5f55...` 的三個 **CI impersonated** caller P0-V PASS：[omniAgent #38357794169](https://github.com/tommylin15/omniAgent/actions/runs/38357794169)。這不是 Janus 工作容器的 E2E。
- Janus [read-only 身分閘門 #38362885044](https://github.com/tommylin15/janus-omniforge/actions/runs/38362885044)：CEO Job／Gateway 相關 describe 階段可走，但 `janus-ci@...` 對專用 market service account **缺 `iam.serviceAccounts.getIamPolicy`**，無法讀證是否具 `roles/iam.serviceAccountTokenCreator`；真實 runtime impersonation **UNKNOWN／BLOCKED**。不得無授權擴 IAM。
- 此切片需繼續依 exact SHA CI、Release／部署及 live receipt 更新狀態。此前持股 P0 停止指令維持生效；本文件不是任何完成聲明。
