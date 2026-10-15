# Janus 目前狀態

更新：2026-10-15（D01～D05 整合開發／候選驗收）；產品 Release 固定完整來源 SHA `536598f2528550fd60c73786597fdf2740860c9e`。其後 main 的 ops／診斷／文件 commit 不表示換成新的 application runtime source。

**整體 PARTIAL。** 使用者已明確授權 D01～D05 一起開發、以同源整批驗收，取代此前文件-only 暫停；D06 獨立 FinOps、不併入本輪，D07／D08 後置。完整 Release／GHCR digest／0% 候選／自動 OAuth 已 PASS，**正式 API 100% traffic 尚未獲得本產品包的所有真實業務 gate**，不能宣稱產品交付完成。詳見 [TODO](todo.md)、[AI 卡片](execution-cards/README.md) 與 [證據索引](spec/operations-and-testing.md)。

## 能確定的現況與限制

| 項目 | 最近可追溯證據／判定 | 下一步 |
|---|---|---|
| 全市場 | 2026-10-13 名冊 1988；Bootstrap、同日 Cached 已有 PASS 收據；不是永久固定分母 | 不重跑該歷史驗收；驗跨 UI／研究／總控剩餘範圍 |
| 費稅／持股 | 88 筆更正歷史成功不重送；2026-10-15 Owner-scoped 私人 readback（2026-10-14、ledger v354）仍見 00697B `no_eligible_persisted_ohlcv`；新版 quote safety／mixed-date aggregate withholding 已全套 CI PASS，正式 Owner 完整損益未驗 | 查官方 TPEx EOD 來源可用性、正式持股/重算同版 checkpoint，不以缺價貼假價格 |
| 首頁快照 | main 已有正式 caller；057 migration 曾 PASS；最新接線的 runtime 尚待驗收 | 快照產生→API 讀回→冷暖效能 |
| 重算／交易／四頁 | 持股 partial 小計與狀態 Flutter 已修改、完整 Flutter Gate PASS；交易試算與重算舊契約已具實作，**新版本 Owner 交易/重算及四頁 authenticated screenshot 未驗** | 覆蓋同源真實功能、VF-00～08、390px/desktop與可及性 |
| 備份總控 | 新 executor install #38692040229 因 GCP `compute.instances.get` 缺權限 **BLOCKED**（在 VM 修改前失敗）；原 timer 保留，restore/交接 NOT VERIFIED | 受既有治理約束核對最小 IAM 授權途徑；取得合法 VM access 後先新備份＋隔離 restore 再停 timer |
| API／Preview／Jobs | 新版 Release #38691316772 PASS（1265 Python PASS／2 deselected、Flutter、四 GHCR public pull）；0% candidate #38691954051 與 auto-auth #38692148433 PASS。四 Jobs rollout #38692371269、fixed Preview #38692491748 仍以執行時即時終態為準；正式 100% traffic 未切 | 讀回 Jobs／Preview terminal、候選 Owner UI／PnL／性能／rollback，必要 gates 未過不切正式 traffic |
| Iceberg | compact 重寫成功，Core 8162→8225 objects；不是縮檔成功。dry-run 預計74 snapshots／403 orphans | 等既有 rollout／audit cleanup 終態，驗受引用保護清理與等量 I/O |
| Retention fence | 19 份 oversized research 尚未完整讀取，private／PG 引用未全面驗證；一般清理 BLOCKED | 完整引用清單；不以空清單冒充安全 fence |
| 五角色／CEO | B0～B8 歷史 CLOSED；B9 品質未整體通過；omniAgent P0-V 技術 PASS，正式 Owner publication 未通過 | 產品交付後逐角色評估，再驗真實報告 |

## 本輪直接觀測與阻塞（非永久 runtime 快照）

- [新產品 Release #38691316772](https://github.com/tommylin15/janus-omniforge/actions/runs/38691316772) 同一完整 SHA 的 Python/PostgreSQL、Flutter、四公開 GHCR image/pull 全 PASS；[#38691954051](https://github.com/tommylin15/janus-omniforge/actions/runs/38691954051) 0% 候選與 [#38692148433](https://github.com/tommylin15/janus-omniforge/actions/runs/38692148433) 自動 OAuth boundary PASS，不代表 Owner 正向損益與四頁 live PASS。
- [D04 install #38692040229](https://github.com/tommylin15/janus-omniforge/actions/runs/38692040229) 失敗原因為 CI 身分缺 `compute.instances.get`；尚未更動 VM executor／停舊 timer，必要 IAM 擴張依 PROJECT_RULES 人工核准。
- [TPEx 公開來源唯讀診斷 #38692692373](https://github.com/tommylin15/janus-omniforge/actions/runs/38692692373)：官方 `tpex_mainboard_daily_close_quotes` 在 GitHub runner 回應無法 JSON 解碼（`JSONDecodeError`），沒有寫價或私人資料；結合實際 Owner v354 缺價，完整 PnL 保持 PARTIAL。
- 舊 D06 [四 Jobs rollout #38686125420](https://github.com/tommylin15/janus-omniforge/actions/runs/38686125420) 現已查到 `completed/success`，但 [audit-cleanup #38686337134](https://github.com/tommylin15/janus-omniforge/actions/runs/38686337134) 為 `completed/failure`，不因 container／rollout 成功就稱 cleanup PASS。這是獨立 FinOps，不能挪用本 D01～D05 授權重送。
- 本輪尚無 authenticated 手機冷暖 P95／四張真實截圖或完整 Owner 試算/保存/重算 terminal/checkpoint 新版驗收；不以 GitHub mock、公開 API 或上版 build 替代。

## 文件整理結果與下一入口

- [盤點／風險與修正](documentation-review-2026-10-15.md)：文件與程式差異、範圍及驗證。
- [系統建置與驗收補強](spec/system-development-contract.md)：UI、持股操作、模型驗證及 FinOps 的工程契約。
- 未完成工作只在 [TODO](todo.md) 排隊；本頁不維護第二份 checkbox。
- 舊逐次狀態完整保留於 [整編前快照](archive/documentation-baseline-2026-10-15-status.md)，不得用其中過期 PAUSED／IN_PROGRESS 覆蓋本頁。
