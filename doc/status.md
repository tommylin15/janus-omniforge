# Janus 目前狀態

更新：2026-10-15（P0／P1／D04 經 GitHub Actions → GCP WIF 讀回）。最新已驗證 API／固定 Preview 來源 `079cca4f24aedb6285270df8e86f856d2498ce13`；四支 live Jobs 仍須按已驗證 rollout 來源 `536598f2528550fd60c73786597fdf2740860c9e` 判定，不能跨來源當作同一輪可正式切流。

### P0｜TPEx 官方歷史日期長期能力（2026-10-15 本輪）

- **已落地（程式及資料庫）**：`services/api/tpex_quotes.py` 支援官方 `/www/zh-tw/afterTrading/dailyQuotes?date=YYYY/MM/DD&response=json` 的指定交易日查詢（不限 OpenAPI 七日滾動窗口）；嚴格核對官方回應 `date`、有效收盤價與 14:30 發布門檻。近七日 OpenAPI 仍保留，失敗可走官方定日來源。版本化 migration `061_tpex_official_eod_daily` 使用獨立 PostgreSQL 官方日期／價格／來源 URL／record SHA-256／first-observed，不污染 Core/Iceberg canonical；Private Mart 只用不晚於估值日的已保存官方資料。
- **證據**：官方 `00697B` 10/14 原始 JSON 指定日期與 date response [#38715334637](https://github.com/tommylin15/janus-omniforge/actions/runs/38715334637) PASS；migration [#38714018250](https://github.com/tommylin15/janus-omniforge/actions/runs/38714018250) 真實 dev PASS；17/17 歷史、日期、PIT targeted tests [#38717113572](https://github.com/tommylin15/janus-omniforge/actions/runs/38717113572) PASS；完整來源 `285848e28041bf2fb024bd98bd348641f022a1ed` Release [#38717341300](https://github.com/tommylin15/janus-omniforge/actions/runs/38717341300) SUCCESS；API 0% [#38718006906](https://github.com/tommylin15/janus-omniforge/actions/runs/38718006906) 和自動 OAuth／private boundary [#38718076548](https://github.com/tommylin15/janus-omniforge/actions/runs/38718076548) SUCCESS，**未切 100% 流量**。
- **最後 live gate 尚未 PASS**：相同 SHA 四 Jobs rollout [#38718355824](https://github.com/tommylin15/janus-omniforge/actions/runs/38718355824) 以及唯一 Owner、2026-10-14 as-of、全部持股／投資組合總 PnL 驗收 [#38718586032](https://github.com/tommylin15/janus-omniforge/actions/runs/38718586032) 已觸發，**以各自最新終態／receipts 讀回為準**。不得拿 full Release／Migration 替代 real Owner 損益證據。不得使用 10/15 報價計算 10/14，也不得修改真實交易帳本。

**整體 PARTIAL。** 使用者已明確授權 D01～D05 一起開發、以同源整批驗收，取代此前文件-only 暫停；D06 獨立 FinOps、不併入本輪，D07／D08 後置。完整 Release／GHCR digest／0% 候選／自動 OAuth 已 PASS，**正式 API 100% traffic 尚未獲得本產品包的所有真實業務 gate**，不能宣稱產品交付完成。詳見 [TODO](todo.md)、[AI 卡片](execution-cards/README.md) 與 [證據索引](spec/operations-and-testing.md)。

## 能確定的現況與限制

| 項目 | 最近可追溯證據／判定 | 下一步 |
|---|---|---|
| 全市場 | 2026-10-13 名冊 1988；Bootstrap、同日 Cached 已有 PASS 收據；不是永久固定分母 | 不重跑該歷史驗收；驗跨 UI／研究／總控剩餘範圍 |
| 費稅／持股 | 88 筆更正不重送；Owner v354／2026-10-14 仍有 00697B 缺價。live readonly probe #38710480798 + readback #38711328741 證明 private Job 官方 TPEx JSONDecodeError、Core 估值日 10/14、唯一本地最新官方 quote 日 10/15（PIT 未合格）；身份 TPEX／enabled 已證實 | 先修官方來源在 Cloud Run 的 JSON 解碼，再建立日期受限且可持久追溯的 10/14 官方 EOD 價格來源；不可使用 10/15 報價替代 10/14 PnL |
| 首頁快照 | main 已有正式 caller；057 migration 曾 PASS；最新接線的 runtime 尚待驗收 | 快照產生→API 讀回→冷暖效能 |
| 重算／交易／四頁 | 持股 partial 小計與狀態 Flutter 已修改、完整 Flutter Gate PASS；交易試算與重算舊契約已具實作，**新版本 Owner 交易/重算及四頁 authenticated screenshot 未驗** | 覆蓋同源真實功能、VF-00～08、390px/desktop與可及性 |
| 備份總控 | D04 GHA WIF 唯讀 #38710741325 PASS：Scheduler 唯一 janus-ingestion-daily ENABLED 每小時 :30；GCS daily 備份可列 3 份、最新 2026-10-14；Compute VM describe 仍 DENIED_OR_UNAVAILABLE。install #38692040229 缺 compute.instances.get，原 timer 未被本輪停用；isolated restore／handoff NOT VERIFIED | 要執行 VM 內 executor install/restore，須既有授權的 VM 執行路徑或明確核准精確最小 Compute／IAP IAM；未獲權限不切 timer |
| API／Preview／Jobs | 來源 536598 四 Jobs rollout #38692371269 與 Preview #38692491748 均 SUCCESS。更新版 079cca Release #38695837708、0% candidate #38710296292、auto OAuth boundary #38710582355、固定 Preview #38711150682 均 SUCCESS，正式 100% traffic 未切；最新 API／Jobs 仍跨 source SHA | Owner 真實 E2E／PIT 修復、同源 Jobs rollout、Preview UI/業務功能與回滾 gate 完整後才評估正式切流 |
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
