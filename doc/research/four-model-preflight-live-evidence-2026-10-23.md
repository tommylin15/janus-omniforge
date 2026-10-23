# Janus／OmniForge｜四模型研究資料包 Phase 1 Live Preflight 收據（2026-10-23）

> **狀態：PARTIAL**。本輪已完成 `CURRENT` 研究 release 的 **155/155 檔完整 bytes SHA256**、**153/153 Parquet footer 筆數**、**2/2 CSV 行數**真實檢查；**尚未完成 Parquet 逐列資料品質、四模型 X/PIT 以及全量大盤／產業 485 個 partition 機械 Preflight**。不得宣告四模型資料準入 PASS。

## 1. 本輪確實執行的範圍與版本

- Drive 根白名單：`janusChatGPT`，資料來源是 `資料源/JanusDataset_v3_202610/canonical/CURRENT.json` 所指 **`release-0bbae8d9c1ca7d8d`**；不是舊版 `release-b21384aebef3cd70`。
- 讀回 CURRENT SHA256：`0b64ac6927805fb98260121da94624d7e08ac423f0aa13b8349d4c304f0135cd`；驗證結束再讀回，檔案位元組未變。
- 來源 manifest 列 **155 個引用檔**：`ohlcv` 21、`revenue` 49、`financials` 15、`valuation` 36、`corporate_actions` 32、`invalid.csv` 與 `conflicts.csv` 各 1。
- 透過已連接 Google Drive 的檔案位元組讀取功能取得 155 個完整檔案；在本次 Python 容器以 `hashlib.sha256` 實測，**155/155 與 Drive manifest 的每檔 SHA256 相同**。非單純列資料夾或樣本推斷。
- Python 環境沒有 `pyarrow`／`duckdb`，因此採已安裝 Apache Thrift Compact Protocol 讀 **所有 153 個 Parquet footer** 的 `num_rows`、row groups、physical schema 及若有提供的 `null_count`，**沒有解碼 Parquet data pages**。所有 153 個的 rows／row-group 合計與 manifest 一致。
- 兩個 CSV 完整讀取：`conflicts.csv` 266 筆；`invalid.csv` 726 筆，與 manifest 一致。
- GitHub `main` 於此輪觀測為 `7b9316d5e39d05776351248026041ff6c17c1f4a`；該 SHA 是**觀測值**，不是聲稱本輪執行了 GitHub CI。輸入指紋／實測細目見下方 Drive 原始報告。
- 本輪沒有執行 Colab、`label_four_models.py --verify-only` 的真實 Parquet loader、`market_sector_package_preflight.py` 全期 CLI，沒有讀寫 Core/Mart、canonical、GCS、PG、Registry、Risk ACTIVE。

## 2. 實測結果

| 表／類別 | 引用檔 | Manifest rows | Footer / CSV 實讀 rows | bytes SHA |
| --- | ---: | ---: | ---: | --- |
| `ohlcv` | 21 | 799,468 | 799,468 | 21/21 |
| `revenue` | 49 | 92,910 | 92,910 | 49/49 |
| `financials` | 15 | 1,181,442 | 1,181,442 | 15/15 |
| `valuation` | 36 | 78,730 | 78,730 | 36/36 |
| `corporate_actions` | 32 | 891 | 891 | 32/32 |
| `conflicts.csv` | 1 | 266 | 266 | 1/1 |
| `invalid.csv` | 1 | 726 | 726 | 1/1 |
| **合計** | **155** | — | — | **155/155** |

在 Parquet footer **有提供 null_count 統計**的欄位中，估值 `pe_ratio` 為 18,904 筆 null、`pb_ratio` 5 筆、`dividend_yield_percent` 1,495 筆。這是 metadata 統計，不代表已逐列解析其他欄位，也不能把缺少統計的欄位一律當無缺值。PE 無效／缺值本身可能符合公司虧損的經濟意義，不能機械補零或全數判錯。

CSV 中 `conflicts.csv` 實讀 **266 筆**，其中 revenue 188、valuation 78；`invalid.csv` 的 **726 筆**原因均為 `INVALID_SYMBOL_OR_MARKET`。這些是已有隔離記錄，非這次新製造或新清理資料。

**需追蹤的實體 schema 警示**：
`revenue/2022-09.parquet` 僅 4 筆；其 `unit_basis` Parquet physical type 是 **INT32**，但另 48 個 revenue 月分區該欄是 **BYTE_ARRAY (UTF8)**。這可能是 null-only 等格式差異，但尚未做 data-page 解碼／loader 讀回，不把原因當作已確認。標 `WARN_SCHEMA_PHYSICAL_TYPE`；需在完整 Parquet loader 驗證讀取與值語意，**不要改動原始檔**。

## 3. 尚未執行／不能自動判 PASS 的 gate

| Gate | 本輪狀態 | 說明 |
| --- | --- | --- |
| CURRENT + manifest 155 份 bytes SHA | **PASS** | 真實讀回 155/155 |
| 153 份 Parquet footer rows/schema 解讀 | **PASS，含一項 schema WARN** | 全部 rows 相符；2022-09 `unit_basis` 例外 |
| Parquet 全資料列鍵值、OHLC、異常值、交易日與缺值 | **UNKNOWN / NOT_RUN** | 缺可用 Parquet data page decoder，本輪只有 footer metadata |
| `label_four_models.py --verify-only` 實際 loader + 產業 precheck | **NOT_RUN** | 無法把 metadata 驗證冒稱 loader E2E |
| 34 個指定 X 席位的實際 computed coverage | **UNKNOWN / NOT_RUN** | 已知定義 Risk 8、Quant 11、Fundamental 10、Valuation 5；沒有計算當期因子 |
| 歷史產業歸屬／有效期 crosswalk、historical PIT、source authorization | **NOT_VERIFIED** | 研究資料不得自動當 canonical 或可發布 |
| TWSE／TPEx 2025-01～2026-09 market/sector 全量 485 partition | **PENDING / NOT_RUN** | 先前 inventory/抽樣 evidence 存在，但本輪沒有逐檔全部重算 SHA |
| 四模型訓練／OOS／publication | **NOT_RUN / NOT_AUTHORIZED_BY_PREFLIGHT** | 本輪不訓練、不更動模型 |

## 4. 可稽核報告與讀回

Google Drive 已寫入並讀回以下檔案（同一白名單資料夾）：
[**four_model_preflight_live_20261023T111528Z**](https://drive.google.com/drive/folders/1wDp26_-3QjAE0i6rMfuGn8mRVrnqHqVM)

- [preflight_summary.json](https://drive.google.com/file/d/1hZHPy6Mf8_U2WYYk_ZRPvrDTymAM3wQJ/view)
- [preflight_inventory.json](https://drive.google.com/file/d/169EGiwXHeIPygRx_ZhvjyGSS1nvrDKQT/view)
- [preflight_quality.json](https://drive.google.com/file/d/1GwrPfnapxXL1FYoXAZMGhQGOrega5Cws/view)
- [model_feature_coverage.json](https://drive.google.com/file/d/1kXJeejpHgy5OjWGkIogizkLNuTEGO_uR/view)
- [preflight_issues.csv](https://drive.google.com/file/d/1YXAVfEMQS-eLfSowpKGgjWPxgxvHuIEh/view)

四份 JSON 上傳後分別由 Drive 連接器重新下載，與本輪原始本地 bytes 相等。報告摘要 SHA256 `7861dbe865ea7b84fc7d0026ae7d5eb4dc047226304f6114d14cec1b33aad0ff`。

## 5. 下次執行最短閉環

在可讀 Drive 完整檔案且安裝 pandas/pyarrow 的 Colab／等效 Python runtime，依 [一次全量 SOP](four-model-research-package-preflight-runbook.md) 對**同一 pinned release**啟動：
1. 全 release loader `label_four_models.py --verify-only`，完整解碼、檢查 2022-09 revenue `unit_basis`，取得逐表唯一鍵／缺值／市場覆蓋／quarantine/PIT 狀態。
2. 完整執行 `market_sector_package_preflight.py --start-month 2025-01 --end-month 2026-09`，以同一輪輸出全部 485 個候選 partition 的 SHA、OHLC、日曆、問題清單。
3. 逐模型核對 34 X 席位的實際 feature computation、lookback 與必要時點，分開判定可做 RESEARCH_NON_PIT 的部分與 strict PIT 的依賴。
4. 將完成後的 full run 原始驗收收據另存 Drive、讀回；**不要以本輪 partial 替代 full-run**。

本輪僅進行完整性唯讀檢查，未修改來源檔案、未補收、未清理、未貼標、未訓練、未部署、未新增付費資源。
