# AI 任務卡入口

更新：2026-11-25。唯一 active queue：[TODO](../todo.md)。

## 新增待啟動工程卡（DOC_ONLY，等待使用者指定開工）

- [API + AI 個股分析重構工程卡（AI-REF-01～06）](ai-stock-analysis-v2.md)：對應 [正式 SPEC](../spec/ai-stock-analysis-v2.md)（2026-11-23 決策：廢除四模型訓練／推論，改採外部 API + 後端確定性計算 + T1–T5 + Gemini Hydrogen `StockInsightV2`）。本決策覆蓋下表 `SEQ-01`～`08` 原四模型上線目標。
- [股利自動推算與一鍵入帳工程卡（DIV-01～04）](dividend-auto-ledger.md)：對應 [正式 SPEC](../spec/dividend-auto-ledger.md)（2026-11-25 決策：支援現金＋股票股利後端 `Decimal` 推算與樂觀鎖一鍵確認入帳）。

## 既有一覽與歷史路由

原四模型時期逐項指令見 [SEQ-01…08四階段任務卡](sequential-delivery.md)；個人策略接手見 [個人策略工程卡](personal-strategy.md) 與 [實作與驗收WI](personal-strategy-implementation.md)。任務卡存在不是自動執行授權；請先讀 `AGENTS.md` 與 `PROJECT_RULES.md`，再按使用者指定工作包開工。

| 舊卡／ID | 現行去向 |
|---|---|
| UB-01／03／04／05 | SEQ-01…04 |
| RV-01…06 | SEQ-05，發布合流SEQ-08 |
| UB-02／D07 serving／跨Job快取 | SEQ-06 |
| [D08報告卡](../archive/document-cleanup-2026-10-25/execution-cards/d08-ceo-admin-owner-report.md) | SEQ-07，發布合流SEQ-08；僅讀仍適用細節 |
| D07-PRE／X/Y／因子工廠 | 上線必要一致性SEQ-06；全面研究改善移第二版 |
| [D07研究卡](../archive/document-cleanup-2026-10-25/execution-cards/d07-specialist-b9-oos.md)、[模型生命週期卡](../archive/document-cleanup-2026-10-25/execution-cards/d07-model-lifecycle.md) | [2027 Q1第二版](../parking-lot.md#v2-2027-q1)，不自動執行 |
| [A-CHANGE](../archive/document-cleanup-2026-10-25/execution-cards/a-change-analysis.md)、D01～D06、OPS-P0-1、C1-A | 已結案歷史參考，無新異常不重開 |

[統一批次WI](../runbook-unified-batch-ai.md)是SEQ-01…04與08的技術程序，不是額外工作線。舊卡中多線並行、第五模型或已取消稽核門檻不覆蓋現行規則。
