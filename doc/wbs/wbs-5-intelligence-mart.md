# Janus WBS 5 — Intelligence Mart

## WBS 5 — Intelligence Mart

### 5.0 Runtime 與輸入邊界

- `intelligence-mart` 以 Cloud Run Job 執行，只讀 analysis-as-of 可見的
  versioned Core snapshot；Analysis 不得即時補抓、呼叫 scraper 或改寫 Core。
- Mart Job 使用 Direct VPC egress、專用 service account 與 workload-specific
  PostgreSQL catalog／publication credentials；連線池、statement timeout 與 retry
  必須有界。
- 每次執行固定 `execution_id`、`analysis_as_of`、Core snapshot ID、schema／feature／
  model version 與 immutable governance snapshot version，作為重跑及稽核邊界。
- Mart 必須由 ingestion 成功完成 DQ、Core commit 並發出 `core.dataset.ready.v1` 後，
  透過 workflow／event 觸發；事件需攜帶 execution 與 immutable Core snapshot 邊界。
  Cloud Scheduler 不得讓 ingestion 與 Mart 在相同時間各自獨立觸發，以免 Mart
  讀取尚未完成或不一致的 Core snapshot。

### 5.1 Feature pipeline

- 全市場 `mart_screening_signals`：突破、量能、流動性與異動候選。
- 12 月／12 季 Fundamental features。
- PE／PB／ROE／D/E Valuation features。
- 5／20／60 日 Positioning features。
- 20／60／120 日 Quant、Beta、ATR、turnover。
- PIT Event Risk features。
- 關注股深度追蹤層的 `mart_core_alpha`、`mart_risk_portfolio` 與經核准文本的 `mart_alternative_sentiment`。
- 新增單一 `mart_scoped_analysis`，以 market／industry／symbol scope 保存五角色輸出、membership snapshot、evidence、missing data、analysis outcome、prompt version 與 CIO 聚合 payload。
- 新增 `mart_market_regime_daily`、`mart_sector_rotation_daily`、`mart_topic_trends_daily`、`mart_candidate_health` 與 `mart_daily_brief`；每日摘要只組合同一 analysis-as-of 的已發布成品，不重算上游分數。
- 公開 Mart schema 均使用 versioned Iceberg table／partition；至少保存 symbol／industry／coverage、
  analysis date、上述 lineage、completeness、confidence、data quality、publication／
  analysis outcome，以及 evidence／artifact reference。不得只保存無法追溯來源的最終分數。
- `mart_scoped_analysis` 的 aggregate payload 保存 screening／risk／sentiment 摘要、aggregate score、bull／bear、contradictions、contributions、Devil's Advocate 反證、blocked／insufficient-data reason 與 CIO 結構化摘要。

### 5.2 五角色與 Validator

- 五個 discriminated role payload。
- nullable score、confidence、missing_data、evidence。
- URL、時間、單位、duplicate、stale、conflict、future validation。
- Evidence 必須引用可定位的 provenance／Core snapshot；未核准來源、缺 publication
  time 或超過 `analysis_as_of` 的資料不得成為角色或 LLM 輸入。
- 五角色使用 repository 版控的固定 structured prompt，不提供 Admin 編輯或 scope override。每次 execution 固定 prompt version／content hash 至 immutable governance snapshot；修改不得回寫歷史分析。

### 5.3 Aggregator／Publication

- 初始權重與 effective weight。
- bull／bear／contradictions／contributions。
- Devil's Advocate 反證階段與 `mart_scoped_analysis` CIO aggregate payload；兩者只使用合格 evidence。
- 30% development gate。
- manual review、critical、high≥75 blocking。
- immutable governance snapshot version。
- `insufficient_data` 是 completeness gate 的分析結果，必須與 publication lifecycle
  狀態分欄保存；實作前須讓 spec、contracts、API 與 UI 使用同一語意。只有
  `publishable`／`published` 可進公開 service index。

### 5.4 LLM

- 公開批次 Mart 的 LLM provider 只使用 Gemini，與 WBS 4C 的使用者可切換私人聊天室分離；不得使用 OpenAI／Codex API。
- Structured output 與 evidence-only prompt；啟用 Gemini 付費前須通過人工 billing gate。
- Gemini 發生 429／`RESOURCE_EXHAUSTED` 或 provider unavailable 時 bounded retry；仍失敗或其他錯誤皆結構化失敗，不寫 placeholder。

### 5.5 Mart writer

- GCS Mart bucket 保存 Iceberg／Parquet data 與 metadata、versioned feature／role／
  evidence／aggregation payload、model／evaluation artifact 與完整結構化 report；大型 governance diff 亦留在 GCS。
- PostgreSQL 的市場分析邊界只保存 catalog、control、publication、audit、report metadata
  與 bounded service index，包括 object URI、snapshot ID、hash、version 與狀態；私人
  ledger 使用獨立 schema／role。不得保存完整 report、feature 或 evidence payload。
- publication schema 使用 migration、唯一鍵、retention、bounded pool 與
  workload-specific role；blocked／insufficient-data 成品不得進 publishable view。
- 發出 `mart.report.ready.v1`。

### 5.6 驗收條件

- Analysis 不呼叫 scraper。
- LLM 關閉時 deterministic output 不改變。
- blocked 不進 publishable view。
- 同一 Core snapshot + governance version 可重現相同 deterministic 結果。
- Contract、Iceberg schema evolution 與儲存邊界測試證明 PostgreSQL 沒有完整 Mart payload，且 publication index 可解析至正確 immutable GCS／Iceberg artifact。
- market／industry／symbol 分析可由 Admin 解析至正確 immutable `mart_scoped_analysis` artifact；切換 repository prompt version 後只影響新 execution，舊結果仍可依 version／hash 重現。
- 市場狀態、每日摘要、板塊輪動、熱門話題與候選健康度可由相同 analysis-as-of 重建，且 Flutter 不參與分數計算。
