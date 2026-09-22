# Dev 部署與 PostgreSQL Migration Runbook

本文件記錄已驗證的 dev 執行路徑。適用於本機 Windows PowerShell、GCP
project `gen-lang-client-0593591102`、region `us-central1`。執行 GCP
bootstrap、migration、Cloud Build 或 Cloud Run Job 前，仍須依
`doc/PROJECT_RULES.md` 取得當次明確授權。

omniAgent split Chat ownership checkpoint 未修改本 runbook 的 Janus dev 部署路徑：Janus 仍是 Chat thread/event 的 live writer，`016_private_assistant_storage.sql` 已套用歷史不得移除或重排。omniAgent 的 `omni_chat` schema 尚未套用，歷史 owner mapping／export-copy-verify、runtime dispatch、routing cutover 均待獨立驗收；本 runbook 不可作為已 cutover 的依據。

Phase 5 source split 已完成；部署保護把最後一版拆分前 source commit `5d24d0638b2667c6c4e9b68620223adef5c08e8d` 的 User App Web 產物固定於 `services/api/legacy-user-app-web.tar.gz`。每次 API image build 驗證該檔 SHA-256、`/app/` base href 與 legacy Chat route，再解包至 `/app`；不從目前已移除 Chat 的 Janus `apps/user_app` 建立。產物缺失或驗證失敗時 Cloud Build 不會更新 `janus-api`。產物內含目前 dev 使用的 Google User／Admin client IDs；替換時須重做 OAuth 與 UI 驗收。此保護尚未經新 image 的 GCP dev 部署驗收。omniAgent OAuth、runtime dispatch、Janus context、Skills/MCP、歷史資料 migration 與 live cutover 均未完成。

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

Automatic deployment is initiated by the active GCP Cloud Build Developer Connect
triggers. They watch `main` and invoke `cloudbuild.yaml` only when their component
paths match. No service-account JSON key or Terraform is required.

`.github/workflows/deploy-dev.yml` is a manual-only fallback using GitHub OIDC.
Configure these repository Variables before using that fallback:

- `GCP_WIF_PROVIDER`: full GCP Workload Identity provider resource name
- `GCP_CI_SERVICE_ACCOUNT`: the allowed CI service account email

The fallback refuses to run unless the selected ref is `main`; it invokes
`scripts/gcp/deploy-dev.sh` and then `scripts/gcp/verify-dev.sh`.

Automatic trigger mapping:

- `services/api/**`, `packages/admin_api/**`, `packages/web_api/**`,
  `apps/web/static/**`, or `cloudbuild.yaml` → `janus-api`
- `jobs/ingestion-core/**`, `packages/contracts/**`,
  `packages/observability/**`, or `cloudbuild.yaml` → `janus-ingestion-core`
- `jobs/intelligence-mart/**`, `packages/contracts/**`,
  `packages/observability/**`, or `cloudbuild.yaml` → `janus-intelligence-mart`

Other paths, including documentation and `scripts/gcp/**`, do not trigger an
automatic runtime deployment.

API 自動觸發與 GitHub OIDC 手動部署共用 `services/api/Dockerfile`，均套用上述固定 artifact。變更此 Dockerfile 會觸發一次自動 API 部署；推送前先確認 Web artifact 與 checksum 一起提交。不得以目前 Janus User App source 取代該 Web artifact，除非另行完成 UI cutover 與回退驗收。

目前 100% live revision：`janus-api-admin-flutter-mvp-20260921`，image `us-central1-docker.pkg.dev/gen-lang-client-0593591102/janusai-poc/api@sha256:36378556ae201a9e60c536e5146a687b6f6b527fc5219c15cd30db8fb254de22`。registry 只保留最近兩個 API image，舊 digest 不應視為永久保留；repo 內固定 Web artifact 與其來源 commit 是可重建依據。部署前記錄當時 100% revision；如果新 API revision 或其 `/app` 異常，將流量回切該 revision：

2026-09-22 唯讀盤點：live digest `36378556...` 仍在 registry 且有 tag；`usefulness-rollback` revision 所指的 `058d442f...` digest 已不存在，該舊 tag 不能當作可操作 rollback。registry 只保留最近兩版 API image；先建零流量候選再由 main 自動部署第二個新 image，可能清掉目前 live digest。部署前須先取得可操作的舊 API image 保留方案，並驗證固定 Web artifact；否則停止部署並回報 blocker。

```powershell
& $gcloud run services update-traffic janus-api `
  --project=$project --region=$region `
  --to-revisions=janus-api-admin-flutter-mvp-20260921=100
```

回切前唯讀確認該 revision 仍存在且 image digest 可用；若 registry 已清除舊 digest，從含固定 Web artifact 的 repo commit 重建候選 image 並以 `--no-traffic` 驗證 `/app` 後才調整流量。Chat 資料 writer 與 Janus 舊 API 在 UI cutover 前保持原路徑。

The active automatic deployment targets are `janus-ingestion-core`,
`janus-intelligence-mart`, and `janus-api`; the legacy `janus-web` runtime is absent.
The GitHub Actions workflow is manual-only and must remain that way, or the same
push will be deployed twice.

## 2B. WBS-7 dev security／FinOps

After explicit dev authorization, configure and then verify existing resources:

```powershell
$env:GCP_PROJECT_ID = "gen-lang-client-0593591102"
$env:GCP_REGION = "us-central1"
$env:GCP_ZONE = "us-central1-a"
$env:GCP_BILLING_ACCOUNT_ID = "BILLING_ACCOUNT_ID"
$env:ALLOW_DEV_SECURITY_FINOPS = "true"
& "C:\Program Files\Git\bin\bash.exe" scripts/gcp/security-finops-dev.sh configure
& "C:\Program Files\Git\bin\bash.exe" scripts/gcp/security-finops-dev.sh verify
& "C:\Program Files\Git\bin\bash.exe" scripts/gcp/security-finops-dev.sh report
```

The budget is a single 320 TWD notification budget with 10%／50%／100% thresholds;
it is not a spending cap. The report is a bounded resource-exposure inventory. Exact
billed spend remains in Cloud Billing because this dev path does not create a
paid BigQuery billing export. Free Tier PostgreSQL verification requires no
snapshot／PD backup／HA／replica; the Pilot ledger backup is a separately bounded
logical `pg_dump` to restricted Private GCS strategy.

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

### 6.0 三 bundle 收斂

先完成本機 targeted tests 與 shell syntax check，再執行：

```bash
export GCP_PROJECT_ID=gen-lang-client-0593591102
export ALLOW_SECRET_BUNDLE_MIGRATION=true
scripts/gcp/migrate-secret-bundles-dev.sh prepare
```

依序以 `scripts/gcp/deploy-dev.sh` 部署 `ingestion-core`、`intelligence-mart`、
`private-pipeline`、`web`，並以 `scripts/gcp/deploy-agent-gateway-dev.sh` 部署 Gateway。
新版 loader 先隨映像部署，再切換 Secret reference；不得反轉順序。完成所有 runtime
probes 與 Codex A／B entry rotate／destroy 隔離驗收後，才可另設
`ALLOW_SECRET_BUNDLE_CLEANUP=true` 執行：

```bash
scripts/gcp/migrate-secret-bundles-dev.sh cleanup
```

cleanup 會刪除六個 legacy Secret container；驗收未全數通過時禁止執行。

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
