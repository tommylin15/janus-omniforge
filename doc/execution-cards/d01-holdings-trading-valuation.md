# D01｜持股交易／完整估值 — AI 任務執行卡

更新：2026-10-15；v1 文件指示，非工程驗收。

> **本文件是獨立 AI 開發指令卡，不是第二份 TODO。** 唯一狀態、先後順序及執行授權以 [TODO](../todo.md) 為準；現況以 GitHub `main`、CI、實際 GCP dev runtime 為準。製卡不自動啟動工程／Job／部署／訓練／刪除。不得以歷史 archive 或舊 PASS 覆蓋最新結果。

**WBS 責任：**WBS 4J／6（必要時 4R）

**相依與順序：**產品第1項；為 D02 快照、D03 持股卡提供可信資料；與 D05 合併發布。

**執行宣告：**只在使用者明確授權本工作包、TODO 為可執行時，依下列程序完成「分析→修改→適用測試→commit→dev 發布→真實驗收／修復」的整個工作包，不因內部 checkpoint 自行停止；外部安全／授權 blocker 保持 BLOCKED 並記錄。

## 1. 最小必讀文件與工程入口

- [holdings-first.md](../spec/holdings-first.md)
- [quotes-and-broker-profile.md](../spec/quotes-and-broker-profile.md)
- [system-development-contract.md](../spec/system-development-contract.md)
- [wbs-4j-personal-workspace.md](../wbs/wbs-4j-personal-workspace.md)
- [wbs-6-api-and-apps.md](../wbs/wbs-6-api-and-apps.md)
- [user-app.md](../ui/user-app.md)

**實作入口：**`services/api/app.py`、`repository.py`、`trade_calculation.py`、`trade_fees.py`、`private_recalc_queue.py`、`private_pipeline.py`；`apps/user_app/lib/final_ledger.dart`；依 main 查實際 API/router/tests。

## 2. 開工前證據與前置條件

- 讀回目前 API／Private Worker 的 SHA、digest、migration、queue terminal 和既有 Owner checkpoint；00719B 身分／估值與 88 筆費稅更正 PASS 不重送。
- 核對 00697B 及其他持股 TWSE／TPEx／ETF 報價、as-of、PIT、last-success；Owner 持股不因研究母體或今日有效名冊限制而消失。

## 3. 連續執行步驟與交付物

1. 修好合法來源→quote resolver→持股估值：缺一檔價保留所有已知股數成本，affected/aggregate coverage 清楚揭露，缺價不能當0。
2. 交易前唯讀試算與正式保存共用 `MOVING_AVERAGE`、`Decimal`、券商折扣、官方商品費稅與規則版本；顯示預估淨收付、剩餘持股及預估已實現損益。
3. 完成買入、加減碼、部分／全部賣出、零股、股利、更正、作廢、歷史補登、超賣拒絕、競態／版本／冪等；未知入帳先查同 request/key，不盲重送。
4. 重算按鈕→authenticated enqueue→Private Worker terminal SUCCEEDED／exact ledger checkpoint→PnL readback／queue idle／cleanup；股數成本即時呈現與行情刷新、正式重算分離。
5. 持股 UI 將累計未實現損益／報酬放一列，當日行情漲跌放另一列；單一依賴失效不讓全頁永久轉圈。

## 4. 驗收、禁止事項與失敗恢復

**專屬 acceptance：**
- 單元與整合覆蓋稅費、Decimal、移動平均、買賣／零股／股利／更正、競態、冪等、oversell、owner隔離、單檔缺價與過期資料。
- 真實 dev Owner API／Flutter 驗股數成本、各商品價格、完整估值 coverage、試算／保存版次、重算終態+checkpoint與正式 PnL。不能用 00719B 單檔 PASS 推定全部持股。
- 保存成功但 PnL 尚待重算、重算失敗、未知終態須有明確 UI 狀態與有界重試。

**禁止／安全 guard：**
- 不寫 MCP ledger、不為驗收新增個人假交易，不重播已更正的 88 筆。
- 不把無報價商品當成0或以未核准來源補齊；交易被寫入與正式損益結案分別判定。

**失敗恢復：**重試前查 ledger version／同冪等 key 和 queue terminal；不明結果維持 unknown，按已驗證 digest 與部署鎖回復；保留真實交易的 append-only provenance。

## 5. 統一執行協定與結案格式

1. 收到使用者明確「執行本卡」後，先讀 [AGENTS](../../AGENTS.md)、[PROJECT_RULES](../PROJECT_RULES.md)、[README](../README.md)、[TODO](../todo.md)、[status](../status.md)，再最小化讀本卡直接引用的 WBS／SPEC／UI、目前實作與適用 tests。若工作涉及四頁／記帳，另需實際檢視 Final Visual PNG。不可預載全 repository 或 archive。
2. 確認本次授權、最新 `main` SHA、現有工作區 diff（有工作區才檢）、live execution/版本與既有 evidence；不覆寫他人修改，不盲重送 unknown/terminal request。於授權 WBS 內一次完成相依 code→migration→tests→docs→受控 dev 發布→live acceptance→失敗修復，不在內部 dataset／頁面 checkpoint 反覆停等。
3. Commit 前用 `/ponytail-review`；不可用時採實際 diff／連結／契約／適用測試等價 review，並明示替代，不能冒稱執行。直接使用 `main`，不自建 branch/PR；遵守完整 SHA、GHCR immutable digest、共用部署鎖／lease、Job fence、Preview／回復 runbook。
4. **完成 gate**：依適用範圍逐一列 implementation、tests/CI、schema/migration、deployed SHA/digest、真實 request/workload terminal、業務／owner／data readback、failure／rollback。無證據維持 `NOT_VERIFIED`／`PARTIAL`／`BLOCKED`；僅提交或 build PASS 不算完整交付。部分不適用須說明。
5. 僅沿既有授權 dev 成本／IAM／備份；新付費資源、重大擴權、production 首建、大量不可逆資料刪除及不可回復破壞性操作須額外授權。MFA／OAuth consent 由本人完成。secret 不進 Git/log/UI；保留 owner isolation、PIT/provenance、來源使用授權、research/canonical 分離、LLM 不持有 canonical/publication 權限。
6. **固定交接報告**：工作包與輸入/輸出完整 SHA、已修改路徑、targeted test/CI run ID、migration、API/Job digest/Preview、live workload+業務 readback、PASS/PARTIAL/BLOCKED 明細、未知／依賴、失敗恢復及下一入口。最新證據更新既有 [operations](../spec/operations-and-testing.md)／[status](../status.md)，唯一 queue／狀態只回寫 TODO，不在卡片保存短期 runtime 快照。
