# Dev 部署與 PostgreSQL Migration Runbook

本文件記錄已驗證的 dev 執行路徑。適用於本機 Windows PowerShell、GCP
project `gen-lang-client-0593591102`、region `us-central1`。執行 GCP
bootstrap、migration、Cloud Build 或 Cloud Run Job 前，仍須依
`doc/PROJECT_RULES.md` 取得當次明確授權。

Janus Agent／Chat hard split 與單一 Secret bundle 已部署至 GCP dev。Canonical `janus-api` revision `janus-api-runtime-bundle` 使用 immutable digest `sha256:d1b9d7c2f3f5f05d142e514281cb36d791ef81b477ebf3ebadbf7fa310f591bf`、承接 100% traffic，保留 Janus MCP/OAuth 與投資功能，不建置舊 Chat UI。Janus API、private pipeline、ingestion、mart 與 PostgreSQL migration build 共用 `janus-runtime-bundle`。`016_private_assistant_storage.sql` 與歷史資料必須保留。驗收證據與剩餘 gate 見 [split status](omniagent-split-status.md)。下方 Phase 5 記錄只供歷史查核，不代表目前 source／revision。

本 runbook 下方既有的 assistant／Agent Gateway、三 bundle 遷移與 Chat deployment 步驟已過時；不得照舊執行或用來退役資源。Hard split 專用 build／runtime acceptance／cleanup 須依 [split status](omniagent-split-status.md) 逐 gate 執行。

Phase 5 source split 與部署保護已完成：API image 固定使用最後一版拆分前 commit `5d24d0638b2667c6c4e9b68620223adef5c08e8d` 的 `services/api/legacy-user-app-web.tar.gz`，建置時驗證 SHA-256、`/app/` base href、legacy Chat route 與 Admin OAuth client ID；不重建目前已移除 Chat 的 Janus `apps/user_app`。GCP dev build `d46fd92e-1bcf-482b-b4fd-ee59c4ef8c38`、候選驗收 `d61ac9ee-616f-4a37-8010-d1b7f6ddab07` 與 canonical 驗收 `123683e7-6fa8-444e-a00d-e12af07045c8` 均成功。omniAgent OAuth、runtime dispatch、Janus context、Skills/MCP、歷史資料 migration 與 live cutover 均未完成。

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

目前沒有 `janus-api` 自動 Cloud Build trigger；推送 `main` 不會部署 API。
Janus API 以 `scripts/gcp/deploy-dev.sh api` 手動提交既有 Cloud Build，先建置
immutable image，再部署既有 `janus-api` service。source split 的 Cloud Build ID、
digest、revision 與 acceptance builds 見 [split status](omniagent-split-status.md)。

`.github/workflows/deploy-dev.yml` is a manual-only fallback using GitHub OIDC.
Configure these repository Variables before using that fallback:

- `GCP_WIF_PROVIDER`: full GCP Workload Identity provider resource name
- `GCP_CI_SERVICE_ACCOUNT`: the allowed CI service account email
- `GOOGLE_USER_CLIENT_ID` and `GOOGLE_ADMIN_CLIENT_ID`: existing public OAuth
  client IDs required at Flutter Web build time

The fallback refuses to run unless the selected ref is `main`; it invokes
`scripts/gcp/deploy-dev.sh` and then `scripts/gcp/verify-dev.sh`.

`services/api/Dockerfile` 會由 `apps/user_app` build `/app/`，要求既有 User/Admin
OAuth public client IDs。正式切 traffic 前，先以唯一 revision suffix/tag 部署
`DEV_DEPLOY_NO_TRAFFIC=true` 候選，從 Cloud Build worker 跑 public API、Flutter UI、
MCP/OAuth acceptance；全部通過後才以 `gcloud run services update-traffic` 明確切換。
`MCP_OAUTH_ENABLED` 未提供時，deploy script 保留現有 runtime OAuth 設定；明確指定
`true` 才須同時提供既有 issuer、resource URL 與 user allowlist。不得輸出或變更
Secret payload、OAuth secret 或 callback 設定作為一般 image deploy 的副作用。

目前 deployed revision 是 `janus-api-runtime-bundle`。Cloud Build 會清理
未標記的舊 image versions；回切前必須先確認舊 digest 仍存在，不可只憑 Cloud Run
revision 名稱假設 image 可回復。舊 Phase 5 artifact/rollback 段落均為歷史證據。

GitHub Actions `deploy-dev.yml` 仍是手動 fallback；新的 Flutter workflow 只驗證
analyze／test／Web build，不部署 GCP。

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

### 6.0 Janus 單一 bundle（2026-09-23）

目前 Janus 唯一 bundle 是 `janus-runtime-bundle`。三個仍存在的舊 bundle 已刪除；
Codex owners bundle 先前已刪除且沒有 payload。不要再執行下方舊版三 bundle
`migrate-secret-bundles-dev.sh prepare/cleanup` 流程或 Gateway 部署步驟。單一 Secret
採資源層級 IAM，四個 Janus runtime identities 與 Cloud Build default identity 都可讀
完整 bundle；不能依 JSON 欄位區分權限。輪替與 raw-byte 驗證規則仍依本節後續步驟。

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

## 7. 早期 dev bootstrap 證據

以下為早期 checkpoint；目前 trigger、image 與 rollback 現況以 2A 節為準。

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
