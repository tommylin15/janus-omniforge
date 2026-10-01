# Janus Mart v1 → future v2 相容策略

更新：2026-10-01
狀態：`WBS-5-MART-V2-COMPAT` implementation contract

## 現行 canonical 邊界

- `mart.v1.json` / `MartScopedAnalysisV1` 繼續是 deterministic Mart canonical contract；本 WBS 不建立 `mart.v2`，也不修改既有 v1 report payload、Iceberg table identifier 或 publication lifecycle。
- `mart_ai.v1.json` 繼續是五角色／CIO structured-output contract；既有 interpretation artifact 內保存的 output contract hash 不因本 WBS 改寫。
- 新增 `mart_compat.v1.json` 與 `intelligence_mart.compat` 作為 **additive sidecar**。Sidecar 只保存 immutable artifact references，並以 `execution_id`、`analysis_as_of`、`core_snapshot_id`、scope 與 deterministic hash 綁回原 v1 report。
- validation reference 必須指向同角色 interpretation artifact hash；duplicate role/kind、cross-role source hash、base identity mismatch 或 sidecar hash mismatch fail closed。
- compat sidecar 明定 `publication_authority=false`；它不能改寫 canonical facts、deterministic outcome 或 publication status。

## Consumer 相容原則

舊 consumer 可完全不知道 `mart_compat.v1`：仍只讀原本 `mart.v1` report / publication index。需要 AI artifact 的新 consumer 先讀 v1 canonical report，再選擇性讀 sidecar；sidecar 不嵌入、不回填、不修改舊 report。因此 migration 前不得把 sidecar availability 誤當成 `mart.v2` readiness，也不得要求舊 consumer 升版。

## future `mart.v2` migration gate

只有在 provider/CIO/consumer 實作已證明需要整合的新 canonical surface，且另有明確 WBS／schema migration／rollback plan 時，才可建立 `mart.v2`。預定順序：

1. **v1 + sidecar（目前）**：建立 additive contract，保持所有 v1 reader/write path 不變。
2. **dual-read shadow**：新 consumer 可同時讀 v1 + sidecar，保存版本與 hash；舊 consumer 不變。
3. **v2 candidate**：另建 versioned schema／table，不原地改寫 v1；以相同 pinned inputs 比對 deterministic facts、PIT/provenance、analysis outcome 與 artifact lineage。
4. **consumer opt-in**：逐一驗證 API、Admin、User、MCP、evaluation／export consumer；partial success 不視為全體 migration。
5. **cutover decision**：只有全部 acceptance 與 rollback evidence 成立，才更新 canonical publication target。v1 保留可讀 rollback window；不得因 v2 candidate 存在自動刪除 v1。

任何階段若 v2 candidate 與 v1 deterministic facts、PIT／future-leakage fence、provenance 或 publication governance 不一致，維持 v1 canonical 並將 migration 標為 blocked/partial。

## Bounded dev 驗收

沿用 `scripts/gcp/verify_mart_ai_contract.py --manifest-uri <既有 dev manifest URI> --verify-compat`，
在既有 dev Mart Job 執行；必須先有同一 pinned report 的 AI validation acceptance evidence。
讀回既有 interpretation／validation objects，核對 raw-byte／content hash，重跑 validator，
保存並讀回五角色共十個 references 的 create-only sidecar；原 manifest／metadata／report 保持不變。
真實驗收部分是 GCP runtime、pinned report、immutable storage 與 lineage；角色輸出沿用 validation fixtures，
provider_calls／publication_writes 均為零，不代表 provider、CIO 或自然每日五角色運作完成。
