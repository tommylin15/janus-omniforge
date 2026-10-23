# Janus UI — Admin UI

## 2026-10-23｜Admin 操作精簡整包（使用者授權；取代下文衝突的舊導覽）

本輪範圍是現役 Admin 全功能盤點、精簡操作及同批驗收。允許必要 UI 重構，不新增第二套排程／資料庫。以下為目標契約，未經測試、同來源發布與真實驗收不得視為已上線。

### 四個主頁、十項功能

| 主頁 | 功能 | 日常任務 |
|---|---|---|
| 總覽 | 待處理事項 | 實際自動工作結果、上市／上櫃行情完整率、損益更新日；異常附時間、影響及處理入口 |
| 總覽 | 使用情況 | 全站／授權單一使用者的功能使用與失敗情況；保留退出與刪除權 |
| 批次 | 自動工作與紀錄 | 統一所有定時／手動收集、補資料、分析、備份、清理的工作入口與執行控制 |
| 批次 | 損益重算 | 個人重算佇列、並行數、中止及失敗處置；保留 Owner 隔離 |
| 資料品質 | 全市場資料健康 | 上市／上櫃行情、營收、財報缺口；全市場不等於資料已完整 |
| 資料品質 | 個股資料查修 | 查股號／名稱、資料日期與缺口；需補資料時帶往批次，不直接執行 |
| 資料品質 | 採集來源狀態 | 最近採集成功／失敗及時間；來源可以是官方或已核准第三方 |
| 資料品質 | 儲存空間 | 六桶唯讀容量、物件數、保留政策與維護；不新增前台刪除路徑 |
| 系統設定 | 模型與報告管理 | 已保存模型／分析版本、CEO profile／capability、執行與費用稽核；執行操作歸批次 |
| 系統設定 | 券商與隱私設定 | 既有券商費率、使用統計開關及權限說明；重算並行數移至批次 |

### 移除與保留依據

- 移除「市場涵蓋」有效／即將生效名單、進出名單獨立頁；後端官方全市場名冊仍供 ingestion、搜尋及 coverage 分母使用，不刪資料或底層名冊能力。
- 「重要標的」不是人工選股功能，改為個股資料查修；持股／關注股所需120交易日行情仍有現役用途，保留品質檢查。重複分析歷史回歸模型／報告管理。
- 「官方來源」是採集健康紀錄，改名採集來源狀態；不因支援全市場而刪去來源故障診斷。
- 刪除首頁 Core 14／Mart 50／AI 待 WBS-5 等缺乏操作意義的彙總與佔位；不可將有界讀取前50筆當成全站待辦數，也不能拿舊儲存證據冒充即時容量。
- 單獨「權限與稽核」說明頁併入設定，底層 authorization／audit 完整保留。刪除固定未知 I/O 節省率與過時未啟用告示。

### 白話與漸進揭露

- 首屏只回答目前狀況、資料時間、影響、可執行操作；正常、部分缺漏、失敗、執行中、等待依賴、尚未確認不可混為成功。
- 系統內部狀態碼、execution、snapshot、hash、source ID、版本及追蹤資訊放「詳細資訊」。未知需說明缺什麼證據，不堆不可處理的判斷狀態。
- 手機與桌面皆使用現有 Material 元件，主要工作一個入口、一步展開，避免多層下拉及重複控制。

### 批次清單及統一操作

- 按每日／每週／每月／手動與尚未啟用分組；各工作附主要任務與依賴。只列現役定義或文件明定的預計工作，不復活已退役 Cloud Run 月度訓練。
- 每個工作顯示最新執行狀態、預定時間、實際開始／結束、耗時及逾期未執行；最新執行在上。紀錄只列最近7天、每工作最新一份安全執行摘要／log，不展開大量過往紀錄；週／月工作名稱不因上次已超過7天消失，過期紀錄不冒充新狀態。
- 逾期以可信 effective schedule、Controller 啟用時間、交易日／依賴／佇列與實際執行證據判定；缺 runtime schedule 或查詢被截斷時不可憑沒有列出就判未執行。預計但未啟用顯示原因及啟用條件。
- 每工作均有啟動／停止操作位置；後端 allowlist、依賴、同一工作／共享 writer fence、冪等、版本衝突與稽核必須生效。未實作或未授權工作停用按鈕並說明原因，不提供假按鈕。
- 「停止本次」與「暫停後續排程」分開；只作用於確定的 occurrence／execution，不取消共享 Job 其他工作、Owner 重算或未知執行，不回滾已提交資料。無安全中止能力時，明示目前不能停止，允許停止尚未派送的工作或暫停後續排程。
- 補資料、重新分析、重算、備份及清理操作全部歸批次；其他畫面僅能檢視或帶參數前往批次。單純設定（券商、隱私、模型核准／權限）不屬批次啟動。
- 手動與定時共用 Controller request／occurrence／fence，不以 UI 直接呼叫任意 Cloud Run，不新增 Scheduler。即時派送需要的既有身分權限不足時先列具體 blocker，不自行擴權。

### 執行前權限

即時喚醒由 API 身分 `janus-user-api` 對既有 `janus-batch-controller` Job 的 `roles/run.invoker` 提供；停止執行由 Controller 身分既有 `janusDevBatchRunner` 上的 `run.executions.cancel` 提供。兩項最小 IAM 綁定已於 2026-10-23 套用並讀回：API 身分只綁 Controller Job；自訂角色只綁既有 ingestion-core、intelligence-mart、private-pipeline 三個 worker Jobs。停止仍只指定且可確認身分的單次 execution；備份及身分不明的工作不能強制停止。

### 整批驗收

完成 UI、API／Controller、必要資料契約、tests 與文件後集中驗收：4頁10功能、舊深連結相容、白話狀態／未知、手機／桌面、最新排序／7日邊界、日週月與未啟用、時間／耗時／安全log、逾期與例外、手動去重／依賴／啟停隔離、User/Admin／Owner／secret邊界、現有六桶盤點及損益功能回歸。完整 Release／同SHA candidate／auth／受控發布／回滾及登入 Admin 正向讀回完成才 CLOSED。不重做已結案 Stage 清理；長時間遠端任務已啟動後依 PROJECT_RULES §10 交接。

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

UI 應以 backend／controller 的 effective job/occurrence 為準，不再由 Flutter 複製一份排程真相。未來全市場 screening、dirty specialist update、**外部 Colab 模型提交／驗證／版本管理**、On-demand CEO execution 等只有在對應 implementation／runtime 真正存在後才出現，不以 placeholder 假裝可用。已退役的 Cloud Run monthly retrain／reconciliation 不得重新出現在批次手動操作清單。

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
- 外部 Colab 訓練匯入、校準／OOS／evaluation evidence（不得提供舊 Cloud Run fit 按鈕）；
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

### GCS 六桶一鍵唯讀盤點（STAGE-48H）

- 在既有四頁 Admin 的「資料品質 → 儲存維護」以單一按鈕呼叫 `POST /api/v1/admin/gcs-storage/inspect`；後端每次驗證 Admin token，使用既有服務身分讀 GCS metadata（no payload GET，不觸發清理）。前端顯示六個固定 Bucket 的 current objects／bytes、noncurrent bytes、soft-deleted bytes、Stage MD5 疑似重複量、查詢時間與部分成功原因。容量以十進位 MB（1 MB＝1,000,000 bytes）呈現、保留兩位小數、加千分位；物件數也加千分位，缺值不補零。六桶合計包含 current／noncurrent／soft-deleted，僅六桶全部完成時呈現。
- **固定 allowlist 六桶**（Stage、Core、Mart、Private、Research、Cloud Build），後端限制 GCS metadata 頁數與同一 instance 同時掃描數，HTTP 有 timeout；未授權/缺 IAM 會明確返回 blocked／partial，不隱瞞失敗也不補零。Bucket 清單不開放由前端指定，私人資料名稱、hash、payload、Owner 關係皆不得返回。
- 若六桶未全數掃描成功，`totals=null`；成功狀態僅 `KNOWN_BUCKETS_COMPLETE`，不視為整個 project 的費用帳單／所有 Bucket 完整。Admin 僅為**查詢**，沒有「一鍵刪除」。正式啟用需 API 與 Flutter 同 SHA release、Admin OAuth 負向驗證及至少一次有授權 GCS live readback。
- 不新增 API key、付費資源或 GCS 控制平面。缺少 Storage metadata 最小唯讀權限時標 BLOCKED，不自行擴張其他 IAM。

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
| Core execution manifest | 依現行 row／manifest retention 與 current snapshot 引用、writer lock／generation 保護清理；舊 `CORE_RETENTION_FENCE_URI` 歷史研究保留 gate 已取消，不得用它當永久阻擋 |

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
