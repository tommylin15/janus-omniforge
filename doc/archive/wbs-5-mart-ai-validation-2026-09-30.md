# WBS-5-MART-AI-VALIDATION 驗收紀錄（2026-09-30）

判定：**完成，Gate 4 通過**。這是 provider-neutral output validation 完成，尚未啟用
Codex CLI／AI provider、CIO synthesis 或自然每日角色 workload。

## 實作與邊界

- `ai_validation.py` 的 `role-validator-v1` 使用可信 immutable report，重新驗證五角色
  schema／prompt／guardrail、execution／scope／as-of／Core snapshot／feature／governance、
  Fact Pack／evidence hashes、provenance 集合及角色可引用 IDs。
- 沿用原 evidence validator 的 URL、來源授權、單位、duplicate／conflict、dataset
  freshness 檢查，另檢查 publication／availability／observation／record time fence。
- Top-level evidence IDs 必須等於所有 Claim 引用聯集；missing_information 須逐項列出
  missing fact keys。自由數字／補值／計算被拒絕；只有逐字 `fact_key=value` 引用可接受。
  不自行換算單位或 rounding，coverage 不宣稱任意自然語言推論的 entailment 已證明。
- 保存獨立、create-only validation artifact：source interpretation hash、validator version、
  lineage、sorted error codes、validated／blocked 與 analysis outcome；不修改來源 artifact。
  Invalid contract 的拒絕結果使用可信 report audit context，不複製遭篡改 prompt／guardrail。
- 五個不同角色、同 execution／scope／profile 才可 complete validation；缺角色／blocked／
  duplicate role／跨 execution 為 partial。已驗證 insufficient_data 仍不是完整研究成功。
- Validator 沒有 publication authority；既有 deterministic facts、mart.v1 與 publication
  path 不變。CIO qualification／synthesis、CLI auth／worker、自然 daily workload 尚未實作。
  呼叫者須使用可信 validator 保存邊界，content hash 不替代授權。

## 本機與部署

- Mart AI contract／pipeline／runtime targeted tests：78 passed；contract registry：4 passed。
  額外五角色完整 fixture、缺角色／重複角色拒絕 smoke check 通過；僅為 fixtures。
- 驗收腳本 Store smoke check 保存／讀回 15 份結果通過；provider_calls=0、
  publication_writes=0、five_role_success=false。
- `git diff --check` 通過；兩次實作 commit 前 `/ponytail-review` 均為 Lean already. Ship.
- 初次測試遇到 tests import path、report scope 位於 nested scope 與 enriched Lineage 的
  fixture 重建差異，已修正；stale test 改為依既有 dataset freshness 語意注入整組過期資料。
- 實作 commit `59fff8b0d3d8c253f1662e9540ae48f51387714b`，安全覆核修正
  `12468e694bd5714daf435741b95b214d590d9211`。
- 初版 [dev workflow 36694014376](https://github.com/tommylin15/janus-omniforge/actions/runs/36694014376)
  success。最終版 [dev workflow 36694449235](https://github.com/tommylin15/janus-omniforge/actions/runs/36694449235)
  test-mart 78 passed、deploy／verify success；不取消既有 deployment chain。
  其他 runtime components skipped，沒有額外部署。

## GCP dev bounded acceptance

最終 `janus-intelligence-mart` Ready=True，JANUS_GIT_SHA 匹配 `12468e694bd5714daf435741b95b214d590d9211`；
image digest `sha256:68549911768ae6e2345e351cf158237c27d934dc36e0924ca14441bea41cdb43`。
Bounded execution `janus-intelligence-mart-7b6nd` Completed=True、succeededCount=1，
completion `2026-09-30T09:17:45.642981Z`（台北 17:17:45）。

真實 pinned report 上的五份 insufficient-data fixtures 均 validated；十份故障注入
（每角色各一份錯誤數字／不存在 evidence ID，以及跨 as-of context）均 blocked。
保存 15 份 source interpretations、15 份 validation results 與 evidence；同 artifact
重複保存回相同 reference。五份 validated 仍為 insufficient_data，five_role_success=false。

Evidence URI：`gs://gen-lang-client-0593591102-dev-mart/acceptance/ai-validation/role-validator-v1/89b5a9df12b65ed13d6d63bd5ce9801fe3f08dbf3f9b870b4567570aa277cb96/evidence.json`。
Raw-byte evidence hash：`sha256:5d25184e4e0ebfa7c0af3dc5ab3c3afa389eb40a7473ec0e5e87c7ea01f95da5`。
獨立 gcloud GCS 唯讀驗證 30 個 objects 的 raw-byte／content hashes、角色／Core snapshot
lineage、source hash 引用、5 validated／10 blocked 與 publication_authority=false 全數通過。
原 manifest 未補入 AI contract，pinned metadata raw-byte hash 仍匹配原 reference，
Iceberg snapshot 仍是 `1930062826805744877`；provider_calls=0、publication_writes=0。

Pinned source：`gs://gen-lang-client-0593591102-dev-mart/executions/4a429cb4-68ea-4506-985d-12bb817ea775/manifest.json`；
symbol 2330，analysis_as_of 2026-09-24，Core snapshot
`sha256:7d2ced21d2dc5717f0e33037474c4417e432381288ed9fe53f2e535cab75bfa3`，
scoped Iceberg snapshot `1930062826805744877`，deterministic hash
`sha256:89b5a9df12b65ed13d6d63bd5ce9801fe3f08dbf3f9b870b4567570aa277cb96`。

使用已部署的既有 dev Job，execution-only args override：
`python,scripts/gcp/verify_mart_ai_contract.py,--manifest-uri,<上述 gs:// URI>,--validate-roles`，
`ENVIRONMENT=dev`，1 task、180s timeout；不改 persistent command／env，不新增資源。
驗收輸出是固定的故障注入／insufficient-data fixtures，真實部分是 pinned Fact Packs、
GCP runtime、create-only 保存與 artifact readback；沒有呼叫 AI analyst／provider。

## 後續

本 WBS 的 provider-neutral validation 不代表 GCP Codex CLI 已可自主執行，或五角色開始
每日工作。Gate 5／6、CIO、rerun/cache、Admin profile 依各自 WBS 與模型閘門執行。
