# Janus WBS 5 — Token-first Specialist Engines

更新：2026-10-08
狀態：Partial implementation；未完成整體 acceptance

本 WBS 依 [`../decision-2026-10-03-token-first-specialist-and-on-demand-ceo.md`](../decision-2026-10-03-token-first-specialist-and-on-demand-ceo.md)、[`../decision-2026-10-06-bigquery-analytics-over-iceberg.md`](../decision-2026-10-06-bigquery-analytics-over-iceberg.md)、active TODO 與 [`../spec/specialist-engines.md`](../spec/specialist-engines.md) 執行。歷史 implementation／runtime evidence 只作追溯，不改變本 WBS 的現行目標。

## 1. 目標

五個 specialist 的 production 主路徑為 Python／SQL／ML，日常不使用生成式 LLM：

1. Fundamental — deterministic financial features + LightGBM。
2. Valuation — deterministic valuation + LightGBM／CatBoost。
3. Quant — LightGBM baseline + Qlib DoubleEnsemble challenger。
4. Risk／Regime — Riskfolio-Lib + statsmodels／ML regime model。
5. Event／Catalyst — parser／rules + local multilingual encoder classifier。

五 specialist 輸出必須 structured、PIT、可重放、可回測、可版本化；白話說明使用 SHAP／rules／templates，正常 path 0 API token。

## 2. Universe

### Market Coverage

約 500 檔保留低成本 screening 與必要 cross-sectional Quant inference，目的為 discovery，不作 500×5 深度分析。每個交易日 EOD canonical data ready 後執行一次；依 2026-10-10 使用者最新決策，預設維持 PyIceberg，不以 BigQuery fidelity PASS 自動切流。

### Deep Coverage

`active watchlist ∪ effective holdings`，去重後執行完整 specialist engines。Watchlist 50 active distinct-symbol quota 保留；持股離開 500 仍在 Deep Coverage，清倉且不在 watchlist 才退出後續更新。五 specialist 依 dirty dependency／input change 增量執行，不固定每日全重算。

### 執行節奏

- 每日盤後：liquid-500 低成本 screening／cross-sectional discovery。
- 日常 Deep Coverage：只有 `active watchlist ∪ effective holdings` 的受影響 symbol／specialist 因新資料而更新；無變更 reuse。
- 每月重型批次：`specialist-retrain`、calibration、OOS/evaluation、cache/dependency reconciliation 固定**每月第一個週六 10:30（Asia/Taipei）**。
- 不建立每週六 500×5 全量模型排程；月度排程只採上列第一個週六 10:30。

## 3. B 組現行架構：PyIceberg default／BigQuery ML-OOS opt-in

本段先於五引擎 production acceptance 與 rerun-cache 收斂執行，但不得把「架構已核准」誤寫成「BigQuery resource 已建立」。

### 3.1 Data-access boundary

先把目前 `load_core_datasets()`／PyIceberg exact-snapshot read 包成可替換 reader。Reference path 必須維持現有固定 `snapshot_id`、row limit、symbol filter、schema/null/PIT/provenance 語意；BigQuery adapter 不得滲入 specialist engine 的 canonical number 計算介面。

### 3.2 BigQuery adapter

BigQuery 僅在明確 opt-in 的 ML/OOS batch analytics 使用：

- OOS/evaluation SQL window、reduction 與必要的 batch aggregation；
- ML training dataset preparation 和 versioned GCS Parquet export。

每日盤後 liquid-500 screening、一般 specialist 與增量讀取均維持 PyIceberg 預設。

禁止 Storage Read API、`bigquery.readsessions.*` 與 `google-cloud-bigquery-storage`。小型結果使用一般 query/result API；大型 ML input 由 SQL 縮減後輸出 versioned GCS Parquet artifact。

### 3.3 Snapshot fidelity gate

目前 Core catalog 為 PostgreSQL-backed PyIceberg `SqlCatalog`。BigQuery ML/OOS 選用路徑正式執行前必須對同一 immutable Core manifest/snapshot 做 canary compare，證明指定 snapshot、schema evolution、date/timestamp、decimal、null、missing、provenance 與 source authorization 一致。

不得把會隨 latest metadata pointer 漂移的 external table 當成 immutable execution fence。Google-supported Lakehouse/Iceberg REST catalog 可作候選，但不得在無明確授權下啟用 API、建立 catalog／connection／dataset、遷移 catalog 或擴大 IAM。

### 3.4 Cost／I/O／storage policy

- Core Iceberg/GCS 空間預期維持，不以 BigQuery 導入宣稱 storage bytes 自動下降。
- 不建立未經證據支持的 full-Core BigQuery duplicate warehouse。
- Derived table 預設 bounded／TTL／可重建；BigQuery intermediate 不要求回寫 canonical Iceberg。大型 training/evaluation dataset 以 versioned GCS Parquet 固定；永久保存限 PIT/training/evaluation/publication 有需要的 artifact。
- Query 必須 column/date/symbol/partition bounded；記錄 processed/billed bytes、elapsed、Cloud Run peak RSS、GCS I/O evidence（可得時）、export bytes 與 fallback。
- BigQuery failure 必須可 audit fallback PyIceberg，不得影響 ingestion/canonical write 或 PostgreSQL serving。

### B7 每月首週六 retrain / OOS / cache reconciliation — 月度執行 PASS／derived cache freshness PARTIAL

- 實際 controller `Batch("specialist-retrain")` 已從「每月 1 日 10:30」修為「每月第一個週六 10:30 Asia/Taipei」；依賴當日 ingestion / data-supplement 成功，舊 pending 以 `schedule_superseded/skipped` 安全終結，不覆寫 immutable history。
- 既有 Mart retrain 的同一次執行跑 challenger / OOS / calibration；`monthly-reconciliation.json` 驗證 B4 active role input hash 與 artifact，盤點 B6 fixed-source ML/OOS Parquet 的 lineage、版本和 reference protection；跨 Core reuse 只在 fixed source snapshot/pointer + date 相符時成立。留存 historical orphan candidates，不自動刪除/提升 champion/喚醒 CEO。
- 證據：`6a2e76c`、`2285b64`、`fb07979`；initial CI #37711002505 ingestion 151 / Mart 137 PASS + existing dev Job deployment SUCCESS；最新 B7 Mart 143 tests PASS（CI #37711737194），此輪部署/live work item 仍須確認。
- [runtime readback #37712126960](https://github.com/tommylin15/janus-omniforge/actions/runs/37712126960)：controller image=ingestion image，Mart Job Ready=true；但 GitHub CI `janus-ci` 缺 `cloudscheduler.jobs.get`，故 scheduler cron/timeZone/state 實際值 **unknown**。未擴權，不能以 repo cron 或測試代替 live scheduler configuration evidence。
- 2026-10-10 已完成新版手動月度 retrain、Mart Completed、OOS／reconciliation immutable GCS SHA-256 readback（詳見 [status](../status.md)），月度執行機制 **PASS**；B6 ML/OOS derived cache 仍對應舊 Core，freshness **PARTIAL**。不重訓，只在 B8/B9 銜接按本次 Core source fence 更新衍生快取；下次自然首週六 2026-11-07 尚未觀測。B8 同等工作量驗收已啟動，不自動切換 BigQuery default。

## 4. Incremental execution

> B4 已於 2026-10-07 CLOSED / PASS。真實 dev acceptance 對 5 個 Deep Coverage symbols 產出 25 specialist artifacts；同一 Core snapshot 第二輪為 0 computed / 25 reused，且 event-only regression 驗證只有 Event dirty。完整 evidence 見 [B4 結案](../archive/group-b-b4-deep-coverage-closure-2026-10-07.md)。B5 ML/OOS data path 亦已於 2026-10-08 CLOSED / PASS：固定 Core snapshot 產出 10,978 rows、499 symbols、1 Parquet shard 的 immutable training/evaluation input；Cloud Run Mart 真實 readback PASS。見 [B5 結案](../archive/group-b-b5-ml-oos-data-closure-2026-10-08.md)。B6 derived artifact cache 已 CLOSED（見 [B6 結案](../archive/group-b-b6-ml-oos-cache-closure-2026-10-08.md)）；B7 月度 reconciliation、B8 fallback/FinOps、B9 模型 OOS 品質及 promotion 仍未完成。

禁止固定每日把所有 Deep Coverage symbols × 5 全重算。

每個 artifact 保存 input snapshot／content hash、feature／engine／model version、output hash、computed_at、freshness。Core／PIT data 更新後只 invalidate 受影響 dependency：

- monthly revenue／financials → Fundamental；必要時 Valuation。
- EOD price → cheap Valuation refresh、Quant、Risk。
- event → Event。
- 無 input change → cache hit／reuse。

CEO 不被 upstream change 自動觸發；只標記 report freshness／material delta。

## 5. Model cadence

- Specialist inference：有 input change 才跑。
- ML retraining／challenger：第一版固定每月第一個週六 10:30（Asia/Taipei）；Event classifier 依新 labeled data 或 drift 才 retrain。
- 同一月度批次完成 calibration／OOS evaluation／reconciliation，檢查 missed invalidation、artifact identity、model version、orphan cache。
- 新模型先通過 walk-forward OOS／PIT／leakage guard；training success 不代表 promotion。

歷史財報依 2026-10-03 使用者最新指示採資料優先驗證：原始數值版次／公開時間未證明不再阻擋 OOS。以最新官方版本及已知公開／上傳時間回放，時間缺少則採明示期末後 90 天假設；結果標示非嚴格 PIT，報酬標籤成熟／purge 保留。此特例取代歷史財報的嚴格時間 prerequisite，其他來源、品質與隔離契約保留。

## 6. Evaluation

至少：Rank IC、ICIR、IC decay、top-decile future excess-return spread、hit rate、Brier／calibration、Sharpe、max drawdown、turnover、after-cost performance、regime stability。

GitHub framework benchmark 不等於台股 production evidence；champion 由 Janus Taiwan PIT OOS 結果決定。

## 7. 白話報告

五 specialist 產出 deterministic plain-language report：

- structured metrics／probability／score（只在該 engine contract 正式定義時）；
- SHAP／feature contribution；
- positive／negative drivers；
- missing／stale／partial；
- what changed since previous artifact。

LLM 不參與 canonical number 計算。只有使用者明確要求 On-demand CEO，或日後另行核准的 rare escalation，才進 approved LLM runtime。

## 8. GitHub framework policy

Production candidates：

- `microsoft/qlib`
- `dcajasn/Riskfolio-Lib`
- `huggingface/transformers`
- `shap/shap`

Benchmark／challenger：

- `autogluon/autogluon`
- `ProsusAI/finBERT`（benchmark only）
- `AI4Finance-Foundation/FinGPT`（research only）

引入前必須 pin version／license、走 dependency／security review；不直接 fork 整套產品架構進 Janus。

## 9. Acceptance

完成至少證明：

- B 組 analytics reader abstraction 已落地，PyIceberg reference/fallback 與 BigQuery adapter 邊界清楚；
- 至少一個 liquid-500／cross-sectional workload 在同一固定 Core snapshot 完成 PyIceberg vs BigQuery deterministic compare；
- BigQuery path 不使用 Storage Read API，且大型 ML dataset 經 versioned export artifact 交給 training runtime；
- processed/billed bytes、elapsed、peak RSS、GCS I/O／export evidence（可得時）有 before/after，成本未知處保持 unknown；
- BigQuery 失效可安全 fallback，且 PostgreSQL serving／A 組 API/UI 不受影響；
- 未經授權沒有建立 full-Core duplicate、啟用新付費 API、擴大 IAM 或遷移 canonical catalog；

- 每日盤後 500 screening 有真實 dev execution/readback，不產生 LLM calls，也不擴成 500×5 深度 specialist；
- Deep Coverage watch-only／held-only／overlap／held-off-market／exit 語意正確；
- 五 specialist production baseline 在真實 dev PIT data 執行並持久化；
- dirty dependency graph 只重算受影響 specialist；no-change 可 audit reuse；
- 每月第一個週六 10:30 的 retrain／calibration／OOS evaluation／reconciliation effective schedule 已在實際 Scheduler／controller readback，且可安全重跑；champion promotion 有 OOS evidence；
- specialist plain-language output 不依賴 LLM API；
- canonical number、PIT、provenance、missing-data honesty、public/private isolation 保持；
- tests、deployment、live dev execution、artifact persist／readback evidence 齊全。

本 WBS 完成不等於 On-demand CEO 完成；CEO provider/runtime、capability、User／Admin UI 由後續 WBS 驗收。
