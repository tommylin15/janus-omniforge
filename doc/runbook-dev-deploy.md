# Dev 部署與 PostgreSQL Migration Runbook

本文件記錄已驗證的 dev 執行路徑。適用於本機 Windows PowerShell、GCP
project `gen-lang-client-0593591102`、region `us-central1`。執行 GCP
bootstrap、migration、Cloud Build 或 Cloud Run Job 前，仍須依
`doc/PROJECT_RULES.md` 取得當次明確授權。

## 1. 工具與固定變數

本專案使用已驗證的 gcloud binary：

```powershell
$gcloud = "C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
$project = "gen-lang-client-0593591102"
$region = "us-central1"
$zone = "us-central1-a"
```

不要使用 `gcloud.ps1`；在受限 PowerShell execution policy 下可能被阻擋。

## 2. gcloud dev bootstrap (current path)

Terraform is not required. `scripts/gcp/provision-dev.sh` is the explicitly
authorized, idempotent bootstrap entrypoint. It does not delete resources and
fails closed if the fixed PostgreSQL Free Tier shape is missing or has drifted.

For a local, explicitly authorized bootstrap:

```powershell
$env:GCP_PROJECT_ID = $project
$env:GCP_REGION = $region
$env:GCP_ZONE = $zone
$env:GITHUB_REPOSITORY = "tommylin15/janus-omniforge"
$env:GCP_CI_SERVICE_ACCOUNT = "janus-ci@${project}.iam.gserviceaccount.com"
$env:ALLOW_DEV_PROVISION = "true"
& "C:\Program Files\Git\bin\bash.exe" scripts/gcp/provision-dev.sh
```

## 2A. Dev runtime deployment (current path)

Automatic deployment is initiated by three GCP Cloud Build Developer Connect
triggers. They watch `main` and invoke `cloudbuild.yaml` only when their
component paths match. No service-account JSON key or Terraform is required.

`.github/workflows/deploy-dev.yml` is a manual-only fallback using GitHub OIDC.
Configure these repository Variables before using that fallback:

- `GCP_WIF_PROVIDER`: full GCP Workload Identity provider resource name
- `GCP_CI_SERVICE_ACCOUNT`: the allowed CI service account email

The fallback refuses to run unless the selected ref is `main`; it invokes
`scripts/gcp/deploy-dev.sh` and then `scripts/gcp/verify-dev.sh`.

Automatic trigger mapping:

- `apps/web/**` or `cloudbuild.yaml` → `janus-web`
- `jobs/ingestion-core/**`, `packages/contracts/**`,
  `packages/observability/**`, or `cloudbuild.yaml` → `janus-ingestion-core`
- `jobs/intelligence-mart/**`, `packages/contracts/**`,
  `packages/observability/**`, or `cloudbuild.yaml` → `janus-intelligence-mart`

Other paths, including documentation and `scripts/gcp/**`, do not trigger an
automatic runtime deployment.

The active automatic deployment source is now the three GCP Developer Connect
triggers `janus-ingestion-core`, `janus-intelligence-mart`, and `janus-web`.
The GitHub Actions workflow is manual-only and must remain that way, or the same
push will be deployed twice.

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

- Terraform 已從 repository 與 dev deployment path 移除；bootstrap 由
  `scripts/gcp/provision-dev.sh` 負責，PostgreSQL guard 驗證為 `e2-micro`、
  30 GB、`us-central1-a`。
- 三個 GCP Developer Connect triggers 已建立，僅 `main` 且符合 component
  paths 時觸發；GitHub Actions 為 manual-only fallback。
- PostgreSQL migration `004_source_coverage` 成功，並確認新欄位與
  `control.coverage_memberships` 存在。
- 最近直接驗證的 ingestion build：
  `baf5b915-ee80-477b-8ec8-dc1e981fc23a`，digest
  `sha256:16248df5e95afea4cc099016c4c6e1722eade307b53d2065514f7d517f596e8e`。
- 最近直接驗證的 web build：`e021a691-2a0e-42eb-bffd-b25c2ee2ead2`，
  digest `sha256:6746d5985e60781bda04b1965d980e0651c82dd30e7026344e1b30908221cd74`。
- `janusai-poc` 與 `janus-postgres` cleanup policy 均為每個 package 只保留
  最新一版；dry-run disabled，Artifact／Container scanning disabled。
- 新 trigger set 尚待一次符合 component path 的 `main` push 完成端到端驗收；
  `janus-intelligence-mart` Cloud Run Job 尚未建立。
