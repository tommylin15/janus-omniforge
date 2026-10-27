# Janus — 工作責任與順序

更新：2026-10-25。唯一狀態及排序在 [TODO](todo.md)，操作見 [逐項AI指示](execution-cards/sequential-delivery.md)。原多線並行分派停止適用；以下新SEQ只整併舊工作，不增加第二組待辦。

| 順序 | 工作／角色 | 原工作對照 | 依賴與交付邊界 |
|---|---|---|---|
| SEQ-01 | 收取、清理與市場分析總控／資料工程 | UB-01 | 本次已核准規格；[四階段與退出條件](execution-cards/sequential-delivery.md#seq-01) |
| SEQ-02 | 持股、買賣與觀察設定快照／後端／產品工程 | UB-03、4J／4R 的本次增量 | SEQ-01可交接階段；[四階段與退出條件](execution-cards/sequential-delivery.md#seq-02) |
| SEQ-03 | 日週月備份、保留清理與回復範圍／資料維運 | UB-04（不是重開 OPS-P0-1） | SEQ-02可交接階段；[四階段與退出條件](execution-cards/sequential-delivery.md#seq-03) |
| SEQ-04 | 基礎批次集中部署與兩小時切換／發版／維運 | UB-05：UB-01／03／04 合流 | SEQ-03可交接階段；[四階段與退出條件](execution-cards/sequential-delivery.md#seq-04) |
| SEQ-05 | Valuation 真資料、唯一估值卡契約／估值／後端工程 | RV-01…06、UB-02 的 Valuation 子功能 | SEQ-04可交接階段；[四階段與退出條件](execution-cards/sequential-delivery.md#seq-05) |
| SEQ-06 | 四模型正式上線模式、版本與共用快取／模型／推論工程 | UB-02、D07 serving、Risk API/UI、D07-CROSS-JOB-MODEL-CACHE；FACTOR-FACTORY／X/Y 僅必要 serving 一致性 | SEQ-05可交接階段；[四階段與退出條件](execution-cards/sequential-delivery.md#seq-06) |
| SEQ-07 | 分析報告、Owner history 與 UI 完整接線／全端／產品工程 | UB-02、D08、RV-05 合流 | SEQ-06可交接階段；[四階段與退出條件](execution-cards/sequential-delivery.md#seq-07) |
| SEQ-08 | 四分析師到報告 UI 集中發布驗收／整合驗收／發版 | UB-02 完成 gate、RV-06、D08 發布 | **已結案（CLOSED）**：全市場 Quant、Owner 8 檔報告及實機登入驗收完成；圖解白話增量由前端接續；[四階段與退出條件](execution-cards/sequential-delivery.md#seq-08) |

每項均有文件設計、程式開發、測試驗收、部署四階段；設計建議GPT-6 Astra，實作／驗收／部署建議GPT-6.1 Sol。SEQ-01…03先完成可離線交付部分，SEQ-04集中部署並結清live；SEQ-05…07同理交SEQ-08，不能把待集中部署標PASS。

四模型本版正式上線，研究調校移至 [2027 Q1第二版](parking-lot.md#v2-2027-q1)，不形成前置依賴。對現有推論必需的因子公式／X/Y一致性併SEQ-06，不另開資料研究線。

## 原領域 WBS 定位（不構成額外工作）

2026-10-27 個股呈現增量：前端責任為四面向圖解、公告內容、分析技術資料收合及相依測試程式；需求與驗收邊界見 [UI 契約](ui/stock-detail-readable.md)。使用者另行負責測試執行、驗收與上版，本輪不擴展後端或重開模型研究。

- 資料／總控：[WBS 3](wbs/wbs-3-ingestion-admin.md)。
- 私人記帳／快照：[4J](wbs/wbs-4j-personal-workspace.md)、[4R](wbs/wbs-4r-personal-risk.md)。
- 四模型／報告：[Specialist](wbs/wbs-5-specialist-engines.md)、[Mart](wbs/wbs-5-intelligence-mart.md)。
- API／UI：[WBS 6](wbs/wbs-6-api-and-apps.md)。
- 備份／安全／發布：[WBS 7](wbs/wbs-7-security-finops.md)、[WBS 8](wbs/wbs-8-qa-release.md)。
- 已結案：[完成索引](wbs/completed-index.md)。

舊WBS的parallel／第五模型／週月研究稽核／完整PIT等待等相反指示不適用。C1-A、P0-2、OPS-P0-1、A-CHANGE、D01～D06、FINOPS-AB及研究精簡不重開；暫不做事項只留Parking Lot。

分析Mart／頻率增量歸原SEQ-01／05／06／07／08，責任與四階段見[新WI](runbook-analyst-input-mart-ai.md)，不增加獨立批次、工作線或模型調校。
