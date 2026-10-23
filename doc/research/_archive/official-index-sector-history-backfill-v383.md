# Janus 四模型研究資料｜大盤與產業歷史補收 v3.8.3

日期：2026-10-23。**收集用 Colab Notebook（不是純來源探查）**。

## 使用方法

1. 在 Google Colab 開啟 `00_資料收集_v3.8.3_大盤產業歷史補收.ipynb`，執行「全部執行」，Google Drive 授權需由使用者本人完成。
2. 預設 `FACTOR_ONLY=True`、`FACTOR_SOURCE_PROBE=False`、`INDEX_HISTORY_BACKFILL=True`，跳過原 v3.8.2 舊的 264 批檢查／既有 OHLCV 補收，僅跑新增四類指數資料。
3. 預設從 2025-01 收到台灣時區**上個完整月份**。每輪限 70 次 HTTP 與 15 分鐘、間隔 2.5 秒；再次執行相同 Notebook，可從已驗證 Parquet 分區續接。
4. 驗收狀態查看 `janusChatGPT/資料源/JanusDataset_v3_202610/reports/大盤產業補收_latest.csv` 與 `大盤產業補收_latest.json`。每市場逐月／逐日顯示 `VERIFIED`、`SCHEMA_BLOCKED`、`SOURCE_BLOCKED`、`BUDGET_PAUSED` 等狀態。

## 真正補收的四種研究資料

| Source key | 市場 | 類型 | 查詢粒度 | 官方來源 |
|---|---|---|---|---|
| `twse_market` | TWSE | TAIEX 大盤 OHLC | 每月 | TWSE MI_5MINS_HIST |
| `tpex_market` | TPEx | 櫃買大盤 OHLC | 每月 | TPEx daily-indices |
| `twse_sector` | TWSE | 上市每日各產業類股收盤指數 | 每交易日 | TWSE MI_INDEX |
| `tpex_sector` | TPEx | 上櫃各產業類股歷史收盤指數 | 每月 | TPEx daily-sector |

**權利與可用性限制**：官方網頁與開放資料集列示的授權，不自動代表本次確切 HTTP endpoint 的取得、研究儲存、ML 訓練、部署與展示用途均已逐一核可。程式會保留來源／時間／原始 SHA 與 `REQUIRES_INDIVIDUAL_VERIFICATION`。TPEx 網頁後端 endpoint 的 `response=json` 實際返回 schema 尚未 Colab live 驗收：遇到不認得格式時將原始回應封存，標記 `SCHEMA_BLOCKED`，不得回報 `VERIFIED` 或亂猜數字；需要依實際 raw 修 parser。不得繞過 401/403/429。

## 資料與治理

- 新資料在 `derived/factor_inputs/official_index_backfill/v3.8.3/{source}/...` 下，**不覆寫** `canonical/CURRENT.json`、已完成 OHLCV/revenue/financials/valuation、舊模型或 Registry。
- 同資料重跑會驗證 receipt 與所有檔案 SHA-256，完整成功分區跳過，不重抓。
- 原始 raw / normalized JSON / Parquet 分別保存 SHA-256，Parquet 需可讀回且資料筆數一致；無法辨識日期、非同月／同日、重複鍵、不合邏輯的 OHLC、資料太少，都不會保存為 `VERIFIED`。
- `SOURCE_DATA_VERIFIED_COMPLETE` 只表示在指定期間／四類 partition 可驗證；**不代表**取得所有個股歷史產業成分／歷史 PIT 或 source license／正式模型 promotion 通過。
- 要讓個股使用產業動能作 X，還需有各股相對歷史日期有效的 `industry_membership`；不可用今天的產業名冊倒填 2025 年。

## 本地離線驗證

`python -m pytest -q test_official_index_backfill.py`：15 passed、1 skipped（本地環境缺 pyarrow，Colab 安裝格會安裝）。Notebook 所有 code cell 已 `compile()` 通過；**沒有執行 Colab OAuth／真實 TWSE、TPEx HTTP 補收，live results 未知**。

源碼與測試檔同時版本保存於 GitHub `main` 與 Google Drive `janusChatGPT`。此版研究用途、不自動跑貼標或訓練。
