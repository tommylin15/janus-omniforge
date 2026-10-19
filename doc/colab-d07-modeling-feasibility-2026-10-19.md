# D07-PRE｜資料與運算器整合前置評估（含 FINOPS-C，2026-10-19）

> **這是 [TODO D07-PRE](todo.md) 唯一共用前置任務的研究證據，不是新 Colab 或 C-preflight 工單，也不是整體 PASS。** 本輪未重新執行 GCP census、FinOps 收費驗收或 Colab 訓練；資料覆蓋、Colab 建模方式與原 FINOPS-C 成本/安全/parity 必須產生同一份 GO/NO-GO/DEFER 決議。

## 1. 結論

建議 **GO：免費 Google Colab CPU、離線 Quant／Risk PoC**，但 **NO-GO：把正式每月自動排程轉移到免費 Colab**。現有 PyIceberg／B5/B6 產出 frozen、versioned Parquet，Colab 作 research challenger 訓練、walk-forward OOS 與 metrics，成果返回既有 Janus Mart 驗證及受控 model registry；D08 仍僅消費受驗證 Fact Pack。避免再建第二套 Cron／Canonical 倉。

## 2. 現有資料，規模與可靠性分開看

| 固定證據 | 觀察值 | 能／不能推論 |
|---|---|---|
| [B5 ML/OOS 實機結案](archive/group-b-b5-ml-oos-data-closure-2026-10-08.md) | 10,978 rows、499 symbols、Parquet 533,945 bytes、日期 2026-03-19～09-03；20 trading-day label＋5日 stride，含 5/20D returns、turnover、volume、source/provenance | CPU 計算規模小，適合驗證 notebook reproducibility；不能推成 24 月或所有五角色特徵已完整。平均每股約22筆 cohort，重疊 horizon 不是同數獨立樣本 |
| [10/18 Core census #39083283620](https://github.com/tommylin15/janus-omniforge/actions/runs/39083283620) | OHLCV 111,929、valuation 16,595、financials 88,131、benchmark 759、market-volume 39,699、market-activity 135,050 rows | 表間口徑／交易日／市場不同，不能相加成 ML 訓練列，也不是新鮮 10/19 全表 COUNT |
| [全市場保存矩陣](spec/factor-coverage-retention-ledger.md) | 2026-10-17 假設 1,992 普通股 × 約500交易日＝兩年約996,000股日（理論情境） | 不應把111,929與理論值直接當 coverage 分母；一般 Core 價量 row TTL 365 天、Deep 1,096 天，current-only Snapshot 不保證全市場兩年歷史 |
| [10/19 DRL 與背景補收](todo.md) | 月營收13月分市場門檻既有 PASS；八股需求補收 8/8 ready；六股兩年 PE/PB 12/12 正式 API 讀回 | 產品資料可用≠所有股/日期具兩年 OHLCV、合規標籤、嚴格 PIT 或完整 12 季 |
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

## 5. 最小架構與授權

Stage／Canonical Iceberg Core → 既有 PyIceberg B5/B6（BQ 只能另經明確 opt-in）→ immutable 研究 Parquet → Colab CPU notebook → evaluation/model artifacts＋hash → Janus Mart 唯讀驗證與隔離的 registry → 有獨立 gates 才上線／回滾。

只匯出核准 source training-use 的公開研究欄位；不移出 Owner 持股、交易、現金、個資、PostgreSQL secret/token/private key。Colab 使用受限短效讀取／人工匯入；Notebook 不存 GCP 長效憑證或將私有 GCS 資料公開。輸入固定 dataset sha256、schema/feature/label/source/provenance/analysis_as_of、cohort與月度 cutoff；輸出固定 requirements-lock、seed、OOS predictions、metrics、artifact hashes、訓練失敗紀錄。不可只存 Colab ephemeral local file。

ChatGPT 可建立 Notebook／訓練程式／測試及研究收據，卻**不能保證本對話直接控制免費 Colab runtime**。免費版優先互動式 PoC；Google 官方不保證免費 CPU/GPU 或持續時長。要無人值守應比較既有 GCP Jobs 或需另外核准付費與 IAM 的 Colab Enterprise 官方排程；不可新增與 Janus controller 平行的每月正式 Cron。

## 6. Gate 與下一步

- P0：確認舊 B5 Parquet 仍可讀，使用現有 immutable dataset 做 CPU Quant baseline/LightGBM parity，不新增來源、Cron、Model promotion。
- P1：完成 Quant 真實歷史成分/PIT、每月成熟標籤與 OOS cross-section coverage；Risk 真正逐日證據，分模型決策。
- **D07-PRE 合併驗收**：依 [TODO](todo.md) 統一完成 24月逐角色資料覆蓋、成熟 labels、必要補收/Research Export、FINOPS-AB 後 CPU/GCS/BQ 費用／既有額度、Colab/Jobs/PyIceberg 運算比較、exact Core identity/parity、回退與安全，產生一份 go/no-go/defer 結論；**可正式 DEFER BigQuery 直接用既有 Jobs 進入 D07**，不必為開發 D07 強制切換 BQ。

**最終選項：GO（免費 Colab 離線 Quant/Risk CPU PoC）；NO-GO（免費 Colab 正式無人值守月度重訓）；CONDITIONAL（24月完整研究、五角色 Champion、Enterprise 計費排程）。**

官方參考：[Colab FAQ](https://research.google.com/colaboratory/intl/zh-TW/faq.html)、[Colab Enterprise Scheduled Runs](https://docs.cloud.google.com/colab/docs/schedule-notebook-run?hl=zh-tw)。