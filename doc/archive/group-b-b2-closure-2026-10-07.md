# B2 BigQuery compatibility 結案 — 2026-10-07

狀態：**B2 CLOSED / PASS**；僅結案 compatibility spike，不代表 B 組、workload canary、fallback 或 BigQuery default cutover 完成。PyIceberg 保持預設。

## 授權與現況修正

- 使用者明確要求繼續 B2，並明確同意本次付費 query 與雲端資料變更；免費額度內的操作不視為費用變更，規則已寫入 `../PROJECT_RULES.md` §1.3。
- 暫停 checkpoint 的「catalog 尚未建立」與 live readback 不一致。既有 `janus_core_dev` create-time 為 `2026-10-07T07:02:26.277Z`（Asia/Taipei 15:02）；本輪復用既有 catalog，沒有另建 catalog、修改 IAM 或遷移 PostgreSQL canonical catalog。
- 使用本機既有使用者權限完成 table register；不提升 `janus-ci`／Cloud Build 權限。Catalog primary location 為 `US`，storage region 為 `us-central1`，credential mode 為 end-user；不將兩種 location 混稱。

## 驗收

沿用先前有效 evidence：Mart regression 106 PASS、deployment／specialist smoke、三張 legacy fixed-snapshot table 320 rows 與 PyIceberg 相等；本次不重跑這些已通過的 runtime 驗收。

腳本／workflow 修改後，commit `3f5406a` 的 [GitHub CI 37595108822](https://github.com/tommylin15/janus-omniforge/actions/runs/37595108822) **SUCCESS**：adapter 20 PASS、acceptance script checks 3 PASS、兩支 probe script compile PASS；沒有重跑 106 Mart regression 或既有 320-row live compare。

本次真實 GCP dev evidence：

1. Shared catalog：三張 Core table 在 `b2_core_fixed_20261007` 註冊固定 metadata URI，catalog pointer、Iceberg V2 current snapshot 與 B0 fence 均精確相等；不覆寫既有 mapping，也不改 canonical files。
2. Native decimal/schema evolution：在 dev-mart acceptance prefix 建立 `decimal_evolution_4c30da3745`，`DECIMAL(20,4)` 的大數、負數與四位小數相等；schema id 0 → 1，metadata URI 變更，新增 note 欄後舊列為 null，新列為 evolved。Automatic table management 為 false，BigQuery DML 僅在 acceptance table 啟用。
3. Partition pruning：測試 table narrow/wide 為 32/96 processed bytes；真實 `core.ohlcv_v1`、symbol 2330，2026-10-01～10-06 為 **42,678 bytes / 4 rows**，2026-01-01～10-06 為 **1,602,600 bytes / 183 rows**。兩個 query 前後 Core catalog pointer 一致。
4. 本輪 9 個 query/DDL/DML jobs，合計 **62,914,560 billed bytes（60 MiB）**；上限 1,073,741,824 bytes，剩餘 1,010,827,264 bytes，全部 job elapsed <60 秒。Job 帳本跨重試沿用；unknown billed bytes 阻止後續 query。Billed bytes 不代表實際帳單金額，也未驗證帳戶免費額度餘額。
5. 本機新增 targeted checks **3 PASS**，驗 Windows/Linux command dispatch、非零 command failure、跨重啟 budget/unknown job guard，以及 Core pointer drift fail closed。未修改 serving image，不需重新部署。
6. 無 Storage Read API、無 IAM mutation、無 canonical data mutation。小型 acceptance table 與 evidence 留在既有 dev acceptance prefix，不升格 canonical。

前置 table create 三次因 partition spec 欄名／identity transform／partition name 不符 API 限制而被拒絕，未建立 table、未提交 query；修正為 `field-id`、`day` 與 `trade_date_day` 後成功。官方限制：[Lakehouse table options](https://docs.cloud.google.com/lakehouse/docs/table-options)。

## Immutable evidence

- [完整 live evidence](group-b-b2-resumed-live-2026-10-07.json)
- [累計 job 帳本](group-b-b2-resumed-live-2026-10-07.jobs.json)
- GCS：`gs://gen-lang-client-0593591102-dev-mart/acceptance/b2-lakehouse/evidence/2026-10-07-21e3c2e761d9c4cbba33fb916a9429bd8a8ebd62ba30052d981a4472844cf1bc.json`
- Generation：`1791362160238502`；generation=0 write 成功，獨立 readback SHA256 相等。
- SHA256：`21e3c2e761d9c4cbba33fb916a9429bd8a8ebd62ba30052d981a4472844cf1bc`。

下一個 scope 是 B3 liquid-500 screening；shared catalog production adapter 接線、workload canary、failure/fallback 與 FinOps acceptance 仍待後續項目，不切換 default。
