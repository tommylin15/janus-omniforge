# 2026-10-03 Admin UI 範圍與資料治理呈現決策

## 決策

Janus Admin 不重做整套資訊架構，也不導入另一套獨立的 metadata／orchestration 後台。既有 Flutter `資料營運中心` 保留為唯一 active Admin frontend，沿用目前 Material 3 shell 與既有 API／execution／retry 能力，採最小合理變更完成營運閉環。

主導覽收斂為：

1. `總覽`
2. `批次`
3. `個股`
4. `市場資訊`
5. `AI 分析`
6. `資料治理`

其中 `資料治理` 是目前 `進階管理` placeholder 的明確產品化名稱，不代表新增第七個主功能，也不取代 `AI 分析`、`個股` 或 `市場資訊`。在程式與 runtime 尚未完成前，既有 UI 仍可能顯示 `進階管理`；文件更新本身不得視為 implementation completion。

## 設計原則

- Admin 只回答三類日常問題：**今天有沒有異常、批次有沒有正常跑、資料有沒有健康或異常成長**。
- 正常狀態不佔主要畫面；異常才 drill-down。工程欄位、lineage、snapshot、hash、provider、model、artifact 等只在詳細資訊顯示。
- 第一版不要求 DAG、lineage graph、metadata catalog、複雜 dashboard 或大量 chart；現有 Flutter Material 元件足夠時不新增第三方 UI framework。
- 不導入 OpenMetadata、DataHub、Airflow、Kestra、Prefect 等第二套 control plane／scheduler／canonical store。可以參考其 UX，但不得讓它們成為 Janus execution 或 data governance 的第二個 source of truth。
- Manual rerun／retry 一律走 backend allowlist、dependency／exclusive guard、idempotency／duplicate guard 與 audit；Flutter 不直接操作任意 Cloud Run job、checkpoint 或 storage object。
- UI 不自行推導 canonical number、retention completion 或 billable storage；沒有可靠 evidence 顯示 `unknown`。

## 總覽

`總覽` 沿用 actionable-issues-first，只保留少量摘要：

- 今日批次狀態。
- 最近資料品質結果。
- Storage／retention anomaly。
- 需要處理的項目數。

正常 execution 不重複列出。異常項目至少能 drill-down 到「哪一筆、原因、最後更新、是否可安全處理」。

## 批次

`批次` 不以大型 DAG 為必要條件，第一版使用簡單表格／清單顯示 backend 回報的 effective jobs／occurrences。至少顯示：

- batch/job 名稱；
- effective schedule／trigger；
- latest execution state；
- started／finished 或 duration；
- latest success／last update；
- `查看`、安全的 `重試`／`手動執行`。

預設顯示最近 3 天，較舊歷史以日期範圍／cursor 或等價 bounded query 取得。`enqueue`／dispatch 成功不得顯示成 workload 成功。

目前 GitHub `main` 的 controller 固定批次為 `ingestion`、`data-supplement`、`mart`、`data-quality`、`private`、`core-cleanup`、`mart-cleanup`。未來 500 screening、dirty specialist update、monthly retrain／reconciliation、On-demand CEO execution 等只有在對應 implementation／runtime 真正存在後才出現在批次或 AI 管理畫面，不以 placeholder 假裝可用。

## 資料治理

`資料治理` 是單一精簡頁，不拆成多個大型子系統。第一版包含三區：

### 1. 資料層

顯示 Stage／Core／Mart／必要 Private 摘要、最後更新、目前 retention contract 與狀態。Retention 必須依 active SPEC，而不是 UI hard-code 舊值：

- Stage 公開 raw／sidecar／提交證明／隔離資料：超過 7 天清理；queued／running／retrying 共用引用暫時保護。
- Core 一般行情：365 天。
- Deep Coverage 價量與 benchmark：1096 天。
- 財報：12 季。
- Mart 分析列：90 天。
- 每個股完整 specialist 分析：只保留最新 3 代；仍被保留成果物引用的共用內容不得刪除。
- OOS／specialist：保留最新仍使用結果；未完成、無引用且超過 7 天者依 active retention spec 處理。
- Core execution manifest：超過 90 天且無有效引用，並有新鮮 `CORE_RETENTION_FENCE_URI` reference fence 時才可淘汰。

Private retention 不屬目前公開資料刪除治理範圍；若沒有另外已核准 contract，Admin 顯示 `未定義／unknown`，不得套用 Public retention 推測。

### 2. 資料健康

只顯示日常需要判讀的 coverage／freshness／DQ／quarantine 或 blocked 摘要；source、published/fetched time、snapshot、quality flags、PIT／provenance 等進詳細資訊，不在首頁堆滿 metadata。

### 3. 容量與清理

顯示 Stage／Core／Mart／必要 Private 的 live objects／active bytes、最近 maintenance、retention anomaly、protected references 與可可靠取得的 growth 指標。必須區分 Iceberg／GCS live bytes 與 non-current／soft-delete／versioned／billable storage；沒有帳單層 evidence 時 billable 顯示 `unknown`。

UI 應優先顯示異常，例如 retention overdue、Stage/quarantine 未按 contract 清理、protected reference 異常增加、storage growth 或 maintenance failure，而不是建立大量圖表。

## AI 分析保留且獨立

`AI 分析` 不因資料治理頁新增而刪除或縮成治理子頁。它承接 2026-10-03 Token-first 架構：

- 五 specialist production 主路徑為 Python／SQL／ML；正常 path 不是每日五個生成式 LLM workers。
- 管理 specialist champion／model／version／evaluation、dirty dependency／reconciliation 狀態。
- Codex CLI／OpenRouter／Gemini route 僅用於 authorized manual On-demand CEO／rare escalation。
- 管理 CEO provider approval/auth/health、capability、quota/cooldown、usage/cost 與 immutable report／audit。

舊「五分析師共用 LLM provider route」文字若與最新 Token-first TODO／decision 衝突，以最新 active TODO 與 2026-10-03 decision 為準。

## 其他既有功能

- `個股`：保留現有 stock workbench 與後續既定工作，不因此次治理 UI 改版取消。
- `市場資訊`：保留 500 universe／市場資料管理。
- Routing controls 仍是 backend versioned contract；日常 UI 只在對應 `AI 分析` 或 `資料治理` 詳細區呈現，不另建高複雜度主頁。

## 完成判定

本文件是產品／UI scope 決策，不是完成證據。實作完成仍需依 `PROJECT_RULES.md` 綜合 GitHub `main` implementation、targeted tests、deployment、真實 Admin auth、GCP dev runtime、batch／retention telemetry 與 browser acceptance 判定；partial 不得包裝成 full success。
