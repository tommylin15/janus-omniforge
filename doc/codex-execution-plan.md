# Janus｜接手 AI 的唯一工程路由

更新：2026-10-19。本檔只定義 **如何接手與跨元件協作**；**做什麼／何時做／哪些未完成**一律看 [唯一 TODO](todo.md)，不在這裡開第二份 queue。舊 D01～D06／DRL-01 操作命令完整存 [歷史指令](archive/codex-execution-plan-before-consolidation-2026-10-19.md)，不再向其他 AI 發出「恢復舊任務」指令。

## 1. 啟動與責任

依序讀 [AGENTS](../AGENTS.md) → [PROJECT_RULES](PROJECT_RULES.md) → [專案管理](project-management.md) → [status](status.md) → [TODO](todo.md) → **當次唯一任務卡**。其他 SPEC/UI/WBS 只在直接影響時讀；任何舊截面或 Drive 文件不得覆蓋目前 main／runtime。未有當次權限不能推進新付費 API、大幅 IAM 或破壞性操作。

| 現行工作包 | AI 必讀操作卡 | 必要契約／成果 |
|---|---|---|
| **D07-PRE** | [FINOPS/Colab 整合指令 §4](execution-cards/finops-ingestion-iceberg-ab-and-c-gate.md) | [Colab 單一路徑](colab-d07-modeling-feasibility-2026-10-19.md)、[資料治理](spec/data-governance.md)；24月覆蓋、PIT、來源、成本及 Colab 實跑／交回 |
| **D07** | [D07 五角色卡](execution-cards/d07-specialist-b9-oos.md) | [Specialist SPEC](spec/specialist-engines.md)、[WBS-5](wbs/wbs-5-specialist-engines.md)；模型 fit/OOS 與各角色 Promotion Gate 獨立驗證 |
| **D08** | [D08 CEO 卡](execution-cards/d08-ceo-admin-owner-report.md) | [AI/Mart SPEC](spec/intelligence-and-governance.md)、[Admin UI](ui/admin.md)；Validated Fact Pack/Owner/報告 |
| **已結案 D01～D06／DRL-01／Admin v2** | [歷史任務卡索引](execution-cards/README.md)＋[結案](wbs/completed-index.md) | **不重啟**歷史 gate；若新缺陷實際影響正在開發的 D07/D08，按該工項修復 |

## 2. D07-PRE/D07 禁止多套訓練流程

- **定案的唯一建模工作流程**：合格 canonical Core/受控唯讀 Parquet → **Colab 做資料清理／join、特徵、標籤、24月 rolling 模型 fit／校準／OOS** → immutable model/metric/hash → Janus Mart 驗證／登錄／正式推論。BigQuery 預設 DEFER，只有 Colab 大規模資料處理**實測 RAM/耗時/I/O 瓶頸**、成本/PIT／授權合格時才用 SQL **前置縮減**後回 Colab；**不是 BQML、Cloud Run 訓練器或第二套 Cron**。
- 既有第一個週六 10:30 Controller due 保留，但 Mart 的既有 `specialist-retrain` 含訓練程式，尚未遷移；免費 Colab 未證實 unattended。D07 前置先有界人工執行／回傳 hash，未跑標 `PENDING_MANUAL／NOT_VERIFIED`，沿用已核准 baseline，**不可假裝已自動重訓**。若要正式自動化，先取得合法 Colab 執行方式與必要帳號/IAM／付費授權。
- Quant → Risk 先行；Fundamental/Valuation 按真實季度與 source availability；Event 未有合法訓練授權與人審標籤先維持規則。先採 baseline vs challenger 同資料/OOS，成熟 labels、purge、holdout、成本／source/PIT、效能、回滾與受控 promotion；fit success ≠ quality PASS。

## 3. 最小工程閉環與合併驗收

一次指定工作包內：核對 `main` 最新 SHA／相同部署 lease／真實 runtime → 讀最少必要 code/schema/SPEC → 修改並補 tests → targeted tests/CI → 必要 migration、候選、0%/正式 dev、自然／手動 Job → Core/Mart/PG/API/Owner 資料／安全／UI readback → 若失敗修正或可逆 rollback → 保存完整 SHA、test/run ID、image digest、期限、來源與失敗原因於 [Operations](spec/operations-and-testing.md)，只在 [TODO](todo.md) 更動該工項狀態。**文件-only 僅可報 DOC_UPDATED**，無證據維持 PARTIAL/BLOCKED。

每日業務批次只走 [唯一 Controller](runbook-batch-controller-dev.md)；Cloud Scheduler、storage 保護／GCS generation／Owner 私有資料沿原治理。使用 GHCR Release → Cloud Run 候選 → 正式發佈/回滾，不因文件整理新增 scheduler、另一套 Core、model publisher、CI workflow 或免費額度未知的計費資源。

## 4. 本輪報告格式

每次回報列：`work_package`、`main/commit SHA`、變動檔案與安全界線、targeted tests／CI、deploy digest／migration、自然/手動 occurrence 和資料期間、canonical/Owner/模型品質 readback、實測 vs 缺失、rollback、`PASS/PARTIAL/NOT_VERIFIED/BLOCKED` 和下一個唯一入口。對被合併／豁免工作只能連到 archive，不用不同 WBS 重新排出第二張 TODO。
