# 2026-10-12 四頁視覺發版 — 正式 runtime 回滾基準

此檔是 *不可變 checkpoint*，不是每次自動發布核准。來源：[read-only GHCR baseline inventory #38188698614](https://github.com/tommylin15/janus-omniforge/actions/runs/38188698614)；當次跑完時 `execution_fence=PASS`、`execution_blocker_count=0`、`release_lease_absent=true`，未修改 GCP。

- 目前正式 100% serving revision：`janus-api-00457-wed`，完整 source SHA `038498c70e12488f345c3ca0fbe821846ddee4cc`，來源 GHCR digest `9babe654…2e162a11`（API）。
- 四個 Job（`janus-batch-controller`、`janus-ingestion-core`、`janus-intelligence-mart`、`janus-private-pipeline`）均為相同完整 source SHA `038498c70e12488f345c3ca0fbe821846ddee4cc`，各自的 immutable public GHCR digest 與 config fingerprint 已由 runtime 讀回。必要 hash／digest 精確值同步保存於 [baseline JSON](../../ops/ghcr-active-baseline.json)。
- 前次有效完整 GHCR Release：[37953986962](https://github.com/tommylin15/janus-omniforge/actions/runs/37953986962)，來源 `038498c70e12488f345c3ca0fbe821846ddee4cc`。本輪待發布完整 Release：[38153154441](https://github.com/tommylin15/janus-omniforge/actions/runs/38153154441)，來源 `cc7f498671a1252561902f3b883eaf1cc2b8bdad`。
- 視覺版 0% candidate：`janus-api-00468-fik`；同 revision 的固定 `preview` tag 已通過 UI build-id、公開 valuation series 驗收。正式 100% 流量仍是 `038498c70e12488f345c3ca0fbe821846ddee4cc`。
- 自動 OAuth + User/Admin/MCP 負向邊界：[38188581169](https://github.com/tommylin15/janus-omniforge/actions/runs/38188581169) 成功；**不表示**實際 Owner Google login、A/B/A 或正向 PnL 已完成。
- 排程 Scheduler `ENABLED`，Git-ref release lease 不存在，Jobs terminal fence 於 snapshot 讀回為 PASS；此狀態會隨時間改變，實際 rollout 前仍需即時重新 fence，不得以本檔替代。
- 上一個 GHCR baseline 已取代：`fbcc5f58…` 是歷史回滾版本，不應作為目前這個 `cc7f4986…` candidate 的直接 rollback baseline。先前 AR 配置 parity 仍為 NOT_VERIFIED（不因 GHCR 驗證而改寫）。

下一步須依既有共用 lease、真實 Jobs reversible rollout、8 次不同 execution canary、source 與 receipt readback、再 API traffic 正式切換及 readback；不得只憑此 checkpoint 認定發布 PASS。
