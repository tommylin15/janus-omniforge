# D01～D08 獨立 AI 任務卡索引

更新：2026-10-15。任務卡是可交給 AI 的操作與驗收指令，不是第二份 TODO，不新增執行授權或短期 runtime 狀態。

| 工作包 | 執行卡 | WBS 責任 |
|---|---|---|
| D01 | [持股交易／完整估值](d01-holdings-trading-valuation.md) | WBS 4J／6（必要時 4R） |
| D02 | [全市場／首屏快照／效能](d02-full-market-snapshot-performance.md) | WBS 3／6 |
| D03 | [四頁 UI／通用圖表／視覺收斂](d03-four-page-charts-visual.md) | WBS-6-USER-FINAL-VISUAL-CONVERGENCE（非 AI） |
| D04 | [Scheduler 總控／備份交接](d04-controller-backup-handoff.md) | WBS 3／7 |
| D05 | [產品集中發布／完整 dev 驗收](d05-integrated-release-dev.md) | WBS 8／CI-CD |
| D06 | [Iceberg／受引用保護清理／I/O](d06-iceberg-retention-io.md) | WBS 7／retention |
| D07 | [五角色／歷史母體／B9 品質](d07-specialist-b9-oos.md) | WBS-5-MART-SPECIALIST-ENGINES／RERUN-CACHE（B9） |
| D08 | [CEO／Admin／正式 Owner 報告](d08-ceo-admin-owner-report.md) | WBS-5-MART-AI-PROVIDERS／CIO-SYNTHESIS、WBS-6-ADMIN-ANALYSIS-PROFILE |

使用時先讀 [AGENTS](../../AGENTS.md) → [PROJECT_RULES](../PROJECT_RULES.md) → [TODO](../todo.md) 確認指定 Dxx 的授權與 active acceptance，再讀**該一張**任務卡與最小受影響 code/spec/UI；若未授權，卡片存在不代表可啟動。本索引不標 PASS／PARTIAL，真實狀態在 [status](../status.md)，唯一未完成清單在 [TODO](../todo.md)。

八張卡統一包含：責任、依賴、最小必讀、工程入口、前置讀回、執行程序、專屬驗收、安全界線、失敗恢復、相同格式的 CI／dev 真實證據與 AI 交接報告。

例：「執行 D01，依任務卡做到完整 dev 驗收；不要啟動 D07。」


## 首頁／個股與資料指令路由（2026-10-16）

[TODO](../todo.md)確認範圍 → [AI總指令](../codex-execution-plan.md)第1節選卡。DRL-01依總指令第7節（等待恢復）；D02依快照卡；D03依四頁卡。
**UI實際長相看[A第5節](../ui/visual-first-four-pages.md)**，含手機／桌面位置、尺寸、字級、按鈕、缺值樣式；資料→計算→UI→驗收看[B工單](../ui/visual-first-delivery.md)。不另建DRL卡或queue，D07/D08仍後置，本增補不重開真人PASS、不擴正在收尾的D05。
