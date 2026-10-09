# Janus GHCR → GHCR 回復基準驗收 — 2026-10-09（Asia/Taipei）

結論：**目前現役 GHCR immutable rollback baseline 已 live PASS；未來新來源的實際 reverse-update／traffic rollback rehearsal 尚未執行，因此整體 CI/CD 仍 PARTIAL。**

## Current rollback baseline（無新增 GCP 資源／資產刪除）

- 既有完整 GHCR Release source：`fbcc5f58a2fa31f2f36dc4c82702fb62910c7361`；[Full release #37876247130](https://github.com/tommylin15/janus-omniforge/actions/runs/37876247130) SUCCESS。
- [首次唯讀 live #37953767150](https://github.com/tommylin15/janus-omniforge/actions/runs/37953767150) SUCCESS，artifact `ghcr-reversible-baseline-receipt` 的 `phase=VERIFIED_PUBLIC_GHCR_ROLLBACK_BASELINE`、`status=PASS`、`gcp_writes=0`。
- [強化 config fingerprints 後重新 live #37954237695](https://github.com/tommylin15/janus-omniforge/actions/runs/37954237695) SUCCESS，receipt #11627007764 再次 `status=PASS`。Service Ready／latestReady、現役 Revision SHA/digest、兩個 health endpoint、build-id SHA、401 boundary、MCP OAuth／read-only probes、四 Jobs 公開 pinned GHCR manifest 及 SHA label、四組 **runtime config fingerprint**、唯一 Scheduler `ENABLED`、無 active executions、Research image 保護、部署鎖 ABSENT 均實際檢查通過。沒有修改正式流量、Job、Scheduler、DB 或資料。
- API Revision `janus-api-00451-cuw`、100% GHCR source，image digest `sha256:a2c263b3ed8729e6677a47fc1084b51a1833721872045b4d4b78035e778f43cf`。四 Jobs 的 source SHA 和 immutable images 由 `ops/ghcr-reversible-baseline-request.json` 與 readback receipt 共同保存。
- 在 `scripts/gcp/ghcr_jobs_rollout.py` 新增 `reversible_ghcr` 發布模式；**後續 release 必須**提供前版完整 source SHA、四 Job 固定 image digest、相符的 baseline config SHA-256 fingerprints，且匿名 GHCR registry 仍可讀，才允許暫停 Scheduler／執行 update。失敗 recovery 保留原有 reverse-order update、配置/hash readback 和 Scheduler fence；不重用舊 AR forward-only waiver。這些 code/contracts 不能替代下一次實際 rollout 或 rollback readback。
- `ghcr_api_promote.py` 也新增「切流前上一個已上線 Revision 的 GHCR digest／Ready／匿名 registry／source SHA」要求，避免把無法拉取的舊 AR 當成可恢復版本。後續新版需提供當次有效的 owner authenticated acceptance，否則仍阻擋升流量。
- 單一安全例外保留：2026-10-09 由使用者批准的**舊 AR rollback 豁免僅適用 `fbcc5f58...` 當次**。此前 `janus-private-pipeline` 舊 AR 完整 runtime config parity **NOT_VERIFIED**，不能由本版的完整 config fingerprint 反推出歷史差異。歷史 AR rollback **NOT PERFORMED**；目前 baseline rollback readiness **PASS** 不等於 future rollback exercise PASS。

## 後續必要 live gate

1. [ ] 最新完整 GHCR Release 的公開 digest、0% API candidate、基於**相同來源 SHA**的 owner OAuth／PnL／MCP、四 Job GHCR 更新和 8 次不同 canary。
2. [ ] 新 GHCR source 走 `rollback_mode=reversible_ghcr`，真的驗證先前 GHCR image/config 復原；不使用 `user_authorized_forward_only` 舊特例。
3. [ ] API 由 GHCR baseline 進行實際 traffic rollback drill，再完成新源 SHA 正式 100% promotion；持續觀測 service/Revision Ready、其他 tags、lease 清理。
4. [ ] 重複發布 contract、固定 preview tag 自動更新／失敗恢復（如列 active scope），持續保存 Actions receipts；不能將本次唯讀成功寫為 full release 成功。

參考：[目前狀態](../status.md)、[CI/CD TODO](../todo.md)、[GHCR Service route recovery](cicd-ghcr-live-route-finalization-2026-10-09.md)。
