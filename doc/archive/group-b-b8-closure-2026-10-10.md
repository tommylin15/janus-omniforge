# B8 完成驗收 — 同源 PyIceberg／BigQuery 路由、FinOps 與安全回退（2026-10-10）

**驗收判定：B8 CLOSED／PASS（已核准的 dev 同源 benchmark、選路政策與有界故障回退範圍）。** 不代表新 Core 的 B7 derived cache freshness、B9 模型品質或日後正式切換 BigQuery；不把 synthetic BigQuery outage 冒充實際服務中斷。

## 最終決策與實作

- **PyIceberg 是日常 Screening、Specialist 與 ML/OOS 的預設。** BQ 僅明確 `--backend bigquery --bigquery-opt-in` 時處理 ML/OOS SQL/Parquet batch；禁止作 User API hot path、canonical/source of truth 或自動全面 cutover。
- [B5 執行入口](https://github.com/tommylin15/janus-omniforge/blob/main/scripts/gcp/b5-ml-oos-data.py) 已接上 [backend policy](https://github.com/tommylin15/janus-omniforge/blob/main/jobs/intelligence-mart/intelligence_mart/ml_oos_backend_policy.py)。兩路都以 Core immutable manifest hash、`core.ohlcv_v1` snapshot/pointer、date/PIT、source provenance、20 trading-day label／5 trading-day stride、feature/model/schema 版本作固定輸入。
- B5 的 B6 既有 immutable cache 命中仍可安全 readback/reuse，不跑 SQL；cache miss 才選擇 PyIceberg 或 BQ。任何新 Parquet 在 manifest 發表**前**經 Mart `inspect_dataset` schema、row count、hash、maturity/PIT、source authorization 驗證；GCS immutable object 只能 create (generationMatch=0)，不能覆寫 canonical 或舊 B5/B6。
- BQ 執行仍保有 1 GiB cumulative billed guard、每 query 60s timeout、失敗 job 不盲目重送、一般 BigQuery query/result + TEMP native Parquet export，**不使用 Storage Read API**。
- 只有分類的 BQ 系統錯誤（permission／quota／timeout／unavailable）才能在 BQ **尚未開始 export、沒有任何 output shard** 時用相同 Core 的 PyIceberg 單次 fallback；否則 **fail closed**。BQ 已開始 export 即使當下 prefix 看似空白，也不得與後續 PyIceberg GCS 寫入競爭；不刪除可能仍在執行的輸出。來源/PIT/schema/資料一致性失敗都不回退掩蓋。
- 若 BQ job 異常時最終費用不明，manifest／evidence `total_billed_bytes=null` 且 `billed_bytes_complete=false`，絕不誤寫成免費。研究 Parquet 與 canonical 完全分離；沒有新 IAM／LLM／CEO／模型重訓。

## 現場驗收與 CI 證據

1. **BQ 讀權及來源**：[catalog WIF #38030454991 attempt 2](https://github.com/tommylin15/janus-omniforge/actions/runs/38030454991) PASS。使用者本人在 Cloud Shell 核准 project-scoped `roles/biglake.viewer` 與 `roles/bigquery.jobUser`，前一輪 HTTP 403 已解除；GitHub workflow 不自動擴權。
2. **500 screening 500 members 對照**：[screening #38029803051 attempt 2](https://github.com/tommylin15/janus-omniforge/actions/runs/38029803051) PASS，36 tests、三表/PIT/輸出一致；PyIceberg 兩輪 25.30／23.54s，BQ 31.32／34.13s，BQ 四 query billed 40 MiB。因此 screening 不切 BigQuery。
3. **ML/OOS SQL/Parquet 同源 benchmark**：[equal-run #38033560821](https://github.com/tommylin15/janus-omniforge/actions/runs/38033560821) PASS，31 tests；fixed 2026-10-06 Core 與 B5 `10,978` rows x four samples，所有 keys／nulls／provenance／labels 相等（0 differences）。Py local Parquet 10.65／9.98s，BQ GCS native Parquet 8.38／8.74s，2 BQ script jobs 合計 40 MiB billed、GCS export 1,067,915 bytes。**Sink 不同與小樣本**使性能優勢不具切流充分性；`performance_decision=inconclusive`。
4. **B5 產製入口與故障路由實際綜合驗收**：[B8 final #38037557795](https://github.com/tommylin15/janus-omniforge/actions/runs/38037557795) **SUCCESS**（source SHA `b609027e0fcd3b1f681483f0ac73f912c9abdcff`），**44 targeted tests PASS**：
   - offline 直接呼叫新版 **B5 main()** 於 cache miss 的 Py default / BQ opt-in service unavailable / BQ 已提交 export 後 unavailable；確保一次 Py fallback 僅發生於無 export 競寫風險時，其餘 fail closed、無 manifest 偽成功。
   - 同一 GitHub WIF 真實讀 frozen Core 74,999 source rows → 10,978 ML/OOS rows；Py default 與 BQ unavailable（**synthetic injected**）兩次都與不可變 B5 Parquet **0 differences**、catalog fence 前後相符。
   - 同輪真實執行新版 **B5 CLI 預設路徑**，從 dev GCS 命中既有 10,978 rows B6 immutable cache：`status=pass, reused=true, cache_hit_verified=true`，`bigquery_jobs=[]`，**本次快取 readback billed 0**。這個 0 不代表前面兩次 benchmark 的 40 MiB 或未來失敗 Job 免費。
   - 原始 JSON 在 workflow artifact `b8-ml-oos-fallback-38037557795`，14 天 retention；`canonical_write=false`、`cache_write=false`、`cutover=false`，故障注入沒有提交 GCP BigQuery job。
5. **CI**：[對應 SHA selective CI #38037557763](https://github.com/tommylin15/janus-omniforge/actions/runs/38037557763) SUCCESS；最終文件改動另依當次 main selective CI readback。

## Runtime／部署界線

- [既有 Mart entrypoint](https://github.com/tommylin15/janus-omniforge/blob/main/jobs/intelligence-mart/intelligence_mart/__main__.py) 的 active Specialist／Screening 流程一向使用 PyIceberg；`ml-oos-data-acceptance` 只讀取/驗證既有 ML/OOS Parquet，**不是 B5 BigQuery/Py materialization 的執行入口**。
- B8 修改的是 GHA 驗收執行的 B5 standalone materialization 與共用 policy。已直接在既有 dev GCS 經 GitHub WIF 執行新版 B5 CLI 的 readback；沒有變更正在提供真實資料服務的 Mart 邏輯，因此**本次不強制重新建置或部署四個 GHCR images／執行已完成的 B7 月度 Job**。這不是已部署新版 Mart image 的宣稱，也不是 fresh-Core cache-miss 全實際 materialization 證據。
- 當 B7 新 Core 的 derived cache 需要 refresh 時，**仍須另以新 Core snapshot、PIT 與來源權限驗證**；舊 fixed B2 Core 不得替代。該項仍記在 B7 active TODO；B9 模型 OOS 品質另行驗收。B8 的已核准固定 Core performance／reader 選擇／受控故障回退 acceptance 此次結案，不混淆不同 WBS。

歷史失敗與 PARTIAL checkpoint：[2026-10-10 B8 過程記錄](group-b-b8-partial-checkpoint-2026-10-10.md)，此處保存舊 HTTP 403 等原因，不再當作當前 blocking gate。
