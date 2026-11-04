# Janus 可交易 ETF 名冊｜股票／ETF 共用解析 V1（2026-11-04）

## 決策與範圍

使用者 2026-11-04 回報：在持股／記帳「新增交易」輸入 `0050`，畫面要求從下拉選項選取卻查無結果；同日核定「本地名冊優先＋無結果時官方即時補收＋每週同步」，要求修改文件及程式。

**2026-11-04 結案狀態：ETF 新增交易的 Dev migration、同版發布、API 切流、四 Jobs rollout 與使用者 Owner UAT 已 PASS。每週名冊同步首次自然執行收據另列待觀察，不與 Owner 功能結案混為一談。**

- 支援上市、上櫃的台幣計價 ETF 與普通股，交易種類沿用 BUY／SELL／CASH_DIV／STOCK_DIV；交易股數、價格、費稅、損益走現有 Owner ledger，不自行改寫成交資料。
- 名稱搜尋使用 PostgreSQL `control.stock_master`，關注與新增交易共用已核實可交易標的身份；ETF 的 `instrument_kind` 取自 `control.official_instrument_identity_provenance`。
- `stock_master` 為既有持股 FK 與行情 read-model 所需標的身份，不代表模型研究母體。`control.market_universe_members` 僅保留普通股，ETF **不得**因本流程插入研究母體、Quant 排名或四模型正式推論。
- 不新建 Cloud Scheduler／付費 API，不把研究模型補收誤觸發為 ETF 基本面資料補收。
- 不自動新增使用者交易／關注，不放寬 Owner 身份驗證或寫入冪等。

## 資料來源與查詢

1. `/api/v1/me/journal/instruments?q=0050`、`/api/v1/me/watchlist/search?q=0050` 首先讀本地 `stock_master`，代碼精確命中立即回傳。
2. 若輸入符合 ETF 候選代碼形狀且**沒有精確命中**，以固定官方端點確認證券別、名稱、上市／上櫃、實際掛牌日期後，透過有界 PostgreSQL `control.register_verified_etf` 登錄，再重新查本地資料庫。候選碼格式僅是「是否嘗試官方查詢」的條件，**不是官方身份認定**。
3. TWSE 優先 `https://openapi.twse.com.tw/v1/opendata/t187ap47_L`（「基金基本資料彙總表」）；若 OpenAPI 回應不可用，回退 `https://isin.twse.com.tw/isin/class_main.jsp` 的上市 ETF 篩選。TPEx 使用同一 ISIN 目錄的上櫃 ETF 篩選。來源以固定 allowlist；拒絕任意 URL、空資料、重複衝突、未上市、代碼不符或非 ETF。
4. 官方來源查詢失敗回傳 `lookup_status=official_unavailable`，不捏造標的也不讓未驗證代碼通過 UI 選取；官方查無則 `official_not_found`。快取一小時避免同一例外代碼反覆外呼。
5. 目前 Owner 交易表單使用 `TWD`，且無交易幣別切換。外幣加掛代碼末尾 `C`／`K` 暫不自動收錄；外幣交易另需有幣別欄位與換匯契約後才能啟用。
6. 週同步附掛既有 `JANUS_UNIFIED_COLLECTION` worker，依 `control.etf_catalog_sync_state.last_success_at` 以七天週期更新。兩市場必須同時取得有效資料才接受 snapshot；同名重送 idempotent；只更新官方身份、不刪既有持股與交易、不用缺席推定下市。API 的即時補入即使不在同步週期，也可先處理已核實新 ETF。
7. 官方資料記錄 `source_id`、固定 `source_url`、`listed_on`、`verified_on` 與 `instrument_kind`。已被操作員禁用的標的不可由同步重新開啟。

## 已修改的程式路徑

- `packages/etf_catalog.py`：TWSE OpenAPI／ISIN 解析、官方來源可用性、候選代碼校驗、即時 lookup 與週資料集。
- `services/api/repository.py`、`services/api/app.py`：本地標的查詢、ETF 缺值補收、受限 DB 登錄與關注權限檢查。
- `apps/user_app/lib/main.dart`：交易與關注畫面標的欄位、ETF 標記與查無資料提示。
- `infra/postgres/migrations/075_etf_tradeable_catalog.sql`：控制表、有限資料登錄函式及修正不該補收的 ETF 研究需求。
- `jobs/ingestion-core/ingestion_core/etf_catalog_sync.py`、`unified_collection.py`：在既有批次中每週執行，失敗不使其他市場收集結果被覆蓋。
- `tests/test_etf_catalog.py`：來源格式、官方身份、期限、外幣、失敗降級與普通股研究母體隔離。

## 施工／驗收關卡（2026-11-04 實際讀回）

- **CODE／TEST PASS**：Python 全量測試與 Flutter build、四映像完整 Release [#41787167591](https://github.com/tommylin15/janus-omniforge/actions/runs/41787167591)，來源 SHA `60b10da3e2ed4a5b5de3933e592cd8c246f0dcb8`。
- **MIGRATION PASS**：Dev `075_etf_tradeable_catalog` [#41786939582](https://github.com/tommylin15/janus-omniforge/actions/runs/41786939582)；回傳 `status=PASS`、不切換 traffic／image，並建立 0050／006208／00878 可交易名冊種子。
- **DEV API／UI PASS**：0% Candidate [#41787850394](https://github.com/tommylin15/janus-omniforge/actions/runs/41787850394)、OAuth／Owner／MCP 未登入邊界 [#41788086913](https://github.com/tommylin15/janus-omniforge/actions/runs/41788086913)、固定映像 100% API 切流 [#41788208137](https://github.com/tommylin15/janus-omniforge/actions/runs/41788208137)。
- **DEV Jobs rollout PASS**：[四 Jobs 正式更新 #41788625133](https://github.com/tommylin15/janus-omniforge/actions/runs/41788625133)；執行腳本回報 `{"result":"PASS"}`，保留舊映像與已讀回設定雜湊作 rollback。首次嘗試 [#41788439610](https://github.com/tommylin15/janus-omniforge/actions/runs/41788439610) 在變更前因 digest 誤植被拒，已修正重試。
- **OWNER LIVE UAT PASS（使用者宣告）**：2026-11-04 使用者對本次 ETF 新增交易功能回覆「驗收完畢」。此確認不含逐項測試截圖或正式下單；不得推論官方來源故障注入、其他 ETF 全市場覆蓋或每週自然同步已被實際驗證。
- **週同步首輪自然執行：尚未取得讀回**。在既有 `unified_collection` 觸發後，確認 `control.etf_catalog_sync_state.last_success_at` 與 `last_count`、兩個市場來源、保留原有 Scheduler／Jobs 設定；這是後續運維追蹤，不影響本次 Owner UI 功能結案。

## 目前限制

- 「週同步」已隨既有四 Jobs 版本發布，但首輪自然執行成功仍待狀態表及執行收據讀回；不可把 rollout PASS 當成當期資料同步 PASS。
- 上櫃 ISIN 若對 Cloud Run IP 回 403／超時，會回 `official_unavailable`，不偷偷改用未經核准來源；需既有可信代理路徑與 live 測試後再擴充。
- 貨幣別固定 TWD；ETF 的估值、配息口徑、模型卡片與個股深度資料不因交易名冊補入而自動成為可用。
- 官方名冊缺席不推斷下市，也不刪除／重算舊 Owner 交易，避免持股損壞。
