# D04｜Scheduler 總控／備份交接 — AI 任務執行卡

更新：2026-10-15；v1 文件指示，非工程驗收。

> **本文件是獨立 AI 開發指令卡，不是第二份 TODO。** 唯一狀態、先後順序及執行授權以 [TODO](../todo.md) 為準；現況以 GitHub `main`、CI、實際 GCP dev runtime 為準。製卡不自動啟動工程／Job／部署／訓練／刪除。不得以歷史 archive 或舊 PASS 覆蓋最新結果。

**WBS 責任：**WBS 3／7

**相依與順序：**與產品前三項平行整合；備份安全交接獨立 readback；經 D05 受控發布。

**執行宣告：**只在使用者明確授權本工作包、TODO 為可執行時，依下列程序完成「分析→修改→適用測試→commit→dev 發布→真實驗收／修復」的整個工作包，不因內部 checkpoint 自行停止；外部安全／授權 blocker 保持 BLOCKED 並記錄。

## 1. 最小必讀文件與工程入口

- [batch-inventory-2026-10-13.md](../archive/batch-inventory-2026-10-13.md)
- [full-market-batch-policy.md](../spec/full-market-batch-policy.md)
- [retention-governance.md](../spec/retention-governance.md)
- [wbs-3-ingestion-admin.md](../wbs/wbs-3-ingestion-admin.md)
- [wbs-7-security-finops.md](../wbs/wbs-7-security-finops.md)
- [runbook-batch-controller-dev.md](../runbook-batch-controller-dev.md)

**實作入口：**`jobs/ingestion-core/ingestion_core/batch_controller.py`、Cloud Scheduler/Jobs；目前 VM backup executor、原 timer、GCS 代數與 isolated PostgreSQL restore 程序。

## 2. 開工前證據與前置條件

- 讀回 live Scheduler、Actions schedule、原 VM timer、existing execution IDs 與權限，不根據文件快照假定新總控已啟用。
- 核對現存備份 generation／檔案大小／可還原性、三代政策、VM e2-micro/30GB guard；不可新增付費資源。

## 3. 連續執行步驟與交付物

1. 業務排程只由 Cloud Scheduler 總控，Actions 只留已核准備份清理；明確排除重複 cron／重入或共用 lease 競態。
2. 驗 core-ready／dirty owner／snapshot／research 前瞻保留、dispatch lag與 bounded retry，unknown run先查 terminal，不重送舊 request。
3. 完成 controller→新 VM executor→實際 bounded backup→隔離 DB restore→資料完整性/權限→備份輪替→交接 readback。
4. 新 backup/isolated restore PASS 後才停原 timer，再讀回只有一個有效備份執行入口與三代輪替。

## 4. 驗收、禁止事項與失敗恢復

**專屬 acceptance：**
- controller 重入／重複 Scheduler trigger／lease/unknown、備份 checksum、restore/schema/owner access 與錯誤注入 targeted tests。
- live Scheduler／Jobs／Actions／timer 設定與 execution 讀回；真實備份 generation→隔離 PG restore→關鍵資料一致性及最小角色權限、三代政策的稽核證據。
- 只成功備份上傳不算交接 PASS；原 timer 停用必須有新路徑恢復後正常執行的證據。

**禁止／安全 guard：**
- 不可先停原 timer 再測新方案，不刪唯一可回復備份或擴權／增加付費磁碟。
- D06 引用保護與業務資料清理不能被 D04 排程重組順便解除。

**失敗恢復：**新 executor 或 restore 失敗，舊 timer 保持 active；若切換後出錯用已驗證舊設定恢復並防雙重執行；確認 backup generation 及可還原性再結案。

## 5. 統一執行協定與結案格式

1. 收到使用者明確「執行本卡」後，先讀 [AGENTS](../../AGENTS.md)、[PROJECT_RULES](../PROJECT_RULES.md)、[README](../README.md)、[TODO](../todo.md)、[status](../status.md)，再最小化讀本卡直接引用的 WBS／SPEC／UI、目前實作與適用 tests。若工作涉及四頁／記帳，另需實際檢視 Final Visual PNG。不可預載全 repository 或 archive。
2. 確認本次授權、最新 `main` SHA、現有工作區 diff（有工作區才檢）、live execution/版本與既有 evidence；不覆寫他人修改，不盲重送 unknown/terminal request。於授權 WBS 內一次完成相依 code→migration→tests→docs→受控 dev 發布→live acceptance→失敗修復，不在內部 dataset／頁面 checkpoint 反覆停等。
3. Commit 前用 `/ponytail-review`；不可用時採實際 diff／連結／契約／適用測試等價 review，並明示替代，不能冒稱執行。直接使用 `main`，不自建 branch/PR；遵守完整 SHA、GHCR immutable digest、共用部署鎖／lease、Job fence、Preview／回復 runbook。
4. **完成 gate**：依適用範圍逐一列 implementation、tests/CI、schema/migration、deployed SHA/digest、真實 request/workload terminal、業務／owner／data readback、failure／rollback。無證據維持 `NOT_VERIFIED`／`PARTIAL`／`BLOCKED`；僅提交或 build PASS 不算完整交付。部分不適用須說明。
5. 僅沿既有授權 dev 成本／IAM／備份；新付費資源、重大擴權、production 首建、大量不可逆資料刪除及不可回復破壞性操作須額外授權。MFA／OAuth consent 由本人完成。secret 不進 Git/log/UI；保留 owner isolation、PIT/provenance、來源使用授權、research/canonical 分離、LLM 不持有 canonical/publication 權限。
6. **固定交接報告**：工作包與輸入/輸出完整 SHA、已修改路徑、targeted test/CI run ID、migration、API/Job digest/Preview、live workload+業務 readback、PASS/PARTIAL/BLOCKED 明細、未知／依賴、失敗恢復及下一入口。最新證據更新既有 [operations](../spec/operations-and-testing.md)／[status](../status.md)，唯一 queue／狀態只回寫 TODO，不在卡片保存短期 runtime 快照。
