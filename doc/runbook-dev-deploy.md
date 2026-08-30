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

## 6. Secret 建立、輪替與驗證

Secret 值不得出現在 command argv、shell trace、process listing、Cloud Build
substitution、deployment metadata 或 log。特別禁止使用
`docker exec -e PGPASSWORD=<value>`；該值可能被 process listing 讀到。Windows
PowerShell 的文字 pipeline 也可能加入 UTF-8 BOM 或 CRLF，不能只用「可以 access
Secret」作為驗證成功的判準。

### 6.1 建立無 BOM 的隨機 Secret version

在 Git Bash 產生 ASCII CSPRNG bytes，直接以 stdin 交給 `gcloud.cmd`，不經
PowerShell 字串轉碼、不落地、不輸出值：

```bash
openssl rand -base64 36 \
  | tr -d '\r\n' \
  | cmd.exe /d /s /c \
      "gcloud.cmd secrets versions add SECRET_NAME --project=PROJECT_ID --data-file=-"
```

密碼若有格式規則，仍應以相同的 raw-byte stdin 路徑產生；不要把產生結果放進
命令參數。

### 6.2 Raw-byte 驗證

先固定新 version 編號，不使用 `latest`。以 raw pipe 檢查 bytes，輸出只能包含
長度、ASCII 判定與 BOM 判定，不得輸出 hash 或內容：

```bash
cmd.exe /d /s /c \
  "gcloud.cmd secrets versions access VERSION --secret=SECRET_NAME --project=PROJECT_ID" \
  | python.exe -c "import sys; b=sys.stdin.buffer.read(); print('bytes='+str(len(b))+' ascii='+str(b.isascii())+' bom='+str(b.startswith(bytes([239,187,191]))))"
```

ASCII credential/session material 的成功條件為：長度符合該 Secret 契約、
`ascii=True`、`bom=False`。另確認 version state 是 `enabled`。若經 SSH stdin
傳入密碼，接收端在 `read -r` 後仍須移除可能的尾端 `\r`。

### 6.3 Runtime 功能驗證與切換順序

1. 新增 version，但先保留上一個可用 version。
2. Cloud Run/Job 建立新 revision，明確解析該 version；不要只更新既有 instance。
3. 用服務本身驗證 Secret：health、需登入 route、資料庫基礎查詢與 ERROR log。
   Session secret 需用同一個應用程式 encoder/decoder 做短效合成 session smoke；
   PostgreSQL credential 以 runtime 成功連線及權限中繼資料驗證，不另把密碼放進
   argv 做 login smoke。
4. 確認新 revision ready、承接流量且無 runtime error 後，才停用舊 version。
5. 再列出 versions，確認只有目前版本 enabled；失敗時回復舊 revision/version，
   不建立第二套不同驗證路徑。

Google OAuth 的自動測試使用注入 verifier 驗證 callback、CSRF、allowlist、session
簽章與竄改拒絕。真正 Google 帳號登入及 OAuth Console redirect URI 是一次性人工
驗收，不把 Google 帳密或 MFA 納入自動化。

## 7. 本次已驗證的 dev 證據

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
- 最近直接驗證的 web build：`5d919396-ad8a-490e-a07c-30c33c3060bb`，
  digest `sha256:1be0cb5e7cb5056fc2805de3eb9f44214cb969d13e991186872ad39cb32e8123`；
  revision `janus-web-00023-ccj` 已完成公開／受保護路由與 DB-connected smoke。
- `janusai-poc` 與 `janus-postgres` cleanup policy 均為每個 package 只保留
  最新一版；dry-run disabled，Artifact／Container scanning disabled。
- 新 trigger set 尚待一次符合 component path 的 `main` push 完成端到端驗收；
  `janus-intelligence-mart` Cloud Run Job 尚未建立。
