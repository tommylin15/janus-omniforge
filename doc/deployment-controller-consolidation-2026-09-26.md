# Dev deployment controller consolidation（2026-09-26）

## 摘要

2026-09-26 完成 `janus-ingestion-core` 與 `janus-intelligence-mart` 的 dev deployment controller consolidation。

先前 live evidence 已確認，同一個 `main` commit 會同時被兩套 controller 處理：

1. canonical GitHub Actions `.github/workflows/deploy-dev.yml` → `scripts/gcp/deploy-dev.sh`；
2. legacy regional Cloud Build triggers（`us-central1`）。

regional triggers 會對同一 commit 另外啟動 build，形成 duplicate controller surface。此次工作以 guarded cleanup 移除兩個 regional triggers，並在 cleanup 後使用 canonical GitHub path 做 bounded deployment acceptance，再以獨立 read-only probe 驗證 triggers 沒有復活且兩個 Cloud Run Jobs 維持 Ready。

## Cleanup targets

只刪除下列兩個已驗證 identity 的 regional triggers：

- `janus-ingestion-core`
  - trigger id: `5e201f5a-c206-4006-92b9-40a53c4155ed`
  - region: `us-central1`
  - Dockerfile: `jobs/ingestion-core/Dockerfile`
  - runtime: `janus-ingestion-core`
  - image: `ingestion-core:main`
- `janus-intelligence-mart`
  - trigger id: `b8215cb9-1823-401d-b293-65fbdf73ce30`
  - region: `us-central1`
  - Dockerfile: `jobs/intelligence-mart/Dockerfile`
  - runtime: `janus-intelligence-mart`
  - image: `intelligence-mart:main`

沒有變更其他 Cloud Build triggers、Cloud Run services/jobs、Scheduler 或 IAM topology。

## Guarded cleanup evidence

GitHub Actions run：`36229366763`。

mutation 前 guards：

- 兩個 trigger 的 ID、name、`cloudbuild.yaml`、`_DEPLOY_TARGET=job`、Dockerfile、image name、`_IMAGE_TAG=main`、runtime name 必須全部精確匹配；
- 兩個 Cloud Run Jobs 必須先為 `Ready=True` 且已有 runtime image；
- mutation 前完整 trigger JSON 與 Job image state 必須先匯出；
- rollback artifact 上傳成功後才允許 delete。

rollback artifact：

- artifact id: `10902226767`
- name: `legacy-deployment-trigger-backup-8feae12b3df3294bc1586ca10a7f1d47a38f753d`
- digest: `sha256:9b9054f51e86c53662b76b90836835acaf812cb51f60ca2f69ea45ecfdb84a13`
- retention: 30 days

cleanup result：

- trigger `5e201f5a-c206-4006-92b9-40a53c4155ed` deleted；
- trigger `b8215cb9-1823-401d-b293-65fbdf73ce30` deleted；
- delete 後兩個 trigger name 不再出現在 `us-central1` trigger list，且兩個 trigger ID 都無法 describe；
- cleanup 當下兩個 Jobs 仍 `Ready=True`，且 image 未因 trigger-only cleanup 改變。

cleanup 後、canonical acceptance 前的 images：

- `janus-ingestion-core`: `sha256:d81bcac5e99f873f42b231535b5c5ab0640d6d10b447fcbfbd0a3602c1d39d5d`
- `janus-intelligence-mart`: `sha256:a6299d50160f820437350fb55afc1cfca62a6c748d199b56b154625cf33bf4e5`

## Canonical GitHub bounded deployment acceptance

acceptance commit：`5e572e6684d88b452f6ee81e0b5b46a21058c4ce`。

該 commit 只對兩個 Job Dockerfile 加入 stable controller 註解，用來命中 canonical `deploy-dev.yml` path detection；不改 application runtime behavior。

GitHub Actions run：`36229503909`。

scope detection：

- `test-ingestion`: `SUCCESS`
- `test-mart`: `SUCCESS`
- `test-api`: `SKIPPED`
- `deploy-api`: `SKIPPED`

因此本次 bounded acceptance 沒有外溢到 API runtime。

### ingestion-core

canonical workflow 執行：

```text
bash scripts/gcp/deploy-dev.sh ingestion-core
bash scripts/gcp/verify-dev.sh ingestion-core
```

Cloud Build：

- build id: `6ff98342-ea87-4e40-bd58-bfcffdbb2de2`
- image tag: `ingestion-core:dev-5e572e6684d88b452f6ee81e0b5b46a21058c4ce`
- result: `SUCCESS`

Cloud Run Job update 成功；`verify-dev.sh` 回報 `Ready=True`。

### intelligence-mart

canonical workflow 執行：

```text
bash scripts/gcp/deploy-dev.sh intelligence-mart
bash scripts/gcp/verify-dev.sh intelligence-mart
```

Cloud Build：

- build id: `69277068-9412-448c-87e6-ee05c0181eb9`
- image tag: `intelligence-mart:dev-5e572e6684d88b452f6ee81e0b5b46a21058c4ce`
- result: `SUCCESS`

Cloud Run Job update 成功；`verify-dev.sh` 回報 `Ready=True`。

## Independent post-acceptance verification

canonical deployment 完成後，另以 request commit `827be464a7fb19f642e05378b26f18361dfd1e00` 將 guarded workflow 切到 `verify` mode；此 mode 明確輸出 `verify mode: no trigger mutation requested`，只做 read-only verification。

GitHub Actions run：`36229702938`，result `SUCCESS`。

驗證結果：

- `us-central1` 不存在名為 `janus-ingestion-core` / `janus-intelligence-mart` 的 regional triggers；
- trigger ID `5e201f5a-c206-4006-92b9-40a53c4155ed` 不再 resolve；
- trigger ID `b8215cb9-1823-401d-b293-65fbdf73ce30` 不再 resolve；
- `janus-ingestion-core`: `Ready=True`，image digest `sha256:8009ae8eb017a463ea1f145942f2de910b64dc0e48234d0c8c8431c03fd6f9d8`；
- `janus-intelligence-mart`: `Ready=True`，image digest `sha256:d0d5100085fe2f30e4b87891f0e264327cf244f46685826aa180252b39d9c456`。

這兩個 digest 與 cleanup 前不同，符合 canonical GitHub acceptance 已實際更新兩個 Jobs；同時 legacy regional trigger 沒有被 acceptance push 重新建立。

## 判定

- duplicate deployment-controller condition：`RESOLVED`
- canonical dev deployment controller：GitHub Actions `.github/workflows/deploy-dev.yml` + `scripts/gcp/deploy-dev.sh`
- legacy regional triggers：`ABSENT`
- `janus-ingestion-core` deployment acceptance：`PASS`
- `janus-intelligence-mart` deployment acceptance：`PASS`
- current Jobs：`Ready=True`
- workload execution / dataset live acceptance：**不在本次 consolidation scope**；Job `Ready=True` 只證明 deployment/runtime configuration acceptance，不等同 ingestion/mart workload live-data acceptance。

GitHub Actions runner post-job 仍會出現既有 `token-savior` `.gitmodules` cleanup warning 與 Node.js 20 deprecation warning；兩者發生於成功的主要 steps 之後，本次 runs 的 job conclusion 仍為 `success`。此 warning 不納入本次 controller consolidation 的完成條件，但應由獨立 repo/tooling hygiene 工作處理。