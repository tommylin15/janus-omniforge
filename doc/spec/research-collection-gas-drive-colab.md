# D07-PRE｜Colab → Drive 月資料夾研究資料唯一有效契約
更新：2026-10-20。狀態：COLAB_CODE_IMPLEMENTED / LIVE_COLLECTION_PENDING。檔案路徑因既有 GitHub 連結保留，**內容正式覆蓋舊 GAS→ZIP 方案**。

## 唯一資料路線
**官方 TWSE/TPEx（歷史每日全市場行情 + 上市/上櫃公司名冊）→ Google Colab 手動 Python 批量採集、斷點與品質處理 → 私有 Drive `janusChatGPT/資料源/YYYY-MM/` → Colab 因子／標籤／模型 OOS → Janus Mart 受控匯入。** 無需 GAS、GAS Loader、GCP 重訓 Jobs、BQ ML/OOS；Colab MCP 若將來可用只作操作介面，不列前置必要條件。目前 ChatGPT 尚未連上 Colab MCP。禁止把程式已提交冒稱 Colab 現場已執行。

## 普通股母體及歷史限制
- 僅 TWSE／TPEx 上市上櫃**普通股**；以官方公司基本資料（TWSE `opendata/t187ap03_L`、TPEx `mopsfin_t187ap03_O`，必要時官方 CSV）建立白名單，ETF、ETN、基金、權證、債券及非普通股在**下載後入庫前**過濾。優先用官方名冊，而非單靠四碼。
- 歷史按**每日整市場**查詢 TWSE `MI_INDEX` 日期 API 與 TPEx 歷史每日行情，不把 OpenAPI `STOCK_DAY_ALL` 目前快照誤用成歷史 API；每市場×交易日約一筆 HTTP 請求。遵守回應錯誤／429 與限流，不迴避來源限制。
- **重要限制：官方最新公司名冊並非歷史逐日有效名冊，包含不了當時曾上市但已下市的股票。** 首版明列 `historical_survivorship=CURRENT_MASTER_ONLY`、`historical_pit=NOT_VERIFIED`、`research_70pct_certified=false`，只能做研究 PROBE；即使月檔完成，也不能聲稱全歷史 PIT、全市場 70% 品質合格或正式訓練核准。後續如需正式研究門檻，須補歷史普通股名冊或取得合規完整來源及按月適用分母。
- 研究採集正式目標仍以 TWSE、TPEx × dataset × month 的適用資料涵蓋率 ≥70% 衡量；上市／上櫃正式 Core 的 TWSE ≥90%、TPEx ≥70%、Owner 個人行情／ETF 顯示不變。缺值不可補造；來源時間貼標，不得倒填 published_at／observed_at。

## Drive 每月資料夾與效能
```text
janusChatGPT/資料源/
  _control/universe-r1.json
  2025-01/
    ohlcv-r1.csv.gz
    universe-r1.csv
    quality-r1.json
    manifest-r1.json
  2025-02/
    ...
```
- 一個月份一個 Drive 資料夾；相同月份的新資料來源或修訂使用 `r2` 等版次檔名，不能無聲覆蓋已使用的資料。
- 每個來源／市場以 10 個平日作單一壓縮 checkpoint；Colab 暫停後重跑只抓未完成批次。**整月資料與 manifest 校驗後刪除該版中繼 checkpoint**，避免大量碎檔。來源原始回應 SHA256、日期與已收錄 row count 列入 manifest。
- 首版實作僅 OHLCV，其他 valuation/financials/institutional/market_activity/events/benchmark 各依取得授權與官方可用性逐步寫入同月份資料夾；目前缺少的保留 `UNAVAILABLE`，不造空資料或假數字。
- 尚未結束的月份不得封存，並遵守人工 Colab 執行／限速／休市日及中斷續跑。個人非商業研究不等於自動取得所有 ML 訓練、保存和散布權；不得寫入 Owner 私有成本、現金、交易、OAuth token 或秘密。

## D07／上線界線
Quant/Risk 先建立 baseline＋challenger；Valuation/Fundamental 視實際資料，Event 沒有合格標註時 rules only。完整 PIT、成熟標籤、OOS／walk-forward、評估 hash 與訓練授權到齊才可進入受控 Janus Registry；LLM 無 canonical number／最終 publication 權力。已退役舊 GCP/BQ 研究路線按 [唯一結案收據](../archive/d07-gcp-bq-retirement-live-2026-10-20.md) 維持 CLOSED，正式 Stage/Core/Mart、Owner 和週 Iceberg 不受影響。

**實作與操作**：[Colab 唯一 README](../../research/colab/README.md)；**唯一進度**：[Active TODO](../todo.md)。
