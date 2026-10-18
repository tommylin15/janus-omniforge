# D08｜CEO／Admin／正式 Owner 報告 — AI 任務執行卡

更新：2026-10-15；v1 文件指示，非工程驗收。

> **本文件是獨立 AI 開發指令卡，不是第二份 TODO。** 唯一狀態、先後順序及執行授權以 [TODO](../todo.md) 為準；現況以 GitHub `main`、CI、實際 GCP dev runtime 為準。製卡不自動啟動工程／Job／部署／訓練／刪除。不得以歷史 archive 或舊 PASS 覆蓋最新結果。

**WBS 責任：**WBS-5-MART-AI-PROVIDERS／CIO-SYNTHESIS、WBS-6-ADMIN-ANALYSIS-PROFILE

**相依與順序（2026-10-18 更新）：**在 D07、D08 新工程前，必須先依 [FINOPS-AB/C AI 指令](finops-ingestion-iceberg-ab-and-c-gate.md) 完成優先 A＋B、C 開工前的整體重評估及正式記錄 go/no-go/blocked 處置；D07 有效角色與 validated Fact Pack 仍是正式 publication 前置。P0-V 技術已 PASS 不代表真實 Owner 報告 PASS。

**執行宣告：**只在使用者明確授權本工作包、TODO 為可執行時，依下列程序完成「分析→修改→適用測試→commit→dev 發布→真實驗收／修復」的整個工作包，不因內部 checkpoint 自行停止；外部安全／授權 blocker 保持 BLOCKED 並記錄。

## 1. 最小必讀文件與工程入口

- [intelligence-and-governance.md](../spec/intelligence-and-governance.md)
- [specialist-engines.md](../spec/specialist-engines.md)
- [api-and-delivery.md](../spec/api-and-delivery.md)
- [system-development-contract.md](../spec/system-development-contract.md)
- [wbs-5-intelligence-mart.md](../wbs/wbs-5-intelligence-mart.md)
- [wbs-6-api-and-apps.md](../wbs/wbs-6-api-and-apps.md)
- [Admin v2 四頁 UI](../ui/admin.md) 與 [Admin v2 順序決策](../decision-2026-10-17-admin-v2.md)
- [ceo-omniagent-p0v-integration.md](../ceo-omniagent-p0v-integration.md)
- [runbook-mart-ai-providers.md](../runbook-mart-ai-providers.md)

**實作入口：**既有 `OmniGatewayGeminiProvider`、manual CEO request、Admin analysis profile/capability 與 immutable report GCS/PG；具體位置先在 main 查實作。

## 2. 開工前證據與前置條件

- 核對真實 Janus deployed endpoint、ID Token audience、allowlisted Gemini model、provider health/cooldown/quota 和 migration052/管理限額，不把過時實驗 URL 寫死。
- P0-V 合成 full Fact Pack→真實 Gemini→validator 技術 PASS 可重用，真實 Owner 五角色 Fact Pack／immutable publication/historical UI 尚需完整驗收。

## 3. 連續執行步驟與交付物

1. 只讀 validated 五角色及官方 canonical 數值，組成有來源、版本、as-of、missing/conflict/stale 的 Fact Pack；LLM 不補 canonical number、不作 publication 決策。
2. Admin models/profiles/evaluation/immutable history/rollback/capability、health/quota/cooldown/usage/audit；Production Profile 不等於 production GCP。**沿用 ADMIN-V2「系統設定 → AI 模型與 Gateway」子頁及 D07 模型品質容器，不另建獨立 AI 主選單；正式 Owner 報告與瀏覽歷史留 User UI。**
3. Owner 明確手動 request→authenticated Janus→既有 Gateway→Gemini→完整 validator→immutable GCS內容hash＋PostgreSQL索引→Owner history/UI freshness/權限讀回。
4. 報告解釋 thesis、支持/反對訊號、情境、失效條件、來源與 unknown；specialist改版只標 report stale，不默默發新LLM request。
5. 驗 timeout/cancel/5xx/unknown、冪等與安全 retry；無可用 validated inputs 不生成表面完整的報告。

## 4. 驗收、禁止事項與失敗恢復

**專屬 acceptance：**
- contract/security：provider endpoint/model/audience、owner isolation、Fact Pack source/數字比對、validator、immutable/idempotency、限制/usage/secret redaction。
- 真實新手動 Owner request 通過 Gateway/LLM/validator，GCS hash與PG索引一致、Owner history 可授權讀回；Admin v2 系統設定內的 profile/capability/rollback/limits 獨立 readback，不以 UI 搬遷取代原 gate。
- 不把合成 P0-V 技術 PASS 當成正式 Owner publication；部分角色失效有明確 blocked/partial 而非偽造整體成功。

**禁止／安全 guard：**
- 無新通用聊天、每日5個LLM role或自動下單；新付費 API／權限需另核准。
- 未知終態不盲重送、不私自 fallback 到未核准 model；LLM 不擁有 canonical 或最終 publication authority。

**失敗恢復：**Gateway錯誤先讀既有 request 終態，保留前版 immutable 報告與來源；rollback profile/model 後驗證 history/permission，不改寫已發布歷史。

## 5. 統一執行協定與結案格式

1. 收到使用者明確「執行本卡」後，先讀 [AGENTS](../../AGENTS.md)、[PROJECT_RULES](../PROJECT_RULES.md)、[README](../README.md)、[TODO](../todo.md)、[status](../status.md)，再最小化讀本卡直接引用的 WBS／SPEC／UI、目前實作與適用 tests。若工作涉及四頁／記帳，另需實際檢視 Final Visual PNG。不可預載全 repository 或 archive。
2. 確認本次授權、最新 `main` SHA、現有工作區 diff（有工作區才檢）、live execution/版本與既有 evidence；不覆寫他人修改，不盲重送 unknown/terminal request。於授權 WBS 內一次完成相依 code→migration→tests→docs→受控 dev 發布→live acceptance→失敗修復，不在內部 dataset／頁面 checkpoint 反覆停等。
3. Commit 前用 `/ponytail-review`；不可用時採實際 diff／連結／契約／適用測試等價 review，並明示替代，不能冒稱執行。直接使用 `main`，不自建 branch/PR；遵守完整 SHA、GHCR immutable digest、共用部署鎖／lease、Job fence、Preview／回復 runbook。
4. **完成 gate**：依適用範圍逐一列 implementation、tests/CI、schema/migration、deployed SHA/digest、真實 request/workload terminal、業務／owner／data readback、failure／rollback。無證據維持 `NOT_VERIFIED`／`PARTIAL`／`BLOCKED`；僅提交或 build PASS 不算完整交付。部分不適用須說明。
5. 僅沿既有授權 dev 成本／IAM／備份；新付費資源、重大擴權、production 首建、大量不可逆資料刪除及不可回復破壞性操作須額外授權。MFA／OAuth consent 由本人完成。secret 不進 Git/log/UI；保留 owner isolation、PIT/provenance、來源使用授權、research/canonical 分離、LLM 不持有 canonical/publication 權限。
6. **固定交接報告**：工作包與輸入/輸出完整 SHA、已修改路徑、targeted test/CI run ID、migration、API/Job digest/Preview、live workload+業務 readback、PASS/PARTIAL/BLOCKED 明細、未知／依賴、失敗恢復及下一入口。最新證據更新既有 [operations](../spec/operations-and-testing.md)／[status](../status.md)，唯一 queue／狀態只回寫 TODO，不在卡片保存短期 runtime 快照。
