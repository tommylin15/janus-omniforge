# Janus 目前狀態

更新：2026-10-15（文件盤點）；基準 `301e7f7229458e2d1f26818a66b90d0a464fc68f`。

**整體 PARTIAL。本輪只修改文件，不部署、不重算、不訓練、不刪業務資料。**
產品開發沿用最新暫停 checkpoint；先前獨立授權的 FinOps 兩項續工與既有執行不受本文件盤點取消或重送。下一位 AI 先讀 [TODO](todo.md) 與 [開發指示](codex-execution-plan.md)，不要執行歷史「接著做」句子。

## 能確定的現況與限制

| 項目 | 最近可追溯證據／判定 | 下一步 |
|---|---|---|
| 全市場 | 2026-10-13 名冊 1988；Bootstrap、同日 Cached 已有 PASS 收據；不是永久固定分母 | 不重跑該歷史驗收；驗跨 UI／研究／總控剩餘範圍 |
| 費稅／持股 | 059、88 筆更正、ledger352／8 持股的既有讀回 PASS；00697B 缺價，完整 PnL PARTIAL | 核對最新已部署映像是否含 TPEx 修復，再驗完整估值；不重送費稅 apply |
| 首頁快照 | main 已有正式 caller；057 migration 曾 PASS；最新接線的 runtime 尚待驗收 | 快照產生→API 讀回→冷暖效能 |
| 重算／交易／四頁 | 原 queue request 已有終態核對；原 workflow cleanup 失敗仍保留；完整 Owner UI E2E PARTIAL | 新版同源功能、狀態、資料與截圖證據 |
| 備份總控 | 原 timer active、新 executor／隔離 restore 工具尚待真實交接 | 先備份及 restore PASS，再停舊 timer |
| API／Preview／Jobs | 不同元件版本不可互相推定；正式 API 尚無本產品包切流 PASS | 部署前獨立讀回各元件 SHA／digest／traffic／Scheduler |
| Iceberg | compact 重寫成功，Core 8162→8225 objects；不是縮檔成功。dry-run 預計74 snapshots／403 orphans | 等既有 rollout／audit cleanup 終態，驗受引用保護清理與等量 I/O |
| Retention fence | 19 份 oversized research 尚未完整讀取，private／PG 引用未全面驗證；一般清理 BLOCKED | 完整引用清單；不以空清單冒充安全 fence |
| 五角色／CEO | B0～B8 歷史 CLOSED；B9 品質未整體通過；omniAgent P0-V 技術 PASS，正式 Owner publication 未通過 | 產品交付後逐角色評估，再驗真實報告 |

## 本輪直接唯讀觀察

GitHub Actions API 查核時，Jobs rollout [#38686125420](https://github.com/tommylin15/janus-omniforge/actions/runs/38686125420) 為 `in_progress`，audit-cleanup [#38686337134](https://github.com/tommylin15/janus-omniforge/actions/runs/38686337134) 為 `pending`，兩者 `conclusion=null`。這是觀察時點，不是永久現況，也不是 runtime PASS；接手時先讀終態，未知不得重送。

本輪未直接重新查 GCP／私人帳本；上表其餘是版本化既有證據摘要。詳見 [最新證據索引](spec/operations-and-testing.md)、[暫停交接](archive/pause-checkpoint-2026-10-15.md)。

## 文件整理結果與下一入口

- [盤點／風險與修正](documentation-review-2026-10-15.md)：文件與程式差異、範圍及驗證。
- [系統建置與驗收補強](spec/system-development-contract.md)：UI、持股操作、模型驗證及 FinOps 的工程契約。
- 未完成工作只在 [TODO](todo.md) 排隊；本頁不維護第二份 checkbox。
- 舊逐次狀態完整保留於 [整編前快照](archive/documentation-baseline-2026-10-15-status.md)，不得用其中過期 PAUSED／IN_PROGRESS 覆蓋本頁。
