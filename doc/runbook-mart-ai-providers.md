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

CEO 必須使用獨立 `mart-ceo-provider` 映像，既有 `mart-specialist` 不增加 Node/Codex。資源方案見 `../ops/ceo-worker-plan.json`（未核准）；`scripts/gcp/ceo_worker_template.py` 從現有 dev Mart 建立 private local template，固定 1 CPU／1 GiB、單 task、480 秒、0 retry，沿用既有網路與身份，沒有 Scheduler。Codex 使用既有 `codex_auth.auth_session` 的 PostgreSQL account lock 與 dedicated Secret 續期；OpenRouter／Gemini 沿用 free-only gate。未知 usage/cost 顯示 unknown，不補 0。

## 集中驗收／正式 dev 發布

1. 完成全部產品程式與 `/ponytail-review`；GitHub Actions 對完整 SHA 跑全套 Python（含隔離 PostgreSQL ACL／併發）與 Flutter tests/build。
2. 發布四個既有 component 的 public GHCR digest；獨立 `ghcr-ceo-worker-build.yml` 只接受同 SHA 的成功 full release run，將 CEO tag 寫入既有 public Mart package，不建立 GCP 資源。
3. `serving-schema-migration-dev.yml` 的 051 透過固定 hash SQL、現有 ingestion identity 執行 additive migration，避免「新版 image 需要 migration、migration 又需要新版 image」循環；050／051 都需真實 ACL/readback evidence。
4. 新 CEO Job／Job-scoped API execution+read IAM、費用／免費剩餘額度及必要 OAuth 由使用者核准後處理。先完成真實 cold-start／refresh、最少 bounded provider call、persist/readback、owner/cancel/duplicate／failure gate。
5. API 0% candidate、Jobs 各自 fence/canary/rollback；同一工作包一起驗五角色、CEO、Admin、持股／首屏及四頁 authenticated browser。所有 gate PASS 才移轉正式服務的 dev 流量。

任何 gate 為 partial／unknown／blocked 都保留原正式流量；500 檔歷史模型研究後置。權限種類以 [Google Cloud Run IAM](https://docs.cloud.google.com/iam/docs/roles-permissions/run) 為準，API binding 只限這個 CEO Job，不授予 project-wide Run Admin。

日常五分析師操作見 [Specialist engines](spec/specialist-engines.md)。歷史 provider 授權／驗收程序見 [封存紀錄](archive/mart-provider-runbook-before-specialist-removal-2026-10-03.md)，不得再照封存指令執行舊五角色。
