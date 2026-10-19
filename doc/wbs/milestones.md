# Janus｜管理里程碑與工作責任索引

更新：2026-10-19。本檔只有**高階交付節點**，不維護完成百分比、實測數字或第二份待辦。唯一 active 順序在 [TODO](../todo.md)，歷史 M0～M5 與原六頁 Admin 里程碑保存在 [舊版](../archive/wbs-milestones-before-consolidation-2026-10-19.md)。

| 順序／里程碑 | 責任 | 前置／驗收邊界 |
|---|---|---|
| 已結案基線 | D01～D05、DRL-01、FINOPS-AB＋D06、補收、Admin v2 | 按原使用者已接受與 live 範圍結案，不推論沒測的項目 PASS；需修復的新問題由現行工項承接 |
| **M-PRE / D07-PRE** | Data Governance + WBS-5/7 + [AI 指令 §4](../execution-cards/finops-ingestion-iceberg-ab-and-c-gate.md) | 24月 coverage/PIT/來源、Colab CPU frozen data/feature/fit/OOS、成本、安全、BigQuery 必要時前置縮減、合法手動/月度工作；唯一 GO/BLOCKED 決議 |
| **M-MODEL / D07** | WBS-5 Specialist Engines + [D07 卡](../execution-cards/d07-specialist-b9-oos.md) | Quant→Risk→Valuation/Fundamental→Event；逐角色成熟樣本/OOS vs baseline／source/PIT、模型/評估 artifact、Mart 註冊與回復 |
| **M-REPORT / D08** | WBS-5 CEO／WBS-6 Admin User + [D08 卡](../execution-cards/d08-ceo-admin-owner-report.md) | 有效 Fact Pack、Gateway/auth/validator、immutable report／Owner history／UI、資料與發佈分權 |
| 營運證據觀察 | WBS-8 / [Pilot](../pilot-operational-evidence.md)／[Operations](../spec/operations-and-testing.md) | 自然排程/異常/備份/成本觀察，非模型新品前置；production 多人、HA/SLA 仍是未核准後置需求 |

**資料、模型與部署不能混判**：模型研究需求未證實 source/PIT/成熟標籤時標 partial，Colab 免費版 unattended 仍未驗證，不能由文件自動取得 production 訓練權限。選項在 [專案管理風險](../project-management.md#4-重大風險及選項)。沒有明確新付費/IAM 批准，不自行啟用 Colab Enterprise 或擴大全市場 24 月回補。
