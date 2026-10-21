# D01～D08 獨立 AI 任務卡索引

更新：2026-10-19。任務卡只保存**如何操作／驗收**，唯一 active queue 在 [TODO](../todo.md)，已結案卡片不重新形成待辦。

| 工作包 | 執行卡 | WBS 責任 |
|---|---|---|
| A-CHANGE | [方案A卡](a-change-analysis.md) | WBS-5/6；事實/變化/盤前盤後/UI |
| D01 | [持股交易／完整估值](d01-holdings-trading-valuation.md) | WBS 4J／6（必要時 4R） |
| D02 | [全市場／首屏快照／效能](d02-full-market-snapshot-performance.md) | WBS 3／6 |
| D03 | [四頁 UI／通用圖表／視覺收斂](d03-four-page-charts-visual.md) | WBS-6-USER-FINAL-VISUAL-CONVERGENCE（非 AI） |
| D04 | [Scheduler 總控／備份交接](d04-controller-backup-handoff.md) | WBS 3／7 |
| D05 | [產品集中發布／完整 dev 驗收](d05-integrated-release-dev.md) | WBS 8／CI-CD |
| **D07-PRE（唯一研究入口）** | [Colab／Drive 月資料夾 研究規格](../spec/research-collection-gas-drive-colab.md) | 研究普通股、分市場70%、欄位盤點；舊研究退役已結案，不作前置 |
| D06（已併 FINOPS-AB 結案） | [歷史清理任務卡](d06-iceberg-retention-io.md) | 只供歷史／故障定位，不執行獨立工項 |
| D07 | [五角色／歷史母體／B9 品質](d07-specialist-b9-oos.md) | WBS-5-MART-SPECIALIST-ENGINES／RERUN-CACHE（B9） |
| D08 | [CEO／Admin／正式 Owner 報告](d08-ceo-admin-owner-report.md) | WBS-5-MART-AI-PROVIDERS／CIO-SYNTHESIS、WBS-6-ADMIN-ANALYSIS-PROFILE |

使用時先讀 [AGENTS](../../AGENTS.md) → [PROJECT_RULES](../PROJECT_RULES.md) → [TODO](../todo.md) 確認指定 Dxx 的授權與 active acceptance，再讀**該一張**任務卡與最小受影響 code/spec/UI；若未授權，卡片存在不代表可啟動。本索引不標 PASS／PARTIAL，真實狀態在 [status](../status.md)，唯一未完成清單在 [TODO](../todo.md)。

工程卡統一包含：責任、依賴、最小必讀、工程入口、前置讀回、執行程序、專屬驗收、安全界線、失敗恢復、相同格式的 CI／dev 真實證據與 AI 交接報告。

目前範例：「接續 D07-PRE，採 官方 API→Colab→Drive 月資料夾→Colab；不使用舊 Core/BQ／Cloud Run 訓練路徑，正式 Janus 服務不受影響。」


## D01～D06 已結案的 UI／資料指令（歷史索引）

[TODO](../todo.md)確認範圍 → [AI總指令](../codex-execution-plan.md)第1節選卡。DRL-01 及 D02/D03 的原業務驗收已按使用者接受範圍結案，舊 UI 資料工作單僅供新缺陷追溯，**不恢復原 DRL 任務**。
**UI實際長相看[A第5節](../ui/visual-first-four-pages.md)**，含手機／桌面位置、尺寸、字級、按鈕、缺值樣式；資料→計算→UI→驗收看[B工單](../ui/visual-first-delivery.md)。不另建 DRL 卡或 queue，D07/PRE 與 D08 依現行 TODO，不重新驗已接受的真人 PASS。

## 方案 A 新入口
[A-CHANGE AI卡](a-change-analysis.md)：事實解讀→變化狀態→盤前盤後→UI集中驗收；[D07卡](d07-specialist-b9-oos.md)負責X/Y/模型；不重開D01～D06。


D07詳細操作：[Colab採集/清洗/貼標/訓練→GCS→日週批次→月評估](d07-model-lifecycle.md)，沿原D07卡/WBS，不是新queue。

