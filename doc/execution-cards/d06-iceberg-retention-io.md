# D06｜Iceberg／受引用保護清理／I/O — AI 任務執行卡

> **2026-10-18 覆蓋決策：本卡已停止作為獨立 active 施工／驗收入口。** 所有剩餘安全引用保護、Snapshot／Orphan、Core／Mart retention 與 live readback 整併 [FINOPS-AB 唯一任務卡](finops-ingestion-iceberg-ab-and-c-gate.md)；已成功的 D06 477-object cleanup 與 audit mirror 不重跑。**兩天／長時間等量 I/O 量測取消，CANCELLED_BY_USER，不是 PASS。** 以下既有操作僅供歷史事實／引用 guard 查閱，不授權另派 D06 Job、另開 rollout 或啟動長時間量測。

更新：2026-10-15；v1 文件指示，非工程驗收。

> **本文件是獨立 AI 開發指令卡，不是第二份 TODO。** 唯一狀態、先後順序及執行授權以 [TODO](../todo.md) 為準；現況以 GitHub `main`、CI、實際 GCP dev runtime 為準。製卡不自動啟動工程／Job／部署／訓練／刪除。不得以歷史 archive 或舊 PASS 覆蓋最新結果。

**WBS 責任：**WBS 7／retention

**相依與順序：**獨立已授權 FinOps 續工，不因本次製卡重新執行任何 GCP 工作；先查既有終態。

**執行宣告：**只在使用者明確授權本工作包、TODO 為可執行時，依下列程序完成「分析→修改→適用測試→commit→dev 發布→真實驗收／修復」的整個工作包，不因內部 checkpoint 自行停止；外部安全／授權 blocker 保持 BLOCKED 並記錄。

## 1. 最小必讀文件與工程入口

- [retention-governance.md](../spec/retention-governance.md)
- [system-development-contract.md](../spec/system-development-contract.md)
- [operations-and-testing.md](../spec/operations-and-testing.md)
- [wbs-7-security-finops.md](../wbs/wbs-7-security-finops.md)
- [runbook-batch-controller-dev.md](../runbook-batch-controller-dev.md)

**實作入口：**`jobs/ingestion-core/ingestion_core/retention.py`、`tests/test_iceberg_compaction.py`、既有 `scripts/gcp/` maintenance、GCS/Iceberg/API/Jobs/Scheduler。

## 2. 開工前證據與前置條件

- 先讀 #38686125420 rollout、#38686337134 cleanup 的現時 terminal/錯誤／actual applied operations、四 Job digests 和 Scheduler，未知不重送。
- 舊 compact 9 tables 之後 Core 8162→8225 objects；74 snapshots/403 orphan 是 dry-run，沒有直接證明 bytes、objects 或 I/O 下降。

## 3. 連續執行步驟與交付物

1. 量測 ReadObject/GetObjectMetadata 根因：重複 manifest/metadata load、逐檔 HEAD、讀取復用差、小批寫入、版本交錯；先定位真實呼叫鏈。
2. 完整核對 19 份 oversized research 引用清單，以及 Core/Mart/Research/private/PG publication、模型/OOS、generation/snapshot/hash 等不可刪 protected references；任何引用未明時 fail closed。
3. 分開記錄 compact dry-run、actual compact、snapshot expiry、7天 orphan/generation-fenced clean、manifest retirement 的候選／protected／刪除量／bytes；不得因 audit-only 自動放行一般 retention。
4. 在完整保護集與授權範圍內做 bounded cleanup，保護研究、模型、私人與publication正在使用的檔；90天以上 execution manifest 當時為0，不為求刪除量修改門檻。
5. **舊兩天／長時間等量 I/O 比較已取消，不執行**。現行 FINOPS-AB 只使用短窗有界相同工作量 sample（有數值才報告，不能推算節省）；夜批仍服從總控 fence。

## 4. 驗收、禁止事項與失敗恢復

**專屬 acceptance：**
- 單元/整合驗證 snapshot/research/PG/private references、未完寫入、orphan 7天、dry-run/apply、generation fence/unknown fail-closed。
- live readback 被清理與受保護 generations、published snapshot 與所有下游資料讀取一致；actual 刪除／bytes回收具 evidence，不憑 dry-run 回報成功；短窗 I/O 適用即記，兩天 matched window 不作 gate。
- 所有新數字須標明 same-workload 方法和時間區間；未量測不得承諾節省百分比。

**禁止／安全 guard：**
- `CORE_RETENTION_FENCE_URI` 或全引用清單未妥善配置就只能 audit-only，不能把缺引用＝無引用。
- 不可逆大量真資料刪除及無可靠恢復路徑仍須人工授權；不能跨越原 7 日 orphan / generation / 90 日門檻。

**失敗恢復：**先查旧 request terminal／已刪 generations，再安全冪等修復；protected set 變不完整立即停止 apply，保留元資料及清理收據供 rollback/rebuild。

## 5. 統一執行協定與結案格式

1. 收到使用者明確「執行本卡」後，先讀 [AGENTS](../../AGENTS.md)、[PROJECT_RULES](../PROJECT_RULES.md)、[README](../README.md)、[TODO](../todo.md)、[status](../status.md)，再最小化讀本卡直接引用的 WBS／SPEC／UI、目前實作與適用 tests。若工作涉及四頁／記帳，另需實際檢視 Final Visual PNG。不可預載全 repository 或 archive。
2. 確認本次授權、最新 `main` SHA、現有工作區 diff（有工作區才檢）、live execution/版本與既有 evidence；不覆寫他人修改，不盲重送 unknown/terminal request。於授權 WBS 內一次完成相依 code→migration→tests→docs→受控 dev 發布→live acceptance→失敗修復，不在內部 dataset／頁面 checkpoint 反覆停等。
3. Commit 前用 `/ponytail-review`；不可用時採實際 diff／連結／契約／適用測試等價 review，並明示替代，不能冒稱執行。直接使用 `main`，不自建 branch/PR；遵守完整 SHA、GHCR immutable digest、共用部署鎖／lease、Job fence、Preview／回復 runbook。
4. **完成 gate**：依適用範圍逐一列 implementation、tests/CI、schema/migration、deployed SHA/digest、真實 request/workload terminal、業務／owner／data readback、failure／rollback。無證據維持 `NOT_VERIFIED`／`PARTIAL`／`BLOCKED`；僅提交或 build PASS 不算完整交付。部分不適用須說明。
5. 僅沿既有授權 dev 成本／IAM／備份；新付費資源、重大擴權、production 首建、大量不可逆資料刪除及不可回復破壞性操作須額外授權。MFA／OAuth consent 由本人完成。secret 不進 Git/log/UI；保留 owner isolation、PIT/provenance、來源使用授權、research/canonical 分離、LLM 不持有 canonical/publication 權限。
6. **固定交接報告**：工作包與輸入/輸出完整 SHA、已修改路徑、targeted test/CI run ID、migration、API/Job digest/Preview、live workload+業務 readback、PASS/PARTIAL/BLOCKED 明細、未知／依賴、失敗恢復及下一入口。最新證據更新既有 [operations](../spec/operations-and-testing.md)／[status](../status.md)，唯一 queue／狀態只回寫 TODO，不在卡片保存短期 runtime 快照。
