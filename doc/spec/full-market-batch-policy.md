# 全上市櫃個股、總控批次與即時快照契約

**最新執行狀態：**使用者已恢復 P0-1 至 P1-2 合併開發；下方「只更新文件停止」為前次盤點邊界，不再是開發禁令。新版程式／migration 未通過整合驗收前維持 PARTIAL。

更新：2026-10-14。新增分市場缺失率政策（上市 10%、上櫃 30%），取代原統一 10% 門檻；保留 2026-10-13 取消 500 檔母體及總控外業務定時排程決策。實作／切換仍需獨立驗收；本規格不是完成證據。

## 全市場與缺失率

- 市場資料、screening、研究母體、搜尋及新增關注的股票資格，全部改為 TWSE 上市與 TPEx 上櫃的全部個股，以官方有效名冊及證券類型為準，數量隨生效日變動。不再依週成交量截取 500，不以固定 1,700／2,000 取代 500。興櫃未因此加入。
- 個人持股仍由本人 ledger 決定；既有 ETF（含 00719B）行情與持股支援保留，ETF 不混進普通股 coverage 分母。每人／平台既有 50 筆關注 quota 屬另一項限制，這次取消的是股票資格的 500 檔限制。
- 原歷史 500 研究／OOS artifact immutable，保留當時母體；新研究採各歷史日期可證實的全市場名冊，不能以今天名冊回填過去或覆寫舊研究。同名舊欄位若暫留相容，API 須有新 scope/version，不能把全市場數據標成舊 500 語意。
- **必要資料缺失率分市場判定：TWSE 上市 ≤10%（含 10%），TPEx 上櫃 ≤30%（含 30%），才通過各自 coverage 驗收。** 定義為該市場、資料集、資料期間的「預期應有且合法可用資料之缺失股票數 ÷ 預期適用股票數」。TWSE／TPEx 分開檢查並另列合計；不能拿上市大量成功掩蓋上櫃失敗，也不能用已抓到的股票當分母。
- 預期名冊在執行前固定版本；missing、stale 超過資料契約允許期限、非法值都不算成功。停牌無成交、尚未上市／已下市、不適用欄位按事前固定規則分類，公布排除原因與數量；不可為過關臨時縮分母。分母為零標 not_applicable／unknown，不算 100%。月營收／季報按應公布期間，不因非日頻而每天列缺。
- 上市缺失率超過 10% 或上櫃超過 30% 時，對應市場／資料集／期間的 coverage gate 不過；列明缺漏並先做有界補漏，已通過的獨立資料可繼續服務。**上櫃放寬不適用於上市、個人持股估值、來源授權或模型品質。** 缺失可容忍不等於拿零補缺，來源／隱私／金額正確性與模型品質 gate 不豁免。個人正式總損益仍須本人需要的價格／成本完整，不能用市場 coverage 門檻發布缺價總額。
- 全市場指母體，不代表每次全歷史重抓或所有股票每日五模型重算。全市場低成本資料／screening，深度更新按需求與資料變更去重，研究按全市場分片及固定 snapshot 執行；批量大小、API 分頁、HTTP 500、500 筆 change-log 上限不得因文字相同被機械刪除。

## 唯一排程責任

- **Cloud Scheduler → `janus-batch-controller` 是所有業務定時工作的唯一入口。GitHub Actions 唯一允許的 `schedule` 是備份清理。** CI、測試、Release、migration 及受控手動維運保留；手動業務操作需登記總控 request／occurrence 及共用 fence，不可用 push/request JSON 另建自動業務排程。
- 研究延伸／觀察／訓練也遵守總控；未遷入的舊研究定時入口停止，不偷偷用 workflow_dispatch、外部 cron 或另一 Scheduler 補跑。原研究 artifact 可讀，不重播舊固定 request。
- 總控只做 due／dependency／執行狀態決策，短鎖提交意圖後派送；不持鎖等待 worker 完成。統一 occurrence（操作、資料日、scope/version）、request 去重、並行上限、lease、逾時／ambiguous 與補償記錄。Cron 不等於資料 ready，必須核對資料日和成功快照。
- 備份產生也是工作，現有 VM timer 須納入遷移：由總控管「今日備份完成」依賴、沿既有 VM 本機備份工具執行；確認執行／權限／還原證據後再關舊 timer。不可只刪 timer 造成沒有備份。GitHub 清理僅在新備份成功且保留條件成立後執行，獨立檢查 backup age；原三份保留規則不任意擴張。
- 總控喚醒頻率依 dispatch lag 實測決定。現有每小時一次不能拿來滿足秒級操作；需要的非同步任務可由 API 登記後立即喚醒同一總控派送器，並由 Scheduler 作恢復掃描。這是共用權威，不是所有操作等下個整點。

## 即時、快照、批次責任

| 需求 | 正常路徑 | 快照／失效方式 |
|---|---|---|
| 記錄交易、股數、成本、成交損益 | backend 同一交易提交 deterministic projection | owner＋ledger_version；保存成功即新版，衝突重驗，不等 Cloud Run cold start |
| 交易前試算 | backend 唯讀快速計算 | ledger_version＋輸入＋費稅規則版本；不能把試算寫成成交 |
| 持股／關注／個股現價 | PostgreSQL 最新合法報價先回，盤中按需批量更新 | 共用 symbol/market/source/quote_at/version；既有 60 秒 TTL、10 秒手動節流；錯誤留最後成功值及 stale |
| 持股 operational 估值 | 相同 owner ledger version＋quote set | 單次有界讀取／計算；持久化快照可選，用實測決定，不能跨版本拼接 |
| 今日、圖表、搜尋 | 公開 serving recent／latest、官方有效名冊快照 | 新 Core commit 後更新；不在每次頁面掃 Iceberg／全市場 HTTP |
| 正式 Private Mart 報表 | 交易事件合併 dirty owner，立即異步派送；EOD 新價格後補估值 | owner＋ledger checkpoint＋valuation date＋quote/source version；原子發布整套結果，失敗保留舊版並顯示 pending |
| 財報／事件／深度分析 | 官方發布增量，按 dirty symbol／角色更新 | source/input hash 相同即 reuse；不因頁面刷新重跑 |
| 訓練、全歷史回補、品質／清理 | 總控低優先背景工作，分片可續跑 | immutable dataset/model/evaluation snapshot；與交易鎖、資源優先序隔離 |

快照沿用已有 tables／projection／cache，不建立全資料 warehouse 複本。公開與私人快照分權；登出／換帳清除私人 UI cache；回應需含 as_of、coverage、source、status 與版本。先建新版本並驗證再切 latest pointer；不得因部分更新把新舊資料拼成完整結果。保留必要前版與重建路徑，TTL 不是資料 freshness 的替代品。

## 實作及驗收

接手盤點見 [批次清冊](../archive/batch-inventory-2026-10-13.md)。全市場變更須一次覆蓋 SQL membership／rank constraint、ingestion、screening／研究讀取、Admin、搜尋／watchlist、API schema、UI、fixtures、tests 與資源界限。舊 migration 不改寫，用新 migration／相容退場及同源發布。

必驗 >500 且混合 TWSE／TPEx、新增／退出名冊、上市 ≤10% 與上櫃 ≤30% 的含邊界／超標、未知市場／分母、來源失敗、版本／owner 隔離、超過單批／row cap 的完整分片、crash resume 和同一輸入去重。保留 1 CPU／1 GiB 等現有成本約束，以分片／欄位裁切／快照先解決；不得直接提高資源。

排程切換驗收要證明無雙重派送、手動與定時共用記錄、實際 due→dispatch→terminal、資料 readiness、備份不中斷，以及持股／試算／交易的冷暖延遲。一次完成相依開發後集中驗收，不能以總控 Job SUCCESS 或新文件當全系統 PASS。
