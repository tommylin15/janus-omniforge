> **歷史／結案 checkpoint｜不形成目前待辦、Cron 或新工程授權。** 現況見 [TODO](../todo.md) 和 [status](../status.md)。

# 持股／手動損益重算 P0 暫停交接（2026-10-13）

狀態：**PAUSED BY USER／整體 PARTIAL，尚不可宣告最終版上線**。此交接為已核准 P0 工作的恢復入口，不是新工作包；使用者於 2026-10-13 明確要求「先暫停，把目前的工作和最新進度以及需求更新回文件」。**不得因本文件存在而自動重啟**。下一次使用者指示繼續時，先核對 GitHub `main` 與當時 runtime，不盲目重送任何 Job、owner request 或部署。

## 使用者確定的產品需求／完成定義

1. **持股與 500 檔研究池分離**：個人已持有股票、ETF、盤中買入／加減碼、賣出、更正／作廢、股利與查詢不受研究 universe 500 限制；交易寫入後，以 authenticated owner Ledger／current_positions 及必要的 membership 更新為準。沒有券商成交同步證據不得自行推算盤中交易，研究候選池不得冒充 operational holding pool。
2. **行情／損益分離且容錯**：TWSE／TPEx 官方授權報價按商品身分、日期、provenance／PIT 使用，00719B 至少官方 TPEx EOD；沒有可驗證的盤中 tick 不偽造即時報價。單檔缺價時保留已確認 shares、cost、交易紀錄及其他有價股票；缺價股票 PnL 保留 missing／stale，不把整頁資料清空，也不以假 `0` 充數。全組合總額僅在 coverage／as-of 一致且可完整證明時顯示，否則明示 withheld／partial。
3. **持股頁視覺**：上排顯示持股整體未實現損益／報酬，下排才是當日現價、每股漲跌／幅度及該持股的當日變化額；指標單位與時間層級須一致。Ledger Hero、股票卡依最終 UI 契約，390×844 手機／桌面可讀，漲紅跌綠、有缺值／錯誤／loading 的明確視覺，首屏不因報表或任一股票缺價永久 spinner。
4. **手動重算必須可操作**：持股頁不論當年度 YTD 為 0、available 或 stale，均有明確的「重新計算損益」入口。按下只對當前認證 owner enqueue，Worker 負責 private Mart 寫入；`QUEUED/RUNNING/CANCEL_REQUESTED` 按鈕 disabled／不可重複派送，`FAILED/CANCELLED` 有安全原因與重試；狀態輪詢序列化且每請求 bounded（已實作 9 秒上限），可讀最後 ledger checkpoint、進度與 terminal result。
5. **真實 dev 上線門檻**：完整來源同 SHA Python／Flutter／GHCR immutable digest → API 0% Candidate → 自動 OAuth、私人未登入負測（**不要求每版人工 OAuth 登入**）→ 共用 lease／Scheduler／active execution fence／四 Jobs 8 次 canary → 固定 Preview → Owner 真實持股增減／00719B／一般持股／重算 queue end-to-end（須實際 `SUCCEEDED`、checkpoint 追平及清理）→ 手機 390×844／桌面 authenticated 截圖 → 正式 API 100% promotion 與回滾 readback。不可用 build／Job 容器成功取代業務結果驗收。

## 已驗證且不用重做的證據

| 證據 | 判定 |
| --- | --- |
| 00719B 官方 TPEx EOD／owner 私有 Mart price metadata／市值／PnL／ledger checkpoint | [#38257614968](https://github.com/tommylin15/janus-omniforge/actions/runs/38257614968) PASS（限定該次 one-owner 執行，不代表所有 Owner／所有 queue） |
| 新版來源 `50eda171ef6ffb3971a4d140ad09bac870ead6c1`，全套測試／GHCR 映像 | [#38273250472](https://github.com/tommylin15/janus-omniforge/actions/runs/38273250472) PASS |
| 同源 API 0% Candidate、自動 OAuth／private negative | [#38273927543](https://github.com/tommylin15/janus-omniforge/actions/runs/38273927543)、[#38274131449](https://github.com/tommylin15/janus-omniforge/actions/runs/38274131449) PASS |
| 同源四 Jobs、每 Job 兩次 canary | [#38274299751](https://github.com/tommylin15/janus-omniforge/actions/runs/38274299751) PASS；**不代表 Private Recalc queue E2E PASS** |
| 同源固定 Preview 與公開資料 readback | [#38322429759](https://github.com/tommylin15/janus-omniforge/actions/runs/38322429759)、[#38322598975](https://github.com/tommylin15/janus-omniforge/actions/runs/38322598975) PASS，正式 App 100% 流量未因此更動；Preview build SHA `50eda...`，TAIEX 30 點／歷史日期 2026-10-12、owner 未登入 401；market cold 19,047 ms／warm 54 ms（非 P95） |
| **最新來源** `42ae0ff27d057c22d0b240c25322cf546808e261`，安全錯誤類別統計與測試修正 | [GHCR Release #38323413135](https://github.com/tommylin15/janus-omniforge/actions/runs/38323413135) **SUCCESS**：Python／Flutter／四 GHCR image／public pull gate 全 PASS；**僅發布映像，沒有新版本 0% Candidate／Jobs／Preview／正式切流驗收** |
| 上一版正式 App 的受控切流 | [#38262691942](https://github.com/tommylin15/janus-omniforge/actions/runs/38262691942) PASS；先前 runtime 100% 來源 `b1bc785906212b8d2860b1521affb83930d09f04`。下次先重新 readback，不能僅由歷史推定目前仍相同 |

## P0 真正未過關與根因邊界

- **真實 Private Recalculation 佇列 [#38274621290](https://github.com/tommylin15/janus-omniforge/actions/runs/38274621290) FAIL。** Seed 成功，`janus-private-pipeline-45h2t` Cloud Run execution 2 個 Task 容器皆 terminal SUCCESS，然而 [#38322879209](https://github.com/tommylin15/janus-omniforge/actions/runs/38322879209) 自當時 Cloud Logging 讀回的**業務結果**為 Task A `processed=1, succeeded=0, failed=1`、Task B `processed=0`。因此是單一 owner `pipeline.run_user()`／其依賴路徑的真實失敗，不得將「容器 exit 0」解讀成 PnL 成功。
- 最終 verify ingestion execution `janus-ingestion-core-5hksw` terminal FAIL；只看到 RuntimeError 類別，**實際 owner request 的精確 `error_code`／Private Mart 根因仍 UNKNOWN**。安全診斷需查原請求 terminal status、`error_code`、checkpoint 與 dispatch，禁止印出 owner ID、token、交易或敏感價格。
- 歷史清理收據 [#38323214910](https://github.com/tommylin15/janus-omniforge/actions/runs/38323214910) 顯示 `status=succeeded`、`active_request_failed=false`；只證明清理呼叫成功且請求當時不在 active 狀態，**不代表 request 已 SUCCEEDED，也不代表已刪除測試紀錄**。下一步先唯讀核對殘留及其分類，再決定是否可重新 seed。
- 新增 `scripts/gcp/private_recalc_state_probe.py` 僅供受限診斷，前兩次 [#38321027906](https://github.com/tommylin15/janus-omniforge/actions/runs/38321027906)、[#38321865550](https://github.com/tommylin15/janus-omniforge/actions/runs/38321865550) 因錯誤欄位 `created_at`（048 migration 實為 `requested_at`）執行失敗。程式已改成 `WHERE` 與 `ORDER BY requested_at`，**但尚未驗證修正版 SQL 真實成功**；不重送未知狀態工作。兩次診斷 task 最後均經只讀日誌確認 terminal FAIL、非正式重算工作。
- `services/api/private_recalc_queue.py` 已在最新 Release 增加安全 `error_codes`「例外類別→次數」計數（不含 message／user），unit regression PASS；**最新映像尚未部署**，所以尚未取得真實錯誤類別、沒有證據顯示原本失敗已修復。
- **UI 最新 Preview 僅能證明 build／公開 readback，authenticated Owner 的 390×844 與桌面截圖、真實新增／加減碼／手動重算按鈕→Worker→PnL readback 仍 NOT VERIFIED。** 冷啟動曾一次 28 秒 timeout（#38260082698）；後續 11.3 秒／19.0 秒 cold 成功不等於 P50／P95 達標。

## 暫停時的執行狀態與重新開工順序

1. **先核實實況**：GitHub `main` 與 #38323413135 latest release／四 Job immutable digest、API traffic 100%、固定 Preview source、Scheduler／global lease／active executions；任何新來源不得冒用上一來源 gate。
2. **先證明 queue 原始請求的狀態與錯誤分類**：優先唯讀 PostgreSQL 透過既有受限 GCP 路徑、查 `requested_at`／`error_code`／dispatch／processed_ledger_version；另核對是否殘留測試 fixture、是否安全清理。不能取得結果時記為 BLOCKED，不以更多盲目重算洗掉原始證據。
3. **根據證據最小修正 Worker／Private Mart 或 queue 契約**，補足實際缺陷的 targeted tests、失敗重試、owner 隔離、缺價不阻其他持股；新程式必須完整 Release。
4. **只走現有受控四 Jobs／API 流程**，部署同一已驗證 SHA 到既有 dev；對一筆受限 fixture 做 worker 成功、`SUCCEEDED`、ledger checkpoint、fence released、清理／隔離驗收；不為了容易通過而減弱驗證或繞過執行鎖。
5. **Preview／Owner UI 真實操作及 formal API 切流**：驗收手機／桌面、持股新增買賣、更正／作廢、00719B 與不在 500 的持股、失敗／無價 fallback、手動重算直到持股頁讀回 PnL；全 PASS 才正式 100% 同來源切流、回滾 readback、更新結案證據。

## 暫停控制

- 本次使用者只要求**文件回寫並暫停**：不得在本文件 commit 後自動更新 Image、啟動新 GCP Job、migration、發版、清理、正式 App 切流或重新計算。既有 GitHub Actions／既有排程不因「暫停」被擅自取消；若下次恢復前發現新的自然執行，必須重新核實。
- 不重新開 B0～B8；B9 model quality 仍獨立 NOT VERIFIED，P0 UI 與交易重算 P0 不因 500 檔研究進度被視為失敗或 PASS。
- 使用者取消的是發版的**人工** OAuth 登入 gate；可自動執行的 OAuth／安全負測仍必須跑。
- 只使用 `main`，不建 branch／PR；保留舊版可回滾的 immutable digest、lease／Scheduler fence；無來源不造數，partial 不能說成完成。

參考：[最新狀態](../status.md)／[Active TODO](../todo.md)／[User UI 契約](../ui/user-app.md)／[工程規則](../PROJECT_RULES.md)。
