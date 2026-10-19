# D07｜五角色／歷史母體／B9 品質 — AI 任務執行卡

更新：2026-10-15；v1 文件指示，非工程驗收。

> **本文件是獨立 AI 開發指令卡，不是第二份 TODO。** 唯一狀態、先後順序及執行授權以 [TODO](../todo.md) 為準；現況以 GitHub `main`、CI、實際 GCP dev runtime 為準。製卡不自動啟動工程／Job／部署／訓練／刪除。不得以歷史 archive 或舊 PASS 覆蓋最新結果。

**WBS 責任：**WBS-5-MART-SPECIALIST-ENGINES／RERUN-CACHE（B9）

**相依與順序（2026-10-19 更新）：**唯一 D07-PRE 合併兩年資料覆蓋／補收/PIT、**Colab 唯一資料整理／特徵／標籤／模型訓練／OOS 執行器**及大資料才啟動 BigQuery 前置縮減的成本/安全/回退評估；需依 [統一 AI 指令 §4](finops-ingestion-iceberg-ab-and-c-gate.md) 完成同一份 go/no-go/defer 決議後才能啟動 D07。**BigQuery 預設 DEFER；Colab 仍是訓練器，不建立 BQML／GCP training 的替代路徑；若 Colab 實跑或安全證據不足仍 PARTIAL/BLOCKED。** B7 完成不是 B9 模型品質 PASS。

**執行宣告：**只在使用者明確授權本工作包、TODO 為可執行時，依下列程序完成「分析→修改→適用測試→commit→dev 發布→真實驗收／修復」的整個工作包，不因內部 checkpoint 自行停止；外部安全／授權 blocker 保持 BLOCKED 並記錄。

## 1. 最小必讀文件與工程入口

- [specialist-engines.md](../spec/specialist-engines.md)
- [event-labeling.md](../spec/event-labeling.md)
- [intelligence-and-governance.md](../spec/intelligence-and-governance.md)
- [system-development-contract.md](../spec/system-development-contract.md)
- [wbs-5-specialist-engines.md](../wbs/wbs-5-specialist-engines.md)
- [wbs-5-intelligence-mart.md](../wbs/wbs-5-intelligence-mart.md)
- [Admin v2 四頁 UI](../ui/admin.md) 與 [Admin v2 順序決策](../decision-2026-10-17-admin-v2.md)（只供 VF-09 呈現契約；不重啟 D01～D06）

> **D07-PRE 共用評估文件**：[已整理的資料與 Colab 可行性](../colab-d07-modeling-feasibility-2026-10-19.md) 是唯一前置工作包的研究證據，尚需 FinOps、來源、樣本與權限 live readback 才可結案，不是第二個 Colab 工單。

**單一路徑實作要求：** 既有 Core→受控 Parquet 出口；Colab notebook 執行資料清理／feature & label／所有候選模型 fit／walk-forward OOS；結果以 hash/manifest 送回 Janus Mart 驗收、登錄與正式推論。原 `specialist-retrain` GCP 月度 Job 已實作 ML 訓練，是**待改造的現況**；切換前先安全保存當前服務，切換後不得在 Mart 再 fit 新模型或擅自以 GCP 取代 Colab。首週六10:30 只維持單一 Controller due，免費 Colab 先人工啟動及驗收，不宣稱無人值守。資料多時僅 BQ 前置縮減；預設直接 Colab，不另開工單。

**實作入口：**`jobs/intelligence-mart/intelligence_mart/evaluation.py`、`quant_pit.py`、`event_labeling.py`、`scripts/gcp/b9-specialist-oos-quality.py`、月度 retrain artifacts。

## 2. 開工前證據與前置條件

- 稽核全上市櫃歷史每日期當時 membership、退出股、official feature/announcement available-at、source training-use 和 immutable snapshot，缺歷史標 blocked_source_history。
- 核對舊 B9 diagnostic 的 hard-coded blockers、B7 cache/gateway 實際狀態；不重送舊 B7 request，不刪 guard 製造 PASS。

## 3. 連續執行步驟與交付物

1. 凍結完整研究協議：目的/期限、各交易日期群組 OOS folds、mature labels、purge、最後 untouched holdout、train-only 預處理、基準/成本/primary metrics；研究與 strict PIT publication 分開。
2. Quant：zero／動能／Linear 對 LightGBM／Qlib，IC/ICIR、spread、turnover及成本後回撤；Risk：CVaR/beta/drawdown 對 Markov，尾端、高低波動、月度 log score。
3. Fundamental 先修 EPS、淨利年增、財報期別/可得時點再對 LightGBM；Valuation 修 PE/PB/缺值/異常/同業再比 LightGBM/CatBoost，DCF 資料不足標 unavailable。
4. Event 先建立有 training-use 許可且真實人審 event/revision、方向、時間、reviewer/label version；分類做 chronological/event-group holdout 與 macro-F1／校準，不把分類機率當漲幅。
5. 逐角色輸出 baseline、challenger、OOS/不確定性、version/hash、typed provenance/partial/missing、dirty/reuse；正常 inference 0 生成式 LLM token；未有優勢不 promotion。
6. **VF-09 Admin 消費位置：**只對接既有 ADMIN-V2「系統設定 → AI 模型 → Specialist 品質／版本／OOS」子頁與「資料品質」的缺口 detail；復用 persisted typed artifact/API。不得重建獨立 AI 主導覽或影響 D01～D06 原 acceptance；D07 的模型品質及真實 readback gate 不變。

## 4. 驗收、禁止事項與失敗恢復

**專屬 acceptance（模型品質不變；新增的是既有 VF-09 的四頁入口映射，非新模型 gate）：**
- 資料範圍／時間／標籤/公司行動／洩漏驗證；strict_pit=false 財報比較明確標研究-only，不能誤稱嚴格PIT publication。
- 所有角色各自同樣本/期限 baseline/challenger OOS、分月/市場/環境、成本後結果與穩定性、保留負面與失敗實驗。
- GCP Mart 模型／artifact SHA/hash、persisted API、owner isolation、rollback 的 live readback；B9 逐角色判定，不以快取成功替代品質。

**禁止／安全 guard：**
- 不能虛構人審標籤、未驗來源授權；模型已 fit ≠ OOS 有效 ≠ publication 可以用。
- 不自動叫 CEO，不為研究加付費模型；BigQuery 僅大資料前置縮減後 opt-in，不在 BQML 訓練；PyIceberg 只負責既有 Core 讀取／匯出，Colab 唯一整理研究資料與訓練，禁 BQ Storage Read API。

**失敗恢復：**保留舊有效 deterministic baseline 和 frozen datasets，訓練/評估失敗不覆寫 immutable artifacts；新候選只依明確版本與獨立 gates 升級。

## 5. 統一執行協定與結案格式

1. 收到使用者明確「執行本卡」後，先讀 [AGENTS](../../AGENTS.md)、[PROJECT_RULES](../PROJECT_RULES.md)、[README](../README.md)、[TODO](../todo.md)、[status](../status.md)，再最小化讀本卡直接引用的 WBS／SPEC／UI、目前實作與適用 tests。若工作涉及四頁／記帳，另需實際檢視 Final Visual PNG。不可預載全 repository 或 archive。
2. 確認本次授權、最新 `main` SHA、現有工作區 diff（有工作區才檢）、live execution/版本與既有 evidence；不覆寫他人修改，不盲重送 unknown/terminal request。於授權 WBS 內一次完成相依 code→migration→tests→docs→受控 dev 發布→live acceptance→失敗修復，不在內部 dataset／頁面 checkpoint 反覆停等。
3. Commit 前用 `/ponytail-review`；不可用時採實際 diff／連結／契約／適用測試等價 review，並明示替代，不能冒稱執行。直接使用 `main`，不自建 branch/PR；遵守完整 SHA、GHCR immutable digest、共用部署鎖／lease、Job fence、Preview／回復 runbook。
4. **完成 gate**：依適用範圍逐一列 implementation、tests/CI、schema/migration、deployed SHA/digest、真實 request/workload terminal、業務／owner／data readback、failure／rollback。無證據維持 `NOT_VERIFIED`／`PARTIAL`／`BLOCKED`；僅提交或 build PASS 不算完整交付。部分不適用須說明。
5. 僅沿既有授權 dev 成本／IAM／備份；新付費資源、重大擴權、production 首建、大量不可逆資料刪除及不可回復破壞性操作須額外授權。MFA／OAuth consent 由本人完成。secret 不進 Git/log/UI；保留 owner isolation、PIT/provenance、來源使用授權、research/canonical 分離、LLM 不持有 canonical/publication 權限。
6. **固定交接報告**：工作包與輸入/輸出完整 SHA、已修改路徑、targeted test/CI run ID、migration、API/Job digest/Preview、live workload+業務 readback、PASS/PARTIAL/BLOCKED 明細、未知／依賴、失敗恢復及下一入口。最新證據更新既有 [operations](../spec/operations-and-testing.md)／[status](../status.md)，唯一 queue／狀態只回寫 TODO，不在卡片保存短期 runtime 快照。
