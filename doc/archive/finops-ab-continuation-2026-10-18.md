# FINOPS-AB 接續證據（2026-10-18）

狀態：**PARTIAL；不是部署或清理結案**。本次輸入 main `4b1785603aaa23005701f1e72b3377fed1070419`；FINOPS-C、DRL-01、ADMIN-V2 不納入施工。本機既有 ADMIN 檔案與 candidate request 保留、不提交。

## 程式與驗證

- `data_supplement.run_backfill` 同月份 OHLCV 跨股票共用一次 Core write；維持既有最多50股、已接受列、每筆 Stage provenance、部分來源失敗與 commit 失敗回報，不變更既有 source/DQ/PIT/自然排程。
- 新回歸用兩股、兩月證明三份有效來源只有兩次寫入，第一月保留兩份獨立 provenance；一股來源缺失仍 partial；第一月 commit 失敗則記錄該月兩股失敗，第二月仍繼續，Stage 不標全成功。
- 本機 `test_data_supplement.py`、`test_duckdb_iceberg.py`、`test_batch_controller.py`、`test_iceberg_compaction.py`、`test_data_retention.py` 共 **88 passed**（118.34秒）；最終新增 commit 失敗案例另 **1 passed**。既有整合回歸涵蓋重播無新增／更新、合法財報版本、snapshot／retention 防護。初次本機缺 `pytz`，僅安裝至忽略目錄 `.tmp/finops-test-deps`，未修改產品依賴。
- 這是月批 OHLCV 合併，不代表 financials／valuation 全 dataset 合併、A2 各階段 CPU/GCS 歸因或整體 B2 已完成。財報與估值維持既有每股歷史批次。

## 最新唯讀 runtime

以既有本機 GCP identity 唯讀描述四個 dev Job（未派送、未寫入資料或設定），實際 image 均與 `ops/ghcr-jobs-rollout-request.json` 的 `d8a57aa57198e0f383a37125e6b94eb392abe717` rollback baseline 相符：

| Job | GHCR sha256 digest |
|---|---|
| ingestion／controller | `073d7a200a05464542776721d3b3edbc5f6ce438e24e79eb2d39dd24d09ef1d7` |
| Mart | `6a33d77cf9ee55d70fcb62625bd339c377c7b20fe498609a5016d34441df2dc1` |
| Private | `ae91a2f478893cc43840284ca096b0298c6b357f44196d0e818c72c099655d97` |

Scheduler `janus-ingestion-daily`：`ENABLED`、`30 * * * *`、`Asia/Taipei`。這只證明現行喚醒，不證明新週維護旗標已生效。

GitHub main [selective CI #39093581698](https://github.com/tommylin15/janus-omniforge/actions/runs/39093581698) SUCCESS，只對本次輸入版本有效，非新修改或完整 Release gate。

## 真實 blocker 與恢復入口

- [Jobs rollout #39090724732](https://github.com/tommylin15/janus-omniforge/actions/runs/39090724732) 重新確認 `completed/failure`；allowlist 錯誤為 `bounded_release_lease_atomic_lease_claim_rejected_or_unavailable_ref_http_403_integration_permission`。目前 GitHub `refs/tags/janus-ghcr-deploy-global-v1` 查無 ref；不是被占用，不應刪租約或用本機 token 代替 Actions 繞過 fence。失敗 run 已宣告 Contents write，仍須查明 Actions integration／repository policy 的 ref 建立拒絕；不自行擴權。
- D06 publication `core_snapshot_id` 欄位讀權與完整外部引用 fence，仍沿原證據維持 BLOCKED／PARTIAL；本次不重掃既有62／71／96／495份 JSON、不重刪477個物件、不偽造新鮮完整 fence。
- 權限問題解除後：協調 DRL／ADMIN 共用發布來源 → 同 SHA full Release／GHCR → 原子 lease → 受控四 Jobs／rollback → 明確週維護設定與合法來源驗證 → 新鮮完整 retention fence／有界 dry-run 與合法 apply → Core／PG／Mart／Private 讀回。原兩天量測仍 CANCELLED_BY_USER；短窗無可歸因數值時節省百分比 UNKNOWN。
