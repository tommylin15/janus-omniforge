# Operations and testing

## Janus／omniAgent hard split — GCP dev acceptance (2026-09-23)

Pushed `main` source SHA `2692a09` plus MCP acceptance SHA `f80f3c6`. Local checks:
root Python **241 passed**; TypeScript typecheck/lint passed; unit tests **3 passed**;
Flutter analyze **0 errors** (20 existing info notices); Flutter widget tests
**15 passed**; Git Bash `bash -n scripts/gcp/deploy-dev.sh`, Cloud Build YAML parse,
and `git diff --check` passed.

Cloud Build image `53aa871d-7805-4dd4-a8a9-c2eb9101204d` succeeded. Immutable digest
`sha256:d1b9d7c2f3f5f05d142e514281cb36d791ef81b477ebf3ebadbf7fa310f591bf` was deployed
as revision `janus-api-hard-split-20260923-config` and is canonical 100% traffic.
`MCP_OAUTH_ENABLED=true`; old `INTERNAL_ASSISTANT_AUDIENCE`,
`ASSISTANT_SERVICE_ACCOUNTS`, and `MCP_GATEWAY_URL` are absent. OAuth inputs were
read from the existing dev config/bundle; no secret values were logged.

Zero-traffic candidate acceptance builds: MCP/OAuth `064e01e1-61e3-49c2-8328-5357b81e7f24`, public API `ed63f9a8-30f6-4006-a23f-c170372ddc12`, Flutter UI `e916abc7-77c6-488f-8865-a3e80b7a8f2a` — all **SUCCESS**. Post-promotion canonical builds: public API `91f2bda9-75af-48b5-bb8a-068b3079473d`, MCP/OAuth `f90de349-8e64-434a-9667-f0d9aa03e9d5`, Flutter UI `94167f29-c67e-439c-a14c-dcc2d01159d8` — all **SUCCESS**. After cleanup, public API `e5f9fbfa-84b4-4eeb-b5c5-7f10349d9c65` and MCP/OAuth/protocol `dc2f595b-950a-4f4b-986f-ac3497e652a8` — both **SUCCESS**.

Verified health/public domain API guards, Chat/internal routes return 404, `/app` and `/app/admin` bundle/base href/OAuth client ID, MCP OAuth metadata and invalid-flow guards, `initialize`, `tools/list` (three read-only tools), and unauthenticated `tools/call` 401 challenge. No interactive OAuth consent or authenticated `tools/call` was performed; this remains explicitly unverified. Existing three Cloud Run Jobs remain Ready; no data/migrations changed.

After acceptance, deleted Janus-only `janus-agent-gateway`, `janus-mcp-fixture`, empty `janus-codex-owners-bundle`, gateway and POC-invoker service accounts; removed only the gateway SA binding from shared `janus-agent-provider-bundle`, leaving ingestion/mart access. Kept `omniagent-agent-gateway` because request logs show successful calls on 2026-09-23, and retained `omniagent-chat` because it remains the gateway invoker identity. No migration or historical data was deleted. Older Agent Gateway/Phase 5 results below are historical.

## Phase 5 UI split deployment safety（2026-09-22）

Janus API Docker build 使用最後一版拆分前 source commit `5d24d0638b2667c6c4e9b68620223adef5c08e8d` 的固定 Web artifact `services/api/legacy-user-app-web.tar.gz`（SHA-256 `b2cd74213703d606dec511fa2c43befbc5518a8685f5c2bf3c19eab7c7e72825`）。本地與 GitHub CI 均確認 archive、`/app/` base href、legacy Chat route 與 User／Admin OAuth client IDs。Janus CI [run 35705589439](https://github.com/tommylin15/janus-omniforge/actions/runs/35705589439)、omniAgent CI [run 35705540272](https://github.com/tommylin15/omniAgent/actions/runs/35705540272) 均 SUCCESS。GCP dev image build `d46fd92e-1bcf-482b-b4fd-ee59c4ef8c38` SUCCESS，digest `sha256:3be7c05489ab6329632a94372f8c311f7de5a0f4ab485ec012d8340eb2c13d9c`；revision `janus-api-00154-74s` 先以 `phase5-ui` tag 做 0% 流量候選驗收 `d61ac9ee-616f-4a37-8010-d1b7f6ddab07`，再切為 canonical 100% 並通過驗收 `123683e7-6fa8-444e-a00d-e12af07045c8`。兩次 GCP worker 驗證 health、`/app`、`/app/admin`、legacy Chat route 與兩個 OAuth client ID。未執行 omniAgent UI cutover、migration、IAM／Secret／OAuth 變更。GCP 目前沒有 `janus-api` 自動 trigger；本次直接手動提交 `cloudbuild.yaml`，詳見 [dev 部署 runbook](../runbook-dev-deploy.md)。舊 `usefulness-rollback` image 已不存在，使用者接受不保留舊 image rollback。

Janus `apps/user_app`：`flutter pub get` 通過；原樣 `flutter analyze lib test` 因既有 20 個 info-level `curly_braces_in_flow_control_structures` exit 1，專案既有 `--no-fatal-infos` 版本 exit 0；`flutter test` 16 passed；原樣 `flutter build web` 因缺 Web host exit 1，執行 `flutter create . --platforms web --no-pub` 後 build 成功。omniAgent `apps/agent_app`：`flutter pub get`、`flutter analyze lib test`、`flutter test` 4 passed、`flutter build web` 全部成功。source split 與 Janus API deployment safety 已有 GCP dev evidence；omniAgent OAuth、runtime dispatch、Janus context、Skills/MCP、historical migration、live cutover 仍未完成。

## Admin／baseline GCP dev acceptance checkpoint（2026-09-21）

`python -m pytest -q`：261 passed；`npm.cmd run test:unit`：20 passed；Flutter widget：16 passed（新增批次重試回歸曾抓到 `setState` 回傳 Future，已修正重跑）；`flutter analyze --no-fatal-infos`：exit 0，只有 info-level style notices；Python compile、Git Bash `bash -n scripts/gcp/deploy-dev.sh`、`git diff --check` 通過。root `pytest.ini` 將 Janus testpaths 固定為 `tests/`，避免內嵌 `token-savior/scripts` 與 root `scripts` namespace 衝突；內嵌套件測試仍應從其自身 root 獨立執行。

Admin Flutter shell／overview／batch／stock 的本機開發已建立，static Admin 未移除；後端補 membership 與失敗 item 的受限重試 API。`pytz==2025.2` 已加入 API runtime lock；Admin 個股 health 使用 bounded `ohlcv` summary，避免完整 Core summary 在 Cloud Run 掃描大表逾時。

本機：root `python -m pytest -q` **261 passed**；`npm.cmd run test:unit` **20 passed**；Flutter widget **16 passed**；`flutter analyze --no-fatal-infos` exit 0；Python compile、Git Bash `bash -n scripts/gcp/deploy-dev.sh`、`git diff --check` 通過。

GCP dev：Cloud Build `0ebcb910-ede6-4f95-ad9a-3db6df6368b6` SUCCESS，image digest `sha256:36378556ae201a9e60c536e5146a687b6f6b527fc5219c15cd30db8fb254de22`，revision `janus-api-admin-flutter-mvp-20260921-config`；candidate runtime acceptance build `66cab6ed-7b3e-4071-a938-87fe25d81007` SUCCESS，檢查 `/health`、`/app`、`/app/admin` 與未授權 Admin API 邊界。canonical URL 真人 Google Admin OAuth（`tommylin15@gmail.com`）成功；Overview 實際顯示 Core 9、Mart 50、AI 待 WBS-5、失敗／阻擋 11；批次可讀既有 failed executions 與 detail；2330 個股頁顯示 `ohlcv` 10 rows、coverage 1/1、正常，並顯示歷史 Mart reports。

GCP dev 既有 PostgreSQL web roles 已完成可用性驗證；先前為 migration 診斷暫加的 Cloud Build／Compute Secret Accessor 已清除。沒有 production deployment 或新付費資源。五角色／CIO、role-impact／affected-role rerun、完整 Admin parity 依賴 WBS-5，仍不宣稱 WBS-6 三個切片結案。

## WBS 4J Private Pipeline ACL repair（2026-09-18）

根因：`apply-private-storage-postgres-migration.sh` 有 shell bug，第二個 `psql` 命令
缺少 `sudo docker exec`，導致 migration 026 在本機執行而非容器內，使
`private.mcp_oauth_codes` 的 `janus_private_pipeline` 只有 DELETE 沒有 SELECT。
`DELETE ... WHERE user_id=%s` 需要 SELECT 評估 predicate，因此 deletion flow 失敗。

修正：
- `infra/postgres/migrations/027_pipeline_acl_repair.sql`：冪等 `GRANT SELECT, DELETE ON private.mcp_oauth_codes TO janus_private_pipeline`
- `scripts/gcp/apply-private-storage-postgres-migration.sh`：修正 shell bug，兩個 psql 合入同一 `docker exec bash`
- `apply-mart-postgres-migration.sh`、`apply-web-postgres-migration.sh`：加入 027
- `infra/postgres/private-storage-acceptance.sql`：加入 `has_table_privilege` SELECT+DELETE 驗證

GCP dev 直接透過 IAP SSH 執行：`GRANT` + `INSERT 0 1`（migration marker）成功。
ACL 驗證 `SELECT=t, DELETE=t, migrated=t`。
Pipeline execution `janus-private-pipeline-mvnnz`：`succeededCount=1`、`checkpoint=62`、`exit(0)`。
本機 targeted tests：`pytest tests/test_private_pipeline.py tests/test_private_pipeline_scheduler.py` **19 passed**。

## WBS 4J Private Portfolio closed-loop implementation checkpoint（2026-09-18）

Private Pipeline normal execution 改為在有 pending change 時，從 persisted
`core.ohlcv_v1` 解析不晚於 Asia/Taipei 執行日的最新 trading date；explicit
`VALUATION_DATE` 仍保留 historical replay。空 queue 不解析 valuation、不寫 Mart、
不推 checkpoint。current Mart 先取最新 valuation date、同日再取最新 ledger version，
避免 historical replay 蓋掉較新的正常 valuation。dev deploy config 會移除既有固定
`VALUATION_DATE`。

新增四個共用既有 `janus-private-pipeline` Job 的 dev Scheduler config：weekday
07:40／11:00／14:00／21:30、`Asia/Taipei`，沿用
`janus-ingestion-scheduler` identity，僅要求該 Job 的 `roles/run.invoker`。套用腳本具
dev 與 explicit apply guard。

模型切換後已完成本機 targeted validation：47 tests passed、Git Bash `bash -n` 與
`git diff --check` 通過。既有 GCP dev project
`gen-lang-client-0593591102` 已部署 Cloud Build
`faf36436-1287-495a-a0e8-46f2fbc908de` 產出的 private-pipeline image
`sha256:e2b0a93023242e13f4c4578d953bf58ba8d14709f1c30b1f1cefd1aa3d1bc368`；Job
已移除固定 `VALUATION_DATE`，保留既有 service account／network／retry 設定。
四個 Scheduler 已套用且均為 `ENABLED`，target 都是同一個既有 Job；既有 Job 的
`roles/run.invoker` 已授予 `janus-ingestion-scheduler`。

GCP dev smoke execution `janus-private-pipeline-lw895` 以 `Completed=True`、
`succeededCount=1`、log `exit(0)` 完成，application log checkpoint=54；IAP 唯讀
聚合查詢顯示 pipeline checkpoint=54、change-log max=0、pending=0、owners=3、
ledger_events=0。這驗證了空 queue no-op 與新部署可正常啟動。瀏覽器交易入口可載入，
但本次 Google login popup 的 UI 控制逾時，因此本 checkpoint 不宣稱新建交易→批次
Mart→刪除的真人 browser E2E 已完成；既有 2026-09-05 完整交易 acceptance 證據仍
有效，後續只需重新執行該 browser flow 即可補齊本次 runtime change 的 live trade path。

最新驗證日期：2026-09-18

## WBS-8 ChatGPT MCP consent redirect defect acceptance（2026-09-17）

The consent response now keeps the existing restrictive CSP and changes only
`form-action` to `self https://chatgpt.com`; redirect validation and the three
read-only scopes are unchanged. Local targeted verification passed **33 tests**
(`tests/test_mcp_oauth.py`, `tests/test_mcp_adapter.py`, and
`tests/test_user_api.py`), plus Python compile and `git diff --check`.

The source archive was uploaded to the existing Cloud Build bucket by explicit
dev authorization. Cloud Build `715e6b3f-4d64-4a86-9200-b365eafeaabe` produced
image digest
`sha256:acda861018e33c2af30e0c14d80ed1b25df9f587c644c8590bca3445b68cfcc6`.
Cloud Run revisions `janus-api-mcp-csp-adapter` and
`janus-api-mcp-csp-oauth` are Ready, tagged `mcp-adapter`／`mcp-oauth`, and
receive 0% traffic; the service default remains on the existing candidate.

Tagged metadata/negative acceptance passed in Cloud Build
`24b32072-c56f-4695-b982-05d245430a60`: protected-resource and
authorization-server metadata, S256/none declarations, and OAuth negative
guards. Chrome browser acceptance then used the existing ChatGPT custom app
`Janus Dev Read-only v2`: Google callback → Janus consent → clicking `允許`
actually navigated to
`https://chatgpt.com/connector_platform_oauth_redirect` (the popup closed back
to ChatGPT). From the existing `janus-postgres-dev` VM through IAP, the
browser-returned code exchanged successfully and all three tools returned 200:
`janus_sources`, `janus_market_context`, and `janus_private_context`; the
private/market responses were bounded `status=missing` and sanitized.

No new GCP resource, IAM grant, service, or production traffic was created.

## WBS-6 ChatGPT MCP OAuth dev rollout acceptance（2026-09-17）

The existing `janus-api` revision `janus-api-mcp-oauth3-config` was deployed with
no production traffic and the `mcp-oauth` tag. API bundle version 16 contains
`google_user_client_secret` and `mcp_oauth_signing_key`; the explicit dev user
allowlist is `tommylin15@gmail.com`. PostgreSQL migration `026_mcp_oauth_codes`
was applied to the existing `janus-postgres-dev` VM using immutable image
`sha256:c635d2fd249cb9e0c66db313011bcd3bd52fd44f63be108bd868fd0683490733`.

GCP dev VM/IAP acceptance passed: protected-resource metadata 200,
authorization-server metadata 200, incomplete token exchange 400, and missing
S256 authorize request 400; a valid S256 request returned a Google upstream 302.
The exact Google callback is now
`https://mcp-oauth---janus-api-2oo7qbkd5q-uc.a.run.app/oauth/google/callback`;
configure it in the existing Google OAuth client before a browser login. MCP adapter implementation
is now complete; connector acceptance remains the next WBS.

## WBS-6 ChatGPT MCP adapter GCP dev rollout acceptance（2026-09-17）

The workspace source archive was uploaded to the existing Cloud Build bucket by
explicit user approval. Cloud Build `7d070e60-d8c1-4e7f-821f-5d8a54bd9196`
successfully built and pushed image digest
`sha256:a9672d6ddfa8d81a483ea257deaf707cd7576998729bad8f1d5492a61053be01`.
Cloud Run revision `janus-api-mcp-adapter3` is Ready, tagged `mcp-adapter`, and
serves 0% traffic. The OAuth PKCE fix uses the same image in revision
`janus-api-mcp-oauth4`, tagged `mcp-oauth`, also with 0% traffic.

From the existing `janus-postgres-dev` VM through IAP, the adapter tag returned
initialize 200, tools/list 200 with exactly three read-only tools and per-tool
OAuth scopes, and an unauthenticated tools/call 401 with the protected-resource
challenge. A temporary owner OAuth code exchanged for a Bearer token (200),
`janus_sources` returned three bounded sources (200), and an owner-scoped
`janus_private_context` trades read returned bounded `status=missing` (200) with
no `user_id` or `artifact_ref`. The fixture row was deleted and verified absent.
No production traffic or new paid GCP resource was created.

## WBS-8 ChatGPT MCP acceptance preflight — dev OAuth routing defect correction（2026-09-17）

The adapter tag initially advertised the untagged API issuer, while OAuth-enabled
revisions existed only behind tags. The dev deployment now pins
`MCP_RESOURCE_URL=https://mcp-adapter---janus-api-2oo7qbkd5q-uc.a.run.app/mcp`
and `MCP_OAUTH_ISSUER=https://mcp-oauth---janus-api-2oo7qbkd5q-uc.a.run.app`.
Revisions `janus-api-mcp-adapter6` and `janus-api-mcp-oauth6` are Ready, tagged,
and receive 0% traffic; the service default traffic remains unchanged. The
deploy script rejects untagged OAuth/resource values when OAuth is enabled.

GCP VM/IAP checks passed: protected-resource metadata 200 names the adapter tag
and OAuth tag; authorization-server metadata 200 advertises the tagged authorize
and token endpoints, `none` client authentication, all three read scopes, and
S256; authorize returns Google 302 with the tagged Google callback; token exchange
returns a resource-bound token; authenticated sources, market, and private calls
all return 200 with bounded sanitized results. The Google endpoint preflight
returned 302 without `redirect_uri_mismatch`. The existing ChatGPT custom app
`Janus Dev Read-only v2` is available in development mode and its browser OAuth
popup now completes through the tagged consent page to the ChatGPT callback;
tool discovery/UI invocation remains the only outstanding connector acceptance
item. No production traffic or new GCP resource was used.

## WBS-6 ChatGPT MCP adapter implementation checkpoint（2026-09-17）

The existing `janus-api` now exposes stateless `POST /mcp` JSON-RPC for
`initialize`, `ping`, `tools/list`, and authenticated `tools/call`. The three
read-only tools use per-tool OAuth scopes, token-subject owner binding, shared
bounded direct reads, sanitization, and no chat `context_ref` persistence.
Local targeted verification `python -m pytest -q tests/test_mcp_adapter.py
tests/test_mcp_oauth.py tests/test_user_api.py` passed **32 tests**; Python
compile, Git Bash `bash -n`, and `git diff --check` also passed. GCP dev
deployment and runtime acceptance are recorded above.

## Secret bundle recovery after accidental deletion（2026-09-19）

Audit Log recorded `google.cloud.secretmanager.v1.SecretManagerService.DeleteSecret`
for `projects/131494961796/secrets/janus-postgres-api-bundle` at
`2026-09-19T13:07:53.896564036Z`. The deleted container and its versions returned
`NOT_FOUND`; Secret Manager payload recovery was not available.

The same API secret name was recreated with enabled version 1. The payload was built
from the local OAuth Web client file plus newly generated rotated credentials and was
verified against all required API bundle fields without printing payload values. The
six PostgreSQL roles `janus_private_api`, `janus_private_pipeline`, `janus_catalog`,
`janus_web_control`, `janus_web_catalog`, and `janus_public_api` were rotated and
verified as non-privileged roles.

The existing provider bundle was read-modify-written with a new matching
`mcp_owner_signing_key` as enabled version 9; version 8 was disabled, not destroyed,
so the rotation remains reversible. API bundle Secret Manager accessor IAM was
restored for `janus-user-api` and `janus-private-pipeline`. Recovery validation found
`janus-api-00127-sqp` and `janus-agent-gateway-00044-jtn` Ready, and removed all
remote temporary credential files.

This recovery does not constitute MCP connector acceptance: `janus-api` still has
`MCP_OAUTH_ENABLED=false`. OAuth enablement, ChatGPT tool discovery, consent redirect,
and UI invocation remain the next acceptance slice.

## WBS-8 Pilot release baseline acceptance（2026-09-17）

The existing Mart pipeline registers a deterministic `material_change` baseline
from git SHA, immutable image digest, governance／prompt／schema／feature／signal
revisions, model／provider and source／config revision. The baseline ID is derived
from the lineage digest; PostgreSQL rejects conflicting re-registration, and the
Mart manifest／publication linkage rejects Core／Mart or baseline changes for an
existing execution. Artifact Registry retention was not changed.

Local targeted verification `python -m unittest tests/test_pilot_readiness.py`
passed **4 tests**. The existing `janus-postgres-dev` guard remained
`e2-micro`／30 GB `pd-standard`／private IP with no external IP. Its bounded
`pilot-readiness-acceptance.sql` passed migration `025_pilot_readiness`, lineage
relations／columns, role boundaries and transactional baseline registration; the
transaction ended with `ROLLBACK`, so no fixture row remained.

The existing `janus-intelligence-mart` Cloud Run Job is pinned to immutable image
digest `sha256:b497e6ee00792d0caf1f65584674f6bf5fa66ba2ed8facb3b7e392d9c002dd8c`
and carries `JANUS_GIT_SHA=b965410e3fb180a06d20728d3dad0be4306a2a79` plus the same
`JANUS_IMAGE_DIGEST` environment value. No production deployment or new paid GCP
resource was created.

## WBS-6 Pilot usefulness feedback acceptance（2026-09-17）

Local API／model tests `python -m pytest -q tests/test_user_api.py
tests/test_pilot_readiness.py`: **28 passed**. Flutter Cloud Build
`c83cab17-862f-44f9-b722-f57b701a0fb5`: **SUCCESS**, 8 widget tests passed,
analyze passed with existing info-level lints allowed, and release web build
passed. Feedback widget coverage checks loading the owner’s choice and saving a
new choice.

On existing `janus-postgres-dev`, a rollback-only transaction verified feedback
for two synthetic owners remains separate, an update increments its version,
feedback retains the target deterministic hash, and `janus_private_api` cannot
DELETE feedback. The transaction ended with `ROLLBACK`; no fixture data remains.
Migration `025_pilot_readiness` was already recorded by WBS-8 acceptance.

Additional targeted local verification: `python -m pytest -q tests/test_user_api.py`
passed **25 tests**; `bash -n` for the changed deployment and FinOps scripts,
Cloud Build YAML／cleanup JSON parsing, and `git diff --check` passed.

On 2026-09-16, both existing Artifact Registry repositories were updated to keep
two recent versions only for packages with the `api` prefix and one for other
packages; their existing tagged／untagged deletion rules were unchanged. Before
rollout, `janus-api-00077-6s9` received the `usefulness-rollback` tag without
changing its 100% traffic. Cloud Build `67c9b245-d4cf-462c-ab83-bd2f51c0ee48`
deployed candidate image digest
`sha256:f2a9059591cccbefa34e15376bf3f1b649676aa742ac4a2fe382fbc9cae63c23`.
The candidate revision `janus-api-useful-20260916-config` passed readiness and
initially served 0% traffic. Cloud Build `54735d34-6ac1-4e67-81c9-96df751060ff`
passed health, acceptance-page delivery, unauthenticated feedback／profile 401,
and the existing public API smoke assertions. The public Mart route returned the
published 2330 report from its publication index and immutable Iceberg snapshot
in Cloud Builds `de653d4c-07f4-4911-9299-bf45df7685eb` (candidate) and
`9f20b78a-f4c7-4d3b-acf7-8379813b91bd` (canonical URL). The candidate now serves
100% of canonical dev traffic; the previous revision remains tagged for
rollback. An initial Mart verifier invocation failed before making an HTTP
request because PowerShell combined multiple substitutions; the URL-only retry
passed.

After explicit action-time confirmation, the existing `Janus User Dev` OAuth
client was updated with the exact Authorized JavaScript origin
`https://janus-api-2oo7qbkd5q-uc.a.run.app`; redirect URIs and other OAuth
settings were unchanged. The real browser journey then authenticated a user,
loaded the published 2330 report (`analysis_execution_id`
`77777777-7777-4777-8777-777777777777`, `analysis_as_of=2026-09-10`), saved the
user-selected `neutral` feedback, and read it back successfully. The acceptance
page showed `passed: true`; feedback id was
`d5b87b7f-1d28-4a30-aeac-df1075ea082c`, version `1`, updated at
`2026-09-17T01:41:40.800708+00:00`, with deterministic analysis hash
`sha256:2f69320e883782d1345d1b0be6b47a885b25e5b1832c548d2fade2ad43554cff`.
No production deployment or new GCP resource was created.

## WBS-8 Pilot outcome collection acceptance（2026-09-16）

Pilot outcome collection is wired into the Mart processor. Each complete,
publishable symbol report creates immutable 5／20／60 pending rows keyed by
analysis identity and membership snapshot; later runs fill exact trading-day
outcomes with TAIEX-relative return, MFE／MAE, price／benchmark snapshots and
hashed provenance. Missing entry／benchmark data is excluded with a reason;
insufficient future rows remain pending. Core ready events freeze the
analysis-as-of scope and membership used for the report, so outcome evaluation
does not backfill historical samples from the current watchlist.

Local verification: `python -m unittest tests.test_pilot_readiness` **4 passed**;
Python compile and `git diff --check` passed.

GCP dev acceptance on existing `janus-postgres-dev` passed migration marker,
lineage columns, outcome／feedback relations, role privilege boundaries and
baseline registration. The acceptance transaction ended with `ROLLBACK`; the
two temporary SQL files were removed. No production deployment or new paid
resource was created.

The existing `janus-intelligence-mart` Cloud Run Job was then updated to
immutable digest
`sha256:b497e6ee00792d0caf1f65584674f6bf5fa66ba2ed8facb3b7e392d9c002dd8c`
by Cloud Build `727f5730-4baa-458f-a33a-655ccc32f329`; bounded smoke execution
`janus-intelligence-mart-k98dm` completed successfully. The queue was empty,
so the dev database has no baseline-linked reports or outcome rows yet; this is
recorded as runtime-ready evidence, with collection beginning on the next real
publishable report rather than fabricating a sample.

## WBS-7 Pilot ledger durability acceptance（2026-09-16）

既有 `janus-postgres-dev` 已啟用每日 bounded logical backup timer；既有 Private GCS
bucket 的 `pilot-ledger-backups/` managed folder 提供 prefix-isolated VM objectAdmin
與 Cloud Build objectViewer，daily retention 為 14、monthly checkpoint retention 為 6。
VM 維持 private IP／Free Tier machine 與既有 persistent disk；本次僅修正已核准的
`devstorage.read_write` OAuth scope，未建立新 VM、disk、snapshot、Cloud SQL、HA 或 replica。

2026-09-16 UTC backup evidence：owners=2、ledger_events=0、compressed dump
161278 bytes、projected retention 3225560 bytes；daily／monthly object count 各 1。
Cloud Build isolated restore `b12d64a5-dab9-4aef-9853-f06324a015d3` SUCCESS，使用 pinned
PostgreSQL image、`--network none` 與 tmpfs；restore checks 為 `t`，owners=2、ledger_events=0、
owner boundary、latest ledger versions、reversal／replacement correction links 均 valid，
credential-shaped columns=0。

本機驗證：durability shell `bash -n`、Cloud Build YAML parse、`tests/test_pilot_readiness.py`
4 passed、`git diff --check`。

## Artifact Registry／Cloud Run image cleanup repair（2026-09-14）

既有 `janus-api` revision 曾指向已不存在的
`janusai-poc/api@sha256:5de7428d15c2aebdf5757739c73ee587a97039936287d78eb397ad8e053d21b8`；
該 digest 由 build `348ba66d-2015-4faa-8b59-41424ed409f7` 產生，後續同 tag 的
build `194841bf-7b5c-4d6c-a2f1-ad780749acf9` 產生現存的
`sha256:058d442f239b8a757c6321f1638b653930fbbfe014943b177cd8a01d92fb9939`。
`janus-api` 已切換至後者，revision `janus-api-00077-6s9` 的 Ready、ConfigurationsReady
與 RoutesReady 均為 True。

依明確 dev cleanup 授權刪除無 active Cloud Run／VM 引用的三個 image：
`janusai-poc/mcp-acceptance@sha256:0dab19f8e48b92ba303a1d225d08bf39f78789f9805c90ae3be4e799d2460624`、
`janusai-poc/web@sha256:064327b47d334337e169cd5a3a0c72e82879356f739e6dda992fab28e6c5c672`、
`janusai-poc/janus-postgres@sha256:8f2a6bf9b77c5e16b630544007c98a7944caba37cdbf93e4a83bd6889d929b9d`。
兩個 Artifact Registry repository 的 cleanup policy 維持每個 package 最新 1 版、dry-run disabled；
因此不保留 rollback image，未來同一 package 若先產生新 image 而尚未同步更新所有 workload，仍可能重現
active digest 被清理的風險。`janus-postgres/postgres` 與 `janus-postgres-api-bundle` 14／15 版未修改。

## WBS-6 Governance typed editing（2026-09-13）

Admin 已提供 policy governance 的 typed read／diff／save／history API 與 UI。欄位只接受
既定的 role weights、blocking policy、deterministic constants 與 completeness gate；群組
驗證失敗即拒絕，diff 只回傳 bounded path changes。每次儲存要求 reason、status 與
expected version，控制面以原子版本條件更新並追加 immutable audit history；衝突回傳
409，執行流程只讀取已提交 revision。

本機驗證：Admin／FastAPI／PostgreSQL contract pytest **36 passed**，Vitest **20 passed**，
TypeScript 與 ESLint 通過；尚未部署或進行新的 GCP dev acceptance。

## WBS-7 security／observability／FinOps acceptance（2026-09-13）

WBS-7.1～7.4 程式已完成：runtime service-account 與 bounded scaling 寫入 dev deploy；
configure path 會移除 Secret bundle 的 legacy `web-runtime` consumer；四個 dev bucket 共用 noncurrent-version
lifecycle；`security-finops-dev.sh` 提供 guarded configure、read-only verify 與 bounded
monthly resource report。單一 320 TWD notification budget 使用 10%／50%／100% current-spend
threshold，對應 32／160／320 TWD；budget 不是 spending cap。Free Tier PostgreSQL 不建立付費
snapshot／PD backup／HA／replica；Pilot ledger durability 另採 bounded `pg_dump → restricted
Private GCS`，驗收仍要求 PD snapshot 為空。未建立 BigQuery billing export。

Observability 已補 API family request ID／duration SLI、Ingestion execution trace 傳遞、
Job duration／retry／publication counts、無原始 exception 的 bounded failure taxonomy、
source health latest expected／received semantics、Admin aggregate coverage／freshness／cache age／
schema drift，以及 execution → same-trace executions → Core snapshot／Mart report lineage。

本機驗證：targeted pytest **57 passed**、Vitest **20 passed**、TypeScript、ESLint、四個
GCP shell scripts 的 `bash -n` 與 `git diff --check` 通過；Flutter SDK 不在本機環境，未以
本機替代 Flutter acceptance。GCP dev `security-finops-dev.sh verify` 通過 IAM、secrets、
無 user-managed key、network、Cloud Run scaling、GCS lifecycle、Artifact cleanup、禁止
scanning API、PostgreSQL private IP／IAP、無 snapshot 與 320 TWD budget guard。

既有 dev 設定已套用，並由 Cloud Build 建置／部署 `janus-private-pipeline`、`janus-api`、
`janus-ingestion-core`、`janus-intelligence-mart`，共用 tag `wbs7-20260913`；API revision
為 `janus-api-00073-bv9`，後續 security configure revision 為 `janus-api-00074-xxj`。
Cloud Build public API runtime acceptance `1d1ec15c-280b-48ec-afe7-ac8a6b007737` SUCCESS，
驗證 health、404、waiting／publishable、401 boundary 與 redaction forbidden fields。
FinOps budget ID 為 `3a2b9ce0-e903-4094-8ce5-179760eb23e7`。完整 GCP report 的 GCS size
query 以 bounded timeout 保護；實際 billed spend 仍以 Cloud Billing 為準。

## Sol API policy closeout（2026-09-13）

Public policy slice 已完成並部署既有 GCP dev `janus-api`；最終 revision
`janus-api-00070-rvf`（image digest
`sha256:f7c629c71883691148f023b57d702fc021e25911a31ff6e5c3a93173b9557387`）。
Migration `023_public_stock_index` 已套用至既有 `janus-postgres-dev`；SQL acceptance
確認 migration marker 存在、`janus_public_api` 無 `control` schema USAGE、只能 SELECT
publication enabled-stock view，且 view 可查詢。Public runtime 維持 bounded catalog pool、
單一序列化 publication connection、read-only transaction 與 5 秒 statement timeout。

本機 public／runtime／role／user targeted tests 為 **40 passed**，Git Bash `bash -n` 與
`git diff --check` 通過。Cloud Build public API acceptance
`28887ea1-b194-4d95-ab03-63fdebf5609a` 通過 404／waiting／fail-closed auth boundary／
redaction probes；完整 token-savior pytest Cloud Build
`acfeaf2d-deb8-43d5-b5a1-c7749ae8efcf` 為 **3176 passed／5 skipped**。

本切片的 rate-limit／audit policy 已在後續 WBS-6 gate 完成；PostgreSQL
pool exhaustion、restart/reconnect、migration rollback 深測亦已於既有 GCP dev 完成。

## WBS-6 router／PostgreSQL／Flutter／Iceberg acceptance（2026-09-13）

程式已補齊 router-family 固定視窗 rate limit、無 query／token／body 的結構化 request
audit、public typed response，以及 private／admin 分離的 OpenAPI response boundary。
Public publication connection 遇 SQLSTATE `08`／closed connection 時只重連重試一次；
migration 023 改為單一 transaction。GCP dev 驗收腳本另檢查 Cloud Run runtime service
account／anonymous invoker 邊界、PostgreSQL role isolation、publication view/index regression、
失敗 transaction rollback、並行 pool 壓力與 VM restart 後 API reconnect。

Flutter 已加入同日 Today sections、partial 提示、StockHealthCard 圓環與 blocked 隱藏、
screening 分流、關注股個股深度頁、預設收合的 Kline／metrics／五角色／provenance，及
phone／tablet NavigationBar、desktop NavigationRail。App 只呈現後端 Mart 分數與損益。
Iceberg 驗收沿用既有 additive evolution／field ID／old snapshot、incompatible type
rollback 與 Mart replay snapshot idempotency tests，並新增 retry exhaustion fail-closed
case。

依使用者 gate，換模後已依序完成 targeted pytest／完整 pytest、Flutter Cloud Build、API
Cloud Build 與 dev deploy、public API acceptance，以及
`ALLOW_DEV_POSTGRES_RESTART=true scripts/gcp/verify-api-policy-dev.sh` 的既有 dev VM
深測：

- 本機 targeted backend／API／role／runtime／Iceberg tests：**40 passed**；
  `git diff --check` 與 Git Bash `bash -n` 通過。
- `token-savior` 完整 pytest 於 GCP Cloud Build `acfeaf2d-deb8-43d5-b5a1-c7749ae8efcf`：
  **3176 passed／5 skipped**。
- Flutter Cloud Build `edaad569-2c5b-4b7d-a93a-e1cc178cd9e6`：analyze 無 error、
  **6 widget tests passed**、phone／tablet／desktop responsive 與 release web build 通過；
  僅有既存 info-level lint notices，且本機沒有 Flutter SDK。
- Public API acceptance Cloud Build `28887ea1-b194-4d95-ab03-63fdebf5609a` 通過。
  最終 API Cloud Build `aea710f6-cda7-44dd-8816-1e80e3ffe23b` 部署至既有
  `janus-api-00070-rvf`，image digest 為
  `sha256:f7c629c71883691148f023b57d702fc021e25911a31ff6e5c3a93173b9557387`。
  Admin audit probe request ID `7425a207-ddef-4650-91a3-7c96a2bb6028` 在 Cloud Run
  log 出現 safe audit line，query secret 未出現。
- GCP dev PostgreSQL 深測通過：role isolation、publication view/index regression、
  transaction rollback、24 並行 bounded-pool requests，以及 VM reset 後 public API
  reconnect。無 production deploy、無新付費 GCP resource、無 commit／push。

## WBS-6 public runtime／跨系統 checkpoint（2026-09-13）

本機 backend `python -m pytest tests -q` 為 **205 passed**；新增 public endpoint
contract tests 與既有 API／Admin targeted tests 合計 **26 passed**。前端
`npm.cmd run test:unit` 為 **20 passed**，Admin Playwright 為 **9 passed**，
`npm.cmd run build`（TypeScript、ESLint、static web artifact）通過。新增 public
endpoint family 使用既有唯讀 public／Core service，不觸發 scraper、Agent 或 LLM；
空 Core 結果回傳 `waiting`。User App 已加入 Material 3「今日」入口與
`StockHealthCard`，但目前工作站沒有 Flutter／Dart SDK，尚未宣稱 analyze／widget
驗證完成。

完整 `token-savior` suite 改於 GCP dev Cloud Build 執行，build
`18063b1d-897c-4ebf-afdb-e6ac8ab08c1a` 成功（4m49s）；驗收設定固定從 submodule
source root 執行、在 Linux 正規化 hooks line endings、安裝 `memory-vector` 並預熱
FastEmbed，避免 monorepo `scripts` namespace collision。Report block／unblock
publication mutation、WSGI routes 的 FastAPI 遷移與 Flutter SDK 驗收已完成；既有
`janus-web` dev service 已依明確授權刪除；未部署
production、未建立付費 GCP 資源。

### 2026-09-13 WBS-6 closeout slice

- `publication.review_mart_report` migration `022` performs block/unblock mutation under the publication owner, while `AdminService.review_mart_report` records the reason and actor in the same control-plane transaction.
- FastAPI now serves the Admin API and Admin static entrypoint; the dev workflow no longer deploys `janus-web` WSGI and targets `janus-api` instead. The old WSGI module remains only as a test compatibility adapter, and the existing `janus-web` dev service was deleted after explicit approval.
- Flutter phone/tablet/desktop widget coverage is in `apps/user_app/test/widget_test.dart`; `scripts/gcp/cloudbuild-flutter-verify.yaml` runs `pub get`, `analyze`, widget tests, and a release web build because the local machine has no Flutter SDK.
- Flutter Cloud Build `305cb017-bf55-4461-b039-4fca07c95f8c` passed analyze, four widget tests, responsive surfaces, temporary web platform generation, and release web build.
- Existing dev PostgreSQL received immutable image `us-central1-docker.pkg.dev/gen-lang-client-0593591102/janus-postgres/postgres@sha256:87ce1db970c44433f8e3c1cd53f756e3a6c4aae629b620f4c95520c240169568`; migration 022 and role/settings acceptance passed.
- Final `janus-api` revision is `janus-api-00060-bs4`, image digest `sha256:a0206bc153d3530a4148bb061020ab2491e4fac300bee03613d68b97a21c65f0`; GCP public API acceptance `53473f6f-1870-4f91-add7-8aea9e80f055` passed. Dev has no materialized `events` table, so that endpoint returns explicit safe `503 public data unavailable`.

## Secret bundle consolidation checkpoint（未驗證）

已取得人工安全 gate，同意以較大的 workload IAM blast radius 換取較少的 Secret
版本與管理項目。目標由 8 個 container 收斂為 `janus-postgres-api-bundle`（API／Web／
Pipeline）、`janus-agent-provider-bundle`（Agent／Mart／Ingestion）及
`janus-codex-owners-bundle`（owner UUID keyed auth）三個。2026-09-11 唯讀盤點顯示
現有 6 個 enabled versions；若同一 billing account 沒有其他 project 的 active
versions，依 6-version 免費額度，當下 active-version 儲存費預估為 US$0。收斂主要
降低未來 version 成本與操作負擔，不代表目前已有節費。

程式、向後相容欄位 loader、部署順序與 phased GCP migration／cleanup 腳本已修改；
targeted tests、TypeScript build、bash syntax、Cloud Build contract 與三個既有 Job
smoke 均已通過。GCP prepare／部署與六個 legacy Secret cleanup 已完成；目前只剩
三個 Secret container、兩個 enabled versions。Codex A/B live auth isolation 尚待
人工建立 owner auth entry。

## WBS-3-ADMIN-POLISH 驗證（2026-09-11）

Admin status／execution item 改為安全結構化欄表格，支援 sticky header、排序、篩選、分頁、欄位顯示與按需子表；source health／collection config 讀取改為 repository-level bounded keyset cursor。股票刪除 guard 現在會檢查 collection config、execution、market、report、fundamental 五類引用，提供結構化 references endpoint、409 引用摘要與 UI 阻擋原因。完整 `python -m pytest -q tests` 為 154 passed，`npm.cmd run test:unit` 為 18 passed，Admin Playwright 為 9 passed。`npm.cmd run build` 的 typecheck 通過，但 lint 被既有 `.tmp` urllib3 worker 與 `services/agent-gateway/dist` 生成檔 56 個 `no-undef` 阻擋；未修改或清理該生成物。未部署 production、未建立付費資源。

最新完整本機驗證：本次 private-pipeline bundle loader targeted tests 為 6 passed；
`git diff --check` passed。WSL／Windows bash 在本環境回傳 `E_ACCESSDENIED`，因此
未能執行 `bash -n`；未以此宣稱 shell syntax 已驗證。

## WBS-3-ACCEPTANCE GCP dev checkpoint（2026-09-11）

唯讀 baseline：project `gen-lang-client-0593591102`／`us-central1`；唯一 Compute
instance `janus-postgres-dev` 為 `e2-micro`、30 GB `pd-standard`、private IP
`10.42.0.5`、無 external IP；無 Cloud Router／NAT／snapshot／VPC connector。Direct
VPC subnet `10.42.0.0/24` 的 firewall 只允許 target tag `janus-postgres-db` 的
`5432`。Cloud Billing API 已啟用；project 已綁定 `open=true` 的 billing account，
現有 budget `tommyGCP_limitAmt` 為 TWD 100。Google API 沒有直接回報此帳戶的
e2-micro／region 剩餘資格沒有逐項額度 API；依本輪驗收判定，billing／Free Tier
dev guard **通過**。此判定不等同 GCP 對帳單為 US$0 的保證。

PostgreSQL acceptance：兩個並行 transaction 對固定 rollback fixture 執行
`FOR UPDATE SKIP LOCKED`，僅一個 worker claim 成功，fixture 已刪除；35 個短暫連線
中 30 成功、5 個收到 `too many clients already`，釋放後 probe 成功。VM reset
後回到 `RUNNING`，`pg_isready` accepting connections，控制面保留 18 executions。

Secret runtime 修正：GCP metadata 重讀確認目前 3 個 Secret，詳見
[`doc/secret_list.md`](../secret_list.md)。ingestion／mart／private-pipeline 已
分別切換至既有 bundle；private-pipeline API image build
`b7d47342-906c-44c0-8eea-cceda10898c7` SUCCESS，digest
`sha256:dcfe5857e6cd95ce6d576a8394ee0f061530e6e03f6ff756115e5b8f1b28a4be`。
Bundle runtime probes：ingestion idle `janus-ingestion-core-2zhhj`、完整 smoke
`janus-ingestion-core-n8mh2`、mart `janus-intelligence-mart-j2hgn`、private
pipeline `janus-private-pipeline-rvmct` 均 Completed=True；完整 ingestion smoke
為 5 檔、12 items、0 failed、1 個合法 sparse empty。

Canary 證據：既有三個成功 execution（`3fb8c93e...`、`29cabcc3...`、
`89a60703...`）各為 5 檔、12 items、0 failed；bundle 修正後手動觸發既有
Scheduler 的 Cloud Run execution `janus-ingestion-core-j5qbv` 及 control execution
`53d7b34d-85a1-45af-ae1a-3ce6245622ee` 亦成功，5 檔、12 items、0 failed、1 個
合法 sparse empty、5 個 source IDs。這次是 scheduler smoke，不計入連續 3 個交易日；
2026-09-11 07:30（Asia/Taipei）的自動排程 execution
`janus-ingestion-core-4zft5` 成功完成資料日 2026-09-10，control execution
`aa86076c-942e-4f2a-8fa9-2455f3753b5f` 為 5 檔、expected 12 items、received 12、
missing 0、158 received rows、0 failed、0 retries，8 個核准 source／dataset health
均為 `success`；Core 為
143 created、0 reused、8 updated。單次 task 約 4 分 31 秒，既有 job 維持 1 task、
1 vCPU、1 GiB、900 秒 timeout、maxRetries 1，未建立或擴大任何資源。post-fix scheduled
canary 目前為 **2/3**：第二個交易日為 2026-09-12（Asia/Taipei），Scheduler
execution `janus-ingestion-core-824gh` 於 2026-09-11 23:33:53Z 成功，對應 control
execution `9a8086c2-66d5-4be5-88c1-c2e35f19bcf3` 於 23:33:50Z 成功、0 retries；資料日
為 2026-09-11。後續只計 distinct 有效資料日 2026-09-14，對應 Scheduler 執行日
2026-09-15，週末重複資料日不重複計數。三日完成後再彙整
expected／received／missing、Core hash/date/null profile 與完整成本摘要。

使用者要求下於 2026-09-14 05:52Z 手動觸發既有 `janus-ingestion-daily` Scheduler；
Cloud Run execution `janus-ingestion-core-29d2f` 於 05:55Z 成功，5 檔仍為
`1102／2327／2330／2381／4958`，control execution
`31233b8b-6882-436e-ba4a-95a92d938803`，資料日仍為 2026-09-11，`failed=0`、
`empty=0`、`requested=8`、`skipped=12`，全部為既有 fresh data。這是正式排程路徑的
成功 smoke／replay，不新增 distinct trading day，故 canary 維持 **2/3**；未觸發全市場
抓取，也未修改 Scheduler 或 job 設定。

## WBS-3-ACCEPTANCE 完成（2026-09-15）

第三個 distinct trading day 由既有 `janus-ingestion-daily` 自動排程完成：資料日
`2026-09-14`（Asia/Taipei），Cloud Run execution `janus-ingestion-core-c995d`，
control execution `3ee7a128-3a69-4704-8563-2def733032ad`。Scheduler 維持
`ENABLED`、`30 7 * * *`、`Asia/Taipei`；execution 於 `2026-09-14T23:30:03Z`
建立、`2026-09-14T23:32:45Z` 成功完成，`Completed=True`、`succeededCount=1`。

固定 5 檔為 `1102`／`2327`／`2330`／`2381`／`4958`。8 個核准 source／dataset
work items 的摘要為 `requested=8`、`staged=7`、`skipped=5`、`failed=0`、
`empty=0`；5 個 FinMind symbol 因 `official_source_fresh` 合法跳過，故
`expected=12`、`received=12`、`missing=0`。三日 canary 現為 **3/3**。
8 個核准 source／dataset 狀態均為可接受成功：`taiex`、`tpex-benchmark`、
`twse-valuation`、`twse-institutional`、`mops`、`twse-events`、
`twse-market-activity` 實際成功寫入；`finmind` 以 official-source-fresh cache hit
成功略過，沒有 failed／unavailable 狀態。

Core ready event／snapshot 保存 `as_of=2026-09-14`、`row_count=1982`、
`coreSnapshotHash=sha256:64cb0ef47c9102cf0b8c689e9b709acbe018919105beaef6eaedfec929638f98`、
snapshot id `sha256:9834993558b99526296cdd6dece75ff654723a8136aac0b15967971f60c7a642`。
Snapshot 列出 6 個 incremental Core table 的 row counts；本次沒有 DQ failure 或
quarantine，且 artifact 沒有 OHLCV `null_profile` 欄位（本次未選取 OHLCV dataset）。

第三次沿用 immutable image
`ingestion-core@sha256:c5fc66a0ed0d395d07b66b96e6baedcf9739ff94328cb5eb4504ddd2889849f1`；
job 維持 1 task、1 vCPU、1 GiB、1800 秒 timeout、maxRetries 1，execution 約
2 分 22.75 秒。未建立或擴大 GCP 資源；該次 execution 未觸發全市場抓取，後續
full enabled market bounded acceptance 見下節。

## WBS-3 full enabled market bounded acceptance（2026-09-15）

使用者指定「full enabled market」以當時 `control.stock_master` 的 5 檔 enabled universe
為範圍：`1102`／`2327`／`2330`／`2381`／`4958`。既有 market-scope config
`full-market-acceptance` 複用 8 個核准 source／dataset，未設定 symbol allowlist，
由 PostgreSQL market-wide fallback 一次解析 enabled symbols，再由 source adapter 做
symbol fan-out；沒有逐檔重複發出 market-scope request。驗收用 bounded config 已於完成後
停用（`enabled=false`、`collection_enabled=false`、`analysis_enabled=false`），保留 audit
record，避免意外重跑。

第一次執行 `janus-ingestion-core-rpwnz` 立即以 `UNDEFINEDTABLE` 失敗；root cause 是
PostgreSQL fallback query 使用 `s.enabled` 卻未宣告 `s` alias。已在共用
`config_symbols()` 修正為 `FROM control.stock_master s`，並新增最小 repository query
assertion；`python -m pytest -q tests/test_postgres_admin_cursor.py` 為 **6 passed**，
`git diff --check` 通過。修正後 Cloud Build
`8f9e9ca1-8373-4fdb-af37-ff263f68528c` SUCCESS，immutable image
`ingestion-core@sha256:248c170a8a1fe8422dd95ab078eb8d7259ab4ea22b9a86e32978c86d547bead2`。

以 `FORCE_REFRESH=true` 在既有 dev job 完成實抓：Cloud Run execution
`janus-ingestion-core-tf66g` SUCCESS，約 4 分 42.23 秒；control execution
`2191139b-2dab-4bf4-886b-12735e6cdc02` 狀態 `succeeded`。`as_of=2026-09-14`，
`requested=8`、`staged=11`、`skipped=0`、`failed=0`、`empty=1`；唯一 empty 是
FinMind financials 的 `2381`，屬合法 empty。5 檔 fan-out 與 8 個 source／dataset
work items 全部有結果，故 `expected=12`、`received=12`、`missing=0`、`failed=0`。

Core ready event／snapshot：`row_count=1982`、
`coreSnapshotHash=sha256:85ee010136df0bc8f4d98f8d90a18180b9fe8eecba10d07779b76881b5bb5a2f`、
snapshot id `sha256:8adc893ae302055caa227db8b22551cacdd13d59ebd938d84631af3c0aeafee3`，
object `gs://gen-lang-client-0593591102-dev-core/executions/2191139b-2dab-4bf4-886b-12735e6cdc02/core-snapshot.json`。
6 個 Core Iceberg table rows 為 benchmark 42、events 16、financials 1632、
institutional 120、market_activity 132、valuation 40；`analysis_enabled=false`，
因此 `mart_trigger.status=not_required`。本 config 未選 OHLCV，故不宣稱 OHLCV
`null_profile` 驗收。既有 job 維持 1 task、1 parallelism、1 vCPU、1 GiB、1800 秒
timeout、maxRetries 1；未建立或擴大 GCP 資源，也未呼叫 Artifact Analysis／Scanning。

## OHLCV runtime 接入與 5 檔 dev 驗收 checkpoint（2026-09-15）

已將既有 TWSE／TPEx OHLCV adapters 接入 ingestion runtime registry；symbol-scoped
adapter 以每個 symbol fan-out，只有明確 `INGESTION_DATASETS=twse-ohlcv`／`tpex-ohlcv`
才會執行，既有 `first-batch` 預設排程仍固定 8 個原有 dataset。OHLCV rows 先經既有
`validate_ohlcv`，違規資料寫入 Stage quarantine，Core writer 現支援
`core.ohlcv_v1`，summary 保存 accepted／quarantined／warnings／null_profile。TWSE
成交量按官方「成交股數」保存，不再乘以 1,000；來源未提供漲跌百分比時保留 null，避免
把成交筆數誤當百分比。

本機 targeted tests：
`PYTHONPATH=jobs/ingestion-core;. python -m pytest -q tests/stage_core_tests/test_first_batch_sources.py tests/stage_core_tests/test_stage_core.py tests/stage_core_tests/test_2330_closed_loop.py`
為 **27 passed**；`git diff --check` 通過。Cloud Build
`16962da0-7706-4a08-83aa-1348404d6d45` SUCCESS，既有 `janus-ingestion-core` dev job
使用 immutable image
`ingestion-core@sha256:a8953df49f42a9324adeb3eb7cb622de43e75f7fad56763ce11d2bb2beb75dbc`。

Bounded config `ohlcv-acceptance`（TWSE、market-wide、analysis disabled、無 symbol
allowlist）第一次實抓 execution `janus-ingestion-core-x2jh8` 因 stale enabled
`2381` 回傳 0 rows 而阻擋；control item 為 `VALUEERROR`／`failed`。已在既有 dev
`stock_master` 將 `2381` 設為 `enabled=false`、`listing_status=delisted`，並寫入
`stock_disable` audit。這使原先宣告的 5 檔集合收斂為 4 檔有效 enabled universe：
`1102`／`2327`／`2330`／`4958`。

停用 stale symbol 後重跑：Cloud Run execution `janus-ingestion-core-rwt4w`、control
execution `cffec813-2054-4a2d-a4b4-05846f5d8c46` 均成功。4 個 symbol item 各收到
10 rows，合計 `staged=4`、`accepted=40`、`empty=0`、`failed=0`、`quarantined=0`；
每檔 `change_percent` 的 10 筆為預期 null（官方 OHLCV response 未提供該欄），其餘
OHLCV 欄位 null count 為 0。`core.ohlcv_v1` snapshot row count 為 40，metadata
位於 `gs://gen-lang-client-0593591102-dev-core/warehouse/ohlcv_v1/metadata/00005-f4b9a2a5-1a22-4093-b742-661560f5aac3.metadata.json`。
驗收完成後 `ohlcv-acceptance` 已停用並寫入 `acceptance_complete` audit；Scheduler
job 的預設 8 個 dataset 未改動。原始 5 檔中的 stale `2381` 不再被強行納入，故本次
有效 acceptance 是 4 檔，而非虛報 5 檔成功。

同日 replay checkpoint：以 `INGESTION_DATE=2026-09-14`、`FORCE_REFRESH=true` 重抓，
Cloud Run execution `janus-ingestion-core-scdrp`、control execution
`ecd1aef9-c6ec-4e03-ab31-b83506a31cc2` 成功；`core_created=0`、`core_reused=40`、
`core_updated=0`，`core.ohlcv_v1` 維持 40 rows 與相同 snapshot id，證明 natural-key
replay 冪等。每檔仍 accepted 10 rows；每檔另隔離 1 筆 `FUTURE_DATE`／`DATE_ORDER`
（合計 4 筆）至 Stage quarantine，未寫入 Core。runtime application duration 為
14,795 ms；既有 job bounded 為 1 task／1 parallelism／1 vCPU／1 GiB／1800 秒、
maxRetries=1。此次 replay Stage prefix 為 21 objects／32,394 bytes，Core execution
prefix 為 437 bytes；未建立新 GCP 資源。先前 `2381` 空回導致 collection failed 的
負向 execution 亦證明缺檔不會被誤標成功。驗收 config 已再次停用；下一切片才是
`WBS-5-SUPPLY-INTELLIGENCE-PLANNING`。

## WBS-5 feature／publication pipeline GCP dev acceptance（2026-09-12）

WBS-5 的 replay、blocked case 與 Iceberg object listing 已完成。Immutable Core
fixture `wbs5-core-acceptance-20260911` 通過同一 execution replay：Cloud Run
execution `janus-intelligence-mart-ncx8d` 成功，原 execution 的 publication
index 維持 1 筆、Iceberg snapshot 未新增，outbox 維持 1 筆。`manual_review_required`
fixture `99999999-9999-4999-8999-999999999999` 由 execution
`janus-intelligence-mart-n4qbr` 成功處理，結果為 `review_required`／`blocked`，
`ready_at` 為 NULL，不進 `publishable_mart_reports`。

Dev Mart bucket `gen-lang-client-0593591102-dev-mart` wildcard listing 共 62 個
objects，涵蓋 11 個 public Iceberg v2 tables：screening、core alpha、risk portfolio、
alternative sentiment、scoped analysis、market regime、sector rotation、topic trends、
candidate health、daily brief、LLM narratives。WBS-3 acceptance 仍維持暫停 2/3，
本節不宣告 WBS-3 結案。

Negative VPC／identity evidence：workstation 對 private IP `10.42.0.5:5432`
的 TCP probe 為 `False`；暫時移除 PostgreSQL VM 的 `janus-postgres-db` target tag
後，Cloud Run execution `janus-ingestion-core-kjsl4` 已確認 `Started=True` 並以
exit code 1 結束，tag 隨即恢復且 VM 仍 `RUNNING`。`janus-private-pipeline` identity
在 ingestion bundle IAM policy 中沒有 `secretAccessor`。第一次未等 task 啟動即恢復
tag 的 execution `janus-ingestion-core-2hz9h` 不列為負向證據。

### WBS-5 integration／Gemini dev checkpoint（2026-09-12）

Migration 019 已套用至既有 PostgreSQL dev VM；`core.dataset.ready.v1` 只在 Core
commit 成功時入庫，ingestion failed／partial 不入 queue，重送以 Core execution
唯一鍵去重。正確資料 scope 的 ingestion execution `janus-ingestion-core-dnpjd`
觸發 Mart execution `janus-intelligence-mart-8g6qm`，queue
`bd91a12c-ef28-52da-8a4e-1b12cfb45e7c` 成功，產出 market／industry／5 symbol 共 7
份 report。`4ffc17cd-8fb7-5a20-9f39-2f8d3e6422c4` 與
`5ffc17cd-8fb7-5a20-9f39-2f8d3e6422c4` 以相同 Core snapshot 重建，12 份對應
report 的 deterministic hash 全數一致，未重新計算上游分數。

Gemini dev-only fault probes 已通過：quota（429）、provider unavailable（503）、
invalid structured output（200）均保留 deterministic report、queue terminal
`succeeded`，且不寫 placeholder narrative，publication 維持 `blocked`。既有
`JANUS_MART_POSTGRES_BUNDLE` 內的 `gemini_api_key` 已由 Mart runtime 安全映射到
`GEMINI_API_KEY`；真實 live probe `janus-intelligence-mart-9dms6` 確實送出 7 個
scope，但因 REST schema enum 使用小寫而全數回 400 `provider_error`。已修正 request
時的 schema enum 正規化並部署 image digest
`sha256:7355c3a01be5d3e40129a02a60ea9ef5261e90e78b864229d3133bcd6c397623`。新一輪
3-scope live probe `janus-intelligence-mart-ql998`（market／industry／symbol，各 1
次）仍回 400 `provider_error`，queue 與 publication 依然 fail-closed；目前需
保留 provider response body 的安全診斷或確認 bundle key 在 Gemini project 的有效性。
Admin／真人 watchlist flow 仍待 GCP dev authenticated browser session；本機 proxy
不列為驗收證據。期間發現既有 `janus-api` 指向已銷毀的 Secret version 7，已改綁
現有 enabled version 14，重建缺失的 API image（Cloud Build
`bc77ff1e-d19f-4f19-aeb5-d4013cccfa6a`）並部署 revision `janus-api-00052-468`；
直接 GCP URL 現回 401（服務已啟動，僅缺 Google user token）。

Gemini runtime 現已在未指定 `GEMINI_MODEL` 時，每日首次 process 呼叫查詢官方
`models` 清單，依 `gemini-3.8-flash`、`gemini-3.7-flash`、`gemini-3.6-flash`、
`gemini-3.5-flash` 的 Stable 優先序取前三個可用模型並逐一 fallback；明確指定
`GEMINI_MODEL` 時維持單模型模式。模型探索結果按日快取，paid gate 與 scope／次數
上限仍由執行設定控制。

自動選模 live probe `janus-intelligence-mart-cjlpq`（1 個 symbol scope、最多 3 次）
實際依序嘗試 `gemini-3.8-flash`、`gemini-3.7-flash`、`gemini-3.6-flash`，三次均回
400 `provider_error`；queue `succeeded`、report `blocked` 且無 placeholder。模型
fallback 規則已由 GCP dev execution 證實，provider 400 的 key／project 或 request
詳情仍待確認。

### WBS-5 persisted consumer／Admin Analysis authenticated acceptance（2026-09-12）

本機 targeted Python `70 passed`、Admin Vitest `3 passed`、Admin Playwright `9
passed`；Python／JavaScript syntax 與 `git diff --check` 通過。既有 GCP dev project
`gen-lang-client-0593591102` 的 Mart、ingestion-core 與 Web image 已部署；Web
revision `janus-web-00073-lw9`，Web digest
`sha256:da0222d465cff05780064ff5b9876f4478228f1c2acfd37d17248120e40979fa`，Mart
digest `sha256:700ab9d6247a84338ed1302ac476a8d640b2deba91e777a0af749b6d7a424db3`，
ingestion digest `sha256:dacfa965dbc93005942c2190a7531ba4343f3967299c8bf1df5f459b22ef4070`。

GCP dev authenticated Admin 以 `first-batch` immutable Core snapshot 選取 2330，
建立 Analysis execution `8851256a-7cf5-456f-b5dd-f8384ca571d0`；queued 後由既有
Mart Job execution `janus-intelligence-mart-dk558` 消費並成功完成，Admin 顯示
`succeeded`、retry `0`、進行中 `0`。「Mart 分析」入口以
`2026-09-10`／`symbol`／`2330`／`quant`／`publishable` 篩選顯示單筆
`complete`／`publishable`、completeness `75.9%`，artifact link 可解析至 immutable
GCS metadata object。登入前 POST 正確 fail-closed 為 `authentication required`。

### WBS-5 Gemini provider diagnosis／dev acceptance（2026-09-12）

- 本機 targeted `tests/test_intelligence_mart_pipeline.py` 為 `17 passed`；改動檔
  Python compile 與 `git diff --check` 通過。
- Gemini REST adapter 使用官方 `responseFormat.text`、`mimeType=APPLICATION_JSON`
  與小寫 JSON Schema；provider HTTP error 只保留 bounded
  `provider_status`／`provider_reason`／redacted `message`，不寫入 key 或原始
  response body。
- Cloud Build `e2a5410b-8c4d-4d1d-918f-5506e931d1e2` 成功，既有
  `janus-intelligence-mart` Job 使用 image digest
  `sha256:013db1d7fdca9f8da12a9603affff197c5fd36e595f23e974ad2271a1c73b652`。
- LLM-enabled probe `69d9f07a-d459-4eeb-809d-d6b69318021a` 確認 bundle key／project
  可送達 Gemini；400 根因為 `mimeType=application/json` 不符合 REST enum，未寫
  placeholder，publication 仍 `blocked`。
- 修正後 probe `3f86a955-88be-4d1e-ad51-bc91885a7300` 由既有 Job execution
  `janus-intelligence-mart-8jfp6` 成功完成；`gemini-3.8-flash` 回傳 structured
  narrative、evidence IDs 可驗證，`llm.status=succeeded`。同一 deterministic
  report 仍為 `invalid`／`blocked`，因此 blocked 成品未進公開狀態。
- Admin authenticated Mart query 以 `2026-09-11`／`symbol`／`2330` 顯示最新
  immutable artifact `00019-cfad2174-c802-4f31-8934-38b9451a50b7.metadata.json`；
  execution `3f86a955-88be-4d1e-ad51-bc91885a7300` 顯示 `succeeded`、retry `0`。

## P0 WBS 4C acceptance implementation checkpoint（2026-09-10）

本地完成 Gateway handle contract 與 Chat API 串接：Codex 使用
`turn:start`／`turn:events`／`approval`／`turn:cancel`，保存 opaque handle，綁定
owner、logical/native thread、logical/native turn、request 與 params digest；terminal、
expiry、cancel、process error 會清理 App Server、MCP 與 sandbox，部分失敗保留
`CLEANUP_PENDING` 可重試。Chat API 將 gateway event 以既有 Private Storage／event
index 冪等落盤，建立 approval index，SSE 依 gateway cursor 增量同步；OpenRouter／
Gemini 舊同步路徑保留。

本地驗證：`python -m pytest -q tests` 為 150 passed；`npm.cmd run test:unit` 為
17 passed；`npm.cmd run typecheck`、`npm.cmd run build:agent-gateway`、Python
compile 與 `git diff --check` 通過。新增 Chat API contract test 覆蓋 Codex handle、
approval 落盤與 terminal continuation。Flutter 3.47.3／Dart 3.13.3 已準備完成，
`dart format lib test`、`flutter analyze`（無 error，20 個既有 info）與
`flutter test test/widget_test.dart`（2 passed）通過。

GCP dev 已部署既有服務：Gateway revision `janus-agent-gateway-00041-fn`，image
digest `sha256:8c1d0f3f1da04e1f4a336eec0ab97c088afdeb692f4c5a2957001e1ba2aa846b`；
API revision `janus-api-00048-x6x`。Gateway 仍為 `min=0`、`max=1`、
`concurrency=2`、`timeout=300`；本 revision 僅增加 dev-only
`CODEX_SANDBOX_MODE=read-only`，預設 `workspace-write` 與 OpenRouter／Gemini 舊路徑
保留。Gateway image build `0ec796ff-4bc6-4704-aa44-d18e703d9e23` SUCCESS。

owner B `auth_mode=chatgpt` 已重新登入，本機 App Server
`account/read(refreshToken=true)` 回傳 account，並上傳至既有
`janus-codex-owner-b` enabled version 7；owner A 版本全數 destroyed。新 revision
Codex approval live probe `cc5fecfa-b0e4-46f8-be22-391b96e2e15d` SUCCESS：產生真實
`approval_request`、錯誤 native-turn binding 被拒絕、accept 後 command completed、
decline 後沒有 completed command。此前安全 workspace command 直接
`turn_completed` 的 probes 僅作 root-cause evidence，不作 approval evidence。
probe 後 Cloud Build worker 臨時 IAM 已清空，暫存 probe 檔案已刪除。

獨立的 `google-user-client-id` Secret 不存在，但既有
`janus-postgres-api-bundle` 內已有 `google_user_client_id`；bundle 內目前沒有
`google_user_client_secret`，因此 Chat API 的真人 Google OAuth E2E 尚未完成。
OpenRouter/Gemini live build `7d661ef6-3ac5-4dd3-9f69-080966746ad0` SUCCESS；MCP
allowlist 後的 job 仍只有 readiness、未留下 application log，故本次 MCP execution
與完整整合仍未宣稱通過。Private Storage broad Cloud Build 因安全審核拒絕整個
workspace upload 而未重跑，保留本機 150 tests 證據；SSE reconnect 仍待 Chat API
真人 OAuth 路徑驗證。

## P0 WBS 4C acceptance checkpoint（2026-09-09）

Provider live probe Cloud Build `fd435461-71fc-4b8f-86bf-e583431900c5` SUCCESS：
GCP dev gateway signed OpenRouter `openrouter/free` 與 Gemini `gemini-2.5-flash`
dispatch、continuation metadata 與事件中的 API key redaction 均通過；worker
temporary IAM 已清理。

Grounding-enabled gateway revision `janus-agent-gateway-00034-g7l`（digest
`sha256:cf488f313aaa0c598034aecca679a141d0f1cf8024e357bc6487292727b68d98`）完成
部署；Cloud Build `31b2f8ac-25fa-4bbb-aca2-46c2ea3210aa` SUCCESS，實際驗證
OpenRouter streaming 與 Gemini Google Search Grounding citations／usage。
Approval／quota／stream contract Cloud Build `7960f7b5-e1fe-4b63-86cb-50d4b878a8fd`
SUCCESS，涵蓋 Agent Gateway、Gemini、OpenRouter 與 engine-security tests。

Private Storage／privacy／delete contract regression Cloud Build
`275ec264-0dde-46d7-b755-c49ad90b870e` SUCCESS，沿用 containerized API image
執行 `tests.test_assistant_storage`。

GCP dev Cloud Build `a4b5179a-81c2-4688-8558-19656d15ef91`（context sources）、
`115d9d6b-271d-4bf5-b85b-5d3210aa6b57`（Private Storage／Skills）與
`4e481c84-ac3f-4e78-8dad-6758c549cfa7`（Web bundle）均 SUCCESS。MCP transports
在 gateway revision `janus-agent-gateway-00032-k8r` 的 dev-only concurrency=2
驗收中 stdio／Streamable HTTP／legacy SSE、dynamic tools、redaction、timeout、
cancel、disconnect 全部通過；驗收後已恢復 concurrency=1，Job `janus-mcp-acceptance`
已刪除。Gateway 最終 revision `janus-agent-gateway-00033-22h`，acceptance image
digest `sha256:ac1139d7ab5c848c1d5f313069789530303cea1e78faaf95f654e16c6640ce8d`。

Codex managed-auth retry deployed gateway revision `janus-agent-gateway-00035-xtq`
with `@openai/codex@0.153.4` (Cloud Build `75fa29cf-7dfb-4176-9235-0c2ca5a9f0b5`
SUCCESS). Live POC build `ca212276-2dde-4ce1-bbdf-6982c3d943a2` still returned
HTTP 400 `Google API request failed (400)`. A fresh dev device-code probe
`e7b91774-8682-4077-8f5d-d50054d9640d` reached the gateway but returned HTTP 400
`failed to request device code: error sending request for url
(https://auth.openai.com/api/accounts/deviceauth/usercode)`, so no verification code
was produced for the required human approval step. Managed-auth／approval live flow
therefore remains blocked by the upstream auth request; temporary IAM was removed
after both probes.

Follow-up GCP dev diagnostics narrowed this to the Codex Linux App Server rather
than general egress: Cloud Build `6b838dc2-faa2-4eb3-aa3d-594ae02d852a` resolved
and reached the endpoint (GET 405), and `9a251707-c075-40d2-9f32-a6c75eb11023`
received a valid POST device code (`200`). Direct App Server probe
`eff86a80-a94a-44da-af76-0f1efccef287` on Linux `0.153.4` still returned the same
request error. No auth workaround or API-key fallback was introduced; the remaining
action is an upstream Codex CLI/device-auth compatibility fix or an approved newer
runtime release.
An isolated alpha probe of `0.154.0-alpha.10.2` (`e04655d7-28bd-47fa-9a28-8fa98bf61358`)
reproduced the same App Server error, so it was not adopted.
OpenRouter／Gemini 既有成功 probe 仍可參照前述 runtime dispatch evidence。為配合
2026-09-09 approval-handle remediation deployed revision `janus-agent-gateway-00038-j78`
(`sha256:74d2d17903b75ec5540a0150a3f00eb7cbb4a5496888c153c31ce59bcff33f05`) with
`concurrency=2`, `maxScale=1`, and `minScale=0`. Live owner-B turn on the dev
service returned an opaque `turnHandle` and a real shell `approval_request`; the
human-approved `accept` was routed back to the same Codex bridge, produced
`approval_resolved`, command `exitCode=0`, and `turn_completed`. The side effect
created `approved.txt` containing `JANUS_APPROVAL_SIDE_EFFECT`. An initial binding
mismatch was safely rejected, then fixed by separating Janus and Codex native thread
ids before the successful rerun. This validates the dev-only live approval flow;
the in-memory handle remains process-bound and is not a production durability claim.
現行 provider bundle，MCP acceptance 改讀 `mcp_owner_signing_key` 欄位，不建立新
Secret。

2026-09-09 device-auth remediation：Gateway runtime image 已安裝
`ca-certificates` 並設定 `CODEX_CA_CERTIFICATE=/etc/ssl/certs/ca-certificates.crt`；
`verificationUrl` 亦納入 login-start 安全回傳欄位。Cloud Build
`0baeea94-9174-4ceb-9acd-b968e50759dd` SUCCESS，image digest
`sha256:d4cc395510db6216ca518946c167767b9a1ef1679c405dae9c06f910e2192845`，
Cloud Run revision `janus-agent-gateway-00036-2s6`。真人 device-code login
Cloud Build `a98d47f9-508a-4fd6-ae80-4f6c6831d39a` SUCCESS，回報
`device login authenticated`；既有 bridge live verify Cloud Build
`8d3e76c9-7025-442d-ab4c-e9b6dde8db17` SUCCESS，checkpoint reconnect、
cancellation、logout／destroy 通過。驗收後已移除暫時 Cloud Build Secret accessor
與 invoker impersonation IAM。Approval 的真人 side-effect turn 尚未執行，WBS
4C 整合驗收仍未結案。

## P0 WBS 4C Skills（2026-09-06）

GCP dev Cloud Build `262243c4-1323-4eea-80a5-48d1c631be7b` 使用既有
`scripts/gcp/cloudbuild-private-storage-verify.yaml`，在 containerized API image
內執行完整 `python -m unittest tests.test_assistant_storage`，結果 SUCCESS。
驗證涵蓋 Skill manifest validation／credential fail-closed、assistant event
owner isolation／delete、PostgreSQL index contract 與 Codex deletion cleanup
guard；未部署 Cloud Run、未建立新資源，亦未呼叫 Artifact Analysis／Container
Scanning／occurrence API。

## P0 WBS 4C Codex auth lifecycle checkpoint（2026-09-06）

GCP dev Cloud Build `a44a6463-3e76-4d31-b784-84337ea9af88` 通過 Agent Gateway
TypeScript build 與 targeted Vitest；`f1ee3054-7d2f-4bdf-ae61-6f82b0ccfdf3`
通過 private-storage/deletion contract；修正後 `d5301537-af3f-42ac-876a-4587f916b493`
再通過 Gateway build、Vitest 與 Bash syntax。

本次使用 A/B owner Secret 部署 revision `janus-agent-gateway-00026-s8h`，image
digest `sha256:ee1bfd630b6ac2fb1912b764030ef0e866c41c078c60040799e51041d0345db0`，
設定為 `min=0`、`max=1`、`concurrency=1`。Cloud Build
`b131ee1a-cea5-44d2-97f8-04e0d04ef183`（A）與
`7c478c2a-7a5b-4f38-b7f3-146fbad2d237`（B）均 SUCCESS，完成各自 owner-bound
managed-auth load／refresh、cancellation、checkpoint replay、logout／session
eviction 與 destroy retry；兩個 owner Secret version 最終均 destroyed，證明
A/B Secret isolation。互動式 device-code login 的真人瀏覽器流程尚未驗收。

人工 gate 通過後建立 `janus-codex-owner-a`／`janus-codex-owner-b`（各自
`us-central1`、僅保留 dev fixture），並部署 Gateway revision
`janus-agent-gateway-00019-qvv`，image digest
`sha256:dc28e2f4abc51bdad685afea7dcbc6e89f525fdc4cc02f50f6d39d84c5a25daa`。
Live Cloud Build `9f7da474-8a16-457e-a84c-510c06fddb88`（A）與
`a3ef9a23-bd83-482b-ad40-d0802090b129`（B）通過 owner-bound run、cancellation、
GCS checkpoint replay；`eb45609e-e101-4b2c-8349-7d2b233d0b31` 通過 A destroy
兩次冪等後，`c5e69d10-2427-4cf7-af03-935d286ca53c` 證明 B 仍可獨立執行。
更新 logout endpoint 後部署 revision `janus-agent-gateway-00019-qvv`，
Cloud Build `1084498e-0d2f-481f-aa9a-762e1c5ca033` 通過 B run、logout／session
eviction 與 destroy retry；A／B Secret 版本最後均為 `DESTROYED`。Gateway 維持
`concurrency=1`、`maxScale=1`、`minScale=0`。

## P0 WBS 4C runtime dispatch acceptance (2026-09-09)

GCP dev Gateway revision `janus-agent-gateway-00029-5hk` 完成 OpenRouter／Gemini
signed dispatch live probe；Cloud Build `20050302-861a-4c84-84ad-c96f21903776`
結果為 `openrouter dispatch passed`、`gemini dispatch passed`、`DONE`。Codex
既有 POC bridge 由 Cloud Build `9dec1039-0052-420d-9ef1-6719ed46991a`
完成 health、owner-bound login／checkpoint reconnect、logout／session eviction、
destroy retry；checkpoint 為 `60ddd412-f367-4ac9-a5c6-8bbcd6f29e08`。

驗收期間暫時授予 Cloud Build provider bundle accessor 與 dev invoker
Token Creator，完成後均已移除；Gateway 維持 `min=0`、`max=1`、
`concurrency=1`。目前證據包含 Codex POC checkpoint、OpenRouter／Gemini
gateway probe，以及 `tests/test_chat_api.py::test_codex_message_round_trips_gateway_continuation`
的 message → gateway → 下一 turn continuation contract evidence。GCP dev 的
三-runtime 整合重跑仍屬 WBS-4C-ACCEPTANCE，不在本切片宣稱完成。

## P0 WBS 4C MCP Host implementation (2026-09-06)

GCP dev PostgreSQL migration `015_private_mcp_servers` 已套用並以
`private.mcp_servers` 存在性驗證。新增 Secret Manager secret
`janus-mcp-owner-signing-key`，僅授予 `janus-agent-gateway` 與 `janus-user-api`
runtime accessor；未輸出 secret payload。

Cloud Build `fe522ef7-0aed-4739-b7cd-a6fdd5b00c1f` 成功建置 Agent Gateway；最終
dev revision `janus-agent-gateway-00011-d78` 使用 immutable image digest
`sha256:a9e0aad9746c2144368b9808ed3b250e26309e268ab4f805c3049e8e2bbc2d78`。
API Cloud Build `1a0151d4-1ad6-479b-9179-dcbab72cf02e` 成功建置；dev revision
`janus-api-00018-jm9` 使用 image digest
`sha256:ad6ef02c255be4c7666db8869879f6745c75a8c0c3a0760639aaf004a99a3894`。

GCP dev fixture 為私有 Cloud Run `janus-mcp-fixture`，最終 revision
`janus-mcp-fixture-00008-zn5`、image digest
`sha256:7c1258a509c773b1e8b64b3573024033d7a26e36a6a9183a7bfa15c6c7124b3e`，維持
`maxScale=1`、`concurrency=80`、scale-to-zero；gateway 維持 `maxScale=1`、
`concurrency=2`、scale-to-zero。正式 acceptance 在 GCP dev Cloud Run Job
`janus-mcp-acceptance-p7kpf` 通過，Job 完成後已自動刪除。

Acceptance Cloud Build `2bad0afc-ca51-4eb7-abfb-fa05a4a38440` 建置 runner；結果：
stdio `discover=modern/call=ok`、Streamable HTTP `discover=modern/call=ok`、legacy
SSE `discover=legacy/call=ok`、secret structured-content redaction、timeout、
`tools/list_changed`、並行 cancel 與 disconnect 均為 `ok`。有效 HMAC、owner-scoped
tool grants、invalid config／credential boundary 亦已驗證；secret payload 從未輸出。

## P0 WBS 4C Context Sources（2026-09-06）

GCP dev Cloud Build `92131984-c36e-4755-9c20-9f37ba3cea12` 成功完成 source list、
Janus Core／Private Mart preview、opaque context reference、owner/thread isolation、
resolve 與 invalid selector/SQL 驗收。API 最終為 revision `janus-api-00016-4bv`，image
digest `sha256:3e702dac14143d478b7eb11925c8bff4c40c8826f28b4b0907d4228ab55871f9`。

驗收腳本在 Cloud Build worker 內建立的兩個暫時 Token Creator binding 已清理；
`janus-user-api` 對既有 Core catalog password Secret 的 dev read-only accessor 依授權保留。
本機新增 API 測試因 host 缺少 FastAPI runtime 未能 collection；既有 targeted tests 為
13 passed、1 項因 host 缺少 `zoneinfo`／`pytz` 而失敗。腳本 `bash -n` 與 `git diff --check`
通過。

## P0 WBS 4C Cloud Runtime POC（2026-09-06）

Agent Gateway image 使用 immutable digest
`sha256:3aada7f674da8f18d7362b4b02b99c435a78154006ad648b0bb2e5e240bb39e1`。
GCP dev Cloud Run service `janus-agent-gateway` 的 acceptance revision
`janus-agent-gateway-00005-gxb` 通過 100% traffic 驗收；完成後為恢復成本設定建立
`janus-agent-gateway-00006-fj5`，目前為 `min-instances=0`、`max-instances=1`、
`concurrency=1`。

Cloud Build `bfbe9024-6a24-4452-8ca7-a717314813da` 在 GCP worker 內完成 health、
Codex managed auth、workspace-write sandbox、turn cancellation、process stop、
Private GCS checkpoint 與 cursor reconnect。POC response 為 Codex `0.153.0`、
`authRotated=false`、checkpoint
`b36ed5c5-c833-40d0-994f-8c06f8f1862a`、`cancelled=true`、
`process=stopped-after-response`；checkpoint replay 與空 cursor replay 均通過。

驗收期間只暫時授予 Cloud Build identity 對專用
`janus-agent-poc-invoker` 的 `roles/iam.serviceAccountTokenCreator`，build 完成後已
移除；本機未直接呼叫 Cloud Run URL 或使用 proxy。此前為處理 GFE 間歇性 500，驗收
worker 的 health warm-up 改為最多 10 分鐘；最終以 `min-instances=1`、`max-instances=2`
驗收成功後，已回復為上述 scale-to-zero 設定。Codex App Server 仍屬 POC，未宣稱
production-ready。

## P0 WBS 4J 個人工作台實作（2026-09-05）

新增最小 FastAPI User service、獨立 Google User OIDC audience boundary、以 Google
`sub` 對應 UUID 的私人 PostgreSQL repository，以及 journal／notes／watchlist／export／
deletion typed endpoints；client `user_id`、錯誤 issuer／audience／expiry 均拒絕。
Ledger 為固定精度 append-only event，修正使用 reversal／replacement；筆記正文直接寫
Private Iceberg，PostgreSQL 只留索引與 artifact reference。

Private pipeline 依 persisted checkpoint 批次 upsert ledger、note reference、watchlist
與四個 user Mart；移動平均成本納入費稅，缺價保持 null，Iceberg 全部成功後才推進
checkpoint。另加入獨立 private bucket lifecycle、runtime service accounts／PostgreSQL
roles、50-symbol 全域 guard 與 Iceberg-first 可重試刪除流程。最小 Flutter 啟用關注、
記帳／筆記與我的，不加入券商、自動下單、排行榜或 FIFO。

Cloud Build `aa011f3a-b96d-42da-a99e-7bd445eb4a92` 驗證 bash syntax；
`c8a1d829-6898-4bf3-8f08-50c24b94a258` 在一次性 PostgreSQL 16 套用 001–014；
`4f85bf89-ef44-4cab-b8bf-76a448b6bd0c` 通過 Flutter analyze 與 widget test。
Dev migration `014_private_workspace` 已套用，PostgreSQL image digest 為
`sha256:28989610fdf7ce9e379df0554c224b5fe13e7c36b5c32c4fc9522aa528cff0c8`。
User API build `edf6fa7e-cab7-4432-b1cf-3f6c7580daf3` 成功，dev revision
`janus-api-00004-p4q` 使用 image digest
`sha256:487cf1a2824a8126679b9d4eb6b2cff03b86572c4c87805c666c43bdff34ff75`；
`/health` 200、無 bearer 與錯誤 audience 均 401。

兩個 Google OAuth 測試帳號完成真人登入，取得不同內部 `user_id`；A 建立 2330
watchlist 後，B 看不到該列、刪除收到 404，A 仍可讀。PostgreSQL 只讀驗證為 2 users／
2 distinct `google_sub`／2 distinct `user_id`，active watchlist 僅屬 1 user。OAuth client
ID 與 private DSN 的 BOM 已移除；dev DB API 密碼已輪替，Secret 第 1 版已停用，Cloud
Run 固定使用第 2 版。真人 journal／note／Private Iceberg artifact 完整交易情境已由下方
GCP dev acceptance 完成；公開 `mart_scoped_analysis` 尚未產生，個人化 overlay 維持未啟用。
未部署 production。

## WBS 4J complete transaction acceptance (2026-09-05)

GCP dev Web revision `janus-web-00057-h52` served the A/B acceptance page. Two
Google User OAuth subjects resolved to distinct internal users. The acceptance
covered idempotent BUY replay, reversal/replacement correction, cross-year BUY／SELL,
fees／taxes, CASH_DIV／STOCK_DIV, oversell rejection (409), note revision, and
cross-user history／note／correction／revision isolation (B returned 0 rows and 404).

Private pipeline execution `janus-private-pipeline-srmnn` advanced checkpoint 23→46;
the subsequent batch `janus-private-pipeline-kmc7m` advanced it to 54. Metadata
hashes changed for all seven private tables after the latest batch. Deletion request
`cffb8921-1f22-411b-8497-70bfdf8dad85` completed in
`janus-private-pipeline-n7ml8`; PostgreSQL reported `COMPLETED`, A's user／ledger／note
rows were absent, and B's user row remained. No public catalog tables were modified.

## P0 Admin 股票資料狀態（2026-09-03）

股票資料狀態表已顯示 Core 最新日期、精確 row count、coverage 比例、逐欄 null
count／ratio、既有 DQ、來源、snapshot 與 quarantine 摘要；Core reader 使用 bounded
aggregate 計數，不再把最多 200 筆的明細頁誤當總筆數。沒有 persisted quarantine
計數時明示未提供，未新增或校準 DQ 規則。Collection 操作改為「選取股票 → 加入收集
佇列 → 最近執行」，成功送出會清除暫存選取並切至 execution 追蹤。

Targeted Python 48/48、Vitest 2/2、Playwright 6/6、TypeScript typecheck、ESLint、
Web production build 與 `git diff --check` passed；未操作 GCP、未部署。

## P0 五檔 Scheduler canary 觀察（2026-09-03）

Cloud Scheduler `janus-ingestion-daily` 維持 `ENABLED`、`30 7 * * *`、
`Asia/Taipei`。2026-09-03 07:30（Asia/Taipei）準時觸發 Cloud Run execution
`janus-ingestion-core-8mvg4`，使用既有 immutable image
`sha256:673d74bd2da1798f7d581e45e1142deb986ed284950a4ea7f8ffe63642aa1186`；兩次 task
attempt 均失敗，persisted execution IDs 為
`629adfdc-63c5-4608-92e3-bc8cb6e0108f` 與
`74aeeff7-fd33-43bc-b6e7-d8cead2b0ad8`。五檔仍為
`1102／2327／2330／2381／4958`；`twse-valuation`、`twse-institutional` 收到 HTTP
307，`mops`、`twse-events` 收到 HTML，整體正確標記 failed，未誤報成功。retry 的
freshness guard 略過已完成的 7 項，未重複寫入 Core。

相同 image 的前一日 Scheduler execution `janus-ingestion-core-485bg` 於
2026-09-02 07:30 成功；四個官方 endpoint 在 2026-09-03 11:02 再次唯讀檢查時已回
HTTP 200，故目前記為上游排程時段異常，不修改程式或手動補跑。連續成功計數重置為
0/3，下一個交易日繼續觀察；尚未產生可結案的三日 expected／received／missing、
8 來源、Core profile 與成本摘要。

## P0 WBS 3 第一個可獨立驗收切片（2026-09-02）

Web build `311b584b-82f7-4b4b-9277-1737d9f159f9` 成功；dev revision
`janus-web-00037-g25` 使用 immutable image
`sha256:90dd2684a4b23c7d14c91b9113b9bd9c57c0550b07bbcc9e3405aa56555b5d44`，
實際 URL `https://janus-web-2oo7qbkd5q-uc.a.run.app`。2026-09-02
10:47–11:40（Asia/Taipei）以短效合成 session 完成 live Playwright：390px
responsive、恰有七個資料營運 tabs、Collection 可見，Analysis action／Mart／AI
Prompt 不存在；Analysis API 回 400 且 execution IDs 前後不變。HTML／Admin API responses 未出現 raw payload、object
URI、secret、完整 upstream error 或 traceback。Admin status／execution／source
health 查詢前後 persisted source health 完全相同，證明查詢未呼叫上游。

ingestion dev image 為
`sha256:673d74bd2da1798f7d581e45e1142deb986ed284950a4ea7f8ffe63642aa1186`。
五檔 `1102／2327／2330／2381／4958` 的 2026-08-28 單日 backfill execution
`312bcec0-453f-46eb-9caf-2bd633d23edb` 由 Cloud Run execution
`janus-ingestion-core-g26kr` claim，4m32.71s 後 succeeded：8 個來源、11 個 Stage
payload、11 metadata、11 manifest、0 quarantine、1 Core commit fence，
`failed=0／empty=1／created=0／updated=114／reused=289`。Admin detail 為 12 個
success／fallback／合法 empty items，安全訊息只包含 `Core committed` 或
`source returned no rows`；五檔股票 status 均可查，2381 當次 persisted row count
為 0，未在 UI 補值或誤報成功。

同日 replay execution `ac61b175-01cf-456b-982a-6c5e33fa9b53` 由
`janus-ingestion-core-8cvrh` claim，4m58.22s 後 succeeded；Stage／fence 數量相同，
`created=0／updated=0／reused=403`，證明 replay 未增加 natural-key rows。null 不覆蓋
有效值由完整 pytest 的 null-preserving merge regression 通過。受控 failure execution
`cfd83043-c8aa-4ce8-bff9-8cc3ab34b881` 經既有一次 retry 後為 `failed`、
`retry_count=2`、`error_code=COLLECTION_FAILED`，Admin response 無 traceback 或完整
error，未誤標成功；partial item 狀態由 framework regression 驗證。

Stage cleanup 於 2026-09-02 15:47–15:50（Asia/Taipei）以相同 immutable ingestion
image 執行；Cloud Run execution `janus-ingestion-core-fvltp` 與 persisted execution
`4e134da7-2a6d-488f-a704-b9c78b1cb87d` 均 succeeded。retention 經 Admin API 與 audit
由 30 天暫改 1 天後，三個 cleanup items 分別刪除 18／9／18 個 Stage objects；清理後
三個 Stage prefix 均為 0 objects，三個 `core-commit.json` immutable fence 均保留。
既有 failed execution `cfd83043-c8aa-4ce8-bff9-8cc3ab34b881` 未成為 cleanup candidate，
狀態維持 failed。retention 已透過相同 API 恢復 30 天、`cleanup_enabled=true`、version
3，兩次異動均由 `tommylin15@gmail.com` 留下 audit。

Web 設定維持 `minScale=0`；Cloud Monitoring 04:02Z 顯示 final revision 的 active／
idle instance 均為 0，實際 scale-to-zero 通過。本切片已完成；下一項為連續 3 個交易日
Scheduler 驗收，完整 DQ 校準與其他 WBS 仍未宣稱完成。
未部署 production、未建立新資源或提高限額，且未呼叫 Artifact Analysis／
Container Scanning／occurrence API。

## P0 Iceberg schema evolution tests (2026-08-31)

Core Iceberg regression 驗證 additive nullable 欄位會取得新 field ID，既有 field
IDs 保持穩定；舊 rows 對新增欄位回傳 null，既有 snapshot 保留且仍可讀。
不相容型別變更會在 commit 前被拒絕，不產生新 snapshot 或改寫既有資料；欄位語意
或單位改變仍依契約建立新 table version。Iceberg targeted pytest 5/5、完整
`python -m pytest -q tests` 98/98、適用的 Python compileall 與
`git diff --check` passed；本切片未操作 GCP。

## P0 2330 Source → Stage → Core → Admin integration (2026-08-31)

本機 integration regression 以 injected 2330 TWSE source fixture 建立 persisted
collection execution，驗證 raw／quarantine Stage objects、Core materialization 與
Admin HTTP status query。Admin 結果涵蓋 latest Core date、dataset coverage、row
count、DQ warning count、quarantine count，以及 persisted execution／provenance
關聯；response 不含 raw payload、object URI、secret、完整 upstream error 或
traceback，Admin query 期間 source adapter 呼叫數不增加。

同日 replay 維持單一 Core natural-key row 與相同 content hash，且 incoming null
close 未覆蓋既有有效值。Targeted pytest 11/11、完整 `python -m pytest -q tests`
96/96 與適用的 Python compileall passed；未操作 GCP，既有 dev migration
`009_admin_cursor_indexes` 未重複套用。

## P0 Admin cursor dev migration (2026-08-31)

PostgreSQL migration `009_admin_cursor_indexes` 已套用至既有 dev VM
`janus-postgres-dev`。`control.schema_migrations` 已記錄該 version；
`control.executions_admin_page_idx` 的實際定義為
`CREATE INDEX executions_admin_page_idx ON control.executions USING btree (requested_at DESC, execution_id DESC)`。
PostgreSQL readiness 回報 accepting connections，VM／container 暫存 migration 檔案均已清除。

套用前後的唯讀資源盤點一致：project `gen-lang-client-0593591102` 只有既有
`us-central1-a` `e2-micro` VM 與單一 30 GB `pd-standard` boot disk，VM 只有
private IP `10.42.0.5`、無 external IP；snapshot 與 Cloud Router／NAT 清單為空。
未重建 image、未重啟 PostgreSQL container、未建立額外雲端資源，且未部署
production 或呼叫 Artifact Analysis／Container Scanning／occurrence API。

## P0 Mart runtime connectivity (2026-08-31)

PostgreSQL build `36823a97-1ef1-4046-9700-37223be1bdf0` 產生 immutable digest
`sha256:6fe7049c87c07429ab4eb8563a704ff9d54951dbe28338e1ac657b2ae50ebd51`；
migration `008_mart_runtime_roles.sql` 已建立 non-superuser／non-createdb／
non-createrole／non-replication 的 `janus_mart_catalog` 與
`janus_mart_publication`，HBA 僅允許 `10.42.0.0/24` TLS 連線。

Mart 修正版 build `9a94e089-a89b-4e44-9351-3c9fb166b569` 產生 digest
`sha256:cbd336ace6629c1a78769673ad5415f0d6475a42766510f9b9ef2ea7d24fd007`。
Cloud Run Job `janus-intelligence-mart` 使用專用 service account、Direct VPC
`private-ranges-only`、`janus-intelligence-mart` network tag、固定 Secret version 1、
1 CPU／1 GiB／300 秒 timeout／1 retry。Execution
`janus-intelligence-mart-hd86r` 成功；catalog／publication 皆回報 private address、
bounded privileges `ok`。第一次 execution `janus-intelligence-mart-rpwjj` 只因
PostgreSQL 回傳 CIDR 形式 `172.17.0.2/32` 被驗證器誤判，已以 `ip_interface` 修正並
留下 regression test。臨時 VM Secret IAM 已撤銷，local／VM credential temp files
均已清除。

Cloud Scheduler `janus-ingestion-daily` 目前只呼叫 `janus-ingestion-core:run`；Mart
尚未排程。WBS／todo 已要求 ingestion DQ／Core commit 成功後由
`core.dataset.ready.v1` workflow／event 觸發 Mart，不得以同時獨立排程取代依賴。

Google login handoff 在驗證 ID token 後，以短效簽章 handoff 完成同源 POST；第二段
回應使用 `303 See Other`，在同一 response 設定 HttpOnly session cookie 並導向
`/admin/stocks`。不得使用零秒 meta refresh，以免瀏覽器在 cookie 提交前先載入
Admin、被誤判未登入而退回 `/login`。Auth 專項 7/7 與全套 78/78 tests passed。

## P0 Web runtime deployment (2026-08-30)

PostgreSQL migration `007_web_runtime_roles.sql` 已套用至 dev，Web control role
對明確列出的 control tables 使用一致的 SELECT／INSERT／UPDATE／DELETE 權限；
catalog role 對 catalog metadata 為 SELECT-only，且
`default_transaction_read_only=on`。實機權限查詢結果為
`catalog_write_tables=0`、`control_dml_missing=0`。兩個 role 均不是 superuser、
createdb、createrole 或 replication role。

PostgreSQL build `da62fdb1-f3f5-4436-bc28-0a18edd4e9ac` 的 immutable image digest
為 `sha256:f81ef216a81b003edd6b319cb2ab04f65b453c34c1fae09d8cf7f44e9de993b7`。
Web build `5d919396-ad8a-490e-a07c-30c33c3060bb` 的 immutable image digest 為
`sha256:1be0cb5e7cb5056fc2805de3eb9f44214cb969d13e991186872ad39cb32e8123`；
Cloud Run revision `janus-web-00023-ccj` ready 且承接全部 dev traffic。

Cloud Run 保持 `allUsers` invoker，由 application middleware 執行 allowlist session
驗證。未登入 smoke：`/health` 與 `/login` 回 200、`/admin/stocks` 轉址至
`/login`、Core API 回 401；短效合成簽章 session smoke 對 Admin 與
`/api/v1/core/2330/summary` 均回 200。revision ERROR log 查詢無結果，證明 Web
runtime 已透過 Direct VPC private path 使用專用 control/catalog credential。

Web catalog Secret 目前只保留 version 3 enabled，先前版本已 disabled；Web session
Secret 只保留 raw-byte 驗證為 48-byte ASCII、無 BOM 的 version 4 enabled，versions
1–3 均 disabled。Secret 值沒有寫入 repository 或正式驗證輸出；後續輪替必須依
`doc/runbook-dev-deploy.md` 的 raw-byte、runtime、disable-old-version 順序執行。

## Dev delivery automation and artifact retention (2026-08-28)

Terraform is no longer a repository or deployment dependency. Dev bootstrap is
performed by the explicitly authorized, idempotent
`scripts/gcp/provision-dev.sh`; it verifies the fixed PostgreSQL Free Tier shape
and does not create a missing PostgreSQL VM automatically.

Automatic runtime deployment is owned by three regional GCP Cloud Build
Developer Connect triggers, all restricted to branch `^main$` and component
paths:

- `janus-ingestion-core` (`5e201f5a-c206-4006-92b9-40a53c4155ed`):
  `jobs/ingestion-core/**`, contracts, observability, and `cloudbuild.yaml`.
- `janus-intelligence-mart` (`b8215cb9-1823-401d-b293-65fbdf73ce30`):
  `jobs/intelligence-mart/**`, contracts, observability, and `cloudbuild.yaml`.
- `janus-web` (`c08067dd-5c44-414f-9e8d-9d94e89b4089`): `apps/web/**` and
  `cloudbuild.yaml`.

Documentation-only and `scripts/gcp/**` changes do not trigger runtime builds.
The former two triggers were deleted before these three current triggers were
created. `.github/workflows/deploy-dev.yml` is manual-only (`workflow_dispatch`)
and restricted to `main`; its repository variables are
`GCP_WIF_PROVIDER` and `GCP_CI_SERVICE_ACCOUNT`. No long-lived service-account
JSON key is used. A path-matching push has not yet been used as end-to-end
evidence for the new trigger set; automatic trigger acceptance remains pending.

The last directly verified runtime deployments remain Cloud Build
`baf5b915-ee80-477b-8ec8-dc1e981fc23a` for ingestion-core at
`sha256:16248df5e95afea4cc099016c4c6e1722eade307b53d2065514f7d517f596e8e`
and `e021a691-2a0e-42eb-bffd-b25c2ee2ead2` for web at
`sha256:6746d5985e60781bda04b1965d980e0651c82dd30e7026344e1b30908221cd74`.
The `janus-intelligence-mart` trigger and Cloud Run Job now exist. Manual build,
immutable deployment, Direct VPC, Secret Manager, and database smoke acceptance
passed; a path-matching automatic trigger run remains pending.

Artifact Registry repositories `janusai-poc` and `janus-postgres` use the same
active cleanup policy with dry-run disabled: each image package keeps only its
most recent version, while older tagged and untagged versions are eligible for
deletion after one second. The old untagged PostgreSQL digest
`sha256:8dfe6976ca822f87a6ba42743bb0f841d4bee3352a66816d663f2bc0961f7c4e`
was permanently deleted; `postgres:16.15` remains at
`sha256:6fe7049c87c07429ab4eb8563a704ff9d54951dbe28338e1ac657b2ae50ebd51`.
Artifact Analysis and Container Scanning remain disabled and were not called.

## P0 Admin follow-up (2026-08-28)

Admin now has persisted settings and immutable audit metadata in SQLite and
PostgreSQL migration `006_admin_settings_audit.sql`, with optimistic version
checks. The source catalog API/UI exposes cadence, coverage tier, retention,
authorization status, and max-symbol quota; candidate/blocked enabled configs
are rejected. Stock status details expose the aggregate Core summary,
including latest date, row count, DQ warnings, and quarantine count when the
read-only Core runtime is connected. The existing Direct VPC Web Cloud Run
service has access to the control/catalog Secret Manager containers; no secret
values are committed or invented.

Frontend Vitest and Playwright configurations/tests were added. Dependencies
were not installed in this restricted environment because the npm registry
request stalled; browser discovery returned no available in-app browser.
Local HTTP smoke returned 200 for `/health`, `/admin/stocks`, and the Admin JS
asset. Python discovery ran 63 tests successfully; Python compileall,
JavaScript syntax, and git diff checks passed. Terraform is no longer part of
the repository or validation path.

## P0 Query／Admin application layer (2026-08-28)

`packages.web_api.CoreQueryService` is the read-only Core application boundary.
Dataset identifiers are allowlisted, symbol/date values are parameterized, and
pagination is bounded. It exposes row count, latest date, null profile, and
quality flags without returning Stage payloads. `apps.web.server` provides a
Cloud Run-compatible WSGI boundary with safe 4xx/5xx responses and a health
endpoint; runtime database wiring remains an explicit deployment configuration.

`packages.admin_api.AdminService` provides bounded stock search, enabled/delete
operations, queued collection/analysis triggers, recent execution/detail views,
and effective-time membership views. It delegates FK/reference protection,
candidate/blocked source rejection, and core-50 limits to the control plane;
collection work is never executed in the request path.

`/admin/stocks` now provides the first responsive Admin Data Operations UI:
10-row stock pages, cross-page selection, separate collection/analysis enqueue,
the latest 50 persisted executions with on-demand safe details, persisted source
health, and effective-time core membership editing. Runtime PostgreSQL wiring,
typed schedule/source authorization editing, audit/optimistic concurrency, and
browser interaction coverage remain open acceptance conditions.

UI acceptance may run against a local browser/Playwright environment or against
the existing GCP dev Cloud Run service when a real runtime is required. After
the manual billing gate has been satisfied, the existing dev service may be
started on demand without separate per-run approval. The cloud path must verify
the actual dev URL, responsive and interaction behavior, Admin API/runtime
connectivity, and safe output; evidence records the Cloud Run revision,
immutable image digest, test URL/time, and scale-to-zero state. This authorization
does not cover production deployment, higher resource limits, or new paid GCP
resources.

Source health summaries are now available from both SQLite reference and
PostgreSQL control adapters. Migration `005_source_health_telemetry.sql` adds
bounded aggregate coverage, cache, fallback, schema-drift, and tier fields;
raw upstream payloads remain excluded.

Validation for this change: 10 focused Admin/API tests passed; JavaScript syntax,
Python compileall, and diff checks passed. Full discovery ran 58 tests: 56 passed
and only the two existing PyIceberg tests failed to import because `pyiceberg` is
not installed. Browser discovery returned no available local browser; visual
interaction remains pending and may be completed through the authorized GCP dev
Cloud Run acceptance path above. No cloud deployment or paid resource was
created.

## PostgreSQL dev/MVP topology

Development PostgreSQL is a self-managed Compute Engine `e2-micro`
VM in `us-central1`, with private networking, no external IP, at most 30 GB
Standard Persistent Disk, and IAP／OS Login. The dev VM is provisioned at private
IP `10.42.0.5`. Free Tier mode does not create scheduled snapshots, backups, HA,
or replicas and is not a production HA decision. Cloud SQL is not part of the
selected dev topology.

The Free Tier target also limits outbound data to 1 GB/month. Eligibility is
evaluated by billing account and region; the resource limits do not guarantee a
zero bill.

## PostgreSQL control integration

`PostgreSQLControlPlane` is the production repository for control metadata. It
uses injected bounded connections, transaction-scoped writes, server-side
statement/idle timeouts, transition checks, and `FOR UPDATE SKIP LOCKED` queue
leases. Response cache payloads remain in GCS; PostgreSQL stores only URI,
hash, TTL, observed time, and state. The migration is idempotent and includes
expiry/health indexes and pruning support. Ingestion private-IP authentication
and control-symbol reads are validated; Web and Mart paths remain pending. The
Trino replacement is complete in the development runtime. No production
deployment was performed.

Provisioning gate: PostgreSQL VM, PostgreSQL repository/migration, private
connectivity, control/catalog schema bootstrap, and PostgreSQL readiness must
pass before a Cloud Run DuckDB runtime deployment is attempted.

DuckDB runs embedded in the Cloud Run ingestion Job and reads/writes Iceberg
data and metadata in GCS. PostgreSQL remains the control DB and SQL catalog
metadata store; it does not store Iceberg data files. The VM has only 1 GiB RAM
and is reserved for PostgreSQL control/catalog metadata.

The source control contract separates `market_wide`, `core_focus`, and
`market_macro` coverage. Collection configs persist cadence, scope,
authorization status, retention class, PII, republishing permission, and a
maximum symbol count. Historical coverage membership is append-only with
effective timestamps; `core_focus` is capped at 50 symbols. Candidate or blocked
sources are rejected before queueing, while source IDs remain available in the
contract for later approval review.

Artifact Registry cost guard: image push/pull, immutable digest, metadata and
cleanup only. Artifact Analysis API, Container Scanning API, vulnerability
scanning and occurrence APIs are prohibited; no scanning API was called during
this change.

## P0 資料控制面與 Ingestion Framework

- Python unit/contract tests：42 targeted tests passed；`compileall` passed；`git diff --check` passed。Full discovery remains blocked only by the local environment missing `pyiceberg` for two existing DuckDB/Iceberg tests。
- Python compileall：passed。
- Control schema：SQLite reference implementation covers stock master with
  collection-reference protection, dataset collection config, separate
  collection/analysis queue commands, persisted execution/items, response
  cache, incremental cursors, and source-health telemetry.
- Execution statuses：queued、running、retrying、succeeded、partial、failed。
- Item availability：success、empty、partial、fallback、stale、unavailable、
  schema_drift、failed。
- Adapter framework：sync/async `SourceAdapter`, bounded timeout, exponential
  backoff, retry-after support, per-source rate limiting, exact schema-drift
  detection, safe error taxonomy, and no raw upstream error persistence.
- Cache/incremental：market-scope responses share one market/day batch key;
  symbol-scope responses retain the exact start boundary; successful primary
  observations advance a cursor with configured overlap. Partial/fallback/stale
  responses are not promoted to successful cache entries.

## P0 Stage／Core

- Python unit/contract tests：39 passed（含 Stage/Core、DuckDB/Iceberg、framework/control、contract、DB session timeout 與 sparse-empty semantics）。
- Python compileall：passed。
- gcloud bootstrap guard：PostgreSQL `e2-micro`、30 GB、固定 zone 驗證通過。
- GCP Developer Connect triggers：三個 component trigger 已建立；新的 path-matching push acceptance 尚待驗證。
- Artifact Registry：兩個 repositories 均啟用 keep-latest-1 cleanup policy，dry-run disabled。
- Cloud Build images：`d6f62619-eba6-47b2-b238-c1057774a611` 與
  `fcbae728-f254-458e-8475-0c69b3e5a34f` 均成功。

Stage writer 使用 immutable create-if-absent、SHA-256 content hash、受控 ID、
去敏 source URL、execution manifest 與 quarantine sidecar。Core DQ 覆蓋
required key、type、date、duplicate、unit、range、schema drift、null-preserving
merge、欄位語意 zero 與極端漲跌保留警示。

2330 Stage → Core closed loop：`ingestion_core.sources` 提供 TWSE／TPEx OHLCV
normalisation；`pipeline.run_2330` 建立 persisted collection execution，將 raw
payload／sidecar／quarantine 寫入 Stage，使用 Core DQ materialise deterministic
OHLCV rows，並透過 event sink 發出 `core.dataset.ready.v1`。Core summary 保存
row count、content hash、date coverage、null profile、warning/quarantine count
與 provenance ID。重跑使用 Stage create-if-absent 與 null-preserving merge；真實
Cloud Run／VM restart smoke、GCS production object 與 PostgreSQL workload connectivity
仍待 runtime deployment 後驗證，未在本次變更中宣稱完成。

排程 Stage lifecycle 已加入 execution-scoped 模式：payload、sidecar 與 manifest
置於 `executions/{execution_id}/stage/`；Core 成功後以 immutable
`executions/{execution_id}/core-commit.json` 作為清理 fence。清理只接受已有
commit marker 的指定 execution，未 commit 的失敗／重試資料不會被刪除。Cloud
entrypoint 預設啟用此模式，並可用 `PREVIOUS_STAGE_EXECUTION_ID` 指定要清理的前次
成功 execution；Scheduler runtime 與雲端清理 smoke 已完成，詳如下方驗收紀錄。

2026-08-26 runtime smoke 已完成：Cloud Run executions
`janus-ingestion-core-6w8v9` 與 `janus-ingestion-core-vxtcp` 成功；前者輸出
8/8 sources、0 failure、Core reused 79,262，後者以前者的 commit fence 完成
Stage cleanup，前次 `core-commit.json` 保留。Cloud Scheduler
`janus-ingestion-daily` 現為 `ENABLED`，`30 7 * * *`、`Asia/Taipei`。Admin UI／
control DB settings 維護介面仍待後續；完整 incremental merge 已由 DuckDB
runtime 驗收。

DB-backed 五檔 runtime smoke `janus-ingestion-core-nbql7` 成功：從 control DB
讀取 `1102`、`2327`、`2330`、`2381`、`4958`，8 個來源產生 10 個 Stage
objects，`failed=0`、`core_created=0`、`core_reused=419`。FinMind 的 `2381`
與 TWSE events 在該窗口無資料，明確保存為 2 個合法 `empty`，不掩蓋 HTTP／
解析等真正失敗。Direct VPC ingress firewall 使用 private subnet
`10.42.0.0/24` 作 source range，只開放 target tag `janus-postgres-db` 的 5432；
Scheduler 驗收後恢復為 `ENABLED`。

2026-08-28 Trino → DuckDB cutover completed in development. Clean-image
canary `janus-ingestion-core-lngkm` completed in 4m38s with `failed=0`,
`core_created=0`, `core_reused=420`, and `core_updated=0`; the preceding
functional canary `janus-ingestion-core-89q6z` completed with `failed=0` and
`core_created=420`. Both runs read the five configured symbols
(`1102`, `2327`, `2330`, `2381`, `4958`) from the control DB and used the GCS
Iceberg warehouse `gs://gen-lang-client-0593591102-dev-core/warehouse/`.
The final image is
`ingestion-core@sha256:2e72c2a4e39188577e505a215557ebba797e8c5a08d3832243637be8b4fe64af`.
The SQL catalog migration creates the `janus_control.catalog` tables and
PyIceberg-compatible public updatable views; catalog Secret version 3 was
byte-verified against the private `janus_catalog` connection. Trino service,
build trigger, image, rollback tag, and old ingestion digest were removed;
Artifact Registry cleanup is active with dry-run disabled.

Job 亦支援 `INGESTION_DATE` 單日 replay，或以
`BACKFILL_START_DATE`／`BACKFILL_END_DATE` 執行最多 367 個日曆日的 bounded
range replay；`INGESTION_DATASETS` 可限制資料源。每次 replay 都使用新的 execution
ID，並沿用相同 Stage → Core commit fence。

2026-08-28 Web dev deployment：Cloud Build
`fd229529-e8c0-44c4-b0c3-2ef03c1aa691` 使用最小 build context 成功建立並 push
Web image，digest 為
`sha256:a42178256596da6bc0403f9f1bda45bac486da1788c3339ed78a98c2a085be40`。
Cloud Run revision `janus-web-00001-dvz` 已在 `us-central1` ready，使用
`web-runtime`、Direct VPC `private-ranges-only`、`janus-web` network tag，且未
開放匿名存取。Web runtime 已具備可選 PostgreSQL／Iceberg wiring；因尚未配置
Web 專用 control/catalog credential，該 revision 目前使用 safe fallback，DB
connected Web/Admin smoke、Mart Job runtime 與 authenticated HTTP 驗收未宣稱完成。

本機 Python 3.12 已安裝 `duckdb==1.5.5`；`python -m unittest discover -s tests`
結果為 59 tests passed，`compileall` 與 `git diff --check` 通過。

同日 authenticated HTTP smoke 已完成：Cloud SDK `cloud-run-proxy` 已安裝，
`janus-web-00002-472` custom audience 更新後，direct URL 與 localhost proxy
對 `/health`、`/admin/stocks`、`/assets/admin.css` 均回 HTTP 200。Cloud Run
仍為 user Invoker-only，未開放匿名；Token Creator 暫時 binding 已撤銷。

## P0 Core 第一批資料源

`ingestion_core.first_batch` 提供可重播的 credential-free JSON adapter，涵蓋
TAIEX／TPEx benchmark、PE／PB、法人、MOPS／FinMind financials、公司事件與
market activity（融資融券、借券、當沖、注意／處置、issued shares、turnover
等以 metric／unit 表示）。Normalizer 會保留 null 與原始單位，不對缺資料推算；
benchmark collection 與個股行情 collection 分離。`effective_trading_day` 對週末、
休市日與盤前執行回看最近有效交易日。所有 adapter transport 可注入 fixture，
raw payload 仍由 Stage/GCS 層保存，control database 僅保存 cache metadata；SQLite
reference 與 PostgreSQL adapter 均提供 bounded prune。第一批資料源的線上 upstream
API smoke 與實機 workload connectivity 仍需部署後執行。

Cloud Run ingestion Job 已以官方 TWSE／TPEx／MOPS OpenAPI 與 FinMind request
完成第一批 8 個來源的 Stage → Core 雲端 smoke；目前由 embedded DuckDB
寫入 GCS Iceberg。Execution
`janus-ingestion-core-n88jc` 為 8／8 Stage、0 failure，建立／重用合計 79,262
個 natural-key rows，並以來源／觀測日聚合成 8 個 Core partition objects（27.38
MiB）。同日 replay `janus-ingestion-core-nxmwc` 為 `core_created=0`、
`core_reused=79,262`，object count 維持 8，證明 create-if-absent partition commit
不產生重複資料。07:30 `Asia/Taipei` Scheduler 已 ENABLED；前次 Stage cleanup smoke
已完成。

## 2026-08-31 — P0 schedule／backfill／retention dev 驗收

GCP Cloud Build 驗證通過：Python 101 tests；Web Vitest 2、Playwright 5、typecheck、
ESLint 與 production build；PostgreSQL transaction／migration targeted build
`af628b6f-354d-4d68-93df-8c616976f11a`。全程未啟動 WSL。

dev migration `010_execution_runtime_options`、`011_control_settings_ownership` 與
`012_first_batch_source_ids` 已套用。`janus_control` 擁有 `admin_settings`、
`admin_audit` 與其 identity sequence，仍為 bounded non-superuser role；
`first-batch.source_ids` 使用 canonical provenance IDs。

scheduled execution `janus-ingestion-core-jmh8d` 成功，control execution
`dd8ad090-1daf-4522-94a9-6fc5bb8c9862` 為 `succeeded`，正式來源 items 保存
`Core committed`。指定 `2026-08-28`、`2330`、`twse` 的 queue backfill execution
`7362712f-5acf-4c5e-afd8-45fa33268c9e` 經 `janus-ingestion-core-kt9mq` 完成；
valuation 1 row、institutional 3 rows、market-activity 3 rows 已 commit，events 為
合法 empty。ingestion image digest 為
`sha256:ad00a77389beb4a636088e0b6ec9e0ba4fc2b371216d547865b97a599fd9342a`。

實機 smoke 同時發現並修正 PostgreSQL read transaction 在 upstream I/O 期間觸發
10 秒 idle-in-transaction timeout 的問題；repository 現以 autocommit 處理 reads，
write paths 仍使用 explicit transaction。Web dev `/admin/stocks` 未登入回 303 並導向
`/login`。Cloud Scheduler 維持 `30 7 * * *`、`Asia/Taipei`、enabled；Admin 變更
排程時間的自動 Scheduler reconciliation 仍列為後續工作。

## 2026-09-03 — Admin 狀態、來源、排程、版本與登入

Admin 股票資料狀態已改為 bounded aggregate；資料源設定提供 typed edit，並由後端
拒絕啟用 `candidate`／`blocked` 來源及以 authenticated actor 留下 audit。排程設定
成功同步既有 Cloud Scheduler 後才提交 control DB 版本。`/health` 回傳 Cloud Run
revision 並顯示於 Admin；Google 登入可解析 Google GSI 與 Janus session 並存的
cookie，登入期間顯示可存取的 loading 狀態，成功後不保留登入頁 history。

核心 50 使用 `coverage_membership_versions` 保存單調版本與 effective time，membership
rows 保留不可變更歷史 interval；PUT 以 expected version 防止 lost update，actor 只取
authenticated Google email，audit 保存原因與 added／removed diff。UI 會把下一版最低
生效時間推進一分鐘，避免重送相同 effective time；51 檔輸入在 live UI 被拒絕且版本
維持 v3。

GCP dev PostgreSQL build `04fdc438-e079-4182-9b1f-6a77675f06ca` 成功，migration
`013_membership_versions` 已套用既有 private PostgreSQL。Web build
`2873d608-74b3-4409-9c11-e4cf3638b800` 成功；revision `janus-web-00049-ws5` 使用
immutable digest `sha256:5c7db6bbb62b97105113d50f72cb5b494fd38fa61350b6a9c601ac10232c384d`。
真人 Google login 後依序建立 v1 `2330`、v2 新增 `2327`、v3 移除 `2330`；三版
effective interval、`tommylin15@gmail.com` actor、原因、版本與 audit diff 均由
PostgreSQL 實查確認。

dev-only `core-focus-smoke` 沒有固定 collection symbols；Cloud Run execution
`janus-ingestion-core-t72bf` 使用既有 ingestion digest
`sha256:b8840e7c456c3cafe3fee340c8ec3ebbee032c50c5be7ce9a74450bc7f0fea54` 成功。
persisted execution `9ffb6fb9-345f-47ac-a45d-0fdf7f12d8e5` 的
`requested_symbols=["2327"]`、status `succeeded`，MOPS financials 收到 28 rows 並
`Core committed`，證明 worker 依 v3 最新有效名單執行；smoke config 驗收後已 disabled。

驗收後資源 guard 仍為單一 `us-central1-a` `e2-micro`、30 GB `pd-standard`、private
IP、無 external IP；未部署 production、未建立新 VM／disk／snapshot／NAT，亦未呼叫
Artifact Analysis、Container Scanning 或 occurrence API。

## P0 WBS 4C Private Storage (2026-09-06)

Cloud Build contract `2b49fbbc-1dde-4091-9664-7ba33447f2ac` succeeded. PostgreSQL
image build `96ec69fc-5c1a-4b65-97de-cda22b57cba6` produced digest
`sha256:b7f927ea03656eda2c311d77004078efa8379242a3b7fa3ff413c9ec153a1216`;
IAP migration on `janus-postgres-dev` passed migration 016, A/B owner isolation,
event replay, role privilege and credential-column checks in a rolled-back test
transaction. Existing private-pipeline execution `janus-private-pipeline-wwxtl`
passed real GCS/Iceberg event／Skill isolation and cleanup using random owners.

The temporary Job image was restored to the existing `janus-api` digest
`sha256:ad6ef02c255be4c7666db8869879f6745c75a8c0c3a0760639aaf004a99a3894` and the
acceptance flag was removed. Codex managed-auth cleanup remains explicitly
`CLEANUP_PENDING` until an owner-scoped external credential cleaner exists.

## Sol model artifacts／public API／governance audit acceptance（2026-09-12）

- Local targeted Python suite for the changed paths: `46 passed`; additional pipeline,
  admin, cursor, and contract suites also passed. `py_compile`, shell syntax checks, and
  `git diff --check` passed.
- Cloud Build `35d9314c-6832-4d7c-aace-fa3a09a9e6da` built the PostgreSQL image; IAP SQL
  acceptance confirmed migrations `020`／`021`, audit tables, CAS execution, and public
  view-only privileges. Secret bundle version 15 contains the publication password; the
  value was not logged.
- Web revision `janus-web-00076-b4w` deployed to the existing dev Cloud Run service.
  Cloud Build `c0691a59-ee17-4920-9bde-29de34ac8a22` passed the health/public-report
  contract from a GCP worker, including publication-index lookup and immutable Iceberg
  snapshot parsing. An initial 503 was fixed by granting the existing Web runtime
  service account objectViewer on the existing Mart bucket.
- No production deployment, new VM/disk/NAT/snapshot, or new paid resource was created.
