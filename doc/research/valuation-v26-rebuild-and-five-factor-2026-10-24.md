# Janus Valuation｜v25 重建交付及 v26 五因子試訓（2026-10-24）

## 結果與界限

使用者要求：找回／交付 v25 完整模型封包；在既有資料計算 revenue_yoy；擴展 2024–2026 並比較 Ridge／XGBoost。維持研究模型，**不重抓全市場**、`publication_allowed=false`、不改 CURRENT、canonical、Registry 或 Risk ACTIVE。

### v25：REBUILT_AND_TESTED，非原版位元復原

- 已檢查本專案 GitHub research/chatgpt 及授權 Drive 的 janusChatGPT/模型研究/valuation 內容；未找到前一輪 v25 原本兩個 UBJ 與完整 ZIP，故 **絕不宣稱恢復了原 SHA**。
- 已用同一 v23 包的 4,000 個股票×月 FinMind 實際快照與 P0/P1 的 1,181,442 財報逐列清冊 **重新擬合** PE 與 PB 各一套 Ridge／XGBoost，重新保存兩份 .ubj、Ridge scaler/係數 JSON、validation/test predictions、report.json、來源 SHA／feature coverage。原始研究來源 ZIP 唯讀。
- 2023-08..09 log 倍數 MAE：PE train-only 中位數 **0.820786**，Ridge **0.800388**，重建 XGB **0.792825**；PB 依序 **0.494152**、**0.466287**、**0.433192**。PE 370 test rows、PB 622 test rows。此輪重新訓練參數/執行環境與歷史 v25 XGB 分數有小幅差異，不宣稱 bit-exact 等價。
- 四財務 X：roe_proxy、debt_ratio、log_total_assets、market_code；沒有可由此早期交集合理計算的 revenue_yoy，不憑空填滿。財務公布時點採 quarter-end+90d 的 **RESEARCH_NON_PIT** 假設而非史實公告日。
- 本地 targeted tests **6/6 PASS**，其中包含模型 UBJ 重新載入預測一致性、時點、防空值、防目標洩漏、YoY 缺月不錯位和四／五因子同樣本邏輯。

### v26：FIVE_FEATURE_RUNNER_READY，2024–2026 ACTUAL OOS NOT YET RUN

- 已定位既有 frozen research release `release-0bbae8d9c1ca7d8d` 的完整 Parquet：估值 36 個月 2023-10..2026-09，營收 49 個月 2022-09..2026-09，財報 15 季。
- 已製作獨立 Colab `26_Valuation_2024_2026_五因子_時間切分試訓.ipynb`，直接掛載上述 Drive package；不觸發下載/收檔 API。其程式內嵌於 Notebook，不依賴動態 main。
- revenue_yoy = 同股當月 revenue_twd/去年**同一自然月** revenue_twd −1；來源缺去年月或去年值非正則保持 NaN，禁止按「前12筆」錯位；設 source month-end+45d 的研究可用時點。財報採 quarter-end+90d 研究可用時點。研究資料源不是完整 PIT，標 `RESEARCH_NON_PIT`。
- 在**相同五項X非空樣本**上做四因子與五因子比較：train 2024-01..2025-06，validation 2025-07..12，test 2026-01..09；PE/PB 各獨立 baseline/Ridge/XGBoost、四個 UBJ、validation/test predictions、report/版本/SHA；無足量樣本時輸出 `INSUFFICIENT_SAMPLES`。
- **本次工作環境無 pyarrow/fastparquet，且無法從套件源下載；所以沒有實際執行 2024–2026 Parquet train/test，不得報假分數。** Colab 安裝 pyarrow 後「Run all」才會進行真實驗收；試算/合成測試不等同該時段實績。

## 交付位置與剩餘驗收

本輪模型重建及試訓 Notebook、程式與測試已封裝為當次對話的兩個可下載 ZIP（文件與下載鏈結由交付回應提供）。**本輪尚無證據顯示兩個 ZIP 已上傳 Google Drive 或 GitHub**，不能寫成雲端已封存。模型檔留在新研究包，不發布。

下一步只需在可以讀 Parquet 的 Colab 掛載目前 Drive，執行 v26 Notebook、讀回 `janusChatGPT/模型研究/valuation/v26_nonpit_five_feature_20261024/report.json` 與每個 UBJ／預測檔；核對 test 各自月份／模型同樣本及 PE/PB XGB 相對 baseline 是否穩定改善。
