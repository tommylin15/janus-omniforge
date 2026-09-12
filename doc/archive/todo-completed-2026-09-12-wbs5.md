# TODO 完成紀錄（2026-09-12：WBS-5）

本紀錄收納 WBS-5 已完成的實作與驗收項目；未完成條件仍保留在
[`doc/todo.md`](../todo.md)。

## Mart／Agents

- 建立可執行的 `intelligence_mart` package／Cloud Run Job entrypoint、bounded
  runtime 與 persisted queue claim；本機 targeted tests 25/25、GCP migration
  017／018、Cloud Build、完整 pipeline、replay、blocked case 與 62-object／11-table
  listing 通過。
- 完成 exact Core Iceberg snapshot reader、deterministic screening／Fundamental／
  Valuation／Positioning／Quant／Event Risk features、五角色 payload、PIT Evidence
  Validator、effective-weight Aggregator／Devil's Advocate、repository prompt／
  governance hash fence、Gemini-only optional structured narrative，以及 11 個 public
  Iceberg v2／Parquet data products。
- 建立 `core.dataset.ready.v1` → Mart workflow／event trigger；僅接受 ingestion
  成功事件，帶 execution ID 與 immutable Core snapshot ID，並驗證 failed／partial
  不觸發、重送冪等。migration 019、automatic trigger
  `janus-intelligence-mart-8g6qm` 與 Core execution dedupe 通過。
- Mart Job 僅透過 Direct VPC egress 與專用 PostgreSQL metadata roles 存取；feature／
  evidence payload 僅寫入 GCS／Iceberg。
- 固定 Mart execution input contract，禁止 Analysis 即時補抓或改寫 Core。
- 建立公開 versioned Iceberg Mart schemas、market regime／daily brief、sector
  rotation、candidate health、五角色 prompt contract、PIT evidence、insufficient-data
  gate、blocked／publishable view、immutable governance snapshot、deterministic
  rerun，以及 `mart_scoped_analysis` 的 industry／symbol scope 隔離。

## 公開 Mart LLM

- 建立 evidence-only structured prompt；模型不得產生 evidence 外數字或修改 score、
  confidence、quality、publication。
- 完成非 429 結構化失敗、LLM 失敗不寫 placeholder，以及 LLM 關閉時 deterministic
  output 不變的驗證。

## Mart 閉環

- 建立 GCS Mart warehouse／Iceberg namespace 與 versioned partition strategy，產製
  `spec.md` 定義的公開 Mart tables。
- 以 migration 建立 PostgreSQL report metadata／publication service index，具唯一鍵、
  bounded pool、statement timeout、retention 與 workload-specific role。
- 驗證 PostgreSQL 僅保存分析 metadata／artifact reference，私人 ledger 使用獨立
  schema／role；schema／integration test 阻擋完整 Mart payload 寫入 Free Tier VM。
- 發出 `mart.report.ready.v1`，並驗證 blocked 不進 publishable view。
- 驗證相同 Core snapshot、governance、schema／feature／model version 下 2330
  deterministic Mart 可重現。

## Persisted consumer／Admin Analysis authenticated acceptance

- 本機 targeted Python `70 passed`、Admin Vitest `3 passed`、Admin Playwright `9
  passed`；Python／JavaScript syntax 與 `git diff --check` 通過。
- 既有 GCP dev project `gen-lang-client-0593591102` 的 Mart、ingestion-core 與 Web
  image 已部署；Web revision `janus-web-00073-lw9`，Web digest
  `sha256:da0222d465cff05780064ff5b9876f4478228f1c2acfd37d17248120e40979fa`，Mart
  digest `sha256:700ab9d6247a84338ed1302ac476a8d640b2deba91e777a0af749b6d7a424db3`，
  ingestion digest `sha256:dacfa965dbc93005942c2190a7531ba4343f3967299c8bf1df5f459b22ef4070`。
- GCP dev authenticated Admin 以 `first-batch` immutable Core snapshot 選取 2330，
  建立 Analysis execution `8851256a-7cf5-456f-b5dd-f8384ca571d0`；queued 後由既有
  Mart Job execution `janus-intelligence-mart-dk558` 消費並成功完成，Admin 顯示
  `succeeded`、retry `0`、進行中 `0`。
- 「Mart 分析」入口以 `2026-09-10`／`symbol`／`2330`／`quant`／`publishable`
  篩選顯示單筆 `complete`／`publishable`、completeness `75.9%`，artifact link
  可解析至 immutable GCS metadata object；登入前 POST 亦正確 fail-closed 為
  `authentication required`。

## 公開 Mart LLM provider diagnosis

- 本機 Gemini targeted test `17 passed`；Python compile 與 `git diff --check` 通過。
- Gemini REST adapter 改用 `responseFormat.text`、`mimeType=APPLICATION_JSON`、
  小寫 JSON Schema，並以 bounded／redacted provider diagnostics fail-closed。
- Cloud Build `e2a5410b-8c4d-4d1d-918f-5506e931d1e2` 成功，dev Mart image digest
  `sha256:013db1d7fdca9f8da12a9603affff197c5fd36e595f23e974ad2271a1c73b652`。
- Probe `69d9f07a-d459-4eeb-809d-d6b69318021a` 定位 `application/json` enum 錯誤；
  修正後 probe `3f86a955-88be-4d1e-ad51-bc91885a7300`／Cloud Run execution
  `janus-intelligence-mart-8jfp6` 成功，`gemini-3.8-flash` structured narrative
  驗證通過，deterministic report 仍 `invalid`／`blocked` 且未公開。

## Sol model artifacts／public API／governance audit（2026-09-12）

- Mart execution now writes model, evaluation, and governance-diff JSON artifacts with
  create-only GCS semantics and SHA-256 references in the execution manifest.
- Public Web route reads only `publication.publishable_mart_reports`, verifies the
  immutable GCS hash and exact Iceberg snapshot, and fail-closes `blocked`／
  `insufficient_data` rows. Local targeted tests: `46 passed`.
- PostgreSQL migrations 020／021 add audit CAS／bounded retention and the dedicated
  read-only `janus_public_api` role. GCP dev migration SQL acceptance passed; Cloud Build
  `c0691a59-ee17-4920-9bde-29de34ac8a22` passed the live Web public-report contract.
- Initial Web probe returned 503 because the existing Mart bucket lacked the Web runtime
  objectViewer binding; the binding was added to the existing bucket and the same contract
  then passed. No production deployment or new paid resource was created.
