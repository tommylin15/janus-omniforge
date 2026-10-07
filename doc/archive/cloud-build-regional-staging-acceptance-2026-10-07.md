# Cloud Build regional source staging acceptance — 2026-10-07

## 結論

Cloud Build **source-bearing** submission 已統一固定到 `us-central1`，source staging 固定使用既有：

`gs://gen-lang-client-0593591102-cloudbuild-regional/source`

不再依賴 legacy default：

`gs://gen-lang-client-0593591102_cloudbuild/source`

Implementation commit：`c49dc7398edac3926de8fecb248fbf06d556fa7d`。

## 防回歸

`tests/test_container_build_contract.py` 新增 repository-wide contract：

- 掃描 `.github/workflows` 與 `scripts/gcp` 的 `gcloud builds submit`；
- 任何 **有 source** 的 submit 必須有 explicit `--region`；
- 任何 **有 source** 的 submit 必須有 `--gcs-source-staging-dir`；
- staging path 必須落在 approved `-cloudbuild-regional/source`；
- research async build 的 polling `gcloud builds describe` 必須使用與 submit 相同的 `GCP_REGION`。

Portfolio contract run `37570671722`：PASS。

Deploy dev workflow `37570672091`：

- detect：PASS
- test-api：PASS
- test-ingestion：PASS
- test-mart：PASS
- deploy-ingestion：PASS
- deploy-mart：PASS
- deploy-private-pipeline：PASS
- deploy-api：PASS

## 真實 Cloud Build 證據

四個 deployment build 都同時滿足「source 進 regional staging bucket」與「build location=us-central1」：

| Component | Build ID | Source staging | Location | Result |
| --- | --- | --- | --- | --- |
| ingestion-core | `42e1b992-1e84-41bc-8d72-ab5cc1a1f843` | `gs://gen-lang-client-0593591102-cloudbuild-regional/source/...` | `us-central1` | SUCCESS |
| intelligence-mart | `aefa3650-b9c7-444c-812f-b9b81177ce39` | `gs://gen-lang-client-0593591102-cloudbuild-regional/source/...` | `us-central1` | SUCCESS |
| private-pipeline | `674b8249-03a2-41ba-934c-3e7093f06bc2` | `gs://gen-lang-client-0593591102-cloudbuild-regional/source/...` | `us-central1` | SUCCESS |
| api | `f916a761-9399-4a8c-ba3a-12b0371a2203` | `gs://gen-lang-client-0593591102-cloudbuild-regional/source/...` | `us-central1` | SUCCESS |

## no-source build 邊界

`portfolio-live-acceptance.yml` 的 migration 030 build 使用 `--no-source` 且其 config 為 `CLOUD_LOGGING_ONLY`，因此它不是 legacy source bucket 的建立路徑。

曾嘗試把該 no-source build 改成 `us-central1`：

- regional build `b0eb9311-ecec-4357-adbd-415f67a2c375`：build 建立於 `locations/us-central1`，內部 VM/IAP step exit 255；
- retry regional build `d02414e4-2456-4abe-8120-a7d341cb84e7`：相同 exit 255；
- 將該 no-source probe 恢復原本 global 後，build `6cafcc61-0a1d-467d-928a-3b9c656edf2c` 仍在同一 VM/IAP step exit 255。

因此 migration 030 IAP failure 與本次 source staging regionalization 無因果證據；不把它列為本修正 blocker，也不為修 source bucket 擴 IAM。

Follow-up commit `dd7e436e532cec10afab9ba7c9e5fc1bae4dda09` 僅將該 no-source probe 恢復原 execution location。

## 完成判定

本項「防止 `gen-lang-client-0593591102_cloudbuild` 因 repository source build 再生」的 implementation、contract test、CI、deployment 與 live Cloud Build evidence 均已完成。

後續 cleanup：使用者已於 2026-10-07 手動刪除 legacy bucket `gen-lang-client-0593591102_cloudbuild`。此刪除動作依使用者回報記錄；目前正式預期狀態為 legacy bucket 不存在、`gen-lang-client-0593591102-cloudbuild-regional` 保留。若 legacy bucket 再次出現，即視為 regression，需追查 repo 外手動命令、外部 workflow 或其他 tooling 建立來源，不得把它重新納入 canonical deployment。


## Cleanup 後不可回退規則

- `gen-lang-client-0593591102_cloudbuild` 已列為 retired resource name；active build path 不得再引用。
- `tests/test_container_build_contract.py` 新增 hard guard 禁止 active workflow、`scripts/gcp` 與 `cloudbuild.yaml` 再出現該 legacy bucket 名稱。
- 未來若 GCP inventory 再看到該 bucket，狀態應標記為 regression／unknown creator，先追查來源，不得自行修改 runbook 說它是正常資源。
