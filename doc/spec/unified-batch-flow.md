# 統一批次與資料快照契約

更新：2026-10-24。狀態：CODE／文件交付；TEST、DEPLOY、LIVE ACCEPTANCE 均 NOT VERIFIED。
本文件是批次時段、端到端依賴與備份政策的唯一入口，覆蓋舊每日時段與 GitHub 備份 cron。四個模型按可發布設計；這不是目前 Registry、模型效用或 runtime 已通過的宣告。

## 1. 決策與兩方案

Verdict：ACCEPTABLE WITH GUARDRAILS；優先 P1。這是既有系統整併，不新增服務。
| 面向 | A：既有 Controller＋既有 Worker | B：新增 Workflows 編排 |
|---|---|---|
| 業務／架構 | 單一兩小時入口，重用 occurrence | 單入口，服務端步驟鏈 |
| 複雜度／交付 | 小；沿既有 Python、鎖與 queue | 新部署、IAM、計費與錯誤語意 |
| Cloud Run／DB／網路 | 只跑到期工作；共享 busy fence | 額外 orchestration API |
| 安全／成本 | 不擴 IAM；既有有界資源 | 新資源與 IAM 須另評估 |
| 維運／長期維護 | 一份時段表；無常駐等待 | 兩套編排定義需維護 |
| 失敗隔離／回復 | 每一階段有持久終態；回復舊 image | Workflow execution 歷史較完整 |
| 適配性 | 最貼近目前個人研究系統 | 嚴格完成時限、多租戶才有價值 |

選 A。不把整條流程塞進長時間 HTTP 或讓 Controller 常駐等子工作。代價是跨 Worker 最多等下一個兩小時 tick；要更短延遲才重新評估 B。

## 2. 唯一入口與執行表

Cloud Scheduler `30 */2 * * *`，`Asia/Taipei`，唯一目標既有 `janus-batch-controller`。
不新增 Scheduler／Job／PubSub／Cloud Tasks；GitHub Actions 不執行任何日常業務、備份或清理 cron。
既有 VM 一分鐘 timer 只是領取 Controller 已建立的備份 request，不自行建立日期工作。
每兩小時喚醒不等於每兩小時全市場重抓。時間均為 due，不是保證完成時間。

| 工作組／實際 batch | Due | 內容與依賴 |
|---|---|---|
| 市場收取 `ingestion` | 每日 06:30、14:30 | 缺口／增量財務補收 → 正常收取 → Stage → Core → Serving／ready event；同 Worker 順序完成 |
| 市場分析 `market-screening` | 週一至五 08:30、16:30 | 依同日最近 ingestion；早上只處理分析 queue，下午加全市場 screening；四角色、Fact Pack、產品投影共用原 Mart |
| 私人資料 `private` | 週一至五 10:30、18:30、22:30 | 前兩次依市場分析；22:30獨立補償，只用實際可用行情；事件、持股／損益、觀察設定與輸入快照 |
| 即時異動補償 `mobile-ledger` | 每個偶數小時 :30，有待處理資料才跑 | 既有 durable queue；User App 寫入與既有即時重算不等待 cron |
| 私人備份 `ledger-backup` | 每日 02:30 | Controller request → 既有 PG VM dump → daily／weekly／monthly 不可變副本與讀回 → 同執行器保留清理 |
| Stage 清理 `stage-cleanup` | 每日 22:30 | 48h TTL；有效租約、固定 generation |
| Iceberg 維護 | 週六 22:30 | compaction → Mart cleanup → Core cleanup；依終態跨 tick，不承諾同日完 |
| 手動 collection／analysis queue | 每 tick 有工作才派送 | 保留五天窗口、lease、指定 execution，不重放超齡歷史 |

刪除獨立 data-supplement 與 mart 定時定義，不刪其 API／手動能力。三個 Iceberg 子步驟保留，因 writer 與讀者依賴不能安全硬合併成一次刪除。
正常盤後預期 14:30 收取、16:30 分析、18:30 私人更新；上游過慢會順延。來源未公布／缺值顯示 partial，不為準時補造數字。
日曆依既有 holiday_overrides；週末仍允許財務增量、私人事件補償、備份／清理。

## 3. 收取、清理與資料路線

1. 官方批量日行情與 PE/PB 一次收全市場、重用結果；持股／觀察股另做有界財務與缺口補收，不逐股重抓全市場。
2. Stage 原始資料與既有來源／取得時間欄位；相同 payload 重用。只驗必要股票代碼、期別、單位、數值與日期；取消的歷史稽核不恢復。
3. Core 按來源資料鍵 upsert，保留真實資料日期；財報累季／單季、價格還原基準不得混用。
4. Serving 是 UI 快讀投影；Mart 是因子、篩選、四角色與 Fact Pack。UI 不直接掃 Iceberg。
5. 每批有界消化分析 queue；共用現有 input hash／模型版本 cache，沒改動不重算。同一股票跨 Owner 共用公開模型結果；私人成本、現金與設定不混入公開 X。
6. Quant、Risk、Fundamental、Valuation 為四模型。Event 是公告事實及舊資料相容欄位，不新增第五模型或新排程。訓練留 Colab，日常只 inference；不自動重訓／切 Registry。
7. Fact Pack／確定性卡片先落地；CEO 長文沿既有 Gateway 按需產出、保存 Owner history，無每兩小時 LLM 全市場報告。缺模型 artifact 必須顯示 unavailable，不能以 baseline 冒充已發布 ML。

## 4. 私人操作與 UI 快照

買賣記帳不是券商下單。交易、修正、沖銷、觀察股增刪與設定先由既有 Owner API 原子保存及版本化，UI 立即讀回；MCP 保持唯讀。
Private pipeline 保存其實際使用的 ledger_version／watchlist／profile／positions／risk 輸入與結果組合為 `private.workspace_snapshots`，schema v1，owner＋內容 hash 去重。
此快照是分析實際輸入，不宣稱不同 SQL 讀取構成同一 DB transaction。變動中的資料由既有 change queue 再重算。
既有 ledger_events、watchlist_events、profile revisions 保留逐次操作；快照不取代事件帳、不額外寫一份全量交易歷史。
公開 target snapshot 只有去識別股票集合；私人數量、成本、交易與設定不得進公開 bucket、模型 cache 或一般 log。
UI 顯示資料日期、分析日期、更新中／部分成功及上次成功內容；新交易與舊 valuation_version 不可呈現同一最新完整狀態。Admin 顯示三大組與實際子工作、下一 due 和失敗原因。
Private snapshot 是 current Iceberg table 的資料列，不是舊 Iceberg snapshot 保留政策；不因 current-only 清理而刪目前表內歷史列。

## 5. 每日／每週／每月備份及清理

| 層 | 每日 | 每週 | 每月 |
|---|---|---|---|
| PostgreSQL（含私人帳本、現金、觀察設定、控制與 catalog） | 完整 logical dump，保留7份 | 每 ISO 週首個成功 daily 另存1份，保留4份 | 每月首個成功 daily 另存1份，保留6份 |
| 備份清理 | 同 VM 執行器備份讀回後處理；最新 daily ≤36h | 同一保留函式管理週副本 | 同一保留函式管理月副本 |
| Stage | 48h 到期有界清理 | 無第二次全量重抓 | 無 |
| Core／Mart | 不逐日 compact | 既有週六 compaction→retention | 無獨立清理工作 |
| Private 原始事件／設定 | 不套公開 TTL | 不刪 Owner 原始紀錄 | 不刪 Owner 原始紀錄 |
| 模型／報告 | 沿既有分類；保護 ACTIVE／rollback | 不做例行模型稽核 | 不自動 retrain／新OOS gate |

週／月副本是日備份的位元副本，不再 dump 三次；名稱為週一 YYYY-MM-DD、月份 YYYY-MM。週／月既有物件不可覆寫。
每日最多刪3份 daily、1份 weekly、1份 monthly；固定 generation、清理前重讀、清理後數量／bytes 讀回，失敗保留 partial 收據並於下一次成功日備份後重新評估清理。
每日備份成功與 retention 成功分開記錄；清理失敗不能將可用備份改成 failed，也不能宣稱整輪成功。
注意：PG dump 不含 GCS／Iceberg data files；這不是完整 lakehouse 歷史備份。Core／公開 Mart 沿可重建路徑，模型 artifact 及私人不可重建內容沿原保留政策。舊 catalog dump 不保證可指回已刪除的 Iceberg 舊檔；還原必須依交接 WI 驗證目前資料可讀，不能以 pg_restore 成功宣稱全系統已恢復。
備份既有 bucket／VM／prefix 不變；不新增付費資源或擴大 IAM。現有 VM 沒有 prefix delete 權限則標 BLOCKED，不自動 grant。

## 6. 外部作法融入（2026-10-24 查閱）

| 來源 | 已確認能力 | 採用方式 |
|---|---|---|
| [TWSE OpenAPI](https://openapi.twse.com.tw/) | 上市日行情、PE/PB／殖利率等介面 | 優先批量收取後共用，不逐股每日重複查 |
| [TPEx OpenAPI](https://www.tpex.org.tw/openapi/) | 上櫃行情、估值等介面 | 上市／上櫃分流 adapter、統一 Core；不可把上市成功當全市場完成 |
| [FinMind](https://finmind.github.io/)／[快速開始](https://finmind.github.io/quickstart/) | 股價、財報、月營收等；有 token／頻率與付費資料集區分 | 作缺口候選；先重用現有資料，未確認當前資料集存取條件不自動啟用、不新訂閱 |
| [TWSE 資訊使用規範](https://www.twse.com.tw/zh/products/information/use.html) | 即時／延遲資訊另有契約規定 | 日終開放資料與即時報價權利分開，不把公開網頁等同任意再散布 |

這些是來源介面與設計借鑑，不代表本輪已連線採集或驗證新增 adapter。現有 Yahoo EPS 補缺能力沿用；不額外引入網頁爬蟲全市場日批。

## 7. 狀態、風險與交付

- 實作以既有入口與環境參數為主，無新增 IAM／付費 runtime；新 schedule 需部署後才生效。
- 主要風險：兩小時跨階段延遲、未部署混合版本、來源延遲、備份 executable 未同步、週／月副本尚未形成、模型 artifact 尚未正式接入。
- 回復：保存切換前 cron／image digest／VM scripts；先停止新入口再恢復舊版，不能雙 Scheduler 並行；不刪現有備份或私人快照。
- 本輪不執行測試、CI、部署、migration 或 live 驗收。後續唯一操作入口：[AI交接 WI](../runbook-unified-batch-ai.md)；全部剩餘工作在 [TODO](../todo.md)。
