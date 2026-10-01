# 持股 MIS 盤中報價驗收（2026-10-01）

## 範圍與來源決定

使用者確認 MIS 自動取用與私人 UI 雲端展示許可。既有 Shioaji 憑證再次以正式環境登入仍回 permission error，因此本次只整合 TWSE MIS，不建立雙來源切換。持股、成本與 owner boundary 沿用已完成 Private Mart 批次；MIS 只批次查詢 owner 持股的上市／上櫃 symbol。

最新使用者指示：持股頁盤中／盤後只使用 MIS；盤中持股分頁前景每 30 秒更新，非盤中點入只取一次，右上方提供手動更新；現價、均價、成交單價與目標價固定小數二位，金額、股數與比例四捨五入整數並使用 comma／括號負數；報價過期保留最後成功成交價及估值／損益，明示 stale。從未取得報價的持股仍 missing，缺價 aggregate withheld。交易輸入及計算維持原十進位精度。

## 實作與測試

- 初版 commit `5607e9be70ced38c4a4d6e7db1385769abc78f70`；最新要求與冷啟動摘要修正 commit `e6243e347b0dffe89035abce1968edcf1856add3`。
- `GET /api/v1/me/portfolio/quotes` 保留登入、owner、ledger version／snapshot pending 防護。stdlib MIS 取價、10 秒後端受控快取（避免快速連按）、5 秒來源 timeout，不使用掛單價冒充成交價。
- UI 30 秒 timer 僅於持股、前景、目前 route 可見時發送，離頁／背景／dispose 停止；60 秒單次 quote timeout、busy guard 與 generation 丟棄離頁回應。失敗保留最後 UI。摘要 Future 沿既有 API 等待成功回應，避免首次冷啟動超過 8 秒後永久卡在錯誤。
- 本機原始 Python 43 passed、Flutter 42 passed；最新完整 Flutter 44 passed，最後 stale 測試更新後 targeted 3 passed；Python intraday／portfolio API 7 passed。Flutter analyze exit 0，21 個既有 curly-braces info；shell syntax 與 diff check 通過。
- 真實 MIS 本機批次讀取 TWSE 2330／TPEx 6488 成功，驗證 `z=-` 時使用 `trade.z`／`trade.t` 的最後成交紀錄。

## Dev runtime 證據

- 初版 GitHub dev run `36804892892` 的全部 test／deploy／verify success。API revision `janus-api-00279-5cz` Ready、100% default traffic、`JANUS_MIS_QUOTES_ENABLED=true`；`/app/build-id.txt` 與初版 SHA 相同。
- 真實 Google owner UI 成功讀取持股 MIS 報價；CDP 只擷取路徑、時間及 status（未讀／輸出 token）。初版 10 秒請求間隔約 10.006／9.997 秒，手動請求 HTTP 200，離開持股後超過一輪的觀測期間無新 quote 請求。
- 初版 cold read 曾約 35 秒才完成，後續取價回應約 0.09–3.67 秒；這不構成固定 latency／SLA 保證。摘要的 8 秒 timeout 已依此修正。
- 修正 run `36806318280` success；最終 commit `05959ec780cf6b2740240f07a35135beb3d2883d` 的 dev run `36807577636` test-api／deploy-api／deploy-private-pipeline／verify success。Ready revision `janus-api-g05959ec780cf-config` 承接 100% default traffic；build ID 與實際 browser bootstrap 均為最終 SHA。

## 保存與邊界

盤後收盤價由 ingestion 寫入 GCS Core Iceberg `core.ohlcv_v1`；Private Pipeline 用帳本與不晚於估值日的最後收盤價寫入 GCS Private Iceberg `private.mart_user_positions`、`private.mart_user_unrealized_pnl`、`private.mart_user_portfolio_summary`。本次 MIS 不回寫正式 OHLCV／Private Mart。

MIS 是 API process 記憶體快取及當前 UI 保留值；服務重啟、重新開頁或多 instance 不保證保留同一筆。每個來源回應保留真實成交時間，超過 120 秒／非當日仍顯示最後成交但標 stale；此規則不修改正式盤後 aggregate 契約。

最終真實 authenticated 390×844 UI 顯示 MIS 成交價、兩位小數現價／均價與 comma 市值／損益。觀測自動請求 timestamps 5614.026344／5644.020055，間隔 29.993711 秒；手動請求 5622.447454 → HTTP 200 5624.541898。首次 quote response 約 31.24 秒，busy guard 略過重疊 timer；之後回應約 2.09–3.52 秒。手機 screenshot 保存在本機 visualization 目錄，不將私人財務截圖推送 GitHub。

本次只驗收持股功能，不宣稱四頁 Final Visual Convergence、production readiness、多使用者 throughput 或 MIS SLA 完成。未新增 GCP 資源、付費來源或 production 部署。

盤中 gate 同時使用台北平日 09:00–13:30、既有 schedule.holiday_overrides／MARKET_HOLIDAYS 休市表與 MIS 回傳交易日期。日曆讀取失敗仍回傳價格，但停止輪詢。假日新增 fixture 2026-10-09 已驗證單次取價成功、market_open=false。

休市設定需依年度／臨時休市維護；MIS 交易日期只是額外檢查，不是官方即時開市狀態 API。瀏覽器曾載入舊快取 bootstrap 49c7eaca；Page.reload(ignoreCache=true) 後核對 bootstrap 05959ec，必要時使用者應強制重新整理並重新登入。

最終離開持股頁超過 30 秒的網路觀測沒有新 quote 請求。最終 API image digest：`sha256:8a46cc05ad00f517a295672a70b448654611a8acb5fb5cf6290b0372f84e1975`。
