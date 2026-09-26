# Dev Pilot 交易日曆修復 Runbook

用途：在既有 GCP `dev` 平行上線環境，安全套用 `029_twse_2026_holiday_overrides.sql`，修正 Pilot ingestion 對 TWSE 2026 休市日的交易日回推。這是既有 control setting 的版本化修復，不建立新 GCP resource、不擴大 IAM、不重啟 PostgreSQL，也不變更 production。

## 1. 適用範圍

只適用以下 migration：

- `infra/postgres/migrations/029_twse_2026_holiday_overrides.sql`

Migration 會：

- 保留既有 `schedule.holiday_overrides`；
- 聯集 TWSE 官方 2026 休市日期並去重；
- 更新 `control.admin_settings` 的 `schedule` setting 與 version；
- 寫入 `control.admin_audit`，保存變更前 `previous_holiday_overrides` 作 rollback evidence；
- 寫入 `control.schema_migrations` marker `029_twse_2026_holiday_overrides`；
- 若 `schedule` setting 不存在則 fail-closed。

不得把本 runbook 泛化成任意 SQL 的遠端執行入口。

## 2. 權限邊界

`janus-postgres-dev` 沒有 external IP，正常維運沿用既有 operator IAP／OS Login 路徑。

目前 CI 自動化身分不具備這條 VM 管理路徑所需權限：不要為了本 migration 臨時授予 Cloud Build service account 或 `janus-ci` 額外 Compute／IAP 權限。需要執行時，使用原本已核准、能透過 IAP 存取 `janus-postgres-dev` 的 operator gcloud identity。

若 operator identity 本身也無法存取，維持 `blocked` 並依 `PROJECT_RULES.md` 處理權限決策，不繞過 IAP、不新增 external IP。

## 3. 執行前檢查

在 repository `main` 的預期 commit 上執行：

```bash
git status --short
gcloud auth list --filter=status:ACTIVE
gcloud config get-value project
```

確認：

- active account 是既有 operator identity；
- project 是 `gen-lang-client-0593591102`；
- migration 檔與 `scripts/gcp/apply-pilot-calendar-migration-dev.sh` 均來自目前 `main`；
- 沒有要求建立新資源、外部 IP 或 IAM grant。

## 4. 套用 migration

執行：

```bash
bash scripts/gcp/apply-pilot-calendar-migration-dev.sh
```

腳本固定：

- project `gen-lang-client-0593591102`；
- zone `us-central1-a`；
- VM `janus-postgres-dev`；
- migration `029_twse_2026_holiday_overrides.sql`。

可用既有環境變數覆蓋 project／zone／VM，但不得改成 production 或未核准資源。

腳本透過 IAP `scp` migration 到 VM，複製進既有 `janus-postgres` container，以 `ON_ERROR_STOP=1` 執行；最後只輸出 migration marker 與去敏感的 schedule 欄位，不輸出 password／secret。

## 5. 成功判定

至少確認輸出包含：

```text
migration_marker=029_twse_2026_holiday_overrides
```

以及 schedule JSON 中：

- 原本的 `time` 與 `enabled` 沒有被 migration 改寫；
- `holiday_overrides` 至少包含 `2026-09-25` 與 `2026-09-28`；
- `updated_by` 為 `migration-029-twse-2026-calendar`。

SQL 成功仍不等於 Pilot ingestion 已修復；必須繼續做 live bounded acceptance。

## 6. Live bounded ingestion acceptance

Migration 成功後，用既有 `run-dev-ingestion.yml`／`ops/dev-ingestion-request.json` 只觸發受影響的 bounded dataset 驗收，不修改 Job 永久 image／resource limit。

驗收重點：

1. 在 2026-09-26 執行、requested date 落在週末／休市區間時，runtime target trading date 應回推到 `2026-09-24`，不得再把 `2026-09-25` 當成交易日。
2. `twse-valuation`、`twse-institutional`、`twse-market-activity` 不得再因 2026-09-25 休市回應造成相同 `ValueError` failure。
3. 追蹤同一個 Cloud Run execution 到終態；partial／missing 依實際資料狀態回報，不包裝成 full success。
4. 驗收後更新 active status 與 Pilot evidence；未取得 live success 前，`WBS-8-DEV-PILOT-RUN` 仍保持進行中／partial。

## 7. 2026-09-26 bounded acceptance evidence

本節記錄 migration 套用後三個受影響 dataset 的 bounded live acceptance。Requested date 均為 `2026-09-26`，預期有效交易日為 `2026-09-24`。

- `twse-valuation`：Cloud Run execution `janus-ingestion-core-7z8kv` 最終 `Completed=True`、`succeededCount=1`、container `exit(0)`；application summary 顯示 `as_of=2026-09-24`、`dates=[2026-09-24]`、`failed=0`、`status=succeeded`。
- `twse-institutional`：GitHub Actions run `36216088848`；Cloud Run execution `janus-ingestion-core-pwgn9`。第 1 attempt 曾出現 transient `HTTPError`／container `exit(1)`，Cloud Run 依既有 `maxRetries=1` retry；第 2 attempt `exit(0)`，execution 最終 `Completed=True`、`succeededCount=1`。成功 summary 為 `as_of=2026-09-24`、`dates=[2026-09-24]`、`failed=0`、`status=succeeded`、`staged=1`、`core_created=12`；`core.institutional_v1` snapshot 324 rows，Mart trigger `not_required`。
- `twse-market-activity`：GitHub Actions run `36218341537`；Cloud Run execution `janus-ingestion-core-zvbc9`。Execution `Completed=True`、`succeededCount=1`，attempt 0 container `exit(0)`。Runtime override 明確為 `INGESTION_DATASETS=twse-market-activity`、`INGESTION_DATE=2026-09-26`、`FORCE_REFRESH=true`、`MART_JOB` disabled；application summary 為 `as_of=2026-09-24`、`dates=[2026-09-24]`、`failed=0`、`status=succeeded`、`staged=1`、`core_created=12`，`core.market_activity_v1` snapshot 336 rows，Mart trigger `not_required`。

三個 bounded acceptance 均未重現原本 `2026-09-25` 休市日造成的 calendar `ValueError`，因此本次 calendar repair 的 dataset-level bounded acceptance 切片完成。這只代表交易日曆修復的 bounded live acceptance 通過；`WBS-8-DEV-PILOT-RUN` 仍需累積六個 calendar months 的真實 operational evidence，狀態維持 `partial`。

## 8. Rollback

029 不刪除 canonical data，也不重建 schema。若確認需要回復 holiday setting，先從 `control.admin_audit` 中 actor `migration-029-twse-2026-calendar` 的最新紀錄取得 `previous_holiday_overrides`，再透過正常 Admin setting update／audit 路徑回復；不得直接刪除 audit history。

若 migration 尚未執行成功，無需 rollback；只保留 failure evidence，修正執行路徑後再重試。
