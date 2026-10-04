# 042 stock serving projection 完成證據（2026-10-04）

狀態：**DONE**

本檔保存 `042_stock_serving_projection` 在 GCP `dev` 的完成 checkpoint 與 acceptance evidence。它是歷史完成證據，不取代 GitHub `main`、runtime evidence、active SPEC／WBS／TODO。

## 完成範圍

- migration：`infra/postgres/migrations/042_stock_serving_projection.sql`
- control projection：`control.stock_serving_recent`
- publication views：`publication.stock_serving_recent`、`publication.stock_latest`
- public API 對 `ohlcv`／`valuation`／`events` 採 PostgreSQL serving projection first；projection 缺資料或不可用時才 fallback canonical Iceberg。
- `janus_public_api` 只取得 publication read path；owner migration 維持 `janus_publication` owner boundary，不以 `janus_mart_publication` 代替。

## Migration 與 backfill acceptance

2026-10-04 正式 serving-schema migration workflow 已成功完成 042。real-data backfill evidence：

| Dataset | Published rows |
|---|---:|
| `ohlcv` | 74,328 |
| `valuation` | 3,452 |
| `events` | 299 |
| **Total** | **78,079** |

`eligible_rows=78,079`、`published_rows=78,079`，沒有 partial success。

## API hot-path live acceptance

- dev API 已完成 deploy 與 runtime verify。
- workflow run `37195556982` 直接呼叫 live endpoint：`/api/v1/public/history/2330?limit=1&offset=0`。
- response 驗證 `dataset_id=ohlcv`、`symbol=2330` 且至少有一筆 row。
- Cloud Logging 同一輪 runtime evidence：
  `{"component":"janus-api","dataset":"ohlcv","operation":"core_query_source","source":"serving_projection"}`
- 因 API 原本有 Iceberg fallback，只有 API response 成功不足以證明 projection hot path；本次以 source telemetry 明確證明 request 命中 `serving_projection`。

## Publication owner credential repair

042 首輪 rollout 暴露 unified runtime bundle 缺少獨立 `publication_password`，且 migration owner `janus_publication` 與 Mart runtime role `janus_mart_publication` 是不同 identity。修復後：

- credential mapping fail-closed 使用 `publication_password`，不再誤用 Mart credential。
- rotation workflow 可建立／沿用 `publication_password`、同步 PostgreSQL `janus_publication`、驗證 owner login 與 `publication` schema CREATE ownership，驗證成功後才停用較舊 enabled secret versions。
- final successful rotation workflow run：`37195921425`。
- successful Cloud Build：`08c0def2-0e54-4849-8e42-06f7c4f6ab0a`。
- rotation script 使用 stdin 傳遞 credential；credential 不進 argv／一般 log；local verification 使用 Unix socket + `PGPASSFILE`，符合既有 `pg_hba.conf`。

## Temporary IAP 權限收尾

為完成 bounded DB credential repair，使用者曾明確授權暫時給 Cloud Build default identity：

`serviceAccount:131494961796-compute@developer.gserviceaccount.com`

角色：`roles/iap.tunnelResourceAccessor`。

修復完成後此 temporary IAP grant 已撤除。負向驗收：

- workflow run：`37197421793`
- Cloud Build：`de814609-8ec1-430d-a6c4-c821ee6938d6`
- `verify-publication-owner-iap-tunnel`：`FAILURE`
- 後續 `prepare-publication-owner-secret`、`install-publication-owner-rotation-script`、`rotate-publication-owner-database`、`finalize-publication-owner-secret` 均維持 `QUEUED`

因此可確認 temporary IAP access 已撤，且負向驗收沒有進入後續 Secret／DB mutation。

## 後續治理規則

- 不把 temporary Cloud Build IAP grant 當 permanent serving migration control path。
- `janus_publication` owner credential 與 Mart runtime credential 必須維持身份分離。
- Secret 只記 field／consumer／version state／IAM metadata；不得把 payload、password、token 寫入 Git 或一般 log。
- API serving projection 的 live acceptance 必須包含 source-path runtime evidence，不能只以 response success 判定。
- 042 已完成，不應重新加入 active `todo.md`；若未來 schema／projection contract 改變，另開新的 migration／acceptance work item。
