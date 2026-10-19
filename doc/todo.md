# Janus — 唯一 Active TODO

更新：2026-10-19。**只記未完成工程與驗收**；原有結案/部署流水帳完整保留在 [整編前 TODO](archive/todo-before-consolidation-2026-10-19.md)。實際狀態：GitHub main／tests／CI／GCP dev runtime；最高權限與授權依 [PROJECT_RULES](PROJECT_RULES.md)，操作依 [AI 指令](codex-execution-plan.md)。

## 1. 單一執行順序

| 優先 | 工項 | 狀態／責任入口 |
|---|---|---|
| **P0** | **D07-PRE：Colab 單一資料整理與模型訓練前置**（含原 FINOPS-C preflight） | **DESIGN_DECIDED / LIVE_PARTIAL**；[研究與工程流程](colab-d07-modeling-feasibility-2026-10-19.md)、[AI 指令 §4](execution-cards/finops-ingestion-iceberg-ab-and-c-gate.md) |
| **P1** | **D07：五角色 ML／OOS 品質及正式介接** | **PLANNED**、待前置評估有合格處置；[唯一 D07 卡](execution-cards/d07-specialist-b9-oos.md) |
| **P2** | **D08：CEO、Admin 模型管理與受控 Owner 報告** | **PLANNED**、有效 Fact Pack 後；[唯一 D08 卡](execution-cards/d08-ceo-admin-owner-report.md) |
| 非阻擋 | **OPS-OBS：自然排程／Retention 收據與 Pilot 觀察** | **OBSERVATION / NOT_VERIFIED**；既有 [Operations](spec/operations-and-testing.md)／[總控 Runbook](runbook-batch-controller-dev.md) |

**不重開**：D01～D05 `CLOSED/USER_ACCEPTED`、DRL-01 `CLOSED`、FINOPS-AB（已含 D06）`CLOSED`、背景持股/關注股補收 `PASS`、ADMIN-V2 `PASS`。原驗收範圍與缺口不改判；完整實測收據在 [原 TODO](archive/todo-before-consolidation-2026-10-19.md)、[D01～05](archive/d01-d05-relaxed-acceptance-closure-2026-10-17.md)、[DRL](archive/drl01-completed-2026-10-19.md) 和 [Operations](spec/operations-and-testing.md)。歷史工作包的卡片留作維運參考，不能變第二套 active queue。

## 2. D07-PRE｜唯一需先做的完整工作包

**已決策的單一路徑**：Janus 現有合法來源 → Stage／Canonical Iceberg Core → 限定、唯讀 frozen Parquet／hash 出口 → **Colab 統一研究資料清理／Join、feature／label、24 月 rolling 訓練與 OOS** → 不可變模型／評估成果 → Janus Mart 品質驗證、version／rollback、正式推論。**BigQuery 先 DEFER**，只有 Colab 發生**實測**大規模 Join／RAM／時間／I/O 瓶頸，確認收益、合法權限和 parity 後才可作**資料前置縮減**，不是 BQML 或另一訓練平台。日常 Ingestion、Market Screening、Owner／API 不改動。

- [ ] **DATA**：盤點最近24月逐資料集×市場×日期／月份×symbol×horizon 的實際有效 coverage、歷史股票池／退出股、來源 training-use 與時點/PIT、特徵缺失率、成熟 labels、walk-forward folds／purge/holdout。Core 一般 row TTL 365天不等於已具24月；資料缺口按有界合格補收／累積 Research Parquet／insufficient 分類，不補零也不無界補抓。
- [ ] **COLAB**：現有 B5/B6 輸入固定 hash，實際以 Colab CPU 做資料驗證／Join、Quant 零訊號／Linear／LightGBM 與 Risk 統計 baseline／OOS PoC；紀錄 seed、schema、cohort、label maturity、source provenance、CPU/RAM/耗時及模型／結果回傳 GCS/Janus 的不可變 receipts。未達品質保持 baseline。
- [ ] **RUN**：Controller 每月第一個週六 10:30 仍是唯一 due；目前舊 Mart 有訓練程式且**尚未遷至 Colab**。免費 Colab 不保證 unattended，首版先受控人工啟動、回傳、留 `PENDING_MANUAL／NOT_VERIFIED`；只有可驗證且合規的 Colab 無人值守整合並取得必要授權後才能標自動化 PASS。不允許偷偷在 GCP 再訓練冒充 Colab。
- [ ] **FINOPS/SECURITY**：量測適用的 GCS I/O、CPU/RAM、PyIceberg 唯讀出口、Colab 外部來源使用許可、資料/Owner 隔離、金鑰不外流、same-input/hash/parity、失敗回退；僅資料量瓶頸時評估 BigQuery 前置的 billed bytes、共享額度／region／IAM、價格上限及授權。未有實測就維持 DEFER。
- [ ] **GATE**：**一份**日期、SHA、真實覆蓋率、PoC、成本、安全、缺口與 GO/NO-GO/BLOCKED（BQ 可 DEFER）的評估；回寫 [原 BQ 決策](decision-2026-10-06-bigquery-analytics-over-iceberg.md)、WBS5／WBS7／本 TODO。文件提交不能當 live PASS，也不替代 D07 OOS 品質認證。

## 3. D07、D08：前置通過後才開始

**D07**（詳情只維護 [D07 卡](execution-cards/d07-specialist-b9-oos.md)）：
- [ ] Quant→Risk 優先，Valuation/Fundamental 待可比較合法歷史，Event 缺已授權人工標籤先維持 deterministic；依同樣本 baseline/ML、成熟 labels、PIT/時間外 fold、成本／regime、來源/版本與不確定性逐角色評估。
- [ ] 受控更換原 Mart 月度 fit 為 Colab-only 模型訓練；Janus Mart 僅保留接受、驗證、註冊、rollback、inference 和 Admin VF-09；不要雙執行或自動 promotion。
- [ ] 各角色 baseline 與模型品質分級獨立；訓練成功、GCS readback 或 B7 歷史 PASS 不等於 B9／真實 PIT 品質 PASS。

**D08**（詳情只維護 [D08 卡](execution-cards/d08-ceo-admin-owner-report.md)）：
- [ ] 沿用 OmniGateway/Gemini 路由驗證 auth、quota、owner boundary、失敗及回滾；有效 Fact Pack → 手動 request → validator → immutable GCS/PG → User/Owner 授權 history。LLM 不產生 canonical number、不能決定 publication。

## 4. 非阻擋觀察與決策

- **自然 Readiness Ledger**：手動/定向已結案，但 daily/weekly 自然收據仍 `NOT_VERIFIED`，沿現行 Job/Operations 觀察，不新增 DRL 第二施工工單。
- **FINOPS 實刪效果**：候選 Core 6,455／Mart 55 物件不等於實際刪除 objects／bytes，不能從 Job success 推算帳單節省；唯讀查已執行 receipts，**不為填文件再做清理**。使用者取消兩日等量 I/O 比較，狀態為 `CANCELLED_BY_USER`。
- **Dev Pilot**：持續證據見 [Pilot Ledger](pilot-operational-evidence.md)，不另建第二長期監控工單。

**需使用者做的重大選項決定**集中於 [專案管理風險 §4](project-management.md#4-重大風險及選項)。未獲付費、IAM、OAuth、無界回補或破壞性操作授權，不以文件代替；非相關的有界工作仍可進行。已接受缺口／未排程構想一律在 [Parking Lot](parking-lot.md)。
