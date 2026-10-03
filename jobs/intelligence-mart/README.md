# Intelligence Mart job

日常 `MART_OPERATION=queue` 只執行 PIT screening 與五分析師，正常 0 LLM API token。
市場池依 `control.specialist_market_symbols(date)` 的 immutable liquid-500 membership；Deep Coverage 是去識別化 active watchlist ∪ effective holdings，持股離榜仍分析，清倉且取消關注才退出。

成果物 create-only 保存於 `specialists/<content-hash>.json`，每次 execution 保存 membership、screening、manifest 並 readback。缺資料／OOS 尚未驗證如實顯示 partial／blocked，不產生正式健康度或 publication。

`MART_OPERATION=specialist-smoke` 是缺資料契約 smoke；`specialist-acceptance` 才讀指定真實 dev Core fence 與 DB membership。驗收 input URI 限既有 Mart bucket 的 `acceptance/specialists/`。`MART_OOS_EVALUATION=true` 啟用研究評估，不自動 promotion。

`MART_OPERATION=specialist-retrain` 搭配 `MART_OOS_EVALUATION=true`，從既有 dev Core bucket 選最新 immutable manifest，自動計算 raw-byte hash，保留資料的實際 analysis_as_of；未有 snapshot、日期在未來或超過 7 天時拒絕執行。既有 batch controller 每月 1 日 10:30（台北）在 ingestion／data-supplement 成功且 Core/Mart 未忙碌後執行，月初週末也有效。手動以相同 operation 重跑會建立新 execution，訓練／OOS 不自動 promotion；Event 沒有 labeled data 不假裝已重訓。

完整契約與限制見 [SPEC](../../doc/spec/specialist-engines.md)。共用 provider 只接受手動 CEO transport，queue 不呼叫 provider；CEO command／語意驗證仍屬後續 WBS。
