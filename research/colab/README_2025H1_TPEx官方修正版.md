# Janus｜TPEx 官方大盤與產業 2025H1 Colab 修正版

## 直接執行
使用 `00_大盤產業_2025H1_TPEx官方修正版.ipynb`，第一格掛載 Google Drive，第二格直接補收 2025-01～2025-06。
Notebook 自含程式，不需要額外下載 `.py`，也不需要 FinMind 或付費 API。

## 改動
- 先從 TPEx 官方 `www/zh-tw/indexInfo/inx` 月報取得上櫃大盤交易日 OHLC。
- 從 `www/zh-tw/indexInfo/idxsm` 月報取得各上櫃產業**價格指數**日收盤；排除報酬指數，兩者不可混淆。
- 若月報不是相容 JSON 或缺少欄位，自動改由已在開源專案使用的 `www/zh-tw/indexInfo/sectinx` 逐日抓櫃買指數及類股指數。
- 沿用 TWSE `twse_market` 已成功的交易日作預期日曆：TPEx 月分區必須覆蓋全部已證實交易日，產業每日至少十個指數；否則標記 FAILED，不以 partial 冒充 VERIFIED。兩個市場特殊例外需由真實回應另行核對。
- 每個成功月分區保存原始 bytes（fallback 時以帶 Base64 bytes 的 manifest 保存）、標準化 JSON、receipt SHA-256；中途斷線後下次可續收。
- 完整進度保存於 `progress_latest.csv`、`progress_latest.json` 及各失敗月分區 `error_latest.json`。
- **不重新下載或覆寫 TWSE 116 個成功交易日與指數分區、不修改個股收檔、不寫 canonical CURRENT。**

## Drive 輸出
`/content/drive/MyDrive/給ai專用/janusChatGPT/資料源/大盤產業_免費來源_2025H1_試跑/`

## 注意
此修正版依據 TPEx 公開月報入口，以及 `chunkai1312/node-twstock` 的 `sectinx` JSON fixture 與其解析測試設計。已做 Python 語法檢查，**未執行任何真實收檔或 Colab 遠端測試**（依使用者要求）。如果 TPEx 拒絕 Colab 的請求、資料僅部分覆蓋、歷史類股組成不同，報表會標 FAILED/PENDING；應查看來源回應，不能假稱成功。

參考：
- 官方月大盤：https://www.tpex.org.tw/zh-tw/indices/stock-index/industrial/inxh.html
- 官方月產業：https://www.tpex.org.tw/zh-tw/indices/stock-index/industrial/idxsm.html
- 日報表開源 parser：https://github.com/chunkai1312/node-twstock/blob/master/src/scrapers/tpex-scraper.ts
