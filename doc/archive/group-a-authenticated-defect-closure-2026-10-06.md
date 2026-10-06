# A 組 authenticated 驗收與缺陷閉環 — 2026-10-06

狀態：partial；本文件保存本次 bounded evidence，並非 A 組完成宣告。

## 已觀察的真實 evidence

- 同步 GitHub main `9454323a32a4a5b1ed4d6fa3d840624996046741`；保留本機未追蹤 `token-savior/`。
- Chrome 已有真實 User／Admin Google session。以 390×844 viewport 實際檢視 Today、Watchlist、Ledger、Stock Detail；工具 screenshot 擷取差異以 CDP 的明確 clip 解決，未將桌面模擬當 Android evidence。
- Ledger Holdings／Records／Reports summary 與 YTD 在未 mutation 的同一版本一致；Records correction 入口與 canonical monthly/annual report 可見。未新增或更正任何真實交易。
- Admin batches 真實 200，顯示 effective mobile-ledger 與原 private 21:30。Data governance 503；container traceback 根因為 `ModuleNotFoundError: No module named 'google.cloud'`。
- Public market-home 實測 Cloud Logging request latency 三次為 14.473／8.110／7.248 秒；Private Mart endpoint 約 3–6 秒。這是 desktop 首次／未快取讀取 evidence，不是暖機 p95 或手機 SLO。
- Mobile ledger rollout `37416087045` 先於 writer probe 失敗；Drive locate、writer capability、既有 owner mapping 已通過，Sheets read provider unavailable。既有 dev project 的 Sheets API 未啟用。依 Google 官方標準配額免費契約啟用 `sheets.googleapis.com`，未新增資源、IAM 或 quota。唯讀 execution `janus-private-pipeline-d67xx` 成功；原 workflow failed-job retry 最終 success。未 enqueue／append 交易。

## 最小修正

- Today 法人改讀正式 `foreign_net_shares`／`investment_trust_net_shares`／`dealer_net_shares`，明示股數，不冒充金額。
- Exact decimal formatter 支援科學記號，保留 BigInt rounding 與 missing semantics；正式零值不再顯示資料不足。行情／發布狀態與 Ledger 年度說明使用繁體中文。
- Stock Header 使用 enabled-symbol gate、正式 stock-master identity、最多一列 latest persisted OHLCV；歷史收盤價與交易日獨立於研究報告。Primary sections 在各自 response 完成時更新，進階 K 線仍按需。
- API hash-locked runtime 補齊既有 GCS receipt reader 所需 `google-cloud-storage==3.4.1`；Google 公共憑證使用官方建議 CacheControl，JWT／issuer／audience／expiry／allowlist／owner 檢查保留。
- Public market-home 最多 60 秒／單筆 instance cache；Private Mart 最多 32 組 exact snapshot + owner + filters + limit scan cache。每次讀 current snapshot pointer 並檢核 current ledger version；snapshot／owner／ledger version 變動回歸已覆蓋，不快取 notes 或無界 pipeline scan。
- Portfolio runtime 測試明確 stub mobile consumer，避免使用本機 ADC／網路。

## 本機驗證

- Python affected private pipeline／User API／market-home／public routes／portfolio API／revaluation：78 passed。
- Admin API／public runtime／container contract：36 passed；一項檢查 orphan directory 的測試因既有未追蹤 `token-savior/` 而排除，未刪除使用者檔案。
- Python portfolio/mobile queue/consumer 前置 suite：46 passed；新版 public stock-header API：14 passed（與前述 suite 有重疊，不加總）。
- Flutter holdings formatter + Final Visual：12 passed；targeted analyze exit 0，既有 main.dart info lint 保留；Stock Detail analyze 無 issue。
- `git diff --check` 通過。鎖定依賴已由 uv compile 產生；實際 hash-locked runtime install、CI、deployment 與修正版 live readback 由下段補錄。

## 剩餘 acceptance

- 修正版 CI／dev deployment／immutable image 及同 URL live revalidation。
- Android 真實安裝後 User/Admin icon 重開。
- 真實交易／更正、mobile native enqueue、duplicate guard 與 canonical append → pending → Private Mart refreshed。缺真實交易欄位不得自行造假。
- 真實手機 warm core p95 ≤2 秒、visited restore ≤300ms，記錄裝置／網路／樣本數。Desktop baseline 不替代此 gate。
- Admin 六頁／資料治理修正版讀回與四頁完整 visual evidence；失敗繼續最小修正，不擴展 B／C。

成本依據：[Google Sheets API usage limits](https://developers.google.com/workspace/sheets/api/limits)；標準配額內無額外費用，未申請增額。
