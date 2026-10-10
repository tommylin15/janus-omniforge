# Janus CI/CD — GitHub Actions + GHCR + Cloud Run 正式目標契約

## 現況與證據入口（2026-10-10）

**目前核准的 dev GHCR CI/CD 發布範圍：PASS／CLOSED。** 完整 Release、公開 GHCR、固定 Preview、四 Jobs 8/8 live canary、API 新→舊→新 100% traffic rollback 證據集中在 [2026-10-10 結案紀錄](../archive/cicd-ghcr-api-promotion-2026-10-10.md)；本 SPEC 不複製版本號與執行流水帳。使用者明確豁免四項額外／舊 AR 歷史回復演練，狀態為 `WAIVED_BY_OWNER`，技術實測仍為 `NOT_VERIFIED`／`BLOCKED`，細節見 [Parking Lot](../parking-lot.md)。

本節以下是**後續版本仍需遵守的發布契約**，不因這次 CI/CD 結案而取消必要的 SHA、tests、owner/auth、pinned digest、mutex／lease、readback、可回復基準與 fail-closed。實際操作以 [部署 Runbook](../runbook-dev-deploy.md) 為準，當前任務轉入 [B 組](../todo.md)。

## 1. 唯一正式發布鏈

`ChatGPT → GitHub → GitHub Actions → GCP API → GitHub Actions Logs → ChatGPT`

| 節點 | 必須完成 | 禁止誤用 |
|---|---|---|
| GitHub `main` | 完整 commit SHA、指定工作包、審核與 gate 資料 | 以 tag 或單一中途 commit 猜整包範圍 |
| GitHub Actions（CI） | 對待發布 SHA 完整執行適用的 Python／Flutter／schema／migration／security／container tests；全數 PASS | 以 `ci-v2.yml` selective PASS 代替完整 Release tests |
| GitHub Actions（build/publish） | Docker build、GHCR push、公開 package anonymous pull 檢查、不可變 image digest | 呼叫 Cloud Build；推送 GCS／Artifact Registry |
| GCP API（dev Release） | WIF 最小權限；固定 digest、0% API candidate、真實驗收、明確升流量／回滾、Job 安全 gate | `gcloud run deploy --source`、auto-traffic、用 mutable tag 部署 |
| GitHub Actions Logs / summary | gated result、SHA、digest、revision、run ID、失敗分類、遮罩診斷、rollback evidence | 輸出 raw secrets、私人 owner data、無遮罩的 build logs |
| ChatGPT | 讀取相同 workflow run／commit 的證據，回報 PASS／FAIL／PARTIAL／UNKNOWN | 把 workflow success 或文件完成當 live acceptance |

日常 `main` Push 可以執行 selective CI 快速回饋，**正式發布必須另走完整測試的顯式 GitHub Actions Release gate**。Release 不因 Push 自動變更 Cloud Run traffic 或 Job image。跨 commit baseline 從「上一次確認成功發布」至本次目標完整 SHA 計算；同 SHA retry 須冪等且舊 SHA 不覆蓋新 SHA。

## 2. 映像供應與 GCP 使用限制

- GHCR repository / package 須**公開**；即使 GitHub source repository 是公開，仍需分別驗證 GHCR package visibility、匿名 pull、manifest／digest。使用 `ghcr.io/<owner>/<image>@sha256:<digest>` 並對 Cloud Run 實際讀回同一 digest。GHCR 的 CI push 使用受限 `GITHUB_TOKEN`／`packages: write`，不把 registry token 傳給 Cloud Run。
- Google Cloud 官方文件支援 Cloud Run **直接使用公開 GHCR** image；私人 GHCR 需 Artifact Registry remote repository 等替代路徑，屬**本政策不接受的路徑**。外部 image 是否可讀、Cloud Run image import／cache、image 層／可用性必須做真實 dev 探測；若失敗，停止 candidate，不偷偷改成 Artifact Registry mirror。
- Release automation 不建／呼叫 Cloud Build／Trigger、不推 image 或寫 release receipt／mutex 到 Artifact Registry／GCS，不新增 Compute Engine Docker host。這是**部署供應鏈**限制；現有 Iceberg／canonical／business data pipeline 的 GCS 讀寫不受此限制，也不能把舊 GCP 資產「存在」誤判為新 pipeline 主動寫入。
- 對 image lifecycle、GHCR 可用性、舊 revision 必須留存的 digest 做引用清單；暫不執行大規模 image／bucket 刪除。Cloud Run 平台可能進行自身 caching／import，不能冒充已證明「GCP 底層完全零儲存」。

官方依據：[Cloud Run supported container registries](https://docs.cloud.google.com/run/docs/deploying)；[0% candidate、tag 與 rollback](https://docs.cloud.google.com/run/docs/rollouts-rollbacks-traffic-migration)。

## 3. 候選、驗收、升流量與 Jobs

1. 先比對 `main` SHA、完整測試 CI、GHCR public digest、WIF 權限及既有 dev service／Job／Scheduler 的 readback；取得目前 traffic、revision、Job image、環境與 Secret **reference**（非 secret value），檢查 deployment mutex／active execution。
2. 在**既有 Cloud Run Service** 以固定 digest 建立 `--no-traffic --tag <candidate-tag>` revision，讀回 revision name、ready condition、digest 及原本 traffic 未被變更。0% 指正常 service traffic；tag URL 仍允許被授權測試流量。
3. 對 tag URL 跑真實 dev health、未登入拒絕、authenticated owner／OAuth／canonical PnL／MCP、migration／schema 與本次受影響功能的 evidence；status 缺失維持 `UNKNOWN`。不能把 unauthenticated smoke PASS 冒充完整 authenticated gate。
4. 全部必需 gate PASS 才切換到該**明確 revision**（不得使用無驗證 `LATEST`），readback traffic、digest 與使用者可見功能。出錯則恢復先前 traffic／revision 並確認回滾讀回。
5. **Cloud Run Jobs 沒有 0% traffic revision**。四元件中的 ingestion／Mart／private Job 需另設 digest pinning、active execution／Scheduler fence、快照、受控 canary、必要 migration、rollback；不能在 API 0% candidate 階段更新現役 Job image，也不能因單一 API PASS 提前宣稱四元件 Release 完成。
6. 在新版本驗收完成前保留前一版已驗證 image／config 與必要 evidence；失敗／timeout 以 bounded readback、有限重試及復原為準，不重送未知狀態的 Job。新流程使用原有跨 runtime owner Git-ref lease 與 Actions concurrency；每次 Release 仍須核對持鎖者、持久 receipt 與安全解鎖狀態，不能只靠 Actions concurrency。
7. 2026-10-09 使用者收斂範圍：舊 Revision／映像與其他舊 CI/CD 資產清理不屬於本次驗收或結案條件。上一成功版本、digest、設定與回滾證據仍須保留。

## 4. WIF / IAM 與唯讀 Cloud Build 診斷

- GitHub Actions 設 `id-token: write` 以取得 OIDC；WIF 信任範圍限制 repository、ref、workflow/environment，release deploy principal 僅限既有 dev Cloud Run 必要的最小修改與 readback 權限；如需 service identity 使用權則單獨授權。不得將長期 GCP private key 存入 GitHub。
- 既有 Cloud Build 的查詢是**診斷工具，不是新流程的 build step**。在 WIF 診斷身分具 `cloudbuild.builds.get`（必要時 list）與 `logging.logEntries.list` 等唯讀權限時，依 project／region／Build ID 取得 `status`（例如 `SUCCESS`／`FAILURE`）、失敗 step 名稱／ID、step status／exit code（如有），再讀 bounded Logging records 產生**allowlist + redaction** 後的錯誤摘要。只顯示經過資料最小化的欄位，不直接列印原始 log、secret／token、IAM payload 或敏感環境變數；GitHub Actions Logs／summary 保存來源 Build ID、查詢時間、是否部分缺值，再由 ChatGPT 讀取。
- 權限不足、Build 不存在、log 空缺或失敗資訊不全時顯示 `UNKNOWN / BLOCKED`，不得依猜測填上 `SUCCESS` 或失敗 step。診斷不呼叫 `gcloud builds submit`、`builds triggers run` 或任何新的 Cloud Build build／artifact 寫入操作。
- 建置／發版與 Cloud Build 歷史診斷應分離 workflow／IAM 職責；新增 IAM 擴張、服務或付費資源須依專案授權規則處理。

## 5. 歷史 CI/CD 遷移快照

2026-10-08 當時「舊版本仍服務流量／新版 Jobs 尚未上線」等盤點已被真實發布取代，完整保留於 [遷移歷史盤點](../archive/cicd-v2-inventory-2026-10-08.md) 及 [operations evidence](operations-and-testing.md)，**不再構成 active TODO**。

## 6. 本次排除範圍

舊 Cloud Run Revisions、GHCR／Artifact Registry 映像、GCS CI/CD 資產清理不列 active TODO，也不作為新版流程結案條件。既有清理工具不接入新版 Release；歷史盤點只保存證據。發布前仍須證明舊入口不能競跑，並保留回滾所需資產。
## 7. 驗收紀錄

本次真正 Release、Jobs／API live acceptance 與使用者核准豁免各自有獨立收據；見 [結案證據](../archive/cicd-ghcr-api-promotion-2026-10-10.md)、[dev scope](../status.md)。舊版未完成清單僅供 archive 回溯，下一階段請依 B 組 active TODO，不把歷史 CI/CD 當作新 blocker。
