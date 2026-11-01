# 全專案程式清理與效能優化｜CLOSED／PASS（工程發布與自動驗收）

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

2026-11-01 完整 Release [#41265528911](https://github.com/tommylin15/janus-omniforge/actions/runs/41265528911) **PASS**，精確來源 `daf9636e34c3a35b9359ed8c741e01b16bffb4ff`：Linux／隔離 PostgreSQL **2082 passed、2 skipped、2 deselected**（73.75 秒），Flutter 與 API／ingestion-core／intelligence-mart／private-pipeline 四映像建置全部成功，匿名 GHCR digest 讀回成功。新增官方行情批次 SQL 的真實 PG 不可變／整批回滾測試已納入本次 gate。

API 固定 digest：`sha256:849ce46e339f4fa861e6fbd8624315bac06850af2fa646443f87601b9d242072`；四映像其餘 digest 以同 run 的 `ghcr-digest-readback` artifact 為準。候選請求已固定本來源／Release／digest，只允許 API 0% 候選，不切正式流量、不改 Jobs；另以既有唯讀 workflow 取得四 Job 回復基準。

API 0% 候選 [#41268189186](https://github.com/tommylin15/janus-omniforge/actions/runs/41268189186) PASS，原正式 100% 流量保留、health／build SHA／負向 Owner guard 與部署 lease 釋放均通過。四 Jobs 唯讀回復基準 [#41268094614](https://github.com/tommylin15/janus-omniforge/actions/runs/41268094614) PASS（`gcp_writes=0`），現役來源為 `4393543ccd02a4951e97354bd13d14a29f517759`，固定 image／config hash 以該 run 的 baseline artifact 為準。

使用者已明確要求本任務代為等待候選、OAuth 邊界、Jobs rollout、正式切流量與 live 驗收，直到整體結束；不受一般遠端等待交接規則中途停止。OAuth／private boundary [#41268434252](https://github.com/tommylin15/janus-omniforge/actions/runs/41268434252) 已 PASS，僅代表同來源候選的 metadata／未登入拒絕與 MCP challenge；不冒稱真人登入或 Owner 正向讀取。四 Jobs rollout 請求已更新為本輪來源、已成功 Auth run 與唯讀回復基準。下一步為四 Jobs 可回復 rollout → API direct promotion 與真實讀回。新版尚未承接正式流量；未量測 live p50／p95，不標整體 CLOSED／PASS。


## 提交前 review

已依 `/ponytail-review` skill 檢視完整 diff、相依呼叫／正式入口、回歸測試、來源／Owner 隔離、GCS token 到期、SQL 不可變衝突與交易回滾。以既有個人 Dev 負載為界，未發現須先修正的程式問題；此判定允許提交供 CI 驗證，不取代 Linux／PostgreSQL／Dev 的驗收 gate。執行程式碼統計：22 檔、增加 117 行／移除 782 行，淨減 665 行（不含測試／文件）。

### Jobs rollout 修復收據

首次 [#41268808459](https://github.com/tommylin15/janus-omniforge/actions/runs/41268808459) 在 private-pipeline image 更新後，因 gcloud 591 將 `template.clientVersion` 從 568 改寫而觸發完整 config guard，自動 rollback 也因該差異拒絕。Cloud Audit request 比對及將唯一差異還原後的精確 hash 讀回確認原因；沒有 canary／Owner／canonical 寫入。

已由本機既有 GCP／GitHub 身分執行一次精確 terminal-owner recovery：固定失敗 run／HEAD／annotated lease tag，兩次全頁 execution fence、舊 API 單一 100% 與各 Job 原 image／config hash 核對。private-pipeline 透過 v2 PATCH 回復原 image 與 568 metadata；四 Job 原 hash 全數一致，Scheduler `ENABLED`，最後再次驗證 terminal owner 才刪除該精確 abandoned lease。收據 `PASS`，API 流量不變、Owner／canonical writes=0。

rollout 改用 Cloud Run v2 PATCH 帶原 etag 與完整可寫設定，僅改 image；不使用不存在的 updateMask，不重播 execution token、不放寬 hash guard。新增 metadata／設定保留、未知／失敗 operation 與 bounded polling 回歸；API／Jobs／lease 定向 **108 PASS**。映像來源仍為已完整 Release 的 `daf9636e`；這次修改只影響部署操作工具。


修復後四 Jobs [#41269766095](https://github.com/tommylin15/janus-omniforge/actions/runs/41269766095) **PASS**：固定來源 `daf9636e`，八個 distinct canary（每 Job 兩次）全部成功，四 Job config hash 不變，Scheduler `ENABLED`／`30 */2 * * *`，部署 lease 已釋放；回復映像可用，沒有另做舊映像切回演練。部署工具 selective CI [#41269766117](https://github.com/tommylin15/janus-omniforge/actions/runs/41269766117) PASS。API direct promotion 請求已固定此 Jobs run 與原先正式 API `00638-ban`／`28385c78` 回復基準；同步原本 inert templates，保留 `approved=false`。

同時發現既有手動 `p02-controller-diagnostic.yml` 的未縮排 commit-comment 多行字串使每次 push 都產生 workflow syntax failure。移除未被引用的自動留言段與對 Git 的寫權限，保留手動唯讀診斷；YAML parse PASS。本輪不執行或發送該舊診斷留言。


## 最終 Dev 發布與獨立 live 驗收（2026-11-01）

- API direct promotion [#41270980235](https://github.com/tommylin15/janus-omniforge/actions/runs/41270980235) **PASS**：`janus-api-00640-jam`，來源 `daf9636e34c3a35b9359ed8c741e01b16bffb4ff`，單一正式流量 100%，固定 API digest `849ce46e…`。舊 `00638-ban`／`28385c78` 及其固定 GHCR image 保留；`rollback_rehearsal=NOT_REQUESTED`，不冒稱執行過切回演練。
- MCP 既有兩個固定路由同步 [#41271191754](https://github.com/tommylin15/janus-omniforge/actions/runs/41271191754) **PASS**：`mcp-oauth`／`mcp-adapter` 均到同一 `00640-jam`；正式 100% 路由不變，固定 tag 的 build SHA／OAuth／唯讀工具與未登入 guard 通過。
- 部署完成後獨立 GCP 讀回：四 Job 皆為本輪 Release 固定 digest，完整 config hash 不變；唯一 Scheduler `ENABLED`／`30 */2 * * *`／Asia/Taipei，API 單一 100% 及 MCP tags 均正確；全域 lease 讀回 404（已釋放）。沒有新付費資源、IAM 擴權或 Owner／canonical 資料清理。
- 獨立 HTTP smoke：`/health`、`/api/v1/public/health`、`/app/`、JS bundle 均 200，build-id 精確為 `daf9636e`；profile／today-changes／positions／pnl／portfolio summary／Admin 均未登入 401。OAuth discovery／S256、唯讀 MCP tools 與退役 write tool 拒絕通過。完整 hashed JS 與版本化 bootstrap 另讀回 200／正確 JS MIME。
- 已授權 Janus MCP 正向唯讀：`watchlist`、`positions` 各 `limit=1` 成功返回；兩者狀態如實為 `partial`／`truncated=true`，這是有界讀取，不冒稱完整帳本或 PnL 正確性驗證，也未保存私人 payload。
- 正式瀏覽器 reload 後確認新版 Flutter 登入頁、Google 登入入口、品牌圖文及無障礙語意可呈現。初期空白後已實際載入成功；不將載入中的工具觀察誤判為 App 永久空白。真人 Google callback／登入後逐頁操作暫未取得證據，不作本次自動 Release 的必經 gate；既有個人策略使用者操作驗收仍依原 TODO。
- 同步前最新 selective CI [#41270980131](https://github.com/tommylin15/janus-omniforge/actions/runs/41270980131) **PASS**。最終狀態為本輪程式清理、完整測試、既有 Dev 發布與上述有界 live 自動驗收 **CLOSED／PASS**，從 active TODO 移除。

未量測 live p50／p95，不宣稱整體延遲改善百分比；未呼叫付費模型生成報告、不重做歷史模型校準／前瞻效用、全帳本 PnL 或 Owner A/B/A 真人操作。原先外部 frozen fixture skip／Release 既有 deselect 如前列，不改寫為全情境皆已驗證。
