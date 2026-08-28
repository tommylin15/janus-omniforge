# Dev 部署與 PostgreSQL Migration Runbook

本文件記錄已驗證的 dev 執行路徑。適用於本機 Windows PowerShell、GCP
project `gen-lang-client-0593591102`、region `us-central1`。執行 Terraform
apply、migration、Cloud Build 或 Cloud Run Job 前，仍須依
`doc/PROJECT_RULES.md` 取得當次明確授權。

## 1. 工具與固定變數

本專案使用已驗證的 Terraform binary：

```powershell
$tf = "D:\vibeCode\github\janus-omniforge\.tools\terraform\terraform.exe"
$gcloud = "C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
$project = "gen-lang-client-0593591102"
$region = "us-central1"
$zone = "us-central1-a"
```

不要使用 `gcloud.ps1`；在受限 PowerShell execution policy 下可能被阻擋。
不要使用可能是 0 bytes 的 WinGet `terraform.exe` launcher。

## 2. Terraform dev apply

先初始化與驗證，再產生保存的 plan；apply 必須使用同一份 plan：

```powershell
Set-Location D:\vibeCode\github\janus-omniforge\infra\terraform
& $tf init
& $tf validate
& $tf plan -var="project_id=$project" -var="region=$region" -out=dev-current.tfplan
& $tf show -no-color dev-current.tfplan
& $tf apply dev-current.tfplan
```

apply 前確認 plan 沒有建立 production、第二台 PostgreSQL VM、Cloud NAT、
backup、HA、replica 或公開 PostgreSQL `5432`。另外確認
`google_cloud_scheduler_job.ingestion_daily.paused` 為 `false`，避免把既有
啟用中的每日排程意外停掉。

## 3. 透過 PostgreSQL VM 執行 migration

本機沒有 `psql` 時，使用 IAP SCP 將 migration 傳到 VM，再在 PostgreSQL
container 內以 `postgres` OS user 執行。不要直接以 container root 執行，
否則 local peer authentication 會拒絕 `postgres` database user：

```powershell
& $gcloud compute scp `
  D:\vibeCode\github\janus-omniforge\infra\postgres\migrations\004_source_coverage.sql `
  janus-postgres-dev:/tmp/004_source_coverage.sql `
  --project=$project --zone=$zone --tunnel-through-iap

& $gcloud compute ssh janus-postgres-dev `
  --project=$project --zone=$zone --tunnel-through-iap `
  --command="sudo docker cp /tmp/004_source_coverage.sql janus-postgres:/tmp/004_source_coverage.sql && sudo docker exec --user postgres janus-postgres psql -v ON_ERROR_STOP=1 -U postgres -d janus_control -f /tmp/004_source_coverage.sql"
```

migration 後執行唯讀驗證，至少確認 migration version、欄位與 membership
table：

```sql
SELECT version FROM control.schema_migrations ORDER BY version;
SELECT column_name
FROM information_schema.columns
WHERE table_schema = 'control'
  AND table_name = 'collection_configs'
  AND column_name IN ('coverage_tier', 'cadence', 'scope',
                      'authorization_status', 'max_symbols')
ORDER BY column_name;
SELECT to_regclass('control.coverage_memberships');
```

## 4. ingestion-core Cloud Run deployment

目前 `cloudbuild.yaml` 的預設值仍保留通用／歷史 fallback，因此手動建置
ingestion-core 時必須明確傳入 substitutions：

```powershell
Set-Location D:\vibeCode\github\janus-omniforge
& $gcloud builds submit . `
  --project=$project `
  --config=cloudbuild.yaml `
  --substitutions=_DOCKERFILE=jobs/ingestion-core/Dockerfile,_IMAGE_NAME=ingestion-core,_IMAGE_TAG=dev-p0-YYYYMMDD,_DEPLOY_TARGET=job,_RUNTIME_NAME=janus-ingestion-core,_REGION=$region
```

成功條件是 Cloud Build 的 build、push、deploy、cleanup 四個 step 都成功，
且 deploy step 以 Artifact Registry digest 更新 Cloud Run Job。部署後唯讀
核對：

```powershell
& $gcloud run jobs describe janus-ingestion-core `
  --region=$region --project=$project --format="yaml"
```

確認 `status.conditions[type=Ready]` 為 `True`，image 是 immutable
`@sha256:...`，並保留 Cloud Build ID 與 digest 作為證據。不要啟用或呼叫
Artifact Analysis、Container Scanning 或 occurrence API。

## 5. Dev smoke run

得到新 Job image 後可執行一次 dev smoke：

```powershell
& $gcloud run jobs execute janus-ingestion-core `
  --region=$region --project=$project

& $gcloud run jobs executions list `
  --job=janus-ingestion-core --region=$region --project=$project --limit=3

& $gcloud run jobs executions describe EXECUTION_NAME `
  --region=$region --project=$project --format="yaml(status)"
```

首次啟動可能需要數分鐘，常見中間狀態為 `Waiting for execution to start`、
接著 `Started=True`。不要因為本機 `gcloud ... --wait` 等待過久就重複建立
多個 execution；先以 `executions describe` 查詢既有 execution。完整 ingestion
結束後才可判定 smoke 成功或失敗。

## 6. 本次已驗證的 dev 證據

- Terraform `init`、`validate` 通過；apply：`1 added, 2 changed, 1 destroyed`。
- PostgreSQL migration `004_source_coverage` 成功，並確認新欄位與
  `control.coverage_memberships` 存在。
- Cloud Build：`daa3d930-75cf-43a8-b5a5-48e972bdd73d`，四個 step 成功。
- Cloud Run Job image digest：
  `sha256:e85017c3022da240f82cf7c557625a7b17e84249a2d42517d4eb4b6f52531131`。
- 本次 smoke execution：`janus-ingestion-core-kkbkg`；容器已啟動，執行
  完成狀態需由後續 `executions describe` 再確認。
