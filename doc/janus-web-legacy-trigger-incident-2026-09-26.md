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

## 後續治理觀察

同一時段的 runtime evidence 亦顯示 `janus-ingestion-core` 與 `janus-intelligence-mart` 的 regional Cloud Build triggers 曾與 GitHub deployment path 並行觸發並失敗。這兩個 workload 不屬於本次 `janus-web` 修復範圍，本事故沒有刪除或修改它們；應另開 bounded deployment-controller consolidation 項目確認是否仍需要保留 regional triggers，避免把未驗證的相關風險包裝成本次已完成。