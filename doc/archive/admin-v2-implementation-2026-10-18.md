# ADMIN-V2 工程與驗收（2026-10-18）

狀態：IN_PROGRESS。使用者已授權 A1～A5（含 A4-U），未取得本版 dev 證據前不標完成。

## 本版實作

- Flutter 四主頁：總覽／批次／資料品質／系統設定。保留股票搜尋、修復與歷史、全市場、AI/Gateway、Private 執行與 Worker；次層 lazy load，以 hash 保存主頁與次層位置。
- Controller occurrence 顯示查詢期間內最近實際成功／終態、真實 execution 起訖耗時、3／7／31 天及異常篩選；既有安全 retry 不變。沒有部署收據時不推定部署成功。
- 資料品質讀同一 persisted Data Readiness Ledger；未發布即 unknown。股票詳情共用公開 EPS／營收的合法期間，當年合格與歷史 TTM 未認證分開；不建立資料來源或重新計算財報。
- 營運摘要讀 Private aggregate、DB snapshot metadata 與目前回應 SHA/revision；已驗證 digest、protected refs 和可比負載 I/O 沒有來源即 unknown。Storage／retention、Private 執行、Worker 設定分置對應主頁。
- 使用分析預設停用，明示用途／資料類別／管理者可見範圍及保留期限；本人可停用及刪除。既有 App 入口共用記憶體隊列，60 秒或20筆盡力上報、最多100筆、3秒 timeout／一次有限重試。閒置60秒、背景、帳號切換與台北跨日分段。
- 後端 16 KiB／20筆、固定 schema／功能／動作／時間／秒數與速率／每日容量上限；User/Admin event audience 隔離。身分僅來自 token；不保存股票、金額、筆記、自由文字或 URL。batch/event 防重與每日統計／session／去識別月統計同 transaction。
- migration064 新增 PostgreSQL 非必要產品統計及最小權限；raw／ingest receipt 7天、daily／session 180天、去識別月統計12月，Admin read audit180天。沿現有 scheduled Private reconciliation 清理，不新建 Job/Scheduler 或 Iceberg 寫入；本人與全帳號刪除包含使用統計。

## 本機證據

- 相關 Python 回歸130 passed／1 skipped；後續 Admin／usage／Controller 修正集中68 passed／1 skipped。
- Admin shell／overview／batch／stock 與 usage targeted Flutter：14 passed。
- `flutter analyze --no-pub --no-fatal-infos lib test` exit0，無 error／warning；既有及新增 info 尚存，不宣稱零 lint。
- 真實隔離 PostgreSQL 測試本機未配置，交由完整 Release CI；包含 batch/event/session 防重、transaction rollback、opt-out／刪除／跨 owner 與 retention。
- 已讀四頁契約及四張 reference PNG；本次不重開已豁免的 User visual gate，不把 reference inspection 當 live screenshot PASS。

## Commit 前 ponytail-review

以目前個人 dev／e2-micro 和少量已授權帳號為負載假設，查閱呼叫端、API audience、SQL／migration、App 生命週期、Controller 終態、刪除與 targeted tests。修正 receipt 優先防重、User/Admin feature 隔離、刪除後偏好競態、實際 completion 排序及跨 feature monthly lock 順序。無未解決的 commit 阻擋；可提交供完整 CI 驗證，不等於可跳過 dev 發布 gate。

待完成：同 SHA 完整 CI、migration064／實際權限、GHCR／候選／auth／Preview／可逆 Jobs／API 發布、真實 Admin 正向讀回、390px／desktop 及使用分析開關效能與容量／清理驗收。無證據的來源指標維持 unknown，D01～D06／DRL-01／D07～D08 原工作不新增 gate。
