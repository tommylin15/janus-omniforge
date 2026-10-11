# 手動 CEO／Provider 操作

舊五角色 provider 批次已移除；`MART_AI_ENABLED` 不再能啟動日常角色呼叫。
手動 CEO command、owner-scoped status/history、capability/quota/profile、取消與雲端終態核對的程式接線已加入。完成狀態仍以 CI、migration、真實 provider 與候選區驗收為準，不能把程式存在當成已上線。

User API 使用 Google user token；Admin API 使用獨立 Admin token：

- `GET /api/v1/me/analysis/{symbol}`：五個 persisted deterministic specialist 基準與同日／同 Core 市場比較；開頁不呼叫 provider。
- `GET /api/v1/me/analysis/{symbol}/ceo`：有界 immutable CEO history、material change、資料 freshness 與 capability。
- `POST /api/v1/me/analysis/{symbol}/ceo`：帶 `Idempotency-Key` 的明確分析指令；backend 核對使用者、profile、quota/cooldown、in-flight、來源 hash 與日期。重送相同 key 不再次派送。
- `GET /api/v1/me/ceo-requests/{id}`、`POST .../{id}/cancel`、`POST .../{id}/reconcile`：只處理本人 execution。核對需真實 Cloud Run completion evidence；未知狀態不當失敗、不盲目重送。
- `GET /api/v1/admin/analysis`、`GET .../compare?symbol=2330`：基準／版本、已保存前後比較、profile history、capability 與 safe usage/cost audit；無研究品質證据不開放 promotion。
- `PUT /api/v1/admin/analysis/capability`、`PUT .../profiles/{profile_id}`：optimistic version、稽核原因、既有 approved model allowlist。還原是另存新版本，不改舊 execution。

Migration `051_analysis_product` 新增可重建 serving projection 與不可變 request/report/version history。預設 profile 未核准、capability 未啟用；Mart 不取得交易／持股表讀取權。五角色正常路徑仍為 0 LLM token；未驗證機率保持 null。市場比較不以 private watchlist 代替 liquid-500。

CEO 使用既有獨立 `mart-ceo-provider` 映像。受限 Job 已核准，方案見 `../ops/ceo-worker-plan.json`；固定 1 CPU／1 GiB、單 task、480 秒、0 retry，沿用 Mart 網路與身份，沒有 Scheduler。

2026-10-11 使用者指定最小上線路徑：CEO 只呼叫 Gemini `gemini-3.5-flash-lite`，直接沿用 `janus-runtime-bundle` 的 `gemini_api_key`，不新增／複製 Secret。使用者已確認 AI Studio API 專案為 Free tier。Job 設定 `MART_CEO_GEMINI_ONLY=true` 與 `MART_GEMINI_FREE_TIER_CONFIRMED=true`；bounded manual router 只執行 Gemini、固定最新 Lite、單次最多 120 秒且不重試／fallback。原 profile 與 request history 保留；execution audit 額外記錄實際 policy、模型與 token usage，未知 cost 不補 0。額度耗盡時失敗，不切付費模型。

先前暫時恢復的 `janus-mart-codex-auth` 已依使用者要求刪除；本路徑不讀取 Codex auth。Shared Codex adapter 未部署，omniAgent 統一 AI 入口後置。既有三模型 profile 仍可讀取；舊 Gemini 模型保留在 allowlist 以避免破壞不可變歷史，CEO 的實際 Lite override 明列於 execution audit。API 0% candidate、live CEO immutable report、Jobs／正式流量 gate 仍須驗收。Job 更新保存前一設定與 image；舊 dedicated Secret 已不存在，設定 rollback 不代表舊 Codex 功能可用。

官方模型契約：[Gemini 3.5 Flash-Lite](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite)。

## 集中驗收／正式 dev 發布

1. 完成全部產品程式與 `/ponytail-review`；GitHub Actions 對完整 SHA 跑全套 Python（含隔離 PostgreSQL ACL／併發）與 Flutter tests/build。
2. 發布四個既有 component 的 public GHCR digest；獨立 `ghcr-ceo-worker-build.yml` 只接受同 SHA 的成功 full release run，將 CEO tag 寫入既有 public Mart package，不建立 GCP 資源。
3. `serving-schema-migration-dev.yml` 的 051 透過固定 hash SQL、現有 ingestion identity 執行 additive migration，避免「新版 image 需要 migration、migration 又需要新版 image」循環；050／051 都需真實 ACL/readback evidence。
4. 新 CEO Job／Job-scoped API execution+read IAM、費用／免費剩餘額度及必要 OAuth 由使用者核准後處理。先完成真實 cold-start／refresh、最少 bounded provider call、persist/readback、owner/cancel/duplicate／failure gate。
5. API 0% candidate、Jobs 各自 fence/canary/rollback；同一工作包一起驗五角色、CEO、Admin、持股／首屏及四頁 authenticated browser。所有 gate PASS 才移轉正式服務的 dev 流量。

任何 gate 為 partial／unknown／blocked 都保留原正式流量；500 檔歷史模型研究後置。權限種類以 [Google Cloud Run IAM](https://docs.cloud.google.com/iam/docs/roles-permissions/run) 為準，API binding 只限這個 CEO Job，不授予 project-wide Run Admin。

日常五分析師操作見 [Specialist engines](spec/specialist-engines.md)。歷史 provider 授權／驗收程序見 [封存紀錄](archive/mart-provider-runbook-before-specialist-removal-2026-10-03.md)，不得再照封存指令執行舊五角色。

## 報告格式與額度變更

CEO 回覆必須通過 `packages/analysis_models.py` 的 CEO output model；有 provider 回應或 token usage 仍不代表報告成功。提示詞須直接列出 JSON schema、必填欄位與格式範例，包含 stance、thesis／missing_information、claims／evidence IDs、五份 validated specialist hashes；API structured-output schema 同時保留。拒絕格式時不建立有效 report hash、不覆寫歷史，只保留安全 audit；不得記錄原始回覆或憑證。

每日額度上限改為 50 時，先經既有 GitHub Actions migration 路徑套用 `052_ceo_daily_quota_50`，再部署支援 50 的 API／Admin，最後保存本人 capability 並 readback。這是上限與帳號設定兩個步驟；migration 不自動提高任何帳號額度。最新使用者要求為每日 50、冷卻 300 秒，適用進度以 operations checkpoint 為準。
