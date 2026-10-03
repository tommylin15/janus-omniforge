# Janus UI — Admin UI

## 9.0 Target workspace

Admin 的目標是 `apps/user_app` 內的 Flutter workspace，與 User 共用 codebase 但不共用權限。`/api/v1/admin/*` 每次由 backend enforce Admin authorization；User token audience 不可直接呼叫 Admin API，Flutter 隱藏控制也不是 security boundary。

2026-10-02 使用者已決定 legacy static HTML／JS Admin 退役，不再作為 fallback，也不再等待 Flutter parity／rollback gate；Flutter／PWA 是唯一 active Admin frontend。Legacy source 的可還原座標保留於 `archive/legacy-static-admin-retired-2026-10-02.md`，除非使用者日後另行決定，不得重新納入 runtime。

2026-10-03 Admin UI scope 依 [`../decision-2026-10-03-admin-ui-scope-and-governance.md`](../decision-2026-10-03-admin-ui-scope-and-governance.md) 收斂。**這不是整套 Admin 重做。** 既有 `個股`、`市場資訊`、`AI 分析` 保留；原 `進階管理` 的產品目標改名為 `資料治理`，承接資料層、retention、storage 與 DQ 的精簡營運視角。

主導覽目標固定為：

1. `總覽`
2. `批次`
3. `個股`
4. `市場資訊`
5. `AI 分析`
6. `資料治理`

程式／runtime 尚未完成此 rename 前，既有 UI 可能仍顯示 `進階管理`；文件變更本身不得視為 implementation completion。

## 9.0.1 Admin interaction 原則

- Admin 日常只優先回答三件事：**今天有沒有異常、批次有沒有正常跑、資料有沒有健康或異常成長**。
- 正常狀態不佔主要畫面；異常才 drill-down。execution ID、snapshot、hash、provider、model、prompt、artifact、lineage 等工程欄位放在詳細資訊。
- 第一版不要求 DAG、lineage graph、metadata catalog、複雜 dashboard 或大量 chart。現有 Flutter Material 3 元件能完成需求時，不新增第三方 UI framework。
- 不導入 OpenMetadata、DataHub、Airflow、Kestra、Prefect 等第二套 control plane／scheduler／canonical store。可以參考其 UX，但 Janus execution、data governance 與 retention 的 source of truth 仍是 GitHub `main`、PostgreSQL control／publication、Iceberg/GCS persistence 與真實 runtime evidence。
- UI 不自行重算 canonical number、retention completion 或 billable storage。資料不足時顯示 `unknown`／`尚未檢查`／`未定義`，不得補 0 或假裝正常。
- Flutter 不直接操作任意 Cloud Run job name、checkpoint 或 storage object；manual action 必須走 backend allowlist、authorization、idempotency／duplicate guard、dependency／exclusive guard 與 audit。

## 9.1 總覽

首頁採 actionable-issues-first，維持簡單摘要，不把所有正常 execution 與工程 metadata 堆在第一屏。

第一版摘要只需要涵蓋：

- 今日批次狀態；
- 最近資料品質結果；
- Storage／retention anomaly；
- 需要處理的項目數。

有異常時，至少能辨識「哪一筆、原因、最後更新、是否可安全處理」，並可 drill-down 到對應批次、資料或 AI 詳細資訊。可重試項目才顯示 retry／rerun action；partial success 不得顯示成 full success。

`WBS-3-DATA-SUPPLEMENT-V1` 的週六資料品質檢查已接入 Admin Overview：顯示最近檢查時間、通過／需處理／執行失敗、受影響資料與是否需調整每日補資料；「結果與檢核文件」可讀安全結果及 `/api/v1/admin/data-quality/runbook`。檢查本身執行失敗與資料品質不合格必須分開；不透過 Email 或 Codex automation 通知。

## 9.2 批次

`批次` 使用簡單表格／清單作為 Job Control Center，不要求大型 DAG。

每列至少顯示：

- batch/job 名稱；
- effective schedule／trigger；
- latest execution state；
- started／finished 或 duration；
- latest success／last update；
- `查看`、安全的 `重試`／`手動執行`。

預設顯示最近 **3 天** execution／occurrence；更早歷史以日期範圍、cursor 或等價 bounded query 取得。需要快速營運視角時可保留「最近 50 次」preset，但不得成為唯一歷史入口。`enqueue`／dispatch 成功不得顯示成 workload 成功。

目前 GitHub `main` 的 controller 固定批次為：

- `ingestion`
- `data-supplement`
- `mart`
- `data-quality`
- `private`
- `core-cleanup`
- `mart-cleanup`

UI 應以 backend／controller 的 effective job/occurrence 為準，不再由 Flutter 複製一份排程真相。未來 500 screening、dirty specialist update、monthly retrain／reconciliation、On-demand CEO execution 等只有在對應 implementation／runtime 真正存在後才出現，不以 placeholder 假裝可用。

### 9.2.1 Execution detail

row click／`查看` 才載入結構化 detail。至少顯示 status、safe failure reason、source／dataset、target、processed／success／failure／retry、lineage 與可安全採取的 action；不以 raw JSON 作主要 UX。

失敗 item 顯示 retryable／non-retryable／blocked 分類；只能重試 retryable failed item。重試建立新 execution，保留舊 execution 與 retry lineage。

Manual rerun 必須經 backend allowlist、idempotency／duplicate guard、dependency／exclusive guard 與 audit；cleanup／retention 等具刪除效果的作業不在首頁放置高風險一鍵操作。

## 9.3 個股

保留既有 Admin Stock Workbench 與後續既定工作，不因本次治理 UI 收斂而取消。

- 支援代號／中文名稱搜尋、dataset health、gap repair、analysis/read history 等已核准能力。
- Core 最新交易日、dataset、coverage、row count、null ratio、DQ、freshness、source、snapshot ID 與 updated time 使用結構化欄位，不直接輸出 JSON blob。
- row expand／`查看` 才載入 quality flags、association、quarantine reason 等詳細資訊；raw payload、object URI、敏感 URL、secret 與完整 upstream traceback 不得提供旁路。
- 舊 artifact 不可原地修改；重新分析建立新 execution/report。

## 9.4 市場資訊

保留現有市場資訊頁，用於 500 universe／市場資料營運視角。

- 呈現有效 500 檔 ranking、成交量／市場資料、進入／退出、版本與來源狀態。
- 深度追蹤需求只呈現去識別化 symbol demand、effective time 與 cadence，不顯示 user-to-symbol 關係。
- source routing 是 backend versioned contract，不由 Flutter hard-code；只有 approved／authorized source 可進 effective route。

## 9.5 AI 分析

`AI 分析` **保留且與資料治理分開**。它遵守 2026-10-03 Token-first specialist + On-demand CEO 決策，不再把五 specialist 當成每日五個生成式 LLM workers。

### 9.5.1 Specialist management

Admin 後續管理：

- specialist champion／model／version／evaluation；
- coverage 與 latest validated artifact；
- dirty dependency／reuse／reconciliation 狀態；
- monthly retrain／calibration／evaluation evidence；
- blocked／partial／insufficient-data 狀態。

五 specialist production 主路徑為 Python／SQL／ML；正常白話輸出來自 structured output + SHAP/rules/templates，正常 path 0 API token。舊「五分析師共用 LLM provider route」若與 active TODO／2026-10-03 decision 衝突，以最新 Token-first 決策為準。

### 9.5.2 On-demand CEO

Codex CLI／OpenRouter／Gemini 既有 adapter／routing／auth／free-gate 成果保留，但 effective product runtime 僅用於 authorized manual On-demand CEO／rare escalation。

Admin 後續至少管理：

- DB-backed user capability，例如 `ceo_analysis.request`；
- CEO provider approval／auth／health；
- model/profile/version；
- quota／cooldown；
- usage／cost audit；
- immutable execution/report history。

重新分析建立新 immutable execution/report，不覆寫舊報告。Flutter visibility 不能取代 backend authorization。

## 9.6 資料治理

`資料治理` 取代原 `進階管理` placeholder，第一版維持單一精簡頁，不拆成大型 metadata platform。主要包含三區。

### 9.6.1 資料層與 Retention

顯示 Stage／Core／Mart／必要 Private 摘要、最後更新、目前 retention contract 與狀態。Retention 必須依 active [`../spec/retention-governance.md`](../spec/retention-governance.md)，不能由 UI hard-code 舊規則。

目前 Public contract 摘要：

| 資料 | 保留／清理契約 |
|---|---|
| Stage 公開 raw／sidecar／提交證明／隔離資料 | 超過 7 天清理；queued／running／retrying 共用引用暫時保護 |
| Core 一般行情 | 365 天 |
| Deep Coverage 價量與 benchmark | 1096 天 |
| 財報 | 12 季 |
| Mart 分析列 | 90 天 |
| 每個股完整 specialist 分析 | 最新 3 代；仍被保留成果物引用的共用內容不刪 |
| OOS／specialist 成果物 | 最新仍使用結果；未完成、無引用且超過 7 天依 active spec 淘汰 |
| Core execution manifest | 超過 90 天、無有效引用且有新鮮 `CORE_RETENTION_FENCE_URI` 才可淘汰 |

Private retention 不屬目前 Public deletion governance 範圍。若沒有另外已核准 contract，UI 顯示 `未定義／unknown`，不得把 Public retention 套到 private ledger／artifacts。

### 9.6.2 資料健康

只顯示日常需要判讀的 coverage／freshness／DQ／quarantine／blocked 摘要。source、observed/published/fetched time、snapshot、quality flags、PIT／provenance 等放到 detail，不在首頁堆滿 metadata。

資料補強品質檢查至少能呈現：財報季度數、營收月份、行情交易日、明確的 quality reason 與最近檢查時間。`unknown` 不補 0。

### 9.6.3 容量與清理

顯示 Stage／Core／Mart／必要 Private 的：

- live object count／active bytes；
- 最近 maintenance；
- retention anomaly；
- protected reference／snapshot 摘要；
- 可可靠取得的 storage growth；
- cleanup failure／overdue。

必須區分 Iceberg／GCS live objects／active bytes 與 non-current、soft-delete、versioned 或 billable bytes；沒有 billable-storage evidence 時顯示 `unknown`。頁面優先讀 persisted maintenance／telemetry，不在每次 page load 即時 enumerate 整個 bucket。

UI 優先顯示真正需要處理的 anomaly，例如 Stage／quarantine 未依 contract 清理、protected reference 異常增加、storage growth 或 maintenance failure；第一版不要求複雜 chart。

### 9.6.4 Private operations

如顯示 Private Pipeline，只顯示操作所需的去識別化／aggregate metadata，例如 current checkpoint、updated time、latest visible ledger/change version、可可靠計算的 pending/backlog、last execution/result、latest Private Mart valuation date 與 lag。一般 Admin 不顯示使用者交易正文／持股內容。

Private Pipeline 的 effective trigger／schedule 以 GitHub `main` + live Scheduler／batch controller evidence 為準，不能只依舊文件或 UI 字串推定。

## 9.7 Routing controls

Provider／market-source priority 是 backend versioned routing contract，不由 Flutter hard-code。Admin 只編輯已核准設定；runtime 保存 effective route/version、attempt、fallback reason 與實際 source/provider。所有修改保留 actor、timestamp、before/after 與 optimistic lock。

Routing 不另建高複雜度主頁：

- CEO provider route 放在 `AI 分析` 的進階設定；預設 approved route 依 active TODO 為 `Codex CLI → OpenRouter → Gemini`，只適用 On-demand CEO／approved escalation。
- market source route 放在 `市場資訊` 或 `資料治理` 的相關 detail。
- 未核准、auth 不可用、paid gate 未授權的 provider/source 可顯示 blocked/disabled，但不得因排序而自動啟用。

## 9.8 Accessibility／responsive

- Desktop 可使用 `NavigationRail`／單面板 layout；窄螢幕可用 `NavigationDrawer` 或等價單選導覽。
- 頁面標題與目前分頁名稱必須可見；未選分頁不預抓大型 detail。
- loading／empty／error／partial／stale／missing／blocked 依全域 UI state contract 明確呈現，不以 sample／placeholder 補成功。
- 主要操作維持可鍵盤操作與合理 target size；release acceptance 依 `accessibility-and-release.md`。

## 9.9 完成判定

本文件定義目標 UI 契約，不是完成證據。宣稱 Admin operational convergence 完成時，仍需依 `PROJECT_RULES.md` 綜合：

- GitHub `main` implementation；
- targeted tests／CI；
- deployment；
- 真實 Admin auth／audience boundary；
- GCP dev runtime；
- batch／retention／storage telemetry；
- browser acceptance。

文件更新、Flutter build、API 200 或單次 partial execution 都不能單獨構成 full completion。
