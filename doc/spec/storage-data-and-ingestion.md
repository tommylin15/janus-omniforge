# Janus SPEC — 儲存、資料供應與 Ingestion

## 5. 湖倉分層

| 層 | 格式 | 責任 | 寫入者 | 讀取者 |
|---|---|---|---|---|
| Stage／Bronze | 原始 JSON、CSV、受控物件 | 保存來源原貌、request metadata、hash | ingestion-core | ingestion-core、治理稽核 |
| Core／Silver | Iceberg／Parquet | 正規化、去重、單位、日期、null、PIT、provenance、文本與股票代號關聯 | ingestion-core／DuckDB／PyIceberg | intelligence-mart、read-only query runtime |
| Mart／Gold | Iceberg／Parquet | 特徵、角色輸出、聚合、研報、評估 | intelligence-mart | FastAPI、User、Admin |
| Private control／ledger | PostgreSQL append-only events／bounded index | 使用者手動交易、修正、冪等、所有權、目前關注狀態、私人 artifact index 與 pipeline checkpoint | private API | 該使用者、private pipeline |
| Private Core／Mart | 加密受限 Iceberg／Parquet | 交易正規化、筆記 revision、關注歷史、AI messages／context／citations、庫存與損益 | private pipeline／chat persistence | 該使用者的 API，不得公開 |

規則：

- 不可把所有 0 一律轉成 null；須依欄位語意處理。
- 單日漲跌超過 11% 不可直接刪除；先檢查市場限制、除權息、公司行動與跨源差異。
- Core／Mart 使用 immutable snapshot 或 versioned partition，支援重跑與 PIT。
- UI 不得直接讀 Stage 或未發布 Core。
- Core 保存可重算的來源資料與 deterministic 標準化結果；NER 關聯必須保留模型／規則版本與 evidence。情緒分數、AI 示警、動態權重與投資判讀屬 Mart，不得回寫成來源事實。
- Public 與 Private namespace、bucket prefix、Iceberg table、service index、IAM 與 retention 必須隔離；不得以只靠 Flutter 篩選來保護使用者交易資料。
- 交易金額、股數、手續費、稅與損益使用固定精度 decimal，不使用 binary floating point。更正交易以 reversal／replacement event 留痕，不就地改寫稽核歷史。
- 筆記使用單一 append-only revision model，可獨立存在或連結 symbol／trade event；AI 對話保存 message、所用私人 context snapshot、外部 citation、資料日期與執行版本。OpenRouter／Gemini／MCP credential、Codex auth cache、refresh token 與 secret 一律不得進 Iceberg。

PostgreSQL append-only private transaction ledger 是私人交易事實的 OLTP source of
truth；Private Core／Mart 是 derived／normalized result，不是 ledger backup。Dev
Pilot 使用已人工核准的 bounded logical backup：`PostgreSQL logical backup
(pg_dump) → restricted Private GCS`，不改變 ledger semantics、reversal／replacement
history、Private Iceberg pipeline 或 public／private isolation。此例外不授權 PD
snapshot、Cloud SQL、HA、replica、second PostgreSQL VM 或無界 retention。

## 6. 資料供應模型與正式資料來源

### 6.1 雙軌 coverage

| 軌道 | 對象 | 預設頻率 | 必要資料 | 用途 |
|---|---|---|---|---|
| 全市場量化網 | 股票 master 當日所有 enabled 上市／上櫃標的，約 1,700–2,000 檔 | 日頻／公告頻率 | 日 OHLCV、PE/PB、法人、融資券／借券／當沖、基本面摘要、benchmark | 異動偵測、流動性檢查、每日 screening |
| 個人關注股深度追蹤 | authenticated users 的 active watchlist 所形成之去識別化 symbol 聯集；MVP 最多 50 個 distinct symbols | 日頻加上經核准的分 K／Tick、事件與文本 | 深度財報、公司行動／重大訊息、新聞與核准另類資料 | 個人關注、深度特徵、風險分析、PIT 回測與研究報告 |

- `coverage_tier`、去識別化深度追蹤 membership、effective time、collection cadence 與授權狀態必須持久化並可稽核；關注異動不得改寫歷史 membership，Admin 不得看到使用者與 symbol 的對應。
- 高頻、文本與另類資料不得因全市場 collection 自動擴張；MVP 超過 50 個 active distinct symbols 或提高抓取頻率須拒絕並另行評估來源限制、Cloud Run/GCS 成本與授權。此上限是營運護欄，不是「50 大」產品功能。
- collection 與 analysis 分離；進入深度追蹤只代表有使用者關注需求且可收集相應資料，不代表平台推薦、可發布或可自動下單。

### 6.2 五層資料供應責任

1. 官方市場資料：TWSE／TPEx OpenAPI、經核准的 MIS、MOPS、TAIFEX 與政府行事曆。
2. 外部財經資料：只納入已確認 API、授權、保存與再發布條款的供應者，作 enrichment／fallback，不能默認取代官方來源。
3. 平台清理分類：代號、時間、股／張、上市櫃／興櫃、產業／概念與文本實體對應；產業採具 effective time 與 provenance 的多對多 membership，不以單一產業欄覆蓋歷史。
4. 平台計算推導：權值貢獻、融資風險、目標價共識、聲量／情緒、AI 示警；輸出必須標示算法／模型版本並進 Mart。
5. 排程快取健康：來源成功率、成功數、latency、freshness、休市校正、cache age、fallback 與 schema drift。

### 6.3 來源矩陣

| 領域 | Coverage | Primary | Fallback／限制 |
|---|---|---|---|
| OHLCV、PE/PB | 全市場日頻 | TWSE／TPEx | FinMind；yfinance 僅具名低優先 enrichment |
| 法人／信用／借券／當沖／警示 | 全市場日頻 | TWSE／TPEx | 缺資料標 unavailable，不推算 |
| 月營收／季報 | 全市場摘要、關注股深度 | MOPS | FinMind(MOPS fallback)，三類報表分別抓取與 provenance |
| 公司事件／重大訊息 | 全市場索引、關注股全文或結構化內容 | TWSE／TPEx／MOPS | 更正公告保留新舊版本；RSS／頁面抓取須先確認穩定性與使用條款 |
| Benchmark／期貨宏觀 | 市場級 | 官方 TAIEX／TPEx、TAIFEX、政府行事曆 | 優先報酬指數，否則明示價格指數；美股／費半資料須使用核准 provider |
| 持股級距 | 全市場或關注股，依來源能力 | TDCC／政府開放資料 | bucket 定義與更新頻率待人工核准 |
| 分 K／Tick | 關注股 | 經核准 TWSE／TPEx MIS 或授權行情源 | 必須遵守 rate limit、使用與保存條款；未核准不得排程 |
| 新聞／券商研究／目標價 | 關注股 | 核准授權來源 | CMoney、鉅亨／FactSet、Tiingo、Yahoo／Google 等均為候選；逐一完成授權與 provenance 審查後才能啟用 |
| Podcast／社群文本 | 關注股 | 創作者授權、平台條款允許或合法公開資料 | PTT、Dcard、股市爆料同學會及 Podcast 只列候選；須先完成收集、保存、刪除、PII、引用與再發布政策 |
| Adjusted close | 關注股／需要回測者 | 官方公司行動重建（目標） | yfinance Adj Close 僅具名 enrichment |

任何候選來源在完成 legal／license、robots／API terms、rate limit、retention、PII、可引用範圍與成本核准前，狀態必須是 `candidate`／`blocked`，不得進 production collection 或公開 UI。

未核准的候選來源只保留為 disabled／blocked 設定，不建立 adapter、排程或 Admin 審查 UI。取得外部授權與成本核准後，另開 WBS 定義最小審查證據與實作範圍；只有 `official`／`approved_fallback` 可被啟用。

### 6.4 Supply-chain Intelligence 共用資料模型

Supply-chain Intelligence 延伸既有 Stage → Core → Mart 邊界，不另建資料庫或 runtime。
概念模型至少包含 `supply_chain_node`、`supply_chain_edge`、`company_exposure`、
`leading_indicator_definition`、`leading_indicator_observation`、`supply_chain_signal`
與 `expectation_signal`。Edge 至少保存 upstream／downstream node、product／component、
relationship type、`effective_from`、`effective_to`、confidence、evidence／source 與
provenance；關係不是永久靜態 tag。

Relationship／exposure evidence 使用 `confirmed`、`reported`、`inferred`、`hypothesis`
分類。`inferred`／`hypothesis` 不得冒充 confirmed fact，也不得在 deterministic analysis
中視為同等可信度。重要 relationship、indicator 與 signal 均需保留 as-of／effective
time、provenance、source 與 confidence／quality status。

六個 domain 共用一份 Source Matrix。每個 candidate indicator 至少記錄 node／demand
driver、expected lead metric、lead time、affected companies、exposure interpretation、
PIT availability、source license／API terms／retention、collection／storage cost、
coverage、cadence、provenance 與 approval status；未知欄位標 `Unknown`，未核准來源只
能是 `candidate`／`blocked`，不得建立 production adapter。

## 7. Provenance 與時間

所有重要資料必須記錄：

```yaml
provenance_id: string
source_name: string
source_url: safe_url
dataset: controlled_id
observed_at: datetime
published_at: datetime | null
fetched_at: datetime
content_hash: string
is_fallback: boolean
quality_flags: string[]
quality_details: object
```

- `observed_at`、`published_at`、`fetched_at`、`effective_date` 不可互相替代。
- 財報、事件、新聞遵守 `published_at <= analysis_as_of`。
- 市場觀測以 observed_at 判斷時序；沒有獨立 published_at 不等同業務缺值。
- raw payload、object URI、secret、完整 upstream error 不得出現在一般 API/UI。
- 相同 source + dataset + observed time + hash 重用 provenance；內容或時間改變才新增版本。
- PostgreSQL 的市場資料邊界只保存 control／catalog／execution／publication／audit metadata；另以獨立 schema／role 保存私人交易 ledger。raw payload 與 response cache payload 必須留在 GCS Stage，資料庫只保存 URI、hash、TTL 與狀態。

## 8. Ingestion + Core Job

職責：

- async HTTP、bounded timeout、retry、rate limit、schema drift 偵測。
- 原始回應先寫 Stage，再正規化為 Core。
- 增量抓取、交易日／休市校正、全市場回應批次快取。
- 保存 empty、partial、fallback、stale、rate-limited、unavailable。
- 不用新回應的 null 覆蓋既有有效值。
- 通過 DQ 後發出 `core.dataset.ready.v1`；失敗寫 execution 與 quarantine。
- 每次日頻執行先依交易日曆決定 target trading date，查詢 persisted cache／Core freshness；資料已完整則冪等略過，缺少時才依核准的來源優先序收集。FinMind 只在其 dataset 已核准為 fallback 且官方資料缺漏／不可用時呼叫，不由 Admin page load 或 Mart／Agent 直接呼叫。
- 核准的新聞排程使用獨立 execution、bounded overlap window、dedup、quota 與 retention；新聞先寫 Stage／Core 並完成 PIT／provenance／entity-to-symbol，之後才可供 Mart sentiment 與事件分析。

不得：執行 Agent、產生研報、呼叫 LLM 或更改 publication。

## 6.4 Dataset Coverage Inventory 與 Research Context 資料邊界（Planned）

新增 `Dataset Coverage Inventory / Gap Matrix` 作為新 provider 評估前的必要
planning evidence。每個 dataset family 記錄 source、adapter／Core publication evidence、
market／symbol／time coverage、cadence、freshness、PIT history、provenance、license／
approval 與 gap；狀態僅使用 `Implemented | Partial | Unknown | Missing | Candidate |
Blocked`。只有 repository 中可驗證的 adapter、Core publication 與 acceptance evidence
才可標為 `Implemented`；規格列出欄位不等於已實作。新 source 仍須通過
既有 Data Source admission／approval rule。

盤點至少包含 OHLCV、valuation、institutional、margin／financing、securities
lending／short-related、day-trade／market activity、monthly revenue、quarterly financials、
corporate events、benchmark、sector／industry benchmark 與 macro／market-regime inputs。
目前 code 僅證明 bounded `janus-core` resource allowlist 包含 `ohlcv`、`valuation`、
`institutional`、`financials`、`events`、`market-activity`、`benchmark`；這不證明
各市場、欄位、日期與 Core publication 已完整，其實際 coverage 待 inventory 驗證。

Core 保存可重算輸入；Mart 須 deterministic 產生 MA 5／10／20、recent
high／low、ATR、RVOL、volume trend、法人 3／5／10 日聚合、margin change、
relative strength、benchmark-relative return、price／volume state、已定義的
breakout／trend state、已核准籌碼指標，以及 Gate D 後的 supply-chain indicators。
formula、window、null handling、trading-calendar semantics、revision 與 PIT semantics
必須在 implementation contract 中 deterministic 定義；LLM 僅解釋結果。

Private Research State 優先重用 notes revisions、artifact／index、Private Core／Mart
與 owner isolation；儲存責任先由 semantic contract 決定，不預設新 PostgreSQL
table。現有 investment profile 有 risk tolerance、horizon、primary goal 與 minimum cash，
但 concentration boundary／mandate 為 **Schema Extension Candidate**。ResearchContext 只組合
已持久化、同一 `analysis_as_of` 可見的 bounded snapshots，並顯式保留
freshness、missing／stale／partial、fallback、provenance 與 PIT status；禁止把不同
日期的 latest 拼成假的同一時點。
