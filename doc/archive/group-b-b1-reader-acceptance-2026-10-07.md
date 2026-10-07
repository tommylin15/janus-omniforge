# B1 Exact-snapshot Reader 驗收 — 2026-10-07

## 狀態

B1 **CLOSED / PASS**：reader 契約、runtime 接線、targeted CI、既有 dev deployment 與同一固定 snapshot 回歸／artifact readback 均通過。B0 維持 CLOSED，不重新啟用 baseline request。

## 實作與測試

- `8d0d419`：抽出 `AnalyticsSnapshot`／`AnalyticsSnapshotReader`／`IcebergSnapshotReader`，runtime 改用 reader，保留 `load_core_datasets()` 與 `catalog_factory` 相容入口。
- `50b2422f684c7a9cd74013b521ff7cc1b2fd3d4c`：匯出 reader boundary；原 B1 CI／dev deployment run `37548074577` success，Mart targeted tests 96 PASS。
- `984dc8482b351a4b693320634dcddcda8d0bc84a`：補充 identity／table fence／row limit／catalog cleanup negative tests；CI run `37571430590` success，Mart targeted tests **105 PASS**。
- `a05db3e6f16beffb4999e4d8f02251d120a8d160`：補充 runtime 拒絕 reader 回傳不同 snapshot、失敗仍釋放 reader 且不寫 specialist manifest 的檢查；CI run `37572291941` success，**105 PASS**。SPEC 已記錄 reader contract。
- 本機 reader 8 PASS、runtime 9 PASS。完整 specialist 本機測試曾因未安裝 `riskfolio` 失敗；正式完整 targeted evidence 使用已安裝鎖定依賴的 CI，不將環境缺少依賴包裝為通過。
- Runtime 讀取前驗 immutable manifest hash／execution／Core identity；reader 再驗要求的 identity 並使用指定 table snapshot ID。保持 symbol filter、原始欄位/null、PIT validator 與 provenance，超限 fail closed；runtime `finally` 關閉 reader並拒絕不同回傳 identity。
- 未新增 runtime dependency、BigQuery resource/API/IAM、migration 或 canonical write path。

## 固定 snapshot dev 驗收

- 已部署 SHA：`c49dc7398edac3926de8fecb248fbf06d556fa7d`；其中 Mart Python source 與 `50b2422` 一致。
- Mart deployment／smoke：run `37570672091` 的 `deploy-mart` success。
- Image digest：`sha256:0584af672d8baaa5d9953e63cfed2e16266445b1ef0cef0242ccb1ce600a2556`。
- Execution：`janus-intelligence-mart-9krkb`；operation `specialist-acceptance`，1 CPU／1 GiB、1 task、LLM disabled、OOS enabled。
- Input：`gs://gen-lang-client-0593591102-dev-mart/acceptance/specialists/b1-fixed-snapshot-20261007.json`。
- Core execution：`17b091be-c454-4fea-b5de-b16c0a9c8c6c`；analysis_as_of `2026-10-06`。
- Core snapshot：`sha256:1eb49a2d139411245bda3c9d2eb77e451c5f462bb1865406fd8b55a151df61ab`。
- Core manifest raw-byte hash：`sha256:8eda0eaead65dcb2cdf33191337b2d6aae120ca2adfbe77cc511cf8c28d3e0a8`。
- 只覆寫本次 execution env；驗後 readback 證明 persistent Job 仍為 `MART_OPERATION=queue`、無 `MART_ACCEPTANCE_INPUT_URI`，資源維持 1 CPU／1 GiB。

## 結果與 readback

- Execution `succeededCount=1`；完成時間 `2026-10-07T04:42:42.881759Z`（台北 12:42:42）。
- Specialist execution：`f58c3812-2dee-47c8-afc6-c818057183b1`；manifest raw-byte hash `sha256:ad5b90e9a3c4ba094833a9a158d650dfb6361cd2b1a2b5a14c61b5205e66d684`，GCS readback PASS。
- 輸入 **92,653 rows**：benchmark 752、events 329、financials 15,756、ohlcv 70,863、valuation 4,953；與 B0 相同。GCS manifest 中的整數 table snapshot IDs、symbol filter 與全部 scan evidence 也與 B0 完全相同，不以 Cloud Logging 的 scientific notation 反推 identity。
- Reader telemetry 的 Core identity 與要求的固定 snapshot 完全相同。
- **500 screening**，hash `sha256:39b25796ac9d8e13b9bd2925e06a4fe916ba25664cb51cf7b49f5806b904ecc9`，與 B0 完全相同。
- **25 份 specialist artifact** 的 symbol／role／raw-byte hash 與 B0 完全相同；market membership artifact hash 也相同。Runtime 保留既有 immutable artifact write/readback fence。
- EOD missing **0.2%**、各 history window missing **7.8%**，皆 accepted。
- OOS raw-byte hash `sha256:faa877bd3b201e9bab2f24a7ceaed8c13ea7cd387e4f0de99b350166de28e8ec`，GCS readback PASS；**不等於 B0 raw hash**。逐欄比較發現 1,484 個數值尾差、17 個因此改變的內部 output hash，沒有非數值差異，所有 evaluation input hashes 相同；最大絕對差 **2.842170943040401e-14**，全部小於 `1e-12` 浮點比較容差。不修改原始 evaluation 或 canonical 數值，也不宣稱 bitwise identical。
- Elapsed **800.966 s**（約 13 分 21 秒），peak RSS **688.98 MiB**，LLM tokens **0**。B0 為 725.726 s／694.7 MiB；單輪耗時增加約 10.4%，B1 不宣稱效能改善。
- `planned_scan_bytes`／`actual_gcs_read_bytes` 保持 null；沒有可靠 byte telemetry 就不補 0。
- Specialist status 仍為 `partial`、publishable 0；這是後續五引擎 acceptance 的真實狀態，不阻擋已完成的 B1 reader boundary。

B1 結案不代表 B2 BigQuery adapter、自動 fallback、B3 daily schedule 或 B9 五 specialist 整體 acceptance 已完成。下一步為 B2；未授權的新付費 API/resource/IAM gate 保留。
