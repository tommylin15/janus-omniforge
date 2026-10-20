# D07-PRE｜GAS／Drive／Colab 研究資料唯一有效契約
更新：2026-10-20。狀態：DESIGN_APPROVED / IMPLEMENTATION_NOT_VERIFIED。本規格取代舊「必須從 Cloud Run／Canonical Iceberg／BigQuery ML-OOS 匯出模型訓練資料」的 D07-PRE 前置要求。新流程不等於已部署，相關 runtime 完成狀態須另驗。

## 1. 唯一新研究資料路線
**GAS（UrlFetchApp 分批／checkpoint／續跑）→ 已確認允許此用途的第三方資料源（FinMind API 優先）→ Google Drive 私有 janusChatGPT/資料源/YYYY-MM.zip → Google Colab 人工執行特徵／標籤／訓練／OOS → Janus Mart 受控模型接收、驗證、版本管理和推論。**
研究原始資料不必先通過 Cloud Run、Stage、Core、BQ、GCS，Core 已有的公開欄位可以唯讀比對，卻不是研究資料的強制上游。不使用舊 `specialist-retrain`、B5～B8 ML/OOS 中轉或 BQML 建立新訓練流程；BigQuery 的現役非研究用途需分別稽核，不能按產品名稱全刪。

## 2. 母體、品質與第一批目標
- 研究母體限全 TWSE／TPEx 普通股，**排除全部 ETF、ETN、債券、基金、權證與非普通股**；每月依實際名冊儲存股票清單，不得以舊 Liquid 500 或今日清單硬套歷史。
- **研究用資料品質統一 70%，TWSE、TPEx 分市場／dataset／月份各算**。分子為實際符合該 dataset 必要欄位及單位條件的 eligible 股票／應到資料列，分母為該月合格普通股與應到 period；財報/事件按當月應公布／實際事件計算，不將未公布視為缺漏。部分成功可保存但標 PARTIAL；缺值/null、不適用和失敗應分開。
- **只在研究收集層適用 70%**，現行正式 Core 的 TWSE ≥90%、TPEx ≥70%，以及 Owner 個股總資產、正式 API/行情合格規則都不變。
- 第一批盤點現行持股／觀察股的**公開資料欄位**，不匯出 Owner 成本、張數、交易或現金；ETF 連抽樣研究母體也不納入。Quant：OHLCV、量額、指數、法人與公司行動；Risk：OHLCV、指數及可衍生波動/Beta/CVaR；Valuation：PE/PB/殖利率/EPS/ROE，另查每股淨值/股數/FCF/同業；Fundamental：營收/EPS/淨利/ROE/負債，另查現金流、CapEx、毛利率、營益率；Event：事件ID/內容/來源/類型，另查方向/重大性/真人標籤。
- **採集第一輪只檢查欄位能否取得、實際值與非空比例。** 將 published_at、observed_at、fiscal_month、version、collected_at 等實得時間資料貼標，不要求先通過歷史 PIT 連續性／兩年完整回溯才開始收集。正式報酬回測、OOS、模型 promotion 仍須驗標籤成熟及 future leakage，不可倒填虛構當時可得的資料。

## 3. 月檔與 GAS
每月一份 YYYY-MM.zip：universe.csv、ohlcv.csv、valuation.csv、financials.csv、institutional.csv、market_activity.csv、events.jsonl、benchmark.csv、quality.json、manifest.json。沒有可用資料源的子檔標 unavailable，不填假值。GAS 單次執行時限內分批保存 checkpoint、來源及 content SHA；重試缺漏而非重新下載整月；月檔封存成功才供 Colab，修正用有版次的可追溯新檔，不能無聲覆寫正在使用的研究輸入。

用途為個人非商業研究，不新增付費 API。但這不等於免除 API 速率、存取、保存、再利用、ML 訓練及禁止再散布條款；FinMind 以當次帳戶允許的 free plan 使用，Yahoo 未明確允許自動抓取前不作預設。不得將 secret、OAuth token 或 Owner 個資送入公開 log、研究成果或 GitHub。

## 4. 立即退役舊研究執行器，不等待新開發
- **確認新架構不使用、正式服務無相依者現在就移除**，不等 GAS／Colab 新鏈驗收後才移。首批為 Cloud Run Controller 舊 `specialist-retrain` 月度 due、手動 workflow/request、Mart 同名舊 fit 操作，既有 pending 需安全標 skipped／retired。
- 唯讀盤點 Cloud Run Jobs/Scheduler、BQ dataset/table/view/query、相關 GCS 研究暫存與其真實引用；專屬舊研究路徑立即停用／移除，讀回後註記資源 ID、實刪數、備援。不能憑字串匹配刪除仍服務正式 Screening/API 的共用資源。
- 正式 Janus EOD ingestion、market screening、個股／持股／Owner API、Mart、Stage 48h、週 Iceberg 維護、備份保留原職責；GAS 有自己的分批 trigger，不屬 Janus 正式 Cloud Scheduler 第二個 controller。
- 必須分別記錄 REMOVED_FROM_MAIN、CI_PASS、DEPLOYED、RUNTIME_DISABLED、BQ_DELETED 等狀態；GitHub 退役不等於 GCP 已真刪。

## 5. 五模型品質與單一工作入口
Quant／Risk 優先實驗，Valuation／Fundamental 依可得欄位，Event ML 沒有真實授權人審標籤維持 rules。每角色保留缺值、provenance、可重現資料 hash、OOS 和獨立 promotion gate；研究資料不可升格 canonical。工作只在 doc/todo.md 的 D07-PRE／D07，不創造平行 WBS。