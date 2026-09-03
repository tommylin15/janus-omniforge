# Janus — TODO 完成紀錄（2026-09-03）

## P0 — Admin Data Operations

- [x] 股票資料狀態頁提供 Core 最新日期、資料集覆蓋、精確 row count／null
  profile 與既有寫入安全／quarantine 摘要；無 persisted quarantine 計數時明示未提供。
- [x] 資料源設定已成為 typed 管理介面，可編輯 cadence、coverage tier 與
  authorization status；`candidate`／`blocked` 不可啟用，異動使用登入身分寫入 audit。
- [x] Admin 排程設定會同步既有 dev Cloud Scheduler；同步失敗不會提交 control DB
  版本，避免兩端狀態分歧。
- [x] Admin 顯示 Cloud Run revision；Google 登入可正確解析並存的 GSI state cookie，
  登入期間顯示狀態且成功後以 replace 導向，避免誤判未登入與返回登入頁。
- [x] Admin UI 可新增／移除核心 50 membership 與設定 effective time；後端與 UI
  均拒絕超過 50 檔，版本採 optimistic lock，每次異動以 authenticated actor、原因、
  added／removed diff 寫入 immutable audit，Collection worker 只取最新有效名單。

完整測試與 GCP dev 驗收證據記錄於 `spec/operations-and-testing.md`。
