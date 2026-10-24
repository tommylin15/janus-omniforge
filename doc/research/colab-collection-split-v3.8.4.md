> **2026-10-24 政策更新**：研究數字與歷史結論保留；本文舊有逐來源／全歷史 PIT 補證、精確時間校準及新前瞻成熟等待不再是工作或發布前置。取消例行稽核，依 [研究精簡政策](../spec/research-simplification.md) 按需評估；不把取消視為 PASS。

# Janus｜個股、大盤與產業獨立收檔 v3.8.4（2026-10-23）

## 已觀察證據
`大盤產業補收_latest.csv`、同名 JSON 與 20261023T062216665505Z JSON：2025-01～2026-09，63 requests；62 SCHEMA_BLOCKED、1 HTTP_ERROR，0 VERIFIED，84 待驗證分區。兩 JSON 內容完全一致。Drive v3.8.3 raw 顯示 TWSE 大盤、TPEx 大盤／產業的 HTTP 200 HTML 404，而非 JSON。TWSE 產業因沒有市場已驗證交易日曆而未進入任務。

## 真正分離的兩個 Colab 執行入口
1. `research/colab/00_資料收集_v3.8.4_個股.ipynb`：只改 v3.8.2 說明格；九個原 code cell 不變。獨立執行，不依賴大盤。
2. `research/colab/00_資料收集_v3.8.4_大盤產業.ipynb`：不含個股大型收檔程式。獨立 mount Drive／裝依賴／配置／執行大盤產業源。初次 `PROBE_ONLY=True`，只探查 2025-01 且最多 4 次請求；確認來源後才改 False。
3. ChatGPT 貼標仍由 `research/chatgpt/label_four_models.py` 獨立執行；Colab 不做 Y 貼標／訓練／publication。

## 補收修正與安全邊界
- `research/colab/official_index_backfill.py` 改版本 v3.8.4，研究輸出另存 `derived/factor_inputs/official_index_backfill/v3.8.4/`，保留 v3.8.3 raw/receipts，絕不寫個股 CURRENT、Risk ACTIVE。
- TWSE 大盤改為 `https://www.twse.com.tw/indicesReport/MI_5MINS_HIST` 的歷史報表路徑，仍須 Colab live 校對。
- TPEx 目前只有確認存在的 `.html` 官方資料查詢頁；**不是已驗證的 JSON API**。探查若只返回 HTML 將標記 SOURCE_FORMAT_UNSUPPORTED，而非假造數字。需依真實下載連結繼續驗證 API／CSV 解析及授權。
- HTTP 404/410 與 HTTP 200 HTML 404 會標記 SOURCE_ENDPOINT_INVALID；200 HTML 內容頁標 SOURCE_FORMAT_UNSUPPORTED，同輪只查該來源一次；401/403/429 保留拒絕處理，不繞過。
- raw SHA、UTC 時間、source URL/rights、不可變分區、normalized/Parquet 讀回維持。來源不可用時只有 raw 及失敗 receipt，不宣稱 VERIFIED。
- TPEx 月度產業指數實際更新至次月第七個交易日，建模特徵 PIT 需用可得時間而不是只用交易日；歷史產業歸屬與官方 endpoint ML 使用授權尚待個別驗證。

## 測試及驗收
本地原 15 passed 1 skipped 新增三項測試後 `18 passed, 1 skipped`；兩 Notebook code cell 可 compile，個股 code cell 與 v3.8.2 完全一致。**尚未完成 Colab OAuth、TWSE/TPEx 真實回應與 Parquet 實收驗證**，不是 source success 或模型上線。

官方入口：https://openapi.twse.com.tw/ 、https://www.twse.com.tw/zh/indices/taiex/mi-5min-hist.html 、https://www.tpex.org.tw/zh-tw/mainboard/trading/info/daily-indices.html 、https://www.tpex.org.tw/zh-tw/mainboard/trading/statistics/indices/daily-sector.html

## 2026-10-23｜使用者 Colab 2025-01 立即回報與修正

- 已從使用者 Colab 輸出確認：`twse_market` 2025-01 VERIFIED 15 筆；`twse_sector` 2025-01-02 VERIFIED 41 筆，01-03 BUDGET_PAUSED；TPEx 市場／產業原 `.html` 登陸頁都回 `SOURCE_FORMAT_UNSUPPORTED` 與 `NON_JSON_HTML_PAGE_NOT_API`。
- 根因：00B 誤設 `/content/drive/MyDrive/個人用/janusChatGPT`；TPEx 兩來源把 `.html` 展示頁當 API；初探最多四次請求、TWSE 產業按日抓，第四次之後暫停符合配置。
- 本次改為 `MyDrive/給ai專用/janusChatGPT`；TPEx 改用 `/www/zh-tw/` JSON **候選**端點。候選端點和欄位尚無 2025-01 Colab 真實回應證據，若回 HTML/schema 不合仍 fail closed，不能冒稱已修通或已補足。
- 00A 已採正確路徑且穩定，本次維持不變；00B 有內嵌 helper，須與 `official_index_backfill.py` 同步，避免 Colab 跟 GitHub 外部 helper 分歧。研究 `CURRENT`/Risk ACTIVE 不動。既有 VERIFIED receipt 跨重跑保留，TPEx 失敗 receipt 可更新但 raw hash/attempt 不刪改。
- 此修正的實際 Colab 掛載、TPEx 成功列數、日曆完整度、Parquet 讀回及 Drive 檔案覆寫需另有 runtime/Drive evidence 才能改為 PASS。
