# 2026-10-10｜Janus GHCR CI/CD 可自動完成項目收尾驗收

本紀錄僅代表 **CI/CD 非真人 OAuth 阻塞項已處理與驗證；整體 Release 仍 PARTIAL**。以 GitHub `main`、GitHub Actions artifacts 與真實 dev GCP readback 為準。沒有為了湊 PASS 修改正式 100% traffic、任何 Job image、排程、資料庫、Research image 或 IAM。

## 最新非人工已完成證據

| 項目 | 真實結果 |
|---|---|
| 同 SHA 固定 Preview 重送 | [#38009514370](https://github.com/tommylin15/janus-omniforge/actions/runs/38009514370) **SUCCESS**，artifact `ghcr-preview-publish-receipt` #11652832119：`status=PASS`、`phase=VERIFIED_FIXED_PREVIEW_IDEMPOTENT`、`source_sha=038498c70e12488f345c3ca0fbe821846ddee4cc`、`candidate=janus-api-00457-wed`、`preview_tag_mutation_attempted=false`、`canonical_traffic_write=false`、`jobs_or_scheduler_write=false`、`lease_released=true`。完全沒有重寫既有 preview tag。 |
| Preview 失敗時 rollback 及恢復失敗留鎖 | [#38009586797](https://github.com/tommylin15/janus-omniforge/actions/runs/38009586797) selective CI SUCCESS，新增 `test_fault_injection_after_preview_update_restores_previous_revision_and_sha` 與 `test_fault_injection_restore_failure_keeps_owner_lease_and_blocked_receipt`，以 mock 模擬更新後失敗，驗證 restore 前版 SHA、canonical 100% 不變及不可回復時 lease retained。**這是 mock fault-injection，不是 live 人為故障演練**；已存在的正向固定 Preview live PASS 見 [#37956325838](https://github.com/tommylin15/janus-omniforge/actions/runs/37956325838)。 |
| 標準 API traffic promotion 保護 | `ghcr_api_promote.py` 要求正常 Jobs Receipt 為 `reversible_ghcr`、`rollback_baseline_verified=true`、`rollback_available=true`、前版 source SHA 與已驗證 GHCR baseline 一致。Service traffic 切換後最多 12 次 bounded reconciled readback，必須單一 100% 指向目標、服務 Ready／RoutesReady、generation reconciled、tags 和非 traffic config 沒漂移；否則 FAIL／保留安全恢復流程。CI [#38009780327](https://github.com/tommylin15/janus-omniforge/actions/runs/38009780327) PASS。**未真的執行新 SHA 正式切流／回滾**。 |
| 未來 Jobs／API 發布可直接由 ChatGPT 提交受控 request | 既有 `ghcr-jobs-rollout-dev.yml` 的 `ops/ghcr-jobs-rollout-request.json` push gate 不變；新版 `ghcr-api-promote-dev.yml` 新增 **僅** `ops/ghcr-api-promote-request.json` 的受控 push 入口，保留 `janus-dev-runtime-writers` 與合法 Git-ref owner lease。Python API promoter 也必須讀相同 SHA、release_run、jobs_run、owner acceptance 和 GHCR 可逆基準的明確 `approved=true` request，不因手動 workflow_dispatch 就繞過。兩份已配置 rollback digests/hashes 的 **`.template.json` 均 `approved=false`、不觸發任何部署**；[包含全部新契約的 targeted CI #38010078101](https://github.com/tommylin15/janus-omniforge/actions/runs/38010078101) PASS。 |
| 0% 候選存在後舊版 GHCR rollback baseline | 初次重新檢查 [#38009753176](https://github.com/tommylin15/janus-omniforge/actions/runs/38009753176) **FAIL**：曾錯把 `latestReadyRevisionName` 當作 canonical active revision，然而 0% candidate 本來就可能是最新 Ready。程式改為驗證 **實際 100% active revision**、Ready／RoutesReady、observed generation、既有舊版 GHCR digest／Job config fingerprint。重試 [#38010139996](https://github.com/tommylin15/janus-omniforge/actions/runs/38010139996) **SUCCESS**，artifact #11652499914 `status=PASS`、`phase=VERIFIED_PUBLIC_GHCR_ROLLBACK_BASELINE`、`gcp_writes=0`、`ready_for_future_reversible_release=true`、四個 Job pins/fingerprints、Research Job 未異動及 Scheduler／lease 安全。修復只調整錯誤的驗收邏輯，沒有變更雲端資源。 |

## 舊版技術債的實際診斷（不是新版本完成狀態）

[Private Pipeline readonly #38010200797](https://github.com/tommylin15/janus-omniforge/actions/runs/38010200797) workflow **SUCCESS 但 receipt `status=BLOCKED`**，`gcp_writes=0`。其必要的六項（五 Job Ready、五 Job execution terminal、四 identity actAs、Job update/canary IAM、Cloud Build writer、Scheduler）為 PASS，但 `five_rollback_images_registry_readable=BLOCKED(ROLLBACK_IMAGE_NOT_FOUND)`，原因是受保護、未更新的 Research Job 舊 AR 映像不可讀，**不是四個 GHCR target rollback 失敗**。Private Pipeline 歷史前版 hash `4ebd16deaaff...`、現役 GHCR hash `23e6449577d7...` 不同；診斷檢查了 45 條候選設定路徑，未找到「移除單一欄位」即可重現原 hash 的情況。這只能證明「歷史完整設定 parity **NOT_VERIFIED**」，不能推論資料或 Secret 值相同／不同，亦不能偽造原始 snapshot。上一段獨立四 Job GHCR baseline 真實 PASS 可以作為後續新版回滾基準，不可反推 AR 舊版可恢復。

## 尚待真人輸入的唯一發布前置與其依賴工作

1. **真人 Google A → B → A / PnL / owner boundary**：使用者在 [固定 Preview](https://preview---janus-api-2oo7qbkd5q-uc.a.run.app/app/) 驗證候選 `038498c70e12488f345c3ca0fbe821846ddee4cc`，留下有效 SHA／revision／觀察時間的人工驗收；不得以 401/MCP metadata 自動測試冒充。
2. **待真人 Gate 解除後可自動執行**：以新的 owner 收據，建立正式 `ops/ghcr-jobs-rollout-request.json` 的可逆 GHCR→GHCR request（有原版四 image + config fingerprint；Scheduler／execution fence、兩輪 canary 及失敗恢復受保護），讀取真正的 Jobs PASS artifact 後，才建立 `ops/ghcr-api-promote-request.json`，在現有共用鎖內跑真正 API promotion／rollback rehearsal。兩個 request 模板目前刻意 `approved=false`；沒有觸發任何新 Jobs 或正式流量。
3. **不偽造的歷史例外**：舊 AR image rollback／Private Pipeline 舊完整 config parity、受保護 Research Job legacy image 與刻意誘發 live Preview 故障仍維持已記錄 `UNKNOWN/NOT_VERIFIED`；歷史不可信 snapshot 不能補寫成 PASS。舊 AR/GCS 清理不列本次 active CI/CD scope。

結論：**可在人工 OAuth 之前完成的開發、測試、真實 GCP 唯讀與 Preview 冪等驗收已完成。真實新版四 Job rollout／rollback 和 API 100% traffic promotion 因同 SHA 的真人 owner gate 尚未滿足而正確保持未執行。**
