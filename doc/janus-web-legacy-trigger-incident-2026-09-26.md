# `janus-web` legacy trigger 事故紀錄（2026-09-26）

## 摘要

2026-09-25 的 `main` push 後，Cloud Run 出現已退役的 `janus-web` service，revision 無法啟動並回報 container 未在 `PORT=8080` 上 listen。調查確認該訊息是次級症狀；實際啟動錯誤為 legacy image 執行 `apps/web/server.py` 時缺少 `uvicorn`。

更上游的系統性根因是：2026-09-13 已退役的 regional Cloud Build trigger `janus-web` 仍存在，與目前 canonical GitHub Actions deployment controller 並行。該舊 trigger 在 `main` push 時重新 build `apps/web/Dockerfile` 並嘗試部署 `janus-web`，因此把已刪除的 legacy Cloud Run service 復活。

目前 canonical Web/API runtime 是 `janus-api`，不是 `janus-web`。

## 影響範圍

- Cloud Console 顯示 `janus-web` update / traffic forwarding 失敗。
- 失敗 revision：`janus-web-00001-5mp`。
- `janus-web` 沒有 ready revision，也沒有承接正式流量。
- canonical `janus-api` 在事故期間仍可用；本次修復沒有把 legacy `janus-web` image 修活，也沒有切換 canonical runtime。

## 根因證據

### Container 啟動失敗

`apps/web/Dockerfile` 使用 ingestion-core dependency lock，但 `apps/web/server.py` 啟動路徑會 import `uvicorn` 並執行 FastAPI app。實際 Cloud Run revision log 顯示：

```text
ModuleNotFoundError: No module named 'uvicorn'
```

因此 container 在開啟 8080 前即退出。Cloud Run 顯示的「failed to start and listen on PORT=8080」不是 port mapping 或 startup timeout 的主要根因。

### 已退役 trigger 重新建立 service

舊 regional Cloud Build trigger：

- name: `janus-web`
- id: `c08067dd-5c44-414f-9e8d-9d94e89b4089`
- Dockerfile: `apps/web/Dockerfile`
- image: `web:main`
- runtime: `janus-web`

2026-09-25 09:53:39Z，commit `54a62b3fc5ae52ad481aaad03dec9d8fbaa33d5b` 觸發 regional build：

- build id: `ec57b891-912e-476b-bfe9-4eb20b1e0525`
- trigger id: `c08067dd-5c44-414f-9e8d-9d94e89b4089`
- result: `FAILURE`

同一個 push 另由 canonical GitHub deployment path 建置／部署 `janus-api`。因此事故本質是兩套 deployment controller 並存，而不是 canonical `janus-api` deploy target 寫錯。

## 修復

2026-09-26 以 guarded dev repair 執行下列動作：

1. 先驗證 canonical `janus-api` 有 ready revision，且 `/` 回傳 307 redirect 到 `/app`、`/app/` 可載入 Janus 入口。
2. 驗證 `janus-web` 沒有 ready revision，且 image identity 符合已知 legacy `web` image。
3. 驗證 Cloud Build trigger identity、runtime 與 Dockerfile 都精確匹配 legacy `janus-web`。
4. 刪除 regional Cloud Build trigger `c08067dd-5c44-414f-9e8d-9d94e89b4089`。
5. 刪除 failed Cloud Run service `janus-web`。
6. 再次驗證 trigger 與 service 均不存在，且 canonical `janus-api` 仍健康。

repair run：GitHub Actions `36228236969`。

一次性 repair workflow 與 request 在完成後已從 `main` 移除，避免留下不必要的 mutation surface。

## Live acceptance

修復後另以獨立 read-only probe 驗收，不依賴 repair script 自己的結果：

### `janus-web`

GitHub Actions run `36228292815`：

```text
ERROR: (gcloud.run.services.describe) Cannot find service [janus-web]
janus-web service is absent, matching the retired runtime state
```

結果：`PASS`。退役 service 確認不存在。

### `janus-api`

GitHub Actions run `36228336655`：

- latest created revision: `janus-api-g27c8a0b7d091-config`
- latest ready revision: `janus-api-g27c8a0b7d091-config`
- untagged latest traffic: `100%`
- image digest: `sha256:002e52dbebb21dfeb231a556e3c049728e54c9aad2246f3ba834bd1eb2e73991`
- `/`：307 redirect 到 `/app`
- `/app/`：live entrypoint reachable

結果：`PASS`。canonical runtime 在 legacy cleanup 後仍正常。

## Deployment controller consolidation 驗證

2026-09-26 以 bounded read-only probe（GitHub Actions run `36228985208`）直接驗證 `janus-ingestion-core` 與 `janus-intelligence-mart` 的 deployment controller 狀態。

### Canonical GitHub path

目前 `.github/workflows/deploy-dev.yml` 會在 `main` 對 ingestion-core / intelligence-mart 變更時執行 targeted tests，之後呼叫 `scripts/gcp/deploy-dev.sh ingestion-core` 或 `scripts/gcp/deploy-dev.sh intelligence-mart`。`deploy-dev.sh` 明確宣告 GitHub Actions 是 dev deployment controller，並透過 `gcloud builds submit` 建置後套用 canonical Cloud Run Job configuration。

### GCP trigger 現況

`global` location 沒有同名 triggers；`us-central1` 仍存在且未 disabled：

- `janus-ingestion-core`
  - trigger id: `5e201f5a-c206-4006-92b9-40a53c4155ed`
  - config: `cloudbuild.yaml`
  - Dockerfile: `jobs/ingestion-core/Dockerfile`
  - runtime: `janus-ingestion-core`
  - image tag: `main`
- `janus-intelligence-mart`
  - trigger id: `b8215cb9-1823-401d-b293-65fbdf73ce30`
  - config: `cloudbuild.yaml`
  - Dockerfile: `jobs/intelligence-mart/Dockerfile`
  - runtime: `janus-intelligence-mart`
  - image tag: `main`

### 同一 commit 的雙重 build lineage

commit `54a62b3fc5ae52ad481aaad03dec9d8fbaa33d5b` 提供直接重複證據：

regional trigger path 在 `2026-09-25T09:53:39Z` 同時啟動：

- ingestion-core build `841703eb-97da-4196-b2d4-58a52e60b0c6`，`buildTriggerId=5e201f5a-c206-4006-92b9-40a53c4155ed`，結果 `FAILURE`
- intelligence-mart build `1fc89521-413d-491d-826c-27353a1f6ca4`，`buildTriggerId=b8215cb9-1823-401d-b293-65fbdf73ce30`，結果 `FAILURE`

canonical GitHub path 對同一 commit 隨後另外建立無 trigger build：

- ingestion-core build `514b90d9-3b7d-4a0d-b1b9-3ab412f77e9e`，`buildTriggerId=null`，image tag `dev-54a62b3...`，結果 `SUCCESS`
- intelligence-mart build `cbac7b55-90ea-4702-b228-d8942dddff9f`，`buildTriggerId=null`，image tag `dev-54a62b3...`，結果 `SUCCESS`

因此「兩套 deployment controller 並存」已由 live build lineage 證實，不再是推測。

### Current runtime

probe 當下兩個 Cloud Run Jobs 都為 `Ready=True`：

- `janus-ingestion-core` generation `106`，image digest `sha256:d81bcac5e99f873f42b231535b5c5ab0640d6d10b447fcbfbd0a3602c1d39d5d`
- `janus-intelligence-mart` generation `61`，image digest `sha256:a6299d50160f820437350fb55afc1cfca62a6c748d199b56b154625cf33bf4e5`

兩者 `lastModifier` 都是 `janus-ci@gen-lang-client-0593591102.iam.gserviceaccount.com`。

### 判定

- deployment-controller duplication：`CONFIRMED`
- canonical controller：GitHub Actions `deploy-dev.yml` + `scripts/gcp/deploy-dev.sh`
- regional Cloud Build triggers：仍存在，屬於待 consolidation 的 legacy / duplicate controller surface
- current Cloud Run Jobs：`Ready=True`
- consolidation cleanup：`NOT YET APPLIED`

本次驗證只做 read-only runtime inspection；未刪除或 disable ingestion-core / intelligence-mart triggers。