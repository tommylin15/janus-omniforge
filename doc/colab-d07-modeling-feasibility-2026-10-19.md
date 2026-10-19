# D07-PRE｜單一 Colab 資料整理與模型訓練流程（2026-10-19）

> **2026-10-19 使用者定案：模型研究資料整理、特徵工程、標籤/OOS 與全部模型訓練統一在 Google Colab 執行；BigQuery 只在實測資料量／Join/記憶體／耗時出現瓶頸時作「前置縮減」，不用於訓練。** 此為 [唯一 TODO D07-PRE](todo.md) 的工程目標／設計決策，**不是已完成 Colab 實機驗收**。既有 Janus Ingestion／Iceberg Canonical／正式 API、Mart 推論／治理與原 Scheduler 不搬往 Colab，也不複製第二套資料庫。

## 1. 結論

**已選定唯一目標路徑：Janus Core 合法資料／最小唯讀出口 → Colab（資料清理、Join、特徵/標籤、24 月滾動訓練、OOS 與評估）→ 固定版本 GCS 成果 → Janus Mart 品質檢查／模型 registry／受控推論 → D08。** 小資料完全不經 BigQuery；只有同一 Colab 流程發生有證據的大資料瓶頸，才由既有 BigQuery opt-in 產生縮減後的 Parquet 供 Colab 繼續整理與訓練。不得增加 BQML、Cloud Run 訓練或另一套模型執行器。**當前程式仍沿既有 Mart 月度 retrain，切換 Colab 尚未實作／驗收；原正常線上服務不變**。

## 2. 現有資料，規模與可靠性分開看

| 固定證據 | 觀察值 | 能／不能推論 |
|---|---|---|
| [B5 ML/OOS 實機結案](archive/group-b-b5-ml-oos-data-closure-2026-10-08.md) | 10,978 rows、499 symbols、Parquet 533,945 bytes、日期 2026-03-19～09-03；20 trading-day label＋5日 stride，含 5/20D returns、turnover、volume、source/provenance | CPU 計算規模小，適合驗證 notebook reproducibility；不能推成 24 月或所有五角色特徵已完整。平均每股約22筆 cohort，重疊 horizon 不是同數獨立樣本 |
| [10/18 Core census #39083283620](https://github.com/tommylin15/janus-omniforge/actions/runs/39083283620) | OHLCV 111,929、valuation 16,595、financials 88,131、benchmark 759、market-volume 39,699、market-activity 135,050 rows | 表間口徑／交易日／市場不同，不能相加成 ML 訓練列，也不是新鮮 10/19 全表 COUNT |
| [全市場保存矩陣](spec/factor-coverage-retention-ledger.md) | 2026-10-17 假設 1,992 普通股 × 約500交易日＝兩年約996,000股日（理論情境） | 不應把111,929與理論值直接當 coverage 分母；一般 Core 價量 row TTL 365 天、Deep 1,096 天，current-only Snapshot 不保證全市場兩年歷史 |
| [10/19 DRL 與背景補收](archive/todo-before-consolidation-2026-10-19.md) | 月營收13月分市場門檻既有 PASS；八股需求補收 8/8 ready；六股兩年 PE/PB 12/12 正式 API 讀回 | 產品資料可用≠所有股/日期具兩年 OHLCV、合規標籤、嚴格 PIT 或完整 12 季 |
| [B9 品質證據](b9-quality-evidence.md) | Fundamental／Valuation／Quant 既有七個5日模型的 MSE 都比 zero-excess-return 基準差；同日最多2/5/5檔；Risk 23個 OOS 月份、452筆 returns、15月改善8月未改善；Event 無合法人審分類 OOS | 模型品質瓶頸是歷史母體、有效時點、樣本獨立性、基準改善，不是 GPU。已 fit、GCS readback 與品質 PASS 必須分開 |

## 3. 五角色適用順序

1. **Quant：優先**。CPU LightGBM vs 動能／Linear／零訊號；真實 date-as-known 歷史成分、5/20日成熟收益、逐月 purged folds；沒有每期至少10股同日截面時 Rank IC／decile 標 null，不編造可交易績效。
2. **Risk：其次**。保留 CVaR/beta/drawdown 與 Gaussian baseline、比較 Markov 的 prior-only 逐日/逐月 OOS；歷史23個月彙總不能倒推逐日 regime 或尾部命中率。
3. **Valuation：有條件**。六股兩年 PE/PB 適合 feature/provenance 試驗，不代表跨股票 OOS 足夠；Rule/peer baseline 後才考慮 LightGBM／CatBoost，null 與負 PE 不補零。
4. **Fundamental：有條件**。同份財報、正確期間與可比較 EPS/歸母淨利配對、成熟 labels；允許已核准 strict_pit=false 的 research-only 比較，不能冒稱嚴格 PIT 正式模型。
5. **Event：後置**。缺合法 training-use 授權與人審 labels 前先維持 parser/rules；不以外部生成標籤冒充真實 OOS。

## 4. 24 個月滾動不是 24 個月歷史已備妥

- 窗口是模型研究目標，非 Core row TTL／全市場補收新授權；一般市場365天、Deep 1096天、財報12季、Current-only snapshot。不另保存舊 Iceberg snapshot。
- 先逐 dataset × market × symbol × month × horizon 產 coverage/eligible/train/calibration/OOS/holdout counts、PIT 來源、標籤成熟時點；沒有資料保留 insufficient。需要兩年跨市場時另評估既有核准回補或合規 Research Parquet 的每月滾動累積，不直接改 Core 保存策略。
- 先 5/20 trading-day horizon，60/120日後置；20日 label 與5日 stride 會重疊。Walk-forward 按月份切、資料只用當時可得特徵、label mature cutoff、purge/embargo；最後 untouched holdout 不用作反覆調參。

## 5. 單一流程／責任與資料量分支（正式目標）

```text
[既有來源補收／Ingestion] → [Iceberg Core canonical／既有 PyIceberg 唯讀出口]
                               ↓ 限定合法來源、月份、欄位的 Parquet/manifest
                ┌──────────────────────────────────────────┐
                │ 有實測大資料瓶頸嗎？（預設 NO）            │
                │ NO → 直接送 Colab                         │
                │ YES → 已授權的 BigQuery SQL 前置縮減       │
                │       → fixed/hash Parquet → Colab        │
                └──────────────────────────────────────────┘
                               ↓
    [Colab：資料 Join/驗證 → features/labels → 24月 rolling
            → train/calibration → purged OOS → baseline比較]
                               ↓ immutable outputs：dataset/model/evaluation/sha
    [Janus GCS/Mart 驗證、version、受控升級、推論與 API]
                               ↓
                   [D08 CEO Fact Pack]
```

**只有一個模型資料整理與訓練工作流程，Colab 是唯一執行器。** 不建立 BigQuery ML 訓練、Cloud Run ML 迴圈、第二個 Feature Store 或平行週／月 Cron。BigQuery **僅**作大規模資料前置篩選、Join/Window/聚合後的 versioned Parquet export；其輸出仍必須經 Colab 做資料校驗、最後 feature/label 與 model 訓練。PyIceberg 保留 Janus Core 的可靠讀取與最小匯出 adapter，不是另一個模型訓練平台。

**大量資料啟動條件**：Colab 直接讀取/Join 的 RAM 耗盡、實測超時、重複 I/O 成本不合理或 SQL 聚合量級過大，提出同一 workload 的筆數/bytes、峰值 RAM、耗時、GCS I/O、BQ dry-run/可能 billed bytes、來源/PIT parity/rollback、配額/IAM 及收益對照；合格且已有授權才用 BQ 前置，否則維持有界 Colab 工作或標 BLOCKED，不偷偷移轉訓練器。**不設定憑空的列數或大小閾值。**

**2026-10-19 使用者新增決策 R1.A**：本階段 Colab 月度操作採人工啟動 Notebook＋人工確認執行終態；沿用 Janus 首週六10:30 due/結果追蹤、固定資料 hash、模型/eval/hash receipt、未執行保持 pending。**Colab 無人值守能力不是目前要實作的前置，不能因未具免費自動化而阻擋本階段完成，但人工流程未實測前同樣不可宣稱 D07-PRE PASS。**

**月度安排**：每月第一個週六 10:30（Asia/Taipei）維持 Janus 現有 Controller **唯一 due slot**。目標由 Controller 判定是否有成熟新標籤、準備 frozen input、登記一次訓練任務/結果與可回復狀態；**模型 fit／OOS 一律在 Colab**。一般免費 Colab 缺少保證可靠的遠端 unattended execution，本階段先採受控人工啟動 Notebook 並匯回 hash 驗收；未完成當月標 `PENDING_MANUAL／NOT_VERIFIED`、沿用已核准 Champion/Deterministic，不得把 Core 或 Mart 自動訓練當成已完成的 Colab，也不可建立第二個 Scheduler。未來若**使用者另核准**無人值守，再評估合規 Colab 執行方式、費用/OAuth/IAM；本階段 R1.A 已定案，無人值守不是交付項目，不能因此新增第二個 Scheduler。

**版本輸出**：`dataset_manifest`、`model artifact`、`oos_predictions`、`metrics`、`feature/label/source availability`、`requirements/seed`、`hash`、每月 `execution status` 與保留/回退參照。Colab notebook 不存密鑰、不寫 Canonical、不讀 Owner 私有資料；模型結果不能直接 publication。

## 6. 授權與治理

權威流程如上。既有 B5/B6 為唯讀來源匯出／固定資料可重用元件，不再作獨立 Cloud Run 模型訓練器；BigQuery 僅在通過前置縮減 gate 後啟用。

只匯出核准 source training-use 的公開研究欄位；不移出 Owner 持股、交易、現金、個資、PostgreSQL secret/token/private key。Colab 使用受限短效讀取／人工匯入；Notebook 不存 GCP 長效憑證或將私有 GCS 資料公開。輸入固定 dataset sha256、schema/feature/label/source/provenance/analysis_as_of、cohort與月度 cutoff；輸出固定 requirements-lock、seed、OOS predictions、metrics、artifact hashes、訓練失敗紀錄。不可只存 Colab ephemeral local file。

ChatGPT 可建立 Notebook／訓練程式／測試及研究收據，**不能保證本對話直接控制免費 Colab runtime**。依 R1.A 採人工作業，不需要正式無人值守 Colab 排程；仍須實際上傳結果、Janus readback/hash 與失敗回復收據。不能以既有 GCP Job 訓練冒充 Colab。任何新付費／IAM／OAuth consent 均需另行使用者核准。

## 7. Gate 與下一步

- P0：確認舊 B5 Parquet 仍可讀，使用現有 immutable dataset 做 CPU Quant baseline/LightGBM parity，不新增來源、Cron、Model promotion。
- P1：完成 Quant 真實歷史成分/PIT、每月成熟標籤與 OOS cross-section coverage；Risk 真正逐日證據，分模型決策。
- **D07-PRE 合併驗收**：依 [TODO](todo.md) 核對 24月逐角色資料、成熟 labels、合法研究匯出、Colab CPU RAM/耗時/實跑及受控人工回傳、既有 GCS 與 BQ（只有大資料需要）的成本/權限/parity/回退；形成一份驗收決議。**預設 Colab-only prep/train＋既有 Janus 正式 inference，BQ 大資料前置縮減維持 DEFERRED**；不是將訓練改回 GCP。

**唯一選定的目標：Colab 做資料整理＋模型訓練，BQ 只在有實測效益時前置處理，Janus 只管 canonical、月度待辦、治理驗收與正式推論。** Colab 免費版自動化依然 NOT_VERIFIED，PoC、量測與受控流程接線仍屬 D07-PRE／D07 待完成的工程，不列三套同等選項。

官方參考：[Colab FAQ](https://research.google.com/colaboratory/intl/zh-TW/faq.html)、[Colab Enterprise Scheduled Runs](https://docs.cloud.google.com/colab/docs/schedule-notebook-run?hl=zh-tw)。
## 8. R2／R3 缺口量化 — 2026-10-19 有界證據（不是全市場最新 COUNT）

| 項目 | 目前已知 | 尚缺／如何避免誤判 |
|---|---|---|
| **R2：24月全市場 OHLCV 股日** | 規劃使用當時 1,992 普通股 × 500 日＝**996,000 股日組**；2026-10-18 Core 快照總 `ohlcv=111,929` 筆，差額 **884,071 / 88.76%** | **這是不同口徑的規劃數字差，不是 certified coverage/missing %。** 實際市場成分隨日期改變、Core 可含不屬目標市場/窗口者，同筆是否重複或多版本未去重；缺逐月日期×股票 eligible matrix 及 10/19 新 Core census。不得直接開 884,071 筆補抓。 |
| **R2：現有固定訓練 dataset** | B5 immutable `10,978 rows / 499 symbols`、2026-03-19 至 2026-09-03（約 5.5 曆月跨度），不是 500 日×全市場 | 有 20D label/5D stride 重疊，不等同 10,978 筆獨立監督樣本；不足股票和月份須另按 OOS folds/horizons 查，不能外推 24 個月皆可用。 |
| **R2：保存政策** | 一般 Core OHLCV 365 天、Deep OHLCV 1,096 天，模型研究窗口目標 24 月 | 政策相差約12個月（一般 tier），**非現有實際日期缺口**；Deep 亦不保證滿三年。先 inventory 已存在 verified research Parquet 再定向補收，不改 row TTL。 |
| **R3：嚴格 PIT 合格率** | **UNKNOWN；不是 0% 或 100%**。live 5876 financials bounded sample 顯示 `observed_at/availability_at/published_at` 及 source/provenance，但 `publication_time_authoritative=false`、`numeric_revision_verified=null` 的樣本不能認定歷史當時版本完整 | 尚缺每個 dataset 的 authoritative first-published／first-observed、修訂版次、`available_at <= feature_as_of`、train-use 授權、歷史 membership/labels 同時合格的完整去重分母。Current-only snapshot 不能重播舊版；`strict_pit=false` 僅限有清楚 revision leakage 標示的研究。 |

**下一個 D07-PRE 動作**：產 `coverage_by_market_symbol_month`（expected/eligible/available/usable/missing）與 `pit_by_dataset_source_revision`（authoritative timestamp/first-observed/estimated/unknown、original revision verified/unknown、authorized/unknown）雙表，另輸出 5/20/60/120 日成熟 label count、purged folds/holdout。**只有這兩張讀回報表完成後才能說 R2 真缺多少、R3 合格率多少**；不另建獨立 R2/R3 工項、不造假缺值。
