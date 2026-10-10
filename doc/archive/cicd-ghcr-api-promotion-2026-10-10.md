# 2026-10-10｜Janus 新版四 Jobs 與 API 正式切流／回滾實證

本記錄為 GitHub Actions → GHCR → 既有 Cloud Run dev 真實執行，與前期文書／模擬驗收分離。僅記錄不含 Secret／owner payload 的執行收據。正式發佈對象是既有 parallel-live `dev`，非新建 `prod`。

## 來源與核准閘門

- 目標 source SHA：`038498c70e12488f345c3ca0fbe821846ddee4cc`。
- 完整 Python／Flutter gate、GHCR 不可變映像：[`#37953986962`](https://github.com/tommylin15/janus-omniforge/actions/runs/37953986962) PASS。
- 目標候選：`janus-api-00457-wed`；固定 Preview 與負向 OAuth/MCP 驗證此前已 PASS。
- 同 SHA 真人 A→B→A、private owner isolation、PnL：使用者確認 `USER_ATTESTED_NOT_MACHINE_REPLAYED`；證據 `ops/ghcr-owner-acceptance.json`，沒有在本次切流重新登入兩帳號。
- 舊版 public GHCR baseline source：`fbcc5f58a2fa31f2f36dc4c82702fb62910c7361`，唯讀實際驗證 [`#38010139996`](https://github.com/tommylin15/janus-omniforge/actions/runs/38010139996) PASS。

## 四 Jobs 可逆發佈

- [`#38012746734`](https://github.com/tommylin15/janus-omniforge/actions/runs/38012746734) workflow SUCCESS；receipt artifact `ghcr-jobs-rollout-receipt` ID `11655673546` 經實際下載查閱：`phase=PASS`、`source_sha` 正確、`rollback_mode=reversible_ghcr`、`rollback_baseline_verified=true`、`rollback_available=true`。
- 四個目標 `janus-batch-controller`、`janus-ingestion-core`、`janus-intelligence-mart`、`janus-private-pipeline` 各有兩次**不同 execution** 成功，共 8/8 live canary PASS；舊版 snapshots 含 image 與 config fingerprint。受保護 Research Job 非更新目標。
- `old_image_rollback_exercised=false`：**Jobs 舊映像真實回滾仍 NOT VERIFIED**；具備回復基準不等於已演練失敗回復。

## 正式 API 流量與回滾

- 受控 request `ops/ghcr-api-promote-request.json` 由 [commit `882cfb9d`](https://github.com/tommylin15/janus-omniforge/commit/882cfb9d62bbc3c2e7b389cafe1ed66f54f88ce0) 建立；綁定上述來源 SHA、release run、Jobs run、舊版 baseline、相同 SHA owner 收據，`rollback_mode=reversible_ghcr`，沒有套用舊 AR forward-only 豁免。
- [`#38020693214`](https://github.com/tommylin15/janus-omniforge/actions/runs/38020693214) workflow SUCCESS；receipt artifact `ghcr-api-promotion-receipt` ID `11658670617` 經實際下載查閱：`phase=PASS`、`rollback_rehearsal=PASS`、`stage=promote_candidate_final`。
- 實際三段：舊版 `janus-api-00451-cuw` → 新版 `janus-api-00457-wed` 100% → 回滾舊版 100% → 新版 100%。程序逐段確認 Route/Service Ready、generation、一個 100% active、tags 和非 traffic config 不漂移、`/health`、`/api/v1/public/health`、完整 40 字元 `/app/build-id.txt` 與未登入 private 401。最後為新版 100%。
- 舊 GHCR API image 與 source SHA 於切流前完成 public manifest/readback，並保留 `janus-api-00451-cuw`。MCP OAuth/Adapter 與固定 Preview tags 未變；沒有改 DB、schema、Secret、Job 或 Scheduler。

## 尚未驗證／獨立處理

- Jobs 舊映像**刻意真實 rollback**：NOT VERIFIED；API traffic rollback 已 PASS，二者不得混淆。
- Preview **更新後故障**的真實回復演練：NOT VERIFIED；模擬故障回歸 PASS。
- 舊 AR 時期 Private Pipeline 原完整設定 parity：NOT VERIFIED；保護性 Research Job 舊 AR image 可恢復性：BLOCKED。
- 本輪未重跑雙 owner MCP credential 正向 E2E；已使用前述 bounded 只讀／負向 metadata 與人工作業證據，**不得冒充重新驗證**。

CI/CD 的本次 API 正式切流與 traffic rollback gate **PASS**；包含其他獨立缺口的整體 CI/CD 仍 **PARTIAL**。未清理舊 Revision、AR、GCS 或資料庫資產。
