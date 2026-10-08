# Dev 部署與 PostgreSQL Migration Runbook

本文件只記錄**目前可重複執行的 dev 操作程序**。一次性的 build ID、revision、image digest、歷史 split checkpoint 與舊 topology 不固定在本 runbook；需要目前實際狀態時，先查 GitHub `main`、GCP runtime，再對照 [`spec/operations-and-testing.md`](spec/operations-and-testing.md)。

目前 `dev` 是 Janus 個人使用階段的真實平行上線環境。部署、migration、Secret rotation、Job execution 都可能影響真實個人資料；執行前必須遵守 [`PROJECT_RULES.md`](PROJECT_RULES.md) 的費用、安全與不可逆操作授權規則。

## 1. 固定環境與工具

目前 GCP dev 使用：

```powershell
$gcloud = "C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
$project = "gen-lang-client-0593591102"
$region = "us-central1"
$zone = "us-central1-a"
```

Windows PowerShell 優先使用 `gcloud.cmd`；不要為解決 shell 問題放寬 ExecutionPolicy。

執行前至少確認：

- GitHub ref 是預期的 `main` commit；
- 目標是既有 dev resource，而不是新建 production／付費 topology；
- 需要的人工費用／安全授權已取得；
- 目前 Cloud Run／Job image、Secret references、revision／execution 狀態已先唯讀查證。

## 2. Dev bootstrap

目前 bootstrap entrypoint 為 `scripts/gcp/provision-dev.sh`。它應只用於既有 dev topology，並由腳本 guard 檢查 PostgreSQL Free Tier shape。

```powershell
$env:GCP_PROJECT_ID = $project
$env:GCP_REGION = $region
$env:GCP_ZONE = $zone
$env:GITHUB_REPOSITORY = "tommylin15/janus-omniforge"
$env:GCP_CI_SERVICE_ACCOUNT = "janus-ci@${project}.iam.gserviceaccount.com"
$env:ALLOW_DEV_PROVISION = "true"
& "C:\Program Files\Git\bin\bash.exe" scripts/gcp/provision-dev.sh
```

不要把 bootstrap 當成一般部署指令；若 runtime 已存在，只執行本次工作真正需要的最小操作。

## 3. Dev deployment

### 3.1 正式目標：GitHub Actions + 公開 GHCR + Cloud Run

政策見 [PROJECT_RULES §12](PROJECT_RULES.md#12-cirelease-分離2026-10-08-正式目標政策實作遷移中)，完整 acceptance 依 [CI/CD 契約](spec/cicd-v2.md)。**以下是遷移後的操作順序與語意，不是宣稱現有 `main` 已具備此 Release workflow。**

1. 核對 `main` exact SHA／工作包 ID／上次成功發布 SHA、目前 service traffic／Job images 與 active executions。main Push selective CI 僅作回饋；在 Actions 的明確 Release run 跑**完整**適用測試（Python、Flutter、schema／migration、安全／Docker）。
2. 測試全 PASS 後由 Actions 在 GitHub runner build／publish 到 GHCR，讀回 `ghcr.io/...@sha256:...`；驗證 package **public**、匿名 pull 與 digest。任何私有 package、registry 不可達或 fallback 到 Artifact Registry 的需求一律 fail closed，不偷偷改用 Cloud Build、GCS、Artifact Registry。
3. 使用 GitHub Actions OIDC／GCP WIF 最小權限，部署既有 Cloud Run Service 的 **0% 正常流量 candidate**，指定 digest 與候選 tag URL，記錄部署前流量／revision／Job 設定。PowerShell 形式的 **概念範例，勿在 Release workflow 實作並完成前直接當發布指令使用**：

   ```powershell
   $imageRef = "ghcr.io/OWNER/IMAGE@sha256:IMMUTABLE_DIGEST"
   & $gcloud run deploy SERVICE_NAME --project=$project --region=$region --image=$imageRef --no-traffic --tag=CANDIDATE_TAG
   ```

4. 先 readback 0%／revision／digest／Ready；對 candidate tag URL 做 health、未登入拒絕、authenticated owner／OAuth／PnL／MCP 與本次必要真實驗收。成功才指定**已驗證 revision**切流量（不使用未知 `LATEST`），再次 readback。失敗恢復先前 revision／traffic，保留 rollback evidence。
5. **Jobs 不具備 no-traffic candidate**：ingestion／Mart／private pipeline 分別檢查 active execution、Scheduler、image／env／Secret refs snapshot、必要 migration、安全 canary，再以固定 digest 更新既有 Job。不可在 API candidate 階段預先修改排程使用的 Job image；rollback 必須可恢復原設定。無可靠跨 run mutex／durable state 時 Release 不可正式啟用。
6. GitHub Actions run／step logs、job summary 及必要的保護性 artifacts 保存 SHA、full-test gates、GHCR digest、candidate revision／URL（不含 token）、驗收、baseline、流量切換、Job readback 與回滾。**新流程不觸發 Cloud Build、也不主動寫入 GCS／Artifact Registry；不新增常駐 VM。**

### 3.2 既有 Cloud Build：限唯讀診斷，不是新發布步驟

WIF 診斷身分具備指定 project 的 `cloudbuild.builds.get`／必要時 `cloudbuild.builds.list` 與 `logging.logEntries.list` 唯讀權限時，Actions 可按 **Build ID** 查 `SUCCESS`、`FAILURE`、失敗 steps／exit code（如有）及 bounded／mask 後的錯誤摘要。只把經 allowlist 與遮罩的結果寫進 Actions log／summary，再由 ChatGPT 讀相同 run；permission denied、缺 logs 時一律 `UNKNOWN`，不得把未讀到的 log 當 PASS。

**此查詢不允許呼叫 `gcloud builds submit`、`gcloud builds triggers run`、修改 Trigger 或寫入 GCS／Artifact Registry。** 舊 `cloudbuild-v2.yaml`、`janus-dev-v2`、GCS receipts／mutex 與舊 `deploy-dev.yml` recovery 目前仍屬**待遷移的實際 implementation**；僅盤點／保留，不得因新文件就視為停用。不要用先前 `_MODE=shadow/candidate/release` Trigger 命令作為新的正式發布程序。

### 3.3 故障恢復與 digest 引用

每個 Release 使用 SHA/digest fence、bounded timeout／retry、唯一部署 lease、服務／Job baseline snapshot；遇到 API candidate FAIL／Job ambiguous execution／Scheduler readback 缺失時停止 promotion，按原 revision／traffic／Job 設定恢復後 readback。若原 run 未終止或未確認 execution 結果，不能重送 Job，也不能搶鎖。

舊 image inventory／cleanup 僅按仍存在的歷史 Artifact Registry／runtime 引用稽核，**不屬於新 release 的必經步驟**；未確認所有有效 revision／Job／復原引用前，不進行 delete-all 或 aggressive cleanup。既有 dev 業務 data path 的 GCS／Iceberg 保留，不受「新部署管線不寫 GCS」誤傷。

### 3.4 成功 Release 後保留最新 10 個 Cloud Run Service Revision（待串接）

此階段僅對**既有 Cloud Run Service** 執行，不作用於 Job、Job executions、GHCR images、GCS 或 Artifact Registry。只有 full Release tests／authenticated candidate acceptance／100% production traffic promotion／rollback receipt readback 全部 PASS，且已持有同一個跨 run deployment mutex 時才可執行。

1. 從**本次 release outputs** 取得 `PROMOTED_REVISION`，從**上一個成功發布 receipt** 取得 `LAST_SUCCESSFUL_REVISION` 與對應 digest／可重建設定；不得依檔名排序猜成功版。
2. 先以唯讀 inventory／dry-run 確認 current 是 Ready／latestCreated／latestReady、100% 流量指向已驗證的 current；任何 traffic/tag/候選引用都保護。缺欄位、權限或依賴時停止。
3. 上游才可設置 env gates，並透過 WIF 且最小化的 `run.revisions.delete` 權限執行：

   ```bash
   python scripts/gcp/cloud_run_revision_cleanup.py \
     --project "$GCP_PROJECT_ID" --region "$GCP_REGION" \
     --service "$SERVICE_NAME" --current-revision "$PROMOTED_REVISION" \
     --rollback-revision "$LAST_SUCCESSFUL_REVISION"
   # 僅在 acceptance、digest、mutex 真實證據已確認後：
   export JANUS_RELEASE_ACCEPTANCE=PASS
   export JANUS_DEPLOYMENT_MUTEX_HELD=true
   export JANUS_ROLLBACK_DIGEST_VERIFIED=true
   python scripts/gcp/cloud_run_revision_cleanup.py \
     --project "$GCP_PROJECT_ID" --region "$GCP_REGION" \
     --service "$SERVICE_NAME" --current-revision "$PROMOTED_REVISION" \
     --rollback-revision "$LAST_SUCCESSFUL_REVISION" --apply
   ```

4. 對每個刪除候選再次 readback，保護所有流量／tag／最新／回滾引用；刪除後記錄 GitHub Actions 的非敏感摘要與 immediate readback。保留建立時間最新 10 個與所有流量／tag／候選／上次成功版保護引用；如保護集合超過 10 個，全部保留；cleanup fail／partial 不得掩飾已完成 release 的結果。

**目前這段只定義下一版 Release 最後的可呼叫步驟，尚未接到新的 GitHub Actions GHCR release，因此沒有 live Revision 被自動刪除。** Cloud Run [官方限制](https://docs.cloud.google.com/run/docs/managing/revisions)：最新、唯一及仍可接受流量的 Revision 不可刪；刪除不可復原，無請求且無最低執行個體的舊版通常不產生執行費用；revision-level min instances 與 tag 可能令舊版持續計費。

## 4. PostgreSQL migration

Migration 必須使用 repository 內版本化 SQL／migration tooling，不直接在正式資料表手改 schema。

若本機沒有 `psql`，可沿用 IAP 將已審核 migration 傳到 `janus-postgres-dev`，再在 PostgreSQL container 內執行；檔名與 database 必須依該 migration 的實際 contract 決定，不從舊範例猜測。

通用安全原則：

1. 先確認 migration 檔、dependency、target database 與 rollback／rebuild 路徑。
2. Secret／password 不放 argv、terminal output、Cloud Build substitution 或一般檔案；需要暫存時使用 ACL-restricted file 並確實清除。
3. 以 `ON_ERROR_STOP=1` 或等價 fail-closed 模式執行。
4. 完成後唯讀確認 migration marker、預期 schema／constraint／role，以及 service readiness。
5. 對真實資料有影響的 migration，SQL 成功不是完整驗收；還需要適用的 runtime／owner isolation／integration evidence。

版本化 dev migration 屬既有 dev 工程閉環，可在 rollback／rebuild 路徑明確時直接執行；若涉及大量不可逆資料刪除、無可靠復原路徑或新增付費資源，仍需人工授權。

## 5. Cloud Run Jobs

目前主要 Janus Jobs 包括 ingestion、intelligence mart 與 private pipeline；實際存在的 Job、image、env、Secret reference 與 Scheduler 必須在執行前唯讀確認。

經 V2 Release 更新既有 Job 後，至少確認：

- Job `Ready=True`；
- runtime image 解析到預期 immutable digest；
- env／Secret refs 沒有意外漂移；
- 若本次 acceptance 要求 execution，使用既有 Job 執行一次 bounded run，並追蹤同一個 execution 到終態，不因等待過久重複觸發。

常用唯讀查詢：

```powershell
& $gcloud run jobs describe JOB_NAME `
  --region=$region --project=$project --format="yaml"

& $gcloud run jobs executions list `
  --job=JOB_NAME --region=$region --project=$project --limit=3

& $gcloud run jobs executions describe EXECUTION_NAME `
  --region=$region --project=$project --format="yaml(status)"
```

### 5.1 Dev 總控與資料清理

既有 Scheduler `janus-ingestion-daily` 每小時台北時間 `:30` 呼叫 Cloud Run Job `janus-batch-controller`。原 `janus-mart-daily`、`janus-private-pipeline-2130` 暫停保留供回復；自然排程與依賴、防重複驗收通過後才移除。三支資料工作 Job 保留，由總控呼叫。GitHub `iceberg-maintenance-dev.yml` 只保留手動 financials 維護入口。

總控規則在 `ingestion_core/batch_controller.py`：ingestion 每日 07:30、Mart 工作日 09:00 依賴 ingestion／data-supplement、private 工作日 21:30 依賴 ingestion；Mart 清理每日 23:30 依賴 ingestion，Core／Stage 清理依賴 Mart 清理。尚未執行的舊 occurrence 在 dispatch 前依目前契約更新 dependency，避免舊清理順序繼續生效。初期每小時輪詢，未到時間、依賴未成功或 Job 尚未結束時保留待辦，不等待或取消子 Job。PostgreSQL 總控 session lock 防止同時調度，持久化 occurrence 防止重複；不確定的 dispatch 必須人工核對 Cloud execution，不能自動重送。資料寫入／清理共用另一把資料鎖。事件先寫 PostgreSQL outbox，再冪等寫入 `ops.batch_events_v1`，讀回確認後才 acknowledge；Admin UI 查詢尚待串接。

完整清理先確認三支資料 Job 無 active execution。先執行 Mart `MART_OPERATION=retention,MART_RETENTION_MODE=dry-run,MART_AI_ENABLED=false`，核對計畫後改 `apply`；每股保留最新三代五分析師成果物，另暫時保護 queued／running／retrying execution，OOS 只留最新仍使用結果。依 Mart 保留索引、其他仍有效的 public artifact／publication 引用產生新鮮 Core reference fence，再對 ingestion 執行 `ICEBERG_MAINTENANCE_MODE=retention-dry-run`（`QUEUE_CONSUMER=false,MART_JOB=`），核對計畫後改 `retention-apply`。`CORE_RETENTION_FENCE_URI` 只能指向既有 dev Core `maintenance/retention-fences/` 下的一小時內清單，含 `created_at`、`core_snapshot_ids`；worker 另合併 active 作業引用。未提供清單時 Core execution manifest 保持受保護，回報 `reference_fence_required`；目前總控不自動產生此跨 bucket 清單。

Stage／quarantine 七日到期，不以是否已提交 Core 決定保留；active execution 及共用 raw 引用暫時保護。Mart 表保留 90 日、Core 一般行情 365 日、active Deep Coverage 行情與 benchmark 1096 日、財報每組 12 季；缺少資料不造假補齊。當前快照、最近 24 小時快照、最近 90 日每日最後快照與有效引用保護；孤兒檔與舊 metadata 至少七日且使用 generation precondition。報告保存在各 bucket `maintenance/retention/` 並讀回，另獨立盤點 live／全部版本／soft delete。使用者核准 Core／Stage／Mart／Private／research-big-move-500 的非當前版本 lifecycle 改為三日、關閉 soft delete；不立即刪除 live 檔案。research bucket 原本未啟用 versioning，三日規則只約束既有非當前版本，不新增版本副本。既有 soft-deleted 物件仍按刪除時期限到期；GCS lifecycle 非同步執行，live bytes 減少不等於當天計費 bytes 同幅減少。

總控 manifest 由 `scripts/gcp/prepare-batch-controller-dev.py` 依目前 ingestion immutable image、既有網路與 Secret refs 產生，預設 `observe`。更新 image 時須保留既有 `BATCH_CONTROLLER_MODE`、`BATCH_CONTROLLER_NOT_BEFORE`，不能直接套用預設 manifest 後忘記恢復 active。首次啟用先以 seed 採認當天原 Scheduler executions，驗證建立時間符合排程，設定有 timezone 的啟用時間後才 active。限定 IAM 清單見 `infra/gcp/dev-batch-controller-iam.json`；不得自行擴大至 production 或取消／刪除 execution。實際切換與清理證據見 operations ledger。

## 6. Secret rotation

目前 Janus runtime 採用整合後的 Secret bundle；實際 Secret 名稱、enabled versions 與 consumer references 必須先用目前 runtime／[`secret_list.md`](secret_list.md) 查證，不從歷史 split 文件推測。

Secret 值不得出現在 command argv、shell trace、process listing、Cloud Build substitution、deployment metadata 或 log。Windows 文字 pipeline 可能加入 BOM／CRLF，credential/session material 必須做 raw-byte 驗證。

安全切換順序：

1. 建立新 Secret version，保留上一個可用 version。
2. 驗證 raw bytes／格式，不輸出 payload 或 hash。
3. 讓候選 revision／Job 明確解析新 version 或依目前 bundle contract 取得新值。
4. 驗證 health、登入／DB／受影響功能與 ERROR logs。
5. 確認新 runtime ready 且實際承接預期 traffic／execution 後，才停用舊 version。
6. 失敗時回復上一個已驗證 runtime／version，不建立第二套臨時 secret path。

不要啟用 Artifact Analysis、Container Scanning 或 vulnerability occurrence API。

## 7. 驗收與紀錄

每次 deployment／migration／Job／Secret 變更，依本次工作只保存必要 evidence：

- Git commit SHA；
- GitHub Actions workflow/run ID（必要時含唯讀 Cloud Build 歷史 Build ID）；
- GHCR 公開映像確認與 immutable image digest；
- Cloud Run revision 或 Job execution；
- UTC 驗收時間；
- targeted tests／acceptance 實際結果；
- partial／failed／blocked 項目；
- rollback／rebuild evidence（若本次風險需要）。

最新 evidence 摘要更新 [`spec/operations-and-testing.md`](spec/operations-and-testing.md)；完成或被取代的 checkpoint 移入 `archive/`。README、SPEC 索引與本 runbook 不重複保存一次性 build 資訊。

## 8. 歷史資料

2026-09-23 Janus／omniAgent hard split、舊 Phase 5 deployment、舊 Agent Gateway／fixture、舊 Secret bundle 遷移等內容都是歷史 checkpoint，不再作為目前操作步驟。入口見 [`omniagent-split-status.md`](omniagent-split-status.md) 與 `archive/`。


## Owner-scoped Private Mart recalculation queue

Canonical design: `doc/decision-2026-10-07-owner-scoped-parallel-private-recalculation.md`.

- schema migration: `048_private_recalculation_queue`
- User API mutation/manual recalc only enqueue authenticated owner.
- normal scheduled `janus-private-pipeline` remains `taskCount=1`; job parallelism ceiling is 8.
- owner queue execution overrides `taskCount` from Admin setting `private_recalc_workers` (2–8, default 2).
- do not put owner UUID/symbols/trades into Cloud Run execution overrides.
- worker claims use PostgreSQL `FOR UPDATE SKIP LOCKED`; same owner has one active request.
- calculation may run concurrently, but shared Private Iceberg commit uses advisory lock `(1835102836,3)`.
- User-visible terminal failure must be persisted before the worker exits。QUEUED 在 dispatch active 但 5 分鐘無任何 worker claim 時轉為 `DISPATCH_TIMEOUT`；RUNNING/CANCEL_REQUESTED 超過 35 分鐘無 heartbeat 由 reaper 轉為 FAILED/CANCELLED；不得讓 UI indefinitely pending.
- Admin cancel is owner-scoped cooperative cancellation. Do not kill the whole shared execution for a single owner.
- Admin force-fail immediately writes a terminal FAILED state and User-visible safe reason; stale worker completion must not overwrite it.

Dev acceptance must verify migration 048, job default/task parallelism, API → job `roles/run.invoker`, one live owner request transition, duplicate-active suppression, and final Private Mart ledger-version catch-up.

### 2026-10-07 live acceptance 固化

正式 owner-queue live gate 為 `.github/workflows/private-recalc-live-acceptance.yml`。它必須走既有 runtime network path：

1. `janus-ingestion-core` acceptance mode seed 一筆 bounded owner request並驗 same-owner active unique fence。
2. `janus-private-pipeline` 用 `--tasks=2 --update-env-vars=PRIVATE_RECALC_QUEUE_MODE=true` 執行 queue mode。
3. `janus-ingestion-core` acceptance mode verify DB 終態與 worker binding。
4. workflow 最後驗 persistent Job 仍為 `taskCount=1 / parallelism=8`，且 acceptance env 沒有寫回 Job persistent config。

不要改回 Cloud Build → IAP → PostgreSQL VM 的 canary；`janus-ci` 沒有 IAP tunnel 權限，而且這個驗收不需要為此擴 IAM。若 live gate 失敗，先看 seed / queue / verify 哪個 Cloud Run execution 失敗，再處理；不得以 workflow success 取代 DB verify。

## 9. PostgreSQL dev 備份保留（2026-10-08）

- PostgreSQL VM `janus-postgres-dev` 透過 `/var/lib/janus/ledger-durability vm-backup` 產生完整 `pg_dump`，暫存檔在程序結束後清除；永久備份位於既有 `gs://gen-lang-client-0593591102-dev-private/pilot-ledger-backups/`，**不放在 VM 永久磁碟**。
- `daily/` **只保留最新 3 代**；`monthly/` 暫維持原有最多 6 代設定。Repo 的 `scripts/gcp/ledger-durability-dev.sh` 已將 daily prune 調整為 3，但 VM 已安裝的腳本不會因 Git commit 自動同步。
- 目前有效的每日保留執行端是 GitHub Actions `.github/workflows/private-ledger-backup-retention.yml`，每天 **19:00 UTC**（VM 原定備份約 18:00 UTC）依日期排列，只以 GCS 物件 `generation` 前置條件刪除舊 daily，之後重新列舉確保恰好 3 份。workflow 若失敗不得宣稱保留政策已達成；不可因此擴大 IAM 或改動其他 prefix。
- 備份可能包含過去已清除的測試資料；備份屬受保護恢復點，不把刪除現行資料表等同於刪除舊備份內歷史紀錄。GCS soft-delete／非當前版本依 bucket 既有政策另行驗證。
