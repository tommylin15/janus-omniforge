# D05｜產品集中發布／完整 dev 驗收 — AI 任務執行卡

更新：2026-10-15；v1 文件指示，非工程驗收。

> **本文件是獨立 AI 開發指令卡，不是第二份 TODO。** 唯一狀態、先後順序及執行授權以 [TODO](../todo.md) 為準；現況以 GitHub `main`、CI、實際 GCP dev runtime 為準。製卡不自動啟動工程／Job／部署／訓練／刪除。不得以歷史 archive 或舊 PASS 覆蓋最新結果。

**WBS 責任：**WBS 8／CI-CD

**相依與順序：**D01～D04 當次所需 code／migration／tests 就緒，不能擴權啟動 D07／D08。

**執行宣告：**只在使用者明確授權本工作包、TODO 為可執行時，依下列程序完成「分析→修改→適用測試→commit→dev 發布→真實驗收／修復」的整個工作包，不因內部 checkpoint 自行停止；外部安全／授權 blocker 保持 BLOCKED 並記錄。

## 1. 最小必讀文件與工程入口

- [cicd-v2.md](../spec/cicd-v2.md)
- [quality-and-release.md](../spec/quality-and-release.md)
- [operations-and-testing.md](../spec/operations-and-testing.md)
- [wbs-8-qa-release.md](../wbs/wbs-8-qa-release.md)
- [runbook-dev-deploy.md](../runbook-dev-deploy.md)
- [runbook-user-oauth-dev.md](../runbook-user-oauth-dev.md)

**實作入口：**`.github/workflows/` 現有 release、`ghcr-candidate-auth-boundary.yml`、Jobs rollout、fixed Preview/traffic promotion；Cloud Run API、四 Jobs、GHCR 與 Scheduler readback。

## 2. 開工前證據與前置條件

- 逐元件讀最新 main 完整 SHA、GitHub Actions Run、GHCR immutable digest、API/Preview/Jobs revision、Scheduler 與共用 lease；不跨來源 SHA 借用舊成功證據。
- 核對 D01～D04 實際需要的 gates 與受阻項，沒有取得發版所需完整證據前不得推正式流量。

## 3. 連續執行步驟與交付物

1. 整合全部本次適用程式／schema/migration/tests，完整 SHA GitHub Actions 的必要 Python/Flutter/security/build PASS 後才 push 公開 GHCR immutable digest 並驗 pull。
2. API 先 0% candidate，驗 build-id/full SHA、OAuth discovery/PKCE、User/Admin/MCP unauthorized boundary、自動可執行 authenticated owner/PnL 與同 SHA `auth_boundary_run`；不要求每版人工登入。
3. 四 Jobs 分別依 mutex/active execution/Scheduler fence/digest snapshot/受控 canary 與回復路徑更新；Jobs 不是 API 的 0% candidate。
4. 驗 D01 真實損益/重算、D02 snapshot/效能、D03四頁截圖、D04備份總控的適用證據；candidate PASS 才在共用部署鎖下更新 fixed Preview。
5. 必要 gate 全 PASS 才正式 dev traffic promotion，讀回流量與 revision/digest；持續保留 rollback 版本及 receipts。

## 4. 驗收、禁止事項與失敗恢復

**專屬 acceptance：**
- 完整 SHA 與各 CI job/run ID、migration/targeted/Release gates、GHCR public pull+digest；selective push CI 不可取代 release gate。
- API candidate、Jobs terminal+digest、auth boundary、owner isolation/positive PnL、snapshot、UI 四頁及 Scheduler/GCP live 逐項證明，不能只用 metadata/401。
- 正式流量、固定 Preview、rollback readback 與失敗恢復路徑可追溯；partial success 標 PARTIAL。

**禁止／安全 guard：**
- 無每版人工 OAuth login/consent/A→B→A；保留自動 OAuth 及必要正向 owner/資料功能驗收。
- 不建立 Cloud Build/GCS/AR 平行發布流程；build成功或單一 Job exit0 不是產品正式 PASS。

**失敗恢復：**lease/run unknown 先讀回不盲重送；candidate 失敗不換正式/Preview；正式切流後失敗沿 immutable digest、共用鎖 rollback 並確認 readback，保留上一已驗證版本。

## 5. 統一執行協定與結案格式

1. 收到使用者明確「執行本卡」後，先讀 [AGENTS](../../AGENTS.md)、[PROJECT_RULES](../PROJECT_RULES.md)、[README](../README.md)、[TODO](../todo.md)、[status](../status.md)，再最小化讀本卡直接引用的 WBS／SPEC／UI、目前實作與適用 tests。若工作涉及四頁／記帳，另需實際檢視 Final Visual PNG。不可預載全 repository 或 archive。
2. 確認本次授權、最新 `main` SHA、現有工作區 diff（有工作區才檢）、live execution/版本與既有 evidence；不覆寫他人修改，不盲重送 unknown/terminal request。於授權 WBS 內一次完成相依 code→migration→tests→docs→受控 dev 發布→live acceptance→失敗修復，不在內部 dataset／頁面 checkpoint 反覆停等。
3. Commit 前用 `/ponytail-review`；不可用時採實際 diff／連結／契約／適用測試等價 review，並明示替代，不能冒稱執行。直接使用 `main`，不自建 branch/PR；遵守完整 SHA、GHCR immutable digest、共用部署鎖／lease、Job fence、Preview／回復 runbook。
4. **完成 gate**：依適用範圍逐一列 implementation、tests/CI、schema/migration、deployed SHA/digest、真實 request/workload terminal、業務／owner／data readback、failure／rollback。無證據維持 `NOT_VERIFIED`／`PARTIAL`／`BLOCKED`；僅提交或 build PASS 不算完整交付。部分不適用須說明。
5. 僅沿既有授權 dev 成本／IAM／備份；新付費資源、重大擴權、production 首建、大量不可逆資料刪除及不可回復破壞性操作須額外授權。MFA／OAuth consent 由本人完成。secret 不進 Git/log/UI；保留 owner isolation、PIT/provenance、來源使用授權、research/canonical 分離、LLM 不持有 canonical/publication 權限。
6. **固定交接報告**：工作包與輸入/輸出完整 SHA、已修改路徑、targeted test/CI run ID、migration、API/Job digest/Preview、live workload+業務 readback、PASS/PARTIAL/BLOCKED 明細、未知／依賴、失敗恢復及下一入口。最新證據更新既有 [operations](../spec/operations-and-testing.md)／[status](../status.md)，唯一 queue／狀態只回寫 TODO，不在卡片保存短期 runtime 快照。
