# CI/CD 切換後資產清理盤點（2026-10-08）

來源：[GitHub Actions 唯讀盤點 #37767712869](https://github.com/tommylin15/janus-omniforge/actions/runs/37767712869)，使用既有 GCP WIF，沒有執行資源修改或刪除。

## 五類資產清理驗收

| 項目 | 清理條件 | 目前判定 |
|---|---|---|
| GCS 舊 CI/CD 檔案 | 新 GHCR Release 與 rollback PASS；確認所有 reader/writer、前次成功 marker、mutex、objects generation 都不再依賴，才按確切 prefix bounded 刪除並讀回 | BLOCKED |
| GCS 舊專用 Bucket | 證明非共用、沒有備份與業務資料、沒有任何其他 workload 讀寫，而且已可安全刪除全部內容，才能刪除 | BLOCKED |
| Artifact Registry images/tags/digests | 新 GHCR 完整替代，確認 Cloud Run Services 全部 revisions、Jobs／executions、研究與其他系統、rollback digest 均不再引用 | BLOCKED |
| Artifact Registry Repository | 每個 image/digest 均已無引用，非 DB、OmniAgent 或 life-assistant 共用，且原必要 recovery 路徑已移到 GHCR | BLOCKED |
| Cloud Run Service Revisions | 先有新 Release authenticated acceptance、100% promotion、rollback readback，最後保留建立時間最近 10 個，另保護 traffic/tag/candidate/上一成功版等必要引用；不強制刪成恰好 10 | BLOCKED |

**禁止刪除：** PostgreSQL／GCS 備份（包括其他 GCP project）、Iceberg Core／Stage／Mart／Private／Research、交易與筆記、其他應用資料。缺值視為 BLOCKED，不用推測補齊。

## GCS Bucket 唯讀分類

- 候選（尚不可刪）：`gen-lang-client-0593591102-cloudbuild-regional`。目前可見 `v2/builds`、`v2/evidence`，舊 release 仍依賴 GCS receipts／mutex，需再查其他 prefixes／versions。
- 共用性未確認（保留）：`gen-lang-client-0593591102_cloudbuild`（Cloud Build legacy default）、`run-sources-gen-lang-client-0593591102-us-central1`（Cloud Run source deploy）。
- 應用／研究（排除）：`gen-lang-client-0593591102-dev-core`、`-dev-stage`、`-dev-mart`、`-dev-private`、`-dev-research-big-move-500`（完整名稱同前綴）。

## Artifact Registry 唯讀分類

- `janusai-poc`：現役 `janus-api` 與 `janus-ingestion-core`、`janus-batch-controller`、`janus-intelligence-mart`、`janus-private-pipeline`、`janus-research-big-move-500` Jobs 都引用其中的映像 digest，**目前不能刪**。
- `omniagent`：其他系統；`cloud-run-source-deploy`：life-assistant 使用；`janus-postgres`：DB/VM 引用尚未查清。三者都不列入本次清理。

## Cloud Build 與 Revisions

- `us-central1` 五個 Trigger 均啟用，其中僅 `janus-dev-v2` 屬本次 Janus cutover 的待停用目標；`omniagent-release-v2`、`omniagent-main-v2`、`life-assistant-v2-release`、`life-assistant-v2-main` 都是其他系統，不得停。
- `janus-api` 有 **410** 個 revisions。100% 正式流量目前在 `janus-api-g53d655ccb108-config`，latest Ready 為 `janus-api-v2-097e69abdb3e81a78302`（候選），traffic 設定另有 **17** 個 tags。沒有 GHCR 全新 release 的流量／回滾驗收，不可按純時間順序刪到 10。
- 新 GitHub Actions → GHCR → Cloud Run release **尚未完成**。現階段僅唯讀 inventory PASS；部署、停用 Trigger、資料清理均未執行。

## 切換次序

1. GitHub Actions full tests → GHCR 公開 package、digest pinning → 四元件 Cloud Run Service／Jobs 真實部署與 acceptance。
2. Service 0% 候選驗收 → promotion／rollback；Jobs active execution／Scheduler fence／配置 rollback PASS。
3. 唯一正式新入口、immutable GHCR digest、WIF／mutex／前次成功 SHA／readback 均通過，再停用 `janus-dev-v2` Trigger。
4. 依上表逐項執行 GCS／AR evidence-bound dry-run → bounded apply → readback；業務資料與備份全部排除。
