# Janus WBS 5 — Intelligence Mart

## WBS 5 — Intelligence Mart

### 5.0 Runtime 與輸入邊界

- 目前 GCP `dev` 是 Janus 個人使用階段的真實平行上線環境。WBS-5 capability 通過各自 data-trust、runtime、publication 與 integration acceptance 後，可直接在 dev 使用真實資料與真實服務；不需要另一套 Production 環境作為資格證。
- 這個環境定位不放寬資料可信度：canonical data、PIT／future leakage、provenance、source authorization、publication gate、immutable lineage、missing-data honesty 與 LLM 不得修改 canonical numbers 仍是必要條件。
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

- Current implementation：五個 deterministic discriminated role payload，包含 nullable
  score、confidence、missing_data、evidence；這是既有 `mart.v1` compatibility
  surface，不是五個 AI analyst。
- Planned：五個獨立、可平行執行的 evidence-grounded AI analyst stage，輸入 immutable
  Fact Pack、validated evidence、`analysis_as_of`、Core snapshot identity、fixed
  system guardrail、versioned methodology prompt 與 provider/model/parameters。
- Planned role output 至少包含 stance、thesis、key findings、positive／negative
  evidence、contradictions、change drivers、risks、missing information、
  what-would-change-my-view、confidence 與 evidence IDs。
- URL、時間、單位、duplicate、stale、conflict、future validation。
- Evidence 必須引用可定位的 provenance／Core snapshot；未核准來源、缺 publication
  time 或超過 `analysis_as_of` 的資料不得成為角色或 LLM 輸入。
- Planned prompt boundary：System Guardrail locked；五個 Role Methodology Prompt 與
  CIO Prompt 可由唯一 Admin 版本化編輯；Output Schema 由系統控制。所有 version、
  content hash、author、timestamp 與 profile reference 寫入 immutable lineage。

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

- Current implementation：公開批次 Mart 只有可選 Gemini narrator；OpenRouter 目前只在
  私人 Agent Gateway。這些現況不得寫成已完成五角色 AI。
- Planned：以 governed `MartAIProvider` 支援 `GeminiMartProvider` 與
  `OpenRouterMartProvider`；provider failure 不改 deterministic facts，未核准 provider
  或不符合 structured output／context／required parameters 的 model 不可選。
- Provider capability discovery、bounded supported parameters、429／unavailable
  bounded retry、structured failure、usage／latency／cost lineage 與 billing gate
  必須可測試。不得自動加入 Codex／OpenAI API；paid tier 仍須人工授權。
- LLM 只能解釋、比較與合成經驗證 evidence；不得計算、補值、覆寫或發布 canonical deterministic numbers／facts。

### 5.4.1 Planned atomic WBS slices

以下切片全部為 `Planned`，不表示目前 implementation 已完成；依 dependency 排入
parallel-live dev roadmap，完成後依各自 acceptance 在目前 dev 真實使用並持續收集 evidence，不以六個月 Pilot 或未來 Production 作為首次使用資格：

| WBS | 範圍 | Dependency | Acceptance |
|---|---|---|---|
| `WBS-5-MART-FACT-PACKS` | 五份 deterministic Fact Pack、baseline compatibility、hash／version lineage、mart.v1 compatibility | 既有 Core snapshot、analysis.py、mart.v1 | facts 可 deterministic replay；LLM off 不改 facts；canonical numbers、PIT、missing data、provenance 與 evidence refs 可驗證 |
| `WBS-5-MART-AI-ROLE-CONTRACT` | 五個 role schema、guardrail boundary、versioned role prompts、CIO output contract | FACT-PACKS | schema／prompt／lineage fixtures 通過；invalid role 不得假裝成功；old artifacts immutable |
| `WBS-5-MART-AI-PROVIDERS` | MartAIProvider、Gemini、OpenRouter、capability discovery、bounded parameters、billing gate、structured failure | ROLE-CONTRACT | Gemini／OpenRouter contract tests、unsupported model／parameter rejection、429／unavailable retry bounds 通過 |
| `WBS-5-MART-AI-VALIDATION` | schema、evidence、numeric grounding、time fence、missing data、claim coverage validation | ROLE-CONTRACT、PROVIDERS | invalid output blocked；one role failure 不是 full success；provider/model/prompt/input identity 可追溯 |
| `WBS-5-MART-CIO-SYNTHESIS` | validated roles only、CIO synthesis、synthesis validator、no publication authority | AI-VALIDATION | CIO 只讀 validated inputs；validator failure structured；publication 仍由 deterministic gate 決定 |
| `WBS-5-MART-RERUN-CACHE` | single-role rerun、dependency invalidation、content-addressed reuse、immutable lineage | FACT-PACKS、AI-VALIDATION、CIO-SYNTHESIS | 無關 role 不重跑；prompt/model 不重算 facts；governance-only 不呼叫 LLM；相同 identity reuse 且 audit |
| `WBS-5-MART-V2-COMPAT` | mart.v1 additive compatibility、future mart.v2 migration plan | FACT-PACKS、ROLE-CONTRACT | mart.v1 fixtures／consumers 維持；新 contract additive；未完成 migration 前不破壞 v1 |

Leading Indicators 與 Major-wave Prediction 不屬本組 WBS；只保留 extensible contract
space，不加入 role logic、score、CIO 或 publication。

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
- 宣稱某 Mart 能力已可在目前 dev 真實使用時，必須另有相應 live Job／data／publication／API／UI integration evidence；fixture 或 sample UI 不能單獨構成完成。

`WBS-5-SUPPLY-INTELLIGENCE-PLANNING` 是本次 todo 的 planning umbrella，涵蓋以下
foundation、Source Matrix、seed graph、signal／Mart contract 四個切片；它不代表任何
implementation unlock，Gate A–E 仍須逐一滿足。這些 Gate 是資料可信度、來源授權、schema／ingestion 與成本／資源治理 gate，不是「dev 只能 POC」的環境 gate。

### 5.7 `WBS-5-SUPPLY-FOUNDATION` — Supply-chain foundation planning

本切片只做 documentation／planning。定義共用 ontology、node／edge／company exposure
contract、effective-time semantics、PIT／provenance、evidence class 與 signal boundary；
不建立 schema、migration、Iceberg table、adapter 或 Mart implementation。

驗收：common ontology review、relationship／exposure contract、effective time、
`confirmed`／`reported`／`inferred`／`hypothesis`、provenance／PIT requirements 與六個
domain scope 均可由規格判讀。

### 5.8 `WBS-5-SUPPLY-SOURCE-MATRIX` — 六 domain Source Matrix planning

同一份矩陣涵蓋 AI Server／Semiconductor、Memory、EV、Networking、Apple supply chain、
Industrial automation。每列記錄 indicator、source candidate、official／external、lead
metric／time、PIT、license／retention、cost、coverage、cadence、provenance 與 approval
status；未知值使用 `Unknown`／`candidate`／`blocked`，不猜測 license、price、quota 或
coverage，也不建立 source adapter。

### 5.9 `WBS-5-SUPPLY-SEED-GRAPH` — 可驗證 seed graph planning

六個 domain 均在 scope；第一版只規劃可驗證 relationship、evidence 與 effective time。
不得讓 AI 自動把文章轉成正式 supplier／customer fact，不建立 Graph DB、crawler 或
完整公司清單。

### 5.10 `WBS-5-SUPPLY-SIGNAL-MART` — Signal／Mart contract planning

只定義 `leading indicator → exposure → expected impact → market expectation → expectation
gap` contract 與輸出欄位；future implementation 必須重用既有 Stage／Core、PIT、
provenance、immutable snapshot、Mart 與 Cloud Run topology。LLM 只能解釋 evidence，不得
計算 deterministic exposure、score 或數字。

### 5.11 Supply-chain implementation unlock gates

以下 gate 是後續 Supply-chain capability 的必要前置，未通過時只能補 planning／evidence；它們不限制與 Supply-chain 無關的既有 Janus dev 真實使用：

- **Gate A — Foundation／Contract Ready**：ontology、node／edge／exposure、effective
  time、evidence、provenance／PIT、六 domain Source Matrix 第一版與 Pilot measurement／
  epoch design 全部 review 完成。未通過不得建立 schema／ingestion implementation WBS、
  migration、Iceberg table、adapter 或 Mart implementation。
- **Gate B — Individual Source Approved**：每個 source 個別確認 identity、target
  indicator、expected metric／lead time、coverage／cadence、PIT／history、license／API
  terms、retention、citation／redistribution、quota、cost、provenance 與 fallback／failure
  behavior。只有 `approved`、`approved_fallback` 或 `official` 可解鎖最小 ingestion WBS；
  `candidate`／`blocked` 不得進 canonical／live ingestion 或 published analysis。
- **Gate C — Schema／Ingestion Implementation**：Gate A 通過且至少一個 source 通過 Gate
  B，才可排 schema／Iceberg evolution、Stage → Core normalization、DQ／provenance 與
  deterministic signal input；優先重用 existing ingestion-core、catalog、GCS 與 Cloud
  Run jobs／services，不自動新增 runtime。
- **Gate D — Mart Signal Implementation**：至少一組 Supply-chain Core data 已完成
  ingestion、PIT validation、provenance、deterministic replay 與 bounded DQ，才可實作
  leading indicator、company exposure、signal、expectation gap 與 Mart product。
- **Gate E — New GCP Resource**：新增任何 GCP resource、IAM binding、paid API／service
  都要先證明既有 architecture 不足，提出 architecture reason、cheaper alternative、
  cost、operations、IAM／security 與 rollback／exit strategy，並取得使用者明確同意；
  不因 Gate A–D 通過而自動解鎖。

### 5.12 `WBS-5-RESEARCH-MART-CONTRACT`（Pilot Evolution／Planned）

- 定義 research-ready deterministic Mart：MA 5／10／20、recent high／low、ATR、RVOL、volume trend、institutional 3／5／10-day aggregation、margin change、relative strength、benchmark-relative return、price／volume state、formally defined breakout／trend state 與 existing approved chip／positioning indicators。
- formula、window、null handling、trading-calendar、revision 與 PIT semantics 在 future implementation contract 中 deterministic 定義；本 planning 不選定公式，LLM 僅解釋。
- 定義 bounded `Market Regime` contract；輸入僅限當時已核准且有 coverage evidence 的 benchmark、breadth、turnover、institutional、financing 與 macro inputs，其餘標 `Unknown`／`Candidate`／`Blocked`。輸出包含 state、`analysis_as_of`、deterministic confidence、evidence 與 missing data。
- ResearchContext 的 market／company sections 必須可由同一 snapshot／revision replay。Supply-chain indicators 僅在 Gate D 後增量併入；不新建 graph platform／Mart track。
- 本節 capability 通過自身資料與 integration acceptance 後，可直接在目前 parallel-live dev 使用真實資料；`Pilot Evolution` 是 roadmap／evidence 分類，不等於只能用 mock 或等待未來 Production。