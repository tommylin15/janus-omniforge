# Janus｜TPEx 官方大盤／產業 v2｜獨立交易日曆續收

**適用：** 2026-01～2026-09（Notebook 內可直接調整），無需 FinMind、付費 API 或手動編輯 Python 函式。本次只補收 TPEx；保留 TWSE 與個股既有資料。這是 Colab 研究資料收集程式，不會寫入 canonical／production 或啟動模型。

## 一鍵使用

1. 開啟 `00_TPEx大盤產業_獨立日曆續收_v2.ipynb`，執行第一個程式格掛載 Drive、第二個程式格開始收檔。
2. 預設月範圍 `2026-01`～`2026-09`；1 月已驗證分區會核對既有 receipt 和 checksum 後略過；2～9 月逐月補收。要改期間，修改程式格頂端的 `START_MONTH`／`END_MONTH`。
3. 完成／中斷後，到以下路徑看 TPEx 專用進度表：
   `/content/drive/MyDrive/給ai專用/janusChatGPT/資料源/大盤產業_免費來源_2025H1_試跑/progress_tpex_latest.csv`
   同目錄有 `progress_tpex_latest.json`。

## 修正重點

- **不再讀取 `twse_market` 作前置條件。** TPEx `www/zh-tw/indexInfo/inx` 月報本身含每日 OHLC 和交易日期，直接用來產生該月基準交易日； `www/zh-tw/indexInfo/idxsm` 月報的每個產業逐日與它比對。
- TPEx 大盤月報失敗時，先從官方 TPEx 產業月報建立日期，再依 `www/zh-tw/indexInfo/sectinx` 逐日抓取大盤（後續產業亦可採該端點 fallback）。不偷用 TWSE、週一到週五等虛構交易日，也不使用個股股價自行拼成官方指數。
- 至少需有 10～25 個工作日的月資料；產業每交易日至少 10 種價格指數；大盤／產業的交易日集合須完全一致，不能把部分收檔當全成功。**月份來源彼此一致並非獨立官方行事曆驗證，其他獨立來源交叉核對仍屬後續研究驗收。**
- 繼續保存官方原始 JSON bytes、normalized JSON、checksum、receipt 與錯誤分區 `error_latest.json`。已 VERIFIED 分區只讀回驗證，絕不重新覆寫成功數值。
- 新版進度使用 `progress_tpex_latest.csv/json`，**不覆寫舊版** `progress_latest.csv/json`，避免覆蓋 TWSE 的歷史驗收結果。`BLOCKED_MARKET_REFERENCE` 表示當月 TPEx 大盤未取得有效基準，不代表產業資料為 0。
- 研究資料 `RESEARCH_ONLY`；不將價格指數與報酬指數混用，不暗示歷史首次公告時間已獲認證，也不寫入 Janus canonical pipeline。

## 驗證與已知狀態

- 此版已以離線 mocked payload 完成 parser、checksum、續傳、無 TWSE 日曆及 fallback 測試；並以 2026-01 既有 21 筆大盤及 399 筆（19 類×21 日）產業 normalized data 檢查新 gate 通過。
- **尚未在使用者 Colab 遠端實跑 2026-02～09**，因此不能宣稱已收齊。若某月官方返回非 JSON、欄位變更、日期缺漏或 429/403，會在報表標示原因，下一輪續收。
- 官方出處：<https://www.tpex.org.tw/www/zh-tw/indexInfo/inx>、<https://www.tpex.org.tw/www/zh-tw/indexInfo/idxsm>、<https://www.tpex.org.tw/www/zh-tw/indexInfo/sectinx>。

## 原版與相容性

取代之前 `00_大盤產業_2025H1_TPEx官方修正版.ipynb` 的獨立 TPEx 日曆策略，但**不刪舊版、不改原分區路徑**。2025 年已收資料仍在相同 Drive root；新程式只依指定月份運作。
