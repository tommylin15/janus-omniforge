# 全專案程式清理與效能優化

2026-11-01 使用者授權：先完成程式盤點、清理、I/O／查詢／操作／UI 優化與文件更新，再集中整體測試及驗收。既有 Dev 為個人真實服務；不新增付費資源或權限，不刪除真實業務資料。

## 盤點邊界

以 GitHub main `d56ce2b9` 為起點，盤點 tracked source、正式入口與建置設定：`services/api`、兩套 `jobs`、`packages`、Flutter `apps/user_app`、`apps/web`、`scripts`、migrations 與 Actions。Python 靜態盤點涵蓋 563 個檔案（含測試）；追查重複函式、引用及直接相依測試。歷史研究／archive 保留，非本專案的未追蹤 `token-savior/` 不修改。這不是逐行證明所有程式沒有問題。

安全邊界：保留 Owner 隔離、append-only 帳本、冪等、來源驗證、價格不可變衝突、worker lease／fence、canonical／research 隔離及 missing／partial 語意。不因檔案長或名稱 legacy 就刪除仍有功能／測試引用的程式。

## 本輪修改

| 範圍 | 問題與修改 | 驗證重點 |
|---|---|---|
| UI 冗餘 | 移除未被 import／export 的 521 行 `final_today.dart`；正式入口仍用 `final_today_v2.dart` | 正式頁面 widget／build |
| 批次／模型冗餘 | 移除全 tracked tree 無呼叫的舊 Liquid500 排程寫入、研究總控、重複 materialize wrappers 與未使用 helpers 共 9 個函式；保留底層有引用的研究計算 | 既有批次／模型測試及 import 檢查 |
| Iceberg 讀取 | readiness scan 將原本事後檢查的列數上限下推至 scanner（limit+1） | 超限仍拒絕，不將截斷視為完整 |
| 來源授權 | SQLite／PostgreSQL 共用同一份來源 review 判斷 | 核准／缺欄／拒絕規則不變 |
| 公開資料安全 | Public Mart 與 Core 共用既有敏感欄位判斷 | Core 過濾、Mart 拒絕的不同處理仍保留 |
| GCS I/O | store instance 內依 token 實際到期時間重用，提前 60 秒刷新；缺 expiry 不快取 | 期限、刷新錯誤、安全刪除原測試 |
| DuckDB 查詢 | 移除 natural key／非 key 完全相同的 SELECT 分支，共用相同欄位產生式 | merge／Iceberg 既有測試 |
| 行情 SQL | TPEx 每批由 2N 次 SQL 改成兩次；最大 250×8 筆 | 衝突整批回滾、批內重複、輸入驗證、真實 PG |
| 關注操作 | 自動恢復／輪詢共用未完成 request；手動與 mutation 後可強制新讀 | 慢請求、Owner 更換、mutation 後重讀 |
| UI 重新整理 | widget 回歸揭露 6 個檔案共 15 處 Future 賦值 callback；改用不回傳 Future 的同步 setState block，涵蓋今日／關注／Admin／舊入口 | 前景恢復與完整 widget suite |
| 個人策略 UI | 背景完成的請求不能重開 timer；讀取上限 25 秒；Owner 更換失效舊結果 | 背景／前景、Owner 隔離與 timeout |
| 建置 I/O | Docker context 排除本機工具倉庫、暫存及 log | runtime 相依不變 |
| 文件 | README 移除過期五模型路線；TODO 修正 PS-VERIFY 已完成卻仍被列為下一入口 | 連結與狀態一致性 |

## 集中驗證與驗收

程式與文件修改完成後，集中執行新增回歸、完整可執行 Python suite、隔離 PostgreSQL integration、Flutter analyze／完整 widget tests／正式入口 web build，以及 diff／文件連結檢查。修正測試發現的真實問題後重跑受影響範圍。

任何 commit／push 前執行 Ponytail review。CI／Release／Dev runtime 使用同一來源 SHA 與既有安全 gate；未取得收據的部分維持 NOT_VERIFIED，不用本機或 mock 取代真實驗收。新效能宣稱只限有證據的 SQL／metadata call 數；未量測 live p50／p95，不承諾整體延遲改善百分比。

2026-11-01 本機最終收據：

- Python：**2052 passed／21 skipped／8 deselected，exit 0**，142.98 秒。使用現有鎖定版 NumPy／Pandas／API／模型依賴；臨時安裝只在 `.tmp`，產品 dependency 檔不變。JUnit 保存在本機 `.tmp/cleanup-python-final.xml`。
- 21 個 skip 為 19 項未配置的隔離 PostgreSQL 測試、2 項既有外部 Valuation v22 frozen fixture 未提供；8 個 deselect 包含 Release 原本排除的 2 項及 6 個 Windows 無法驗證的案例（GNU bash 日期、SIGALRM／resource、超長環境變數）。另沿既有 Release 排除歷史入口；B8 的 Linux `resource` 模組須由 Linux CI 執行。這不是所有平台測試全數 PASS。
- Flutter：**142 個 widget tests PASS**；最終 `flutter analyze --no-pub --no-fatal-infos lib test` exit 0，109 個 info、無 error／warning；正式 `flutter build web --release -t lib/final_visual.dart --base-href /app/ --no-pub` exit 0。
- 修改檔 Python syntax、文件檔案路徑及 `git diff --check` PASS；本輪 I/O／DuckDB／建置契約定向 45 項 PASS。
- 初輪 Windows suite 的環境差異（缺依賴、Pandas 3）、readiness 新 limit 預期與本機產生檔案檢查均已收斂；未把初輪失敗冒充成功，也未透過刪除功能測試讓結果變綠。

**下一步：完整 Linux Release CI／隔離 PostgreSQL／容器 build，之後依既有 gate 進行 Dev 部署與真實驗收。** 本輪優化尚未部署；未量測 live p50／p95，不標整體 CLOSED／PASS。


## 提交前 review

已依 `/ponytail-review` skill 檢視完整 diff、相依呼叫／正式入口、回歸測試、來源／Owner 隔離、GCS token 到期、SQL 不可變衝突與交易回滾。以既有個人 Dev 負載為界，未發現須先修正的程式問題；此判定允許提交供 CI 驗證，不取代 Linux／PostgreSQL／Dev 的驗收 gate。執行程式碼統計：22 檔、增加 117 行／移除 782 行，淨減 665 行（不含測試／文件）。
