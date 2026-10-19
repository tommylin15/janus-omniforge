# Janus UI — Admin UI

## 9.0 Target workspace

Admin 的目標是 `apps/user_app` 內的 Flutter workspace，與 User 共用 codebase 但不共用權限。`/api/v1/admin/*` 每次由 backend enforce Admin authorization；User token audience 不可直接呼叫 Admin API，Flutter 隱藏控制也不是 security boundary。

2026-10-02 使用者已決定 legacy static HTML／JS Admin 退役，不再作為 fallback，也不再等待 Flutter parity／rollback gate；Flutter／PWA 是唯一 active Admin frontend。Legacy source 的可還原座標保留於 `archive/legacy-static-admin-retired-2026-10-02.md`，除非使用者日後另行決定，不得重新納入 runtime。

**2026-10-17 Admin v2 最新目標：**依 [Admin v2 四頁設計決策](../decision-2026-10-17-admin-v2.md)，取代 [2026-10-03 六頁導航](../archive/decision-2026-10-03-admin-ui-scope-and-governance.md) 的主選單與功能位置，但保留既有權限、稽核、資料安全與已接受功能。**2026-10-19 四頁重構已有適用 Flutter／Python 及權限測試與原 TODO 指定範圍 PASS；本次文件整理未獨立重驗 live 部署。** 本頁是四頁長期 UI 契約，不另開 Admin v2 待辦。

主導覽固定為：

1. `總覽`
2. `批次`
3. `資料品質`
4. `系統設定`

原「個股」和「市場資訊」歸「資料品質」搜尋／detail；原「AI 分析」歸「系統設定 → AI 模型與 Gateway」子頁；原「資料治理」按監控、Private 執行與低頻設定分散到資料品質／批次／系統設定，**原能力不能直接砍掉**。不另開第 5 個 AI 或股票主頁。工程 A1～A5 歷史驗收見 [原 TODO 快照](../archive/todo-before-consolidation-2026-10-19.md)；D01～D06 不加工作，D07／D08 在四頁容器內接入即可，不重開 A1～A5。

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
- 合格的 Private Mart valuation-as-of、D02 snapshot freshness 及有效部署版本可在次層顯示；資料／部署證據不存在時顯示 unknown。

「總覽 → 使用分析」是**次層統計與個人分析**入口，不新增第五主選單：全站使用人數／功能次數／活躍秒數、最近 7／30／90 天；再進入使用者搜尋／個人日曆／各功能操作次數與活躍時間／最近七天粗粒度操作時間線。只接受已驗證來源，無回報或停用收集時不能視為零；完整契約見 [Admin v2 §4.1](../decision-2026-10-17-admin-v2.md)。

有異常時，至少能辨識「哪一筆、原因、最後更新、是否可安全處理」，並可 drill-down 到對應批次、資料或 AI 詳細資訊。可重試項目才顯示 retry／rerun action；partial success 不得顯示成 full success。

`WBS-3-DATA-SUPPLEMENT-V1` 的週六資料品質檢查已接入 Admin Overview：顯示最近檢查時間、通過／需處理／執行失敗、受影響資料與是否需調整每日補資料；「結果與檢核文件」可讀安全結果及 `/api/v1/admin/data-quality/runbook`。檢查本身執行失敗與資料品質不合格必須分開；不透過 Email 或 Codex automation 通知。

### 9.1.1 使用分析 → 單一使用者（A4-U，待實作）

- 全站摘要可選日／週／月，顯示 DAU、總 feature actions、有效活躍秒數與各功能排名。
- `查詢使用者` 支援經 Admin 授權的使用者目錄搜尋，選取後進單人檢視。預設 7／30／90 天各功能頁次數、主動操作、成功／失敗、估計活躍時間、最後活動日；最近 7 天時間線只顯示時段、`feature_id`、事件類型與狀態。
- 手機畫面採卡片 + 功能清單，桌面可加期間表格；不可在總覽直接列出所有人明細或敏感金融資料。
- Feature/key 僅 allowlist，嚴禁展示原始 payload、股票代號、持股、交易金額、筆記內容、搜尋關鍵字、Email 作事件屬性。識別用 Email 只從後端 Admin 授權的使用者目錄取得，個人頁開啟需另行稽核。
- 有效停留時間依頁面切換、前景／背景、焦點及閒置 60 秒計算；不將 IndexedStack 存活、背景頁籤、自動 polling 計成活躍時間。計算不完整顯示 estimated／partial，不宣稱精確注意力時間。
- 非同步上報失敗不延遲頁面切換、登入、交易、記帳、關注或重算；需求列在 ADMIN-V2，不擴張 D01～D06 的驗收。

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

**批次清單不能硬編碼舊七支。** 實作時從 `ingestion_core.batch_controller.BATCHES` 的有效定義、PostgreSQL occurrence／execution 及 live runtime 讀回核對（包括現有 backup、compaction 等維護類）；定義存在不代表部署成功。每筆需區分 scheduled／dispatched／running／terminal、unknown／partial 與成功。

UI 應以 backend／controller 的 effective job/occurrence 為準，不再由 Flutter 複製一份排程真相。未來 全市場 screening、dirty specialist update、monthly retrain／reconciliation、On-demand CEO execution 等只有在對應 implementation／runtime 真正存在後才出現，不以 placeholder 假裝可用。

### 9.2.1 Execution detail

row click／`查看` 才載入結構化 detail。至少顯示 status、safe failure reason、source／dataset、target、processed／success／failure／retry、lineage 與可安全採取的 action；不以 raw JSON 作主要 UX。

失敗 item 顯示 retryable／non-retryable／blocked 分類；只能重試 retryable failed item。重試建立新 execution，保留舊 execution 與 retry lineage。

Manual rerun 必須經 backend allowlist、idempotency／duplicate guard、dependency／exclusive guard 與 audit；cleanup／retention 等具刪除效果的作業不在首頁放置高風險一鍵操作。

## 9.3 資料品質 → 個股資料健康（原 Stock Workbench）

原 Stock Workbench **保留功能但不保留獨立主頁**：在「資料品質」以代號／名稱搜尋、檢查 dataset、合法期間、來源、quality gap、approved repair 及 immutable analysis/history。

- 僅讀既有 Core／Mart／DRL-01 正式 API／provenance；OHLCV 有效 120 個交易日、13 個 fiscal_month、2026Q1/Q2 合格 EPS 與歷史四連季/TTM **未認證**分開顯示，單一合法值可用，不受後置五年 PE/PB 阻斷。
- Core 交易日、coverage、row count、null ratio、quality flags、published/source time、snapshot ID 等放在結構化 detail；缺值／stale／PENDING／PARTIAL／WAIVED_FOR_MVP 不補 0。
- 修復請求沿用 backend approved allowlist／execution／audit，重試建立新的執行紀錄；不可繞過官方來源與合法季度/PIT 判斷。
- Admin 不複製 User 個股價格/KD/估值圖、持股／交易／現金畫面，亦不得在一般 Admin 暴露 Owner 的 user-to-symbol 關係。


## 9.4 資料品質 → 市場與來源（原市場資訊）

原市場資訊 **移為資料品質子頁**：呈現官方上市／上櫃完整 universe、進出變動、版本、source freshness、已核准的 ranking 及 coverage；不得退回歷史 Liquid 500。

- 分市場 coverage 附分母、資料 as-of 與 DQ 原因；TWSE ≥90%、TPEx ≥70% 的既有門檻不改，不把債券 ETF 納入一般四碼上市櫃股票分母。
- Deep Coverage 只顯示去識別化 symbol demand、cadence 與 effective time，不洩露 Owner 關係。
- Source routing 由 backend versioned contract 決定；調整全市場母體不得以人工 Admin master 操作取代官方導入。


## 9.5 系統設定 → AI 模型與 Gateway（原 AI 分析）

原 `AI 分析` 的模型／評估／CEO 管理與可深連結子頁 **保留功能**，但入口歸 `系統設定 → AI 模型與 Gateway`；模型品質中的資料缺口可連至「資料品質」，不再維護第五主頁。遵守 Token-first specialist + On-demand CEO，五 specialist 不是每日五個生成式 LLM workers。D07 的 VF-09 與 D08 後續成果共用此容器。

### 9.5.1 Specialist management

Admin 後續管理：

- specialist champion／model／version／evaluation；
- coverage 與 latest validated artifact；
- dirty dependency／reuse／reconciliation 狀態；
- monthly retrain／calibration／evaluation evidence；
- blocked／partial／insufficient-data 狀態。

五 specialist production 主路徑為 Python／SQL／ML；正常白話輸出來自 structured output + SHAP/rules/templates，正常 path 0 API token。舊「五分析師共用 LLM provider route」若與 active TODO／2026-10-03 decision 衝突，以最新 Token-first 決策為準。

### 9.5.2 On-demand CEO

既有 Codex CLI／OpenRouter／Gemini adapter／routing／auth／free-gate 結果保留；**實際 effective provider、model、audience、quota 與 health 必須讀回現行 Janus→Gateway/runtime**，不能因舊文件列出 provider 順序，就宣稱目前 active route。僅核准的 manual On-demand CEO／rare escalation 可使用對應 LLM 路徑。

Admin 後續至少管理：

- DB-backed user capability，例如 `ceo_analysis.request`；
- CEO provider approval／auth／health；
- model/profile/version；
- quota／cooldown；
- usage／cost audit；
- immutable execution/report history。

重新分析建立新 immutable execution/report，不覆寫舊報告。Flutter visibility 不能取代 backend authorization。

## 9.6 資料品質 → 資料治理與儲存

原「資料治理」合併進「資料品質」的治理／儲存 detail；可按資料層與 retention、DQ／freshness、儲存與清理三區檢視。Private queue／cancel/force-fail 等**執行控制**放「批次」；Worker 數量及版本化低頻設定放「系統設定」。不建 metadata platform。

### 9.6.1 資料層與 Retention

顯示 Stage／Core／Mart／必要 Private 摘要、最後更新、目前 retention contract 與狀態。Retention 必須依 active [`../spec/retention-governance.md`](../spec/retention-governance.md)，不能由 UI hard-code 舊規則。

目前 Public contract 摘要：

| 資料 | 保留／清理契約 |
|---|---|
| Stage 公開 raw／sidecar／提交證明／隔離資料 | 超過 **2 天（48 小時）**清理；queued／running／retrying 共用引用暫時保護 |
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

- CEO provider route 放在「系統設定 → AI 模型與 Gateway」進階設定；目前實際 active route 以 backend／Gateway 的 effective runtime 和已授權版本為準，不能由過時排序推斷。
- market source route 放在「資料品質 → 市場與來源」detail；所有實際切換均須經版本化後端核准。
- 未核准、auth 不可用、paid gate 未授權的 provider/source 可顯示 blocked/disabled，但不得因排序而自動啟用。

## 9.8 Accessibility／responsive

- Desktop 可使用 `NavigationRail`／單面板 layout；390px 窄螢幕採四入口的 `NavigationDrawer` 或等價單選導覽；Stock/AI 內頁保留深連結與返回位置。
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

文件更新、Flutter build、API 200 或單次 partial execution 都不能單獨構成 full completion。**A0 文件整併不等於 A1～A5 Admin v2 主要重構完成；既有 D01～D06 與 DRL-01 不因新 Admin UI 被增加驗收條件。**
