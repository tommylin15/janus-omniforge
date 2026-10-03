# 資料補充與週六檢核操作

本文件對應 `WBS-3-DATA-SUPPLEMENT-V1`。順序為首次回補 → 每日增量 → 週六獨立檢查。使用者採「有資料優先」：缺期與未知公告時間如實呈現；不得把本次取得時間倒填成歷史公告時間。

## 首次回補

程式入口：`jobs/ingestion-core/ingestion_core/data_supplement.py` 的 `run_backfill()`；Cloud Run 入口：`runtime_entrypoint.py` 的 `JANUS_DATA_SUPPLEMENT_MODE=backfill`。使用既有 dev `janus-ingestion-core` Job、原 Stage/Core bucket 與 PostgreSQL control/catalog，不新增資源。

先確認 main 的 CI、部署及 Job image 已符合本次版本，並確認沒有 ingestion execution 還在執行。以下為 PowerShell；使用已登入的 gcloud，Secret 由既有 Job 參照，不貼入命令。

```powershell
gcloud.cmd run jobs executions list --job janus-ingestion-core --project gen-lang-client-0593591102 --region us-central1 --limit 5
$sdk = 'C:/Program Files (x86)/Google/Cloud SDK/google-cloud-sdk'
& "$sdk/platform/bundledpython/python.exe" "$sdk/lib/gcloud.py" run jobs execute janus-ingestion-core --project gen-lang-client-0593591102 --region us-central1 --update-env-vars='^|^JANUS_DATA_SUPPLEMENT_MODE=backfill|JANUS_DATA_SUPPLEMENT_SYMBOLS=1102,2327,2330,4958,5876|QUEUE_CONSUMER=false|MART_JOB=|ICEBERG_MAINTENANCE_MODE=' --async --format='value(metadata.name)'
```

Windows 的 .cmd wrapper 可能把 ^|^ 參數解讀成 shell 管線，因此上例直接使用 SDK 的 Python 入口。其他環境可用 gcloud 原生入口。

記下回傳 execution 名稱，查此 execution 的完成狀態，不因等待較久再啟動第二個。無指定 symbols 時，採當日去識別化分析目標；上限 50 檔，目前回補 adapter 限已核對的 TWSE 合併財報。

原始回應先 Stage，再驗證公司、期別、單位、報表口徑並寫入 Core。財報與月營收採實際 receipt availability；歷史 publication 與原始數值版次維持 unknown。相同觀測值重跑會 reuse，數值變動新增版次。不得覆寫舊 snapshot。

## 驗收與失敗處理

1. 執行成功仍須讀取 Core 的財報季數、月營收月數、價格交易日數，以及完整 Core snapshot manifest；不能只看 Cloud Run 成功。
2. 來源失敗或資料不足顯示 partial，保存安全的 dataset、股號、期別與錯誤類別。原始 HTML/JSON 僅在受控 Stage 排查，不得貼入公開 GitHub 或 Admin。
3. 要驗證 Mart consumer 時使用既有 `janus-intelligence-mart` 的 deterministic/AI-disabled 路徑，確認 feature version 2、收件時間、同日行情對齊與 missing reason；本作業不授權額外模型呼叫。
4. 修正程式後跑相關 targeted tests，執行 `/ponytail-review`，commit/push 由現有 dev CI/CD 部署；重跑前確認舊 execution 已結束。

## 每日增量與週六檢查

程式已接線，是否正式啟用以 `doc/status.md` 與最新 dev evidence 為準。總控定義在 `jobs/ingestion-core/ingestion_core/batch_controller.py` 的 `BATCHES`，沿用既有每小時 :30 總控 Scheduler，不另建 Scheduler：

| 批次 | 台北時間 | 入口／依賴 |
|---|---|---|
| data-supplement | 每日 08:30 | `JANUS_DATA_SUPPLEMENT_MODE=daily`；等待 07:30 ingestion 成功 |
| Mart | 工作日 09:00（下一個 :30 tick 派送） | 等待 ingestion 與 data-supplement 成功；本 WBS 使用 AI-disabled |
| data-quality | 每週六 12:30 | `JANUS_DATA_SUPPLEMENT_MODE=quality`；沒有 ingestion 成功依賴 |

每日 `run_backfill(incremental=True)` 先讀 Core：只抓首次缺期、申報上傳時間變更、週六檢查指出的更正期別；月營收補缺期並重新核對最新已到期月份，行情依既有交易日曆檢查最近 121 個交易日，只重抓缺失日期所在月份；已由 ingestion 補齊就略過行情與 benchmark。歷史財報完整時只查最近兩年的申報索引，較舊期別僅在缺期／檢查要求修復時查詢。同值 reuse；新增／修正才送新的 Core ready/Mart 請求，沒有變動就完成檢查。財報按個股合併 Core commit，每筆仍保留各自 Stage provenance。當期尚未公告的月份不算缺期。

週六 `data_quality.py::run_quality()` 獨立讀取 Core，檢查已核對的 12 季、到期的 12 月、最近一年至少 121 個價格交易日、OHLCV validator、數值格式／單位／同版次衝突／receipt；另外從官方重抓各檔最新一季財報與 12 個月營收核對。此來源重抓範圍不涵蓋全部歷史財報的每一版次，不能宣稱完整 PIT 復原。unknown publication／原始版次是已接受限制，不單獨令本次檢查失敗。

## 收到 Admin 異常後如何處理

在 Admin 總覽點「週六資料品質 → 結果與檢核文件」，讀取受影響股號、dataset、期別、欄位與原因。

- `history_incomplete`：確認近期來源／新上市與合法缺期；有可用來源時重跑 backfill；已接受缺口保留 partial，不捏造資料。
- `source_value_changed`：官方已與 Core 不同；下一次 daily 會針對該期重新抓取，新增實際取得時間的版次，保留舊版本。
- `source_check_failed`：排查官方暫停、限流或 schema；修正 `_fetch`／parser 後 targeted tests、review、dev deploy，再跑 daily。
- `unit_mismatch`、`conflicting_version`、`invalid_numeric_value`：檢查 `financial_publication.py` 與 `normalise_monthly`；不得自動放寬 validator。必要時隔離受影響輸入，先保護其他可用資料。
- `execution_failed`：檢查批次自身失敗，不能據此判定資料正常；只讀該 Cloud Run execution 的安全 error code，修復連線／權限／程式後重跑 quality。

安全重跑：把首次回補命令中的 `JANUS_DATA_SUPPLEMENT_MODE=backfill` 改成 `daily` 或 `quality`。daily 預設使用當日去識別化目標，可省略 symbols；quality 使用當日目標並保留獨立 check。先確認該 Job 沒有 active execution，避免併行寫入；不取消或重複派送不明狀態的工作。

結果保存在 control 的 `data_supplement_quality` 安全 metadata，Admin 使用既有受保護 settings API；操作文件由 `/api/v1/admin/data-quality/runbook` 固定路徑提供。此處不放原始財務數值、raw HTML、owner 關係或 Secret；沒有 Email／Codex automation。

## 修復或重建每日排程

1. 從目前 main 讀 `data_supplement.py`、`financial_publication.py`、`runtime_entrypoint.py` 和 `batch_controller.py::BATCHES`，依上表核對 daily/quality mode、dependency、exclusive guard。週六異常是要求檢視，不直接改動總控或放寬驗收。
2. 先驗證：`PYTHONPATH=.:jobs/ingestion-core:jobs/intelligence-mart python -m pytest -q tests/test_data_supplement.py tests/test_data_quality.py tests/test_batch_controller.py tests/test_duckdb_iceberg.py`（PowerShell 的 PYTHONPATH 分隔符為分號）。Admin 改動加跑 `flutter test test/admin_overview_batch_test.dart` 與 `flutter analyze lib/admin.dart`。
3. 執行 `/ponytail-review` 後 commit/push，由 `.github/workflows/deploy-dev.yml` 部署既有 dev ingestion Job。確認 CI、immutable image 與 Ready；不得建立新資源。
4. 更新既有 `janus-batch-controller` 的 image 為已部署 ingestion 的 immutable image；**保留原 `BATCH_CONTROLLER_MODE` 與 `BATCH_CONTROLLER_NOT_BEFORE`**。若用 `prepare-batch-controller-dev.py` 產生 manifest，其預設是 observe，必須帶回現有值再 replace。不要直接套預設 manifest，也不要以 cutoff 改寫／刪除既有 occurrence。
5. 唯讀核對既有 Scheduler 指向總控且仍為台北時間 `30 * * * *`、active 狀態正確；不要另建第二個 daily Scheduler。確定無 active ingestion／controller 後，跑 daily，再跑 quality，讀回 Core 與 Admin；檢查 `needs_daily_schedule_adjustment` 是否清除，觀察下一個自然 daily／週六 occurrence。
6. 只在實際部署與讀回後更新 evidence。若來源仍不足，保留 coverage/partial 與安全理由；不得把 queued、build 或手動單次成功當成自然排程已驗收。


月營收使用 MOPS 官方歷史彙總 HTML（一般上市 `_0` 與 `-KY` 公司 `_1`），每個市場分類、月份下載一次並共用。採 cp950 解碼，核對公司、期別與千元單位後轉為 TWD；不把取得時間當成歷史公告時間。
