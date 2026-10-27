# Janus SPEC — 儲存、資料供應與 Ingestion

> **2026-10-24 研究精簡決策優先**：本文涉及獨立資料稽核、逐來源補證、全歷史 PIT／精確時間校準、例行週月稽核及自然驗收等待的要求已取消，不再是待辦或發布前置。依 [研究精簡政策](research-simplification.md)，保留必要日期／單位、基本防洩漏與操作安全；歷史證據不改判 PASS。


**2026-10-13 最新範圍：**市場資料、screening、研究母體、搜尋／新增關注資格全部改為上市／上櫃全部個股，必要資料缺失率 TWSE 上市 ≤10%、TPEx 上櫃 ≤30%（均含邊界）分市場通過；不再維持前 500 母體。所有業務批次由 Cloud Scheduler 總控，GitHub Actions 只保留備份清理定時排程。實作與 runtime 切換狀態見 status／operations，不以本契約推定完成。 本文舊 500 範圍已被取代，歷史識別字／證據保留；完整 [新契約](../spec/full-market-batch-policy.md)。

> **2026-10-19 治理覆蓋註記**：公開 Core／Mart Iceberg **只保留 current snapshot**，不再以 named/24h/研究引用保護歷史 snapshot；所以舊「immutable snapshot 支援歷史完整 PIT 重播」不能再當現況。正式 Core／Mart 的受控數值及來源繼續可追溯；**五分析師新版研究資料不經本 Stage/Core/Ingestion 必經鏈**，改由 [GAS→Drive 每月ZIP→Colab](research-collection-gas-drive-colab.md) 獨立保存 hash/manifest/quality。新增持股／關注股補收採既有去識別化 demand＋每日08:30兜底；第三方直接補資料依 PROJECT_RULES §1.7。路由見 [資料治理入口](data-governance.md)、[補資料](../runbook-data-supplement.md) 與 [Retention](retention-governance.md)。

## 5. 湖倉分層

| 層 | 格式 | 責任 | 寫入者 | 讀取者 |
|---|---|---|---|---|
| Stage／Bronze | 原始 JSON、CSV、官方 MOPS 財報 HTML、受控物件 | 保存來源原貌、request metadata、hash | ingestion-core | ingestion-core、治理稽核 |
| Core／Silver | Iceberg／Parquet | 正規化、去重、單位、日期、null、PIT、provenance、文本與股票代號關聯 | ingestion-core／DuckDB／PyIceberg | intelligence-mart、read-only query runtime |
| Mart／Gold | Iceberg／Parquet | 特徵、角色輸出、聚合、研報、評估 | intelligence-mart | FastAPI、User、Admin |
| Private control／ledger | PostgreSQL append-only events／bounded index | 使用者手動交易、修正、冪等、所有權、目前關注狀態、私人 artifact index 與 pipeline checkpoint | private API | 該使用者、private pipeline |
| Public Serving Projection | PostgreSQL `control.*_serving_recent` | 低延遲查詢快取（日頻 OHLCV、估值、EPS、月營收）；採 Tier-1（2年）與 Tier-2（120天）分級淘汰與容量防護 | FastAPI Public Runtime | User App 圖表與個股資訊（詳見 [歷史種子與 Serving 契約](history-seed-pipeline.md)） |
| Private Core／Mart | 加密受限 Iceberg／Parquet | 交易正規化、筆記 revision、關注歷史、AI messages／context／citations、庫存與損益 | private pipeline／chat persistence | 該使用者的 API，不得公開 |

規則：

- 不可把所有 0 一律轉成 null；須依欄位語意處理。
- 單日漲跌超過 11% 不可直接刪除；先檢查市場限制、除權息、公司行動與跨源差異。
- Core／Mart 的 current snapshot 保證當次合法讀取；需要重播研究／歷史 PIT 須保有經驗證的 frozen/versioned 輸入與 availability/provenance，已清除的舊 snapshot 不保證可讀。
- UI 不得直接讀 Stage 或未發布 Core。
- Core 保存可重算的來源資料與 deterministic 標準化結果；NER 關聯必須保留模型／規則版本與 evidence。情緒分數、AI 示警、動態權重與投資判讀屬 Mart，不得回寫成來源事實。
- Public 與 Private namespace、bucket prefix、Iceberg table、service index、IAM 與 retention 必須隔離；不得以只靠 Flutter 篩選來保護使用者交易資料。
- 交易金額、股數、手續費、稅與損益使用固定精度 decimal，不使用 binary floating point。更正交易以 reversal／replacement event 留痕，不就地改寫稽核歷史。
- 筆記使用單一 append-only revision model，可獨立存在或連結 symbol／trade event。歷史 Janus assistant data 與已套用 schema 保留；不代表由 Janus 繼續寫入或自動搬移至 omniAgent。omniAgent conversation storage／credentials 由其自身規格管理，不進 Janus Iceberg。

PostgreSQL append-only private transaction ledger 是私人交易事實的 OLTP source of
truth；Private Core／Mart 是 derived／normalized result，不是 ledger backup。Dev
Pilot 使用已人工核准的 bounded logical backup：`PostgreSQL logical backup
(pg_dump) → restricted Private GCS`，不改變 ledger semantics、reversal／replacement
history、Private Iceberg pipeline 或 public／private isolation。此例外不授權 PD
snapshot、Cloud SQL、HA、replica、second PostgreSQL VM 或無界 retention。

## 6. 資料供應模型與正式資料來源

各因子的實際收錄母體、關注／持股深度、資料筆數估算與 retention/歷史保護對照，見 [因子收錄與保存矩陣](factor-coverage-retention-ledger.md)。實測 row count 不能用估計替代。

### 6.1 雙軌 coverage

| 軌道 | 對象 | 預設頻率 | 必要資料 | 用途 |
|---|---|---|---|---|
| 全上市櫃市場資訊 | 官方有效名冊全部上市／上櫃個股；排名來源每日仍須各市場一次全市場批次抓取 | 每日名冊版本、日頻行情 | 日 OHLCV、PE/PB、法人、融資券／借券／當沖、基本面摘要、benchmark | 異動偵測、流動性檢查、每日 screening |
| 個人關注股深度追蹤 | authenticated users 的 active watchlist 所形成之去識別化 symbol 聯集；MVP 最多 50 個 distinct symbols | 日頻加上經核准的分 K／Tick、事件與文本 | 深度財報、公司行動／重大訊息、新聞與核准另類資料 | 個人關注、深度特徵、風險分析、PIT 回測與研究報告 |

- `coverage_tier`、去識別化深度追蹤 membership、effective time、collection cadence 與授權狀態必須持久化並可稽核；關注異動不得改寫歷史 membership，Admin 不得看到使用者與 symbol 的對應。
- 高頻、文本與另類資料不得因全市場 collection 自動擴張；MVP 超過 50 個 active distinct symbols 或提高抓取頻率須拒絕並另行評估來源限制、Cloud Run/GCS 成本與授權。此上限是營運護欄，不是「50 大」產品功能。
- collection 與 analysis 分離；進入深度追蹤只代表有使用者關注需求且可收集相應資料，不代表平台推薦、可發布或可自動下單。
- 官方名冊按生效日更新，全市場必需資料缺失率按 TWSE ≤10%、TPEx ≤30% 分市場通過 coverage；來源失敗保留最後有效版本並明示 stale。新加入 watchlist 可選全上市櫃個股；已持有股票即使離榜，也應沿源頭 → Stage → Core → Private Mart 補行情，不用 UI 假價。

### 6.2 五層資料供應責任

**資料補收最新決策（2026-10-18）**：依 [PROJECT_RULES §1.7](../PROJECT_RULES.md)，可直接使用 Yahoo 等第三方已整理的真實歷史資料，不必先窮盡官方來源。第三方單季EPS可直接引用，不要求另找官方股數分母；保留第三方身分、URL、取得時間、期別、單位與每股口徑，經既有驗證後沿Stage→Core→serving發布。本節及下表的官方優先／候選逐源人工審查限制，對使用者已授權的無新增費用公開資料補收由此決策取代；實際adapter、登錄與runtime支援仍需驗證，不因文件核准假稱已上線。

1. 官方市場資料：TWSE／TPEx OpenAPI、經核准的 MIS、MOPS、TAIFEX 與政府行事曆。
2. 外部財經資料：可用於補收／enrichment／fallback；已授權補收可直接選用公開可讀的第三方數值，不以官方缺漏或官方查找完成為前提。保留實際來源、取得方式與口徑，不冒稱官方；新增費用與權限仍依專案規則。
3. 平台清理分類：代號、時間、股／張、上市櫃／興櫃、產業／概念與文本實體對應；產業採具 effective time 與 provenance 的多對多 membership，不以單一產業欄覆蓋歷史。
4. 平台計算推導：權值貢獻、融資風險、目標價共識、聲量／情緒、AI 示警；輸出必須標示算法／模型版本並進 Mart。
5. 排程快取健康：來源成功率、成功數、latency、freshness、休市校正、cache age、fallback 與 schema drift。

### 6.3 來源矩陣

| 領域 | Coverage | Primary | Fallback／限制 |
|---|---|---|---|
| OHLCV、PE/PB | 全上市櫃個股 日頻；持股／關注股依缺口定向補收 | 全市場既有 TWSE／TPEx 批次；定向補收可直接選 Yahoo／FinMind | 不要求官方先行；保存供應者身分、還原／每股口徑。定向補收不得擴成全市場逐檔盲抓 |
| 法人／信用／借券／當沖／警示 | 全上市櫃個股 日頻，依已核准市場批次來源能力 | TWSE／TPEx | 缺資料標 unavailable，不推算或逐檔放大 |
| 月營收／季報 | 全上市櫃個股 摘要、關注股深度；每次補收範圍依TODO | MOPS或可取得的第三方來源 | Yahoo股市、FinMind等；第三方單季EPS可直接補收，區分供應者口徑與官方申報，保存provenance |
| 公司事件／重大訊息 | 全上市櫃個股 索引、關注股全文或結構化內容 | TWSE／TPEx／MOPS | 更正公告保留新舊版本；RSS／頁面抓取須先確認穩定性與使用條款 |
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
- `WBS-3-DATA-SUPPLEMENT-V1` 依使用者 2026-10-02「資料優先」決策，允許已核對的月營收／財報歷史數值供目前研究。權威發布時間或原始數值版次未證明時保留 unknown；真正收到的版本以 receipt availability、原始 hash、公司／期別／單位／口徑留痕。該 receipt 只證明 Janus 自此時持有此版本，不能證明歷史市場首次可得性，不能倒填取得前的 PIT 回測。這是資料用途契約；第一版官方資料接線與真實 dev 驗收已於 2026-10-03 完成，見 [結案證據](../archive/wbs-3-data-supplement-v1-completed-2026-10-03.md)。已接受的歷史 PIT／版次限制仍保留。
- 財報版本 identity 使用 `version_at`，與可為 null 的 `published_at` 分開；未知發布時間時必須保留可證明且有時區的 `availability_at`。同一來源、公司、期別、statement、metric 的數值／單位／口徑未變可重用；更正值以新版本保存。同版次出現不同數值不得覆寫。舊表新增欄位與新資料寫入須保留既有快照；此第一版實作已完成 dev deployment／live 驗收；證據見上述結案文件。
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
