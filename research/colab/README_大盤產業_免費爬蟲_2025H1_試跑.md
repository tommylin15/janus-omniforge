> **2026-10-24 政策更新**：研究數字與歷史結論保留；本文舊有逐來源／全歷史 PIT 補證、精確時間校準及新前瞻成熟等待不再是工作或發布前置。取消例行稽核，依 [研究精簡政策](../../doc/spec/research-simplification.md) 按需評估；不把取消視為 PASS。

# Janus｜大盤／產業免費爬蟲 Colab｜2025H1 試跑

> **研究試跑版、尚未執行實際抓取或測試。** 此版不使用 FinMind 付費 API、不貼標、不改 canonical CURRENT／模型 Registry／已穩定的個股 00A。

## 操作方式

1. 在 Google Drive `給ai專用/janusChatGPT/CoLab程式` 打開 `00_大盤產業_免費爬蟲_2025H1_試跑.ipynb`，選擇「使用 Google Colaboratory 開啟」。或從本文件相同 GitHub 路徑開啟。
2. 執行第一個程式格掛載 Google Drive；再執行第二個程式格，即會收取 **2025-01～2025-06 全部月份**，而非僅測試一日或一月。
3. 程式預設：`START_MONTH='2025-01'`、`END_MONTH='2025-06'`、`MAX_REQUESTS=360`、`MAX_MINUTES=90`、`INTERVAL_SECONDS=2.0`。不要以高並行方式對官方資料站發大量請求。
4. 停止後或重新開啟時，重新執行即可讀取各分區 checksum 續抓未完成資料；不需要重新開始。

## 四類來源

| 資料 | 方式 | 注意 |
|---|---|---|
| TWSE 大盤 | TWSE `indicesReport/MI_5MINS_HIST` 月資料 | 取得交易日及 OHLC |
| TWSE 產業類股 | TWSE `rwd/zh/afterTrading/MI_INDEX?type=ALLBUT0999` | 參考 [claude-cloud-premarket-brief](https://github.com/timwei0801/claude-cloud-premarket-brief) 的表格解析策略；按已驗證交易日查詢 |
| TPEx 大盤 | TPEx 官方月度 `daily-indices`、`indices-pricing` 候選路徑 | 僅 JSON+有月份有效指數列才會標 VERIFIED |
| TPEx 產業 | TPEx 官方月度 `daily-sector`、`idxsm` 候選路徑 | 需要在你的 Colab 現場確認 API 格式與可存取性 |

[Tw_stock_crawer](https://github.com/nk7260ynpa/Tw_stock_crawer) 的 TPEx `tpex.py` 是**上櫃個股**資料，不含官方產業類股指數；本試跑版參考其 HTTP/非 JSON 診斷邏輯，但不會從個股 `df_tpex` 造出官方指數點數。

## 實際輸出

執行前確認 Drive 掛載根目錄為：

`/content/drive/MyDrive/給ai專用/janusChatGPT`

研究資料儲存：

`.../janusChatGPT/資料源/大盤產業_免費來源_2025H1_試跑/`

每個成功分區包含原始回應 `raw-<sha256>.json`、標準化 `normalized-<sha256>.json`、驗證收據 `receipt.json`。重新執行只有驗證收據與檔案 checksum 正常的分區才跳過，否則失敗狀態會保留供診斷。

每次作業執行期間、正常結束或可捕捉的手動停止，持續寫出：

- `progress_latest.csv`：每個來源／分區 VERIFIED、FAILED、PENDING、WAITING_CALENDAR、原因與列數。
- `progress_latest.json`：整體期間、各來源成功／未完成數、最新完成位置、下一個待補分區、請求總數。
- 分區內 `error_latest.json`：最近一次失敗原因。

如 Colab 強制中斷導致 `finally` 無法執行，前面完成的分區與逐步更新的進度仍在 Drive；重新執行時會讀取 receipt 恢復。

## 預期侷限與檢查結果

- **本次依要求不執行收檔試驗**；這份程式與 API 整合尚未獲得實際 Colab PASS。
- TPEx 端點若回 HTML、403 或格式不同，會記錄 `FAILED`，而不是寫假資料。請把失敗月份及 `progress_latest.json` 貼回來，再依現場回應修正。
- `VERIFIED` 代表該分區 JSON 解析、欄位與 checksum 通過；尚不能代表跨歷史期間的產業分類完整性或研究因子可直接投入 PIT 訓練。
- 本版本不將個股現行產業分類回填 2025，亦不將報酬指數冒充價格指數。
- 所有資料僅供 `RESEARCH_ONLY`，須遵守各來源允許的用途與標示規則。
