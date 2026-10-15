# Janus 目前狀態

更新：2026-10-15（P0 Owner backend PASS；P1 固定 Preview 發布請求已提交）。已驗證同源 `285848e28041bf2fb024bd98bd348641f022a1ed` API 0% candidate、自動 OAuth boundary、四 Jobs rollout，及 Private Mart readonly #38732675488 + final gate #38733406224 PASS。最後已確認的固定 Preview 為 079cca；285848 新發布請求 commit `78bf14bb`，**尚缺該次 workflow 終態及 live tag／build-id readback**；正式 100% traffic 不切，P1 仍 OPEN。

### P0｜TPEx 官方歷史日期長期能力（2026-10-15 本輪）

- **已落地（程式及資料庫）**：`services/api/tpex_quotes.py` 支援官方 `/www/zh-tw/afterTrading/dailyQuotes?date=YYYY/MM/DD&response=json` 的指定交易日查詢（不限 OpenAPI 七日滾動窗口）；嚴格核對官方回應 `date`、有效收盤價與 14:30 發布門檻。近七日 OpenAPI 仍保留，失敗可走官方定日來源。版本化 migration `061_tpex_official_eod_daily` 使用獨立 PostgreSQL 官方日期／價格／來源 URL／record SHA-256／first-observed，不污染 Core/Iceberg canonical；Private Mart 只用不晚於估值日的已保存官方資料。
- **證據**：官方 `00697B` 10/14 原始 JSON 指定日期與 date response [#38715334637](https://github.com/tommylin15/janus-omniforge/actions/runs/38715334637) PASS；migration [#38714018250](https://github.com/tommylin15/janus-omniforge/actions/runs/38714018250) 真實 dev PASS；17/17 歷史、日期、PIT targeted tests [#38717113572](https://github.com/tommylin15/janus-omniforge/actions/runs/38717113572) PASS；完整來源 `285848e28041bf2fb024bd98bd348641f022a1ed` Release [#38717341300](https://github.com/tommylin15/janus-omniforge/actions/runs/38717341300) SUCCESS；API 0% [#38718006906](https://github.com/tommylin15/janus-omniforge/actions/runs/38718006906) 和自動 OAuth／private boundary [#38718076548](https://github.com/tommylin15/janus-omniforge/actions/runs/38718076548) SUCCESS，**未切 100% 流量**。
- **Owner backend P0 10/14 PASS（與 P1 UI／正式切流分離）**：四 Jobs [#38718355824](https://github.com/tommylin15/janus-omniforge/actions/runs/38718355824) SUCCESS。先前 Owner [#38724207848](https://github.com/tommylin15/janus-omniforge/actions/runs/38724207848) 因雙 ETF 00697B／00719B 缺 Core 日期價 FAILED（#38730256233 精確恢復 lease）；兩檔同日合法官方價格補齊後，Owner [#38730741579](https://github.com/tommylin15/janus-omniforge/actions/runs/38730741579) 完成 derived Mart 寫入但因舊 Private Iceberg schema 不儲存 `stale_price_count`，驗收腳本誤判 aggregate FAILED；#38732315439 安全恢復該次 lease。**真實唯讀** [#38732675488](https://github.com/tommylin15/janus-omniforge/actions/runs/38732675488) 驗 v354／2026-10-14：8/8 有市值、8/8 未實現損益、aggregate_status=available、missing_price_count=0、affected_symbol_count=0、總市值／總未實現損益／報酬欄位非空。最終 immutable receipt gate [#38733406224](https://github.com/tommylin15/janus-omniforge/actions/runs/38733406224) SUCCESS；修正驗收 guard targeted [#38733406111](https://github.com/tommylin15/janus-omniforge/actions/runs/38733406111) SUCCESS。**缺席的舊欄位維持 null，不造假為0；`aggregate_status=available` 由 deterministic Mart 計算的 missing/stale 皆零產生。** 同次記錄的終態 FAILED 不更改歷史判定，也沒有重新發起衍生重算。

**整體 PARTIAL。** 使用者已明確授權 D01～D05 一起開發、以同源整批驗收，取代此前文件-only 暫停；D06 獨立 FinOps、不併入本輪，D07／D08 後置。完整 Release／GHCR digest／0% 候選／自動 OAuth 已 PASS，**正式 API 100% traffic 尚未獲得本產品包的所有真實業務 gate**，不能宣稱產品交付完成。詳見 [TODO](todo.md)、[AI 卡片](execution-cards/README.md) 與 [證據索引](spec/operations-and-testing.md)。

### P1｜2026-10-15 Owner 唯讀資料與固定 Preview 接續

- **固定 Preview 請求已提交，未證實更新成功**：[commit `78bf14bb`](https://github.com/tommylin15/janus-omniforge/commit/78bf14bb1665be93ef6f7048d71458632bdbc871) 將 `ops/ghcr-preview-request.json` 目標改為 285848 GHCR API 固定 digest，引用既有成功 release #38717341300、candidate #38718006906、OAuth boundary #38718076548；workflow 沿用共用 lease，只准更新 preview tag，不准切正式流量或改 Jobs。此交接尚**未取得新 workflow run 終態、tag／build-id readback**，不能宣稱 fixed Preview 已更新。
- **已授權 Owner MCP 正向唯讀讀回（2026-10-15）**：`positions` 為 `available`、8/8 有效市價／市值，兩檔債券 ETF `00697B`／`00719B` 均有 `price_status=available`，共同 `valuation_date=2026-10-14`、`ledger_version=354`；`annual-pnl` 為 `available`，同日期／版本。此為真實 Owner backend read path，**不是**正式 App UI／手動重算按鈕端到端證明。
- **最新估值仍待獨立驗收**：讀回時刻 10/15 晚間，Owner Private Mart 最後估值為 10/14；官方定日來源的歷史價在 PostgreSQL，與一般已發布 Core `ohlcv` 非同一存放路徑。對兩檔 ETF 查 `janus-core/ohlcv` 的 10/14～10/15 區間均回 `missing`，**不能因此倒推已持久化的 TPEx 官方歷史價遺失**，但新交易日 EOD→Private Mart→UI 的完整更新仍 `NOT_VERIFIED`。既有正常 private 批次在台北 21:30，不因 21:06 的前批次狀態誤判批次失敗；批次後須核對相同 owner ledger checkpoint、PIT 與 freshness。
- **P1 尚缺的硬 gate**：固定 Preview 285848 workflow terminal／`/app/build-id.txt` 與現役 Jobs readback；authenticated Owner UI（股數、市值、當日漲跌、累計未實現與總損益）；重新計算按鈕→owner enqueue→worker terminal→ledger/checkpoint/PnL；390px／desktop 截圖及適用性能、正式 dev 流量及 rollback 讀回。缺證據就維持 `PARTIAL`，不可拿 P0 成功逕行 API 100% promotion。

## 能確定的現況與限制

| 項目 | 最近可追溯證據／判定 | 下一步 |
|---|---|---|
| 全市場 | 2026-10-13 名冊 1988；Bootstrap、同日 Cached 已有 PASS 收據；不是永久固定分母 | 不重跑該歷史驗收；驗跨 UI／研究／總控剩餘範圍 |
| 費稅／持股 | **P0 backend as-of 2026-10-14 PASS**：00697B／00719B 官方歷史日價、Owner v354，8/8 持股市值及未實現損益都有值，aggregate_status available，缺價／受影響商品 0，總計非空；#38732675488 與 #38733406224 PASS，舊失敗執行保留 FAILED | P1 前端正式持股頁／計算按鈕與新當日估值、正式流量切換另驗；不重做 88 筆費稅事件 |
| 首頁快照 | main 已有正式 caller；057 migration 曾 PASS；最新接線的 runtime 尚待驗收 | 快照產生→API 讀回→冷暖效能 |
| 重算／交易／四頁 | 持股 partial 小計與狀態 Flutter 已修改、完整 Flutter Gate PASS；交易試算與重算舊契約已具實作，**新版本 Owner 交易/重算及四頁 authenticated screenshot 未驗** | 覆蓋同源真實功能、VF-00～08、390px/desktop與可及性 |
| 備份總控 | D04 GHA WIF 唯讀 #38710741325 PASS：Scheduler 唯一 janus-ingestion-daily ENABLED 每小時 :30；GCS daily 備份可列 3 份、最新 2026-10-14；Compute VM describe 仍 DENIED_OR_UNAVAILABLE。install #38692040229 缺 compute.instances.get，原 timer 未被本輪停用；isolated restore／handoff NOT VERIFIED | 要執行 VM 內 executor install/restore，須既有授權的 VM 執行路徑或明確核准精確最小 Compute／IAP IAM；未獲權限不切 timer |
| API／Preview／Jobs | 最新已驗證來源 285848 Release #38717341300、API 0% #38718006906、OAuth #38718076548、四 Jobs #38718355824 SUCCESS；fixed Preview 尚為先前 079cca #38711150682、正式 100% traffic 未切 | P1 實際 owner UI/API、同版 Preview／正式 dev 切流與回復驗收，不以 P0 backend PASS 當成 App 已發布 |
| Iceberg | compact 重寫成功，Core 8162→8225 objects；不是縮檔成功。dry-run 預計74 snapshots／403 orphans | 等既有 rollout／audit cleanup 終態，驗受引用保護清理與等量 I/O |
| Retention fence | 19 份 oversized research 尚未完整讀取，private／PG 引用未全面驗證；一般清理 BLOCKED | 完整引用清單；不以空清單冒充安全 fence |
| 五角色／CEO | B0～B8 歷史 CLOSED；B9 品質未整體通過；omniAgent P0-V 技術 PASS，正式 Owner publication 未通過 | 產品交付後逐角色評估，再驗真實報告 |

## 本輪直接觀測與阻塞（非永久 runtime 快照）

- [新版本 full Release #38695837708](https://github.com/tommylin15/janus-omniforge/actions/runs/38695837708) 來源 `079cca4f…` 四公開 GHCR、Python/PostgreSQL、Flutter PASS；[#38710296292](https://github.com/tommylin15/janus-omniforge/actions/runs/38710296292) API 0% 與 [#38710582355](https://github.com/tommylin15/janus-omniforge/actions/runs/38710582355) auto OAuth boundary、[#38711150682](https://github.com/tommylin15/janus-omniforge/actions/runs/38711150682) 固定 Preview SUCCESS；Jobs 仍在較舊 SHA，不能做同源正式切流。
- [部署鎖安全恢復 #38709075307](https://github.com/tommylin15/janus-omniforge/actions/runs/38709075307) SUCCESS，原有 GitHub lease ref 已不存在。D04 [唯讀 #38710741325](https://github.com/tommylin15/janus-omniforge/actions/runs/38710741325) 確認唯一 Scheduler 與 3 份 GCS 備份，但 CI VM describe 缺權限；[#38692040229](https://github.com/tommylin15/janus-omniforge/actions/runs/38692040229) install 仍 FAILED，未停原 timer。
- [TPEx 官方來源 #38694634095](https://github.com/tommylin15/janus-omniforge/actions/runs/38694634095) GitHub runner 讀到 00697B、OpenAPI 12,466 rows、正確 2026-10-14 日期；[live readonly #38710480798](https://github.com/tommylin15/janus-omniforge/actions/runs/38710480798) 與 [日志 readback #38711328741](https://github.com/tommylin15/janus-omniforge/actions/runs/38711328741) 則確認 Cloud Run 官方 fetch JSONDecodeError，且 Core valuation 10/14 / saved quote 10/15 不符 PIT。Owner Mart [#38695729369](https://github.com/tommylin15/janus-omniforge/actions/runs/38695729369) `held_etf_official_eod_missing` FAILED，無法宣稱 PnL PASS；本輪均未重送 owner ledger events。
- 舊 D06 [四 Jobs rollout #38686125420](https://github.com/tommylin15/janus-omniforge/actions/runs/38686125420) 現已查到 `completed/success`，但 [audit-cleanup #38686337134](https://github.com/tommylin15/janus-omniforge/actions/runs/38686337134) 為 `completed/failure`，不因 container／rollout 成功就稱 cleanup PASS。這是獨立 FinOps，不能挪用本 D01～D05 授權重送。
- 本輪尚無 authenticated 手機冷暖 P95／四張真實截圖或完整 Owner 試算/保存/重算 terminal/checkpoint 新版驗收；不以 GitHub mock、公開 API 或上版 build 替代。

- [公開效能 #38695300866](https://github.com/tommylin15/janus-omniforge/actions/runs/38695300866) 固定 Preview 先前來源 536598 30/30 公開 API，P50 47.43ms／P95 51.42ms；[圖表 #38696030009](https://github.com/tommylin15/janus-omniforge/actions/runs/38696030009) 18 指標有 16 available、2 EPS missing。不可外推為新版 079cca authenticated UI 或手機冷暖 P95。
- GCP_MCP Google OAuth `redirect_uri_mismatch` 屬連接器授權，工程改以已驗證 GitHub Actions → GCP WIF 執行，不調整 Janus OAuth Client 或任意擴 IAM。

## 文件整理結果與下一入口

- [盤點／風險與修正](documentation-review-2026-10-15.md)：文件與程式差異、範圍及驗證。
- [系統建置與驗收補強](spec/system-development-contract.md)：UI、持股操作、模型驗證及 FinOps 的工程契約。
- 未完成工作只在 [TODO](todo.md) 排隊；本頁不維護第二份 checkbox。
- 舊逐次狀態完整保留於 [整編前快照](archive/documentation-baseline-2026-10-15-status.md)，不得用其中過期 PAUSED／IN_PROGRESS 覆蓋本頁。
