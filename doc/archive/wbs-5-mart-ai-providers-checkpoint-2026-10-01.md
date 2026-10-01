# WBS-5-MART-AI-PROVIDERS partial checkpoint（2026-10-01）

本項 **尚未完成**。使用者已確認 Sol，明確核准把目前 Codex 帳號資格存入既有 dev
Secret bundle、先驗收最多一股×五角色且每角色一次，不啟用付費 API；另指定預設
`gpt-6.1-sol`＋`low`（輕），未來以 Admin 選擇為準。

## Implementation／dev evidence

- Commit `ec8fdce84e8f90ab9a7f6bff6118c3b32df30383`：工具停用、ChatGPT auth cache 檢查、
  version／usage 診斷去敏、process launch 失敗結構化、同批次 cache 更新、五角色 failure
  artifacts／validator、immutable manifest identity fence，以及單股實際 provider 驗收入口。
- 本機完整相關驗證 **95 passed／3 deselected**（Windows 不跑 Linux process tests）；
  canonical dev workflow `36813262424` **98 passed**、deploy／verify success。
- Job Ready；image digest `sha256:277511581df4fbb0bf7622c466d6447566f83c717ed1babca56229e2f9c4155a`。
- 原 preflight `janus-intelligence-mart-vk4n5` 為 `blocked/auth_required`，無模型呼叫。
  使用者授權後，既有 `janus-runtime-bundle` 從 version 2 新增 version 3；只保存安全版本 metadata。
  Auth 內容經 stdin 傳輸，不進 repository、argv、log 或 artifact。未變更 IAM。
- `janus-intelligence-mart-mpd29` 因未帶 `ENVIRONMENT=dev` 在任何 model call 前失敗；
  task 自動重試也在同一 dev gate 擋下，兩次均 **provider_calls=0**，不得列為成功。
- 修正 execution-only env 後，`janus-intelligence-mart-l79st` 成功退出；
  `maxRetries=0`、tasks=1、每角色 max_attempts=1，五次 model calls，無額外 retry／fallback。
  建立該 execution 後已恢復一般 Job 的 canonical `maxRetries=1`。

真實來源（symbol 2330、analysis_as_of 2026-09-24）：
`gs://gen-lang-client-0593591102-dev-mart/executions/4a429cb4-68ea-4506-985d-12bb817ea775/manifest.json`。
原 manifest／metadata 保持不變；未寫 publication，未使用 paid API。

| Role | CLI exit／duration | Validator | Outcome／reason |
| --- | --- | --- | --- |
| fundamental | 0／16830 ms | validated | insufficient_data |
| valuation | 0／9022 ms | validated | insufficient_data |
| positioning | 0／33361 ms | blocked | claim_coverage_mismatch |
| quant | 0／53743 ms | blocked | ungrounded_numeric_claim |
| event_risk | 0／13431 ms | validated | insufficient_data |

全部 interpretation 為 `schema_validated`，model／lineage 為 `gpt-6.1-sol`／`low`、CLI 0.159.2。
觀察到 input_tokens=59262、output_tokens=3295、cached_input_tokens=0；actual cost／subscription
剩餘 quota 為 unknown，不視為免費。Summary 為 `validation_outcome=partial`、
`analysis_outcome=partial`、`five_role_success=false`；不能把退出碼 0 或 schema 合格當完整研究成功。

Evidence：
`gs://gen-lang-client-0593591102-dev-mart/acceptance/ai-providers/960ae03cae4cf2983e3d35391db2ed8bb1a843b6d9a6f13979152890ca4b3bd3.json`。
Object hash `sha256:960ae03cae4cf2983e3d35391db2ed8bb1a843b6d9a6f13979152890ca4b3bd3`。
獨立讀回 **17 objects**（evidence、5 attempts、sidecar、5 interpretations、5 validations）
的 hashes／固定 model／reasoning／validator status 通過。CLI storage cat 耗時過長後改以有逾時
的 GCS REST 讀取；兩次唯讀驗證最終均通過，未新增 provider calls。

## Target projection

既有 dev PostgreSQL 已套用 migration `036_mart_ai_targets`。以
[`verify_mart_ai_targets.sql`](../../scripts/gcp/verify_mart_ai_targets.sql) 使用既有
`janus_private_api`／`janus_mart_publication` 執行真實 trigger／ACL 驗收：watch-only、held-only、
重疊去重、兩 owner、取消關注仍持有、退出聯集、as-of history fence、replay floor、private SELECT
拒絕共九類通過；所有合成 rows／projection 已 rollback。Mart 不具 private schema/table 讀取權。
Replay floor 為 migration 日，不能把更早日期當 exact membership replay。
本項僅證明真實投影／隔離，尚未證明 target snapshot 與 provider 的同 execution 整合。

## 未完成條件／下一入口

1. Mart 身分只有 Secret accessor；子程序更新 cache 目前只供同一批次後續角色使用，尚無跨 Job
   的續期保存／rotation／revocation／重新授權驗收。擴大 Secret 寫入權或新增 dedicated auth Secret
   必須先取得安全／費用決策，不自動替共享 runtime bundle 加 writer 權限。
2. 核准的五次 model calls 已全部使用。Target 聯集＋immutable Core＋五角色的同 execution
   GCP 驗收，及修正 prompt 後的定位／量化再驗收，需要新增明確的 bounded quota 授權。
   Validator 不放寬、失敗不靠 silent fallback 隱藏。
3. 自然批次尚未啟用 `MART_AI_ENABLED=true`，daily workload／CIO 屬後續 gate。
4. Admin 官方授權入口與最新帳號可用模型選單需求已記錄在 `WBS-6-ADMIN-ANALYSIS-PROFILE`；
   UI 尚未實作，不能將本機 model cache 當最新即時清單。

操作限制見 [provider runbook](../runbook-mart-ai-providers.md)。
