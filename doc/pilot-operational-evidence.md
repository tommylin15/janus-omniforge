# Dev Pilot Operational Evidence Ledger

更新：2026-09-26

用途：為 `WBS-8-DEV-PILOT-RUN` 的六個 calendar months evidence window 保存小型、可持續追加的 operational checkpoint。`pilot_started_at=2026-09-24T15:29:19Z`。本檔不是新的 implementation source of truth；目前實作與完成狀態仍以 GitHub `main`、實際 GCP dev runtime、tests／CI／deployment／integration evidence 為準。資料不足時一律記為 `unknown`／`not observed`，不得用文件推測成功。

完整歷史 implementation／test／deployment ledger 仍保留於 [`spec/operations-and-testing.md`](spec/operations-and-testing.md)。由於該檔已很大，GitHub connector 無法安全做 server-side patch 時，不以整檔覆寫方式追加 checkpoint；本檔專門保存 Pilot evidence window 的新增 bounded checkpoint，並由 [`status.md`](status.md) 提供目前狀態入口。

## Checkpoint 001 — 2026-09-26

觀察窗口：`2026-09-24T15:29:19Z` 至 `2026-09-26T06:32:55Z`。

### Scheduler／ingestion

- 自然排程 Cloud Run execution `janus-ingestion-core-n8bs2` 由 `janus-ingestion-scheduler@gen-lang-client-0593591102.iam.gserviceaccount.com` 建立於 `2026-09-25T23:30:01.699740Z`，即 Asia/Taipei `2026-09-26 07:30:01`。這是既有 `janus-ingestion-core` Job 的真實 Scheduler path，不是 fixture。
- Execution 使用既有 `first-batch`，`INGESTION_DATASETS` 為 8 個既有 dataset，`MART_JOB=janus-intelligence-mart`、`MART_OPERATION=queue`；job 維持 1 task、1 vCPU、1 GiB、`maxRetries=1`。
- 該 execution 最終 `Completed=False`、`failedCount=1`、`retriedCount=1`。attempt 0 與 attempt 1 都以 container `exit(1)` 結束；application failure summary 兩次都列出 `twse-valuation`、`twse-institutional`、`twse-market-activity`，target date 均為 `2026-09-25`，error 均為 `ValueError`。
- Fresh read-only runtime inspection 由 GitHub Actions `Inspect dev runtime` run `36224058493` 完成；inspection workflow 成功只代表 evidence 讀取成功，不代表 `janus-ingestion-core-n8bs2` workload 成功。

### Manual intervention／calendar repair

- 上述 failure 保留為 Pilot operational failure evidence，沒有因後續修復而刪除或改寫。
- 版本化 migration `029_twse_2026_holiday_overrides.sql` 後續透過既有 operator IAP 路徑套用；migration marker 與 `2026-09-25`／`2026-09-28` holiday overrides 已有 live evidence。沒有為修復新增 GCP resource 或擴大 IAM。
- 修復後三個受影響 dataset 已分別完成 bounded live acceptance，requested date 均為 `2026-09-26`，正確回推 `2026-09-24`：
  - `twse-valuation`：execution `janus-ingestion-core-7z8kv`，最終 `Completed=True`、`succeededCount=1`、container `exit(0)`，application `failed=0`、`status=succeeded`。
  - `twse-institutional`：GitHub Actions run `36216088848`／execution `janus-ingestion-core-pwgn9`；第一次 attempt 為 transient `HTTPError`／`exit(1)`，既有 retry 後第二次 `exit(0)`，execution 最終成功；成功 summary `failed=0`、`status=succeeded`、`core.institutional_v1` 324 rows，Mart `not_required`。
  - `twse-market-activity`：GitHub Actions run `36218341537`／execution `janus-ingestion-core-zvbc9`，attempt 0 `exit(0)`，execution `Completed=True`／`succeededCount=1`；summary `failed=0`、`status=succeeded`、`core.market_activity_v1` 336 rows，Mart `not_required`。
- 三個 bounded repair acceptance 均未重現原 calendar `ValueError`。這證明 dataset-level calendar repair acceptance 通過，但不能把手動 bounded acceptance 當成後續自然 Scheduler 已恢復正常的證據。

### Analysis／Mart evidence

- 本 checkpoint **不宣稱已有新的 post-start analysis success**。觀察到的自然 Scheduler execution 在 ingestion 階段失敗，沒有形成可用來宣稱 downstream Mart success 的成功 ingestion evidence。
- 三個 calendar-repair bounded acceptance 為隔離 ingestion 修復而執行，Mart trigger 明確為 disabled／`not_required`；因此也不把它們算成 analysis evidence。
- 以上只表示「本 checkpoint 尚未取得可歸屬於上述自然排程／修復流程的 post-start analysis success evidence」，不是對整個 GCP project 的 Mart execution 做全域不存在聲明。

### Backup／restore、outcome、usefulness、cost、security／privacy

- Entry Gate 前後已有既存 baseline evidence；本 checkpoint 沒有重新執行 backup／restore、outcome／feedback count、cost report 或 security／privacy verifier。
- 因此這些類別在本 checkpoint 的 **post-start delta** 均記為 `not observed`，不得假設與 Entry baseline 相同，也不得推測有新變化。
- 本 checkpoint 本身只新增 read-only runtime inspection 與文件紀錄；沒有建立新 GCP resource、沒有擴大 IAM、沒有 production deployment、沒有讀出 secret payload。

### Checkpoint 判定

- `WBS-8-DEV-PILOT-RUN`：`partial`，六個 calendar months operational evidence window 持續中。
- Calendar repair dataset-level bounded acceptance：完成。
- 自然 Scheduler post-repair recovery：**尚未由後續自然 execution 證明**；下一次可用的自然 Scheduler execution 應另作獨立 evidence slice，不能由本次 bounded acceptance 代替。
- Post-start analysis、backup／restore delta、outcome、usefulness、cost、security／privacy：本 checkpoint 沒有新增可宣稱 evidence；維持 `not observed`，待後續真實事件累積。

相關程序與 calendar repair 細節見 [`runbook-pilot-calendar-repair.md`](runbook-pilot-calendar-repair.md)；parallel-live dev 操作語意見 [`runbook-parallel-live-dev.md`](runbook-parallel-live-dev.md)。

## Checkpoint 002 — 2026-09-26

觀察窗口：`2026-09-26T08:18:06Z` 至 `2026-09-26T08:25:40Z`。

### Deployment controller reliability／manual intervention

- 前一輪 runtime investigation 已由 live Cloud Build lineage 確認 `janus-ingestion-core` 與 `janus-intelligence-mart` 同時存在兩套 dev deployment controller：canonical GitHub Actions `.github/workflows/deploy-dev.yml` + `scripts/gcp/deploy-dev.sh`，以及 legacy `us-central1` regional Cloud Build triggers。此 duplicate surface 會讓同一個 `main` commit 另外啟動 regional build，形成不必要且失敗的第二條 deploy path。
- Guarded cleanup run `36229366763` 在 mutation 前精確驗證兩個 trigger 的 ID、name、Dockerfile、runtime、image substitutions 與 enabled state，並確認兩個 Cloud Run Jobs 皆 `Ready=True`。
- mutation 前完整 trigger JSON 與 Job image state 已先保存為 GitHub Actions artifact `10902226767`，digest `sha256:9b9054f51e86c53662b76b90836835acaf812cb51f60ca2f69ea45ecfdb84a13`；artifact 成功後才刪除：
  - `janus-ingestion-core` trigger `5e201f5a-c206-4006-92b9-40a53c4155ed`
  - `janus-intelligence-mart` trigger `b8215cb9-1823-401d-b293-65fbdf73ce30`
- cleanup 後兩個 trigger names 不再出現在 `us-central1` trigger list，兩個 trigger IDs 都無法 describe；兩個 Cloud Run Jobs 仍 `Ready=True`，且 trigger-only cleanup 沒有改變原 runtime image。
- 本次 cleanup 沒有新增 GCP resource、沒有擴大 IAM、沒有建立 Production topology，也沒有把 legacy regional triggers 修活或保留成 fallback controller。

### Canonical bounded deployment acceptance

- acceptance commit `5e572e6684d88b452f6ee81e0b5b46a21058c4ce` 只在兩個 Job Dockerfile 加入 stable deployment-controller 註解，用來命中 canonical path detection；沒有改 application runtime behavior。
- GitHub Actions run `36229503909`：
  - `test-ingestion`: `success`
  - `test-mart`: `success`
  - `deploy-ingestion`: `success`
  - `deploy-mart`: `success`
  - `test-api`: `skipped`
  - `deploy-api`: `skipped`
- canonical ingestion Cloud Build `6ff98342-ea87-4e40-bd58-bfcffdbb2de2` 成功，image tag `ingestion-core:dev-5e572e6684d88b452f6ee81e0b5b46a21058c4ce`；Cloud Run Job update 成功，`verify-dev.sh ingestion-core` 回報 `Ready=True`。
- canonical mart Cloud Build `69277068-9412-448c-87e6-ee05c0181eb9` 成功，image tag `intelligence-mart:dev-5e572e6684d88b452f6ee81e0b5b46a21058c4ce`；Cloud Run Job update 成功，`verify-dev.sh intelligence-mart` 回報 `Ready=True`。
- 這個 acceptance 只驗證 canonical deployment path、targeted tests 與 Cloud Run Job configuration；沒有執行 ingestion／Mart workload，因此不得解讀成 live-data workload acceptance。

### Independent post-acceptance verification

- request commit `827be464a7fb19f642e05378b26f18361dfd1e00` 將 guarded workflow 切到 `verify` mode；run `36229702938` 明確輸出 `verify mode: no trigger mutation requested`，因此此輪是獨立 read-only post-acceptance verification。
- 驗證結果：兩個 legacy regional trigger names／IDs 仍 absent，canonical acceptance push 沒有把它們重新建立。
- `janus-ingestion-core`：`Ready=True`，image digest `sha256:8009ae8eb017a463ea1f145942f2de910b64dc0e48234d0c8c8431c03fd6f9d8`。
- `janus-intelligence-mart`：`Ready=True`，image digest `sha256:d0d5100085fe2f30e4b87891f0e264327cf244f46685826aa180252b39d9c456`。
- 一次性 cleanup workflow／request 後續已從 `main` 移除，避免留下額外 mutation surface；正式 closure evidence 見 [`deployment-controller-consolidation-2026-09-26.md`](deployment-controller-consolidation-2026-09-26.md)。

### Checkpoint 判定

- duplicate dev deployment-controller condition：`RESOLVED`。
- canonical dev deployment controller：GitHub Actions `.github/workflows/deploy-dev.yml` + `scripts/gcp/deploy-dev.sh`。
- `janus-ingestion-core` deployment acceptance：`PASS`。
- `janus-intelligence-mart` deployment acceptance：`PASS`。
- `WBS-8-DEV-PILOT-RUN`：仍為 `partial`；本 checkpoint 增加的是 manual intervention／deployment reliability evidence，不代表六個 calendar months evidence window 完成。
- 自然 Scheduler post-calendar-repair recovery：仍是下一個未取得的自然 runtime boundary；本 checkpoint 的 deployment acceptance 不可代替 Scheduler／workload recovery evidence。
- Post-start analysis、backup／restore、outcome、usefulness、cost、security／privacy：本 checkpoint 沒有新增足以改變既有判定的 evidence，除 deployment reliability／manual intervention 類別外仍依前一 checkpoint 狀態累積。
