# Janus／OmniForge 資料治理 C1-A 準備與 C0-Live 補驗並行計畫｜2026-10-23

> **執行範圍：治理文件與既有證據的唯讀分析。** 這份文件是 C1-A 的可操作準備清單，**不是 C1-B 清掃許可證**；本輪未使用 PostgreSQL arbitrary SELECT、Iceberg live catalog、Cloud Scheduler/Cloud Run live list、GCS 本日 object inventory；未修改應用程式、排程、模型或任何資料。見 [C0 原始盤點及歷史 Live 收據](data-governance-c0-2026-10-23.md)。
>
> **狀態：C1-A 文件／候選與條件 = PREPARED；C0-Live = PARTIAL/BLOCKED；C1-B = NOT_AUTHORIZED / NOT_READY；批准實刪 Table/Column/Object = 0。** 本文中的「0」只表示經核准可刪清單為空，**不是**實際系統沒有冗餘。環境限定既有 dev parallel-live，GitHub main；不可自行把研究材料認定 production canonical。

## 1. 證據與版本

| 對象 | 唯讀證據 | 信心／限制 |
|---|---|---|
| 工程政策 | [PROJECT_RULES](../PROJECT_RULES.md) §1.6、§1.8、§1.12 | CODE_RULE；Stage 48h、Iceberg current-only、Risk rollback 狀態須遵守當時和後續實際讀回 |
| Iceberg Core 定義 | [DuckDBIcebergCore](../../packages/duckdb_query/iceberg.py) 的 \`IDENTIFIERS\`、\`PARTITIONS\` | CODE_CONFIRMED；九個定義不等於 Live 九張 |
| Mart 歷史 handle | [storage.py](../../jobs/intelligence-mart/intelligence_mart/storage.py) 的 \`MART_TABLES\`、\`MartMaintenanceStore\` | CODE_CONFIRMED；十一個定義不等於 Live 十一張 |
| Mart 可達維護路徑 | [Mart retention](../../jobs/intelligence-mart/intelligence_mart/retention.py) \`run()\`、\`table_exists\`、\`table.delete(expired)\` | CODE_CONFIRMED：現存表可能受 retention 寫入；無舊 analysis writer **不代表表可 DROP** |
| PG 發布契約 | [Migration 018](../../infra/postgres/migrations/018_mart_publication.sql) 中 \`publication.mart_report_index.table_identifier\` = \`mart.mart_scoped_analysis_v1\` 的 CHECK | CODE_CONFIRMED、LIVE migration applied UNKNOWN；這是**硬依賴候選**，必須禁止盲刪 |
| 雙寫路徑 | [ingestion_core.__main__](../../jobs/ingestion-core/ingestion_core/__main__.py) 約 508 與 540–584 行 | CODE_CONFIRMED：先寫 market-volume 全官方批次，投影並 DQ 後再寫 ohlcv |
| Core 被讀取 | [risk_inputs.py](../../jobs/intelligence-mart/intelligence_mart/risk_inputs.py) \`core.ohlcv_v1\`、[market_screening.py](../../jobs/intelligence-mart/intelligence_mart/market_screening.py) \`core.ohlcv_v1/core.benchmark_v1/core.valuation_v1\` | CODE_CONFIRMED；但 30 日 runtime usage 未查 |
| 四模型 X contract | [janus_precision.py](../../research/chatgpt/janus_precision.py) \`VERSION='3.8.2'\` | CODE_CONFIRMED：8+11+10+5=34 席位、27 unique；非四模型皆已啟用的證據 |
| GCS 歷史觀測 | [FinOps #39552667601](https://github.com/tommylin15/janus-omniforge/actions/runs/39552667601)，2026-10-21 05:59:59 UTC，job 119065218667 | HISTORICAL_RUNTIME_RECEIPT：6 buckets、7156 objects、782661499 current bytes + 2749618 noncurrent bytes，**不得當成今日值** |
| Risk 變更歷史 | [rollback #39938087196](https://github.com/tommylin15/janus-omniforge/actions/runs/39938087196)，2026-10-23 10:19 UTC | HISTORICAL_RUNTIME_RECEIPT：GCS / PG DETERMINISTIC 讀回 PASS；早期 ACTIVE 不能覆蓋較新回滾 |

本次檢查時 GitHub main 基準 SHA = \`7b9316d5e39d05776351248026041ff6c17c1f4a\`（C0 補驗收據 commit）；正式操作前仍須重新固定當前 HEAD SHA、catalog metadata location／snapshot、執行時間及有權唯讀的帳號角色。**C1-A 是一份規劃，非 Live 當下的簽核記錄。**

## 2. C1-A 候選決策矩陣（不執行物理清掃）

| ID / 優先 | 實體與目前分類 | 已知 writer / reader / dependency | 尚缺的 C0-Live 證據 | 如獲准進 C1-B 的最小策略／回復 | 此輪 |
|---|---|---|---|---|---|
| C1A-01 / P0 | \`core.market_volume_v1\`、\`core.ohlcv_v1\`：CONSOLIDATE_CANDIDATE | \`ingestion_core.__main__\` 同一 market-volume 批次兩階段寫；\`risk_inputs\`、\`market_screening\` 依賴 OHLCV；PG serving projection 有後續讀者 | 兩表實存、schema、鍵覆蓋、數值與單位、官方全市場 vs DQ accepted 子集、來源/PIT、PG/API/研究讀者、增量性能 | **先比對，後提出兼容 reader / writer 冗餘計算優化**；保留市場全量與 DQ 差異，另備可回切原 writer 的 git/release，決不先 DROP | BLOCKED_FOR_PHYSICAL_CLEANUP |
| C1A-02 / P0 | \`mart.mart_scoped_analysis_v1\`：KEEP_DEPENDENCY_PENDING | MartMaintenanceStore/retention；Migration 018 \`publication.mart_report_index.table_identifier\` CHECK 固定此值，舊 publication 函式與報表可能引用 | catalog exist/snapshot、PG index 實際列數/約束是否套用、API/舊 fallback、發布保留/owner refs | 若全可替換才做**另案**有遷移/資料重建的相容層；舊表先保留至 reader、index 相容 PASS，拒絕直接 DROP | PROTECTED_GATE |
| C1A-03 / P1 | 其餘十個 \`mart.mart_*_v1\`：RETIRE_CANDIDATE | \`MartMaintenanceStore\` 名稱維護；\`retention.py\` 按存在性掃表，可能執行 row-level retention，不能視為無使用 | 逐張實存+快照+行數、90日規則/檔案引用、30日 reader/writer、舊 API/研究依賴 | \`ABSENT\` 只修文件；存在但零讀者仍需 snapshot、可恢復資料副本/重建證據、保留期一致性及停寫 gate，才可另案提退役 | UNKNOWN |
| C1A-04 / P1 | 同名／同義因子：ALIAS_CANDIDATE | \`factor_factory_v1.py\` 中有直接公式關係；\`janus_precision.py\` 固定 X schema | 每個模型版本、input order、單位、時點、window、缺值策略與逐值 parity，是否正式服務使用 | 只做 alias mapping/serializer 與版本遷移，保留舊 schema/replay 入口；無並存與回切時不 DROP | NO_COLUMN_DROP |
| C1A-05 / P1 | PG serving / publication / control：KEEP_UNTIL_EVIDENCED | \`publication.mart_report_index\`、outbox、\`control.executions\`、\`catalog.iceberg_tables\` 等契約各不相同 | 真實 \`pg_catalog\` 表欄、index/FK、migration applied、最近使用、service queries、privileges | 控制與發布治理表先保留；不存在時修文件，確證 stale table 才另案審查 | UNKNOWN |
| C1A-06 / P2 | 舊 JSON writer / notebook / 一次性入口：DOCUMENT_ONLY_CANDIDATE | GitHub 研究/舊 entrypoint，正式端可能間接引用 | main reachability、Active Workflow/Colab 版本與產物、replay 契約 | 可先統一說明與標 deprecated；有能回切的 source SHA 之後才另案刪碼 | NO_CODE_CHANGE |
| C1A-07 / P2 | Stage TTL / Iceberg orphan：KEEP_EXISTING_POLICY | \`PROJECT_RULES.md\`、\`ingestion_core.retention\`、現有 FinOps/maintenance | 今日 objects 的 48h metadata、有效租約 \`claimed_until>UTC now\`、generation、orphan current ref | 既有 48h Stage policy、週 Core/Mart 維護**不變**；僅計畫 future dry-run，不與 C1 table DROP 合併 | NO_CLEANUP |
| C1A-08 / 保護 | Private Owner、Risk Registry/rollback、research frozen、RAW/Y/PIT/PROVENANCE：KEEP_EXCLUDED | Owner/ledger、模型來源、研究封存、published & available timestamps | 僅需最小必要 metadata 依賴以避免誤刪，不讀私人資料內容 | 不納入 C1-B 刪除候選；任何另案需明確範圍授權 | PROTECTED |

**特殊注意：** \`mart.mart_scoped_analysis_v1\` 在 \`018_mart_publication.sql\` 出現 **PG CHECK constraint**，即使最終 Iceberg catalog 不存在，也不能直接把此 migration 中的名稱引用誤認為「要 DROP 的 PG table」；分別檢查 catalog 真實性、當前 migration 運行版本與歷史 publication contract。

## 3. 11 個歷史 Mart handle 逐張檢查清單

下表皆僅 \`CODE_CONFIRMED\`，\`LIVE_EXISTS=UNKNOWN\`、\`LIVE_ROW_COUNT=UNKNOWN\`、\`LAST_READER=UNKNOWN\`。全數可能經現有 \`MartMaintenanceStore\`/retention 讀取或維護；不可單因沒有 legacy analysis writer 就標 \`ABSENT\`。

| Iceberg identifier | 優先排除的下游/發布依賴 | 暫判 |
|---|---|---|
| \`mart.mart_screening_signals_v1\` | screening artifact、API fallback、PG publication | RETIRE_CANDIDATE |
| \`mart.mart_core_alpha_v1\` | alpha 研究／舊評分與 schema contract | RETIRE_CANDIDATE |
| \`mart.mart_risk_portfolio_v1\` | Risk/Owner 私有安全邊界、舊讀者 | RETIRE_CANDIDATE / OWNER_PROTECTED |
| \`mart.mart_alternative_sentiment_v1\` | 事件、外部 sentiment、研究參考 | RETIRE_CANDIDATE |
| \`mart.mart_scoped_analysis_v1\` | **PG \`publication.mart_report_index\` CHECK**、outbox/報表、snapshot | **KEEP_DEPENDENCY_PENDING** |
| \`mart.mart_market_regime_daily_v1\` | regime 模型/市場頁或研究 | RETIRE_CANDIDATE |
| \`mart.mart_sector_rotation_daily_v1\` | 產業/輪動資料讀者 | RETIRE_CANDIDATE |
| \`mart.mart_topic_trends_daily_v1\` | 主題趨勢顯示/研究 | RETIRE_CANDIDATE |
| \`mart.mart_candidate_health_v1\` | candidate 品質、管理後台 | RETIRE_CANDIDATE |
| \`mart.mart_daily_brief_v1\` | 盤前/盤後簡報、歷史發布索引 | RETIRE_CANDIDATE |
| \`mart.mart_llm_narratives_v1\` | 報告、歷史內容及舊引用 | RETIRE_CANDIDATE |

**不存在 ≠ 無權限 / 讀取失敗。** catalog 回應查無及 PyIceberg API 正常時才可標 \`ABSENT\`；permission denied／connection failure／schema mismatch 仍 \`UNKNOWN\`。任何 ABSENT 只允許清整文件／候選清單，不新增實體 DROP 工作。

## 4. 因子別名不是物理欄位去重

研究 contract \`janus_precision.py VERSION=3.8.2\` 四個 X：

- Risk 8：\`vol20,vol60,drawdown60,abs_return5,volume_ratio20,atr14_pct,abs_overnight_gap5,log_turnover20\`。
- Quant 11：\`ret5,ret20,ret60,ma20_distance,ma60_distance,vol20,vol60,drawdown60,volume_ratio20,log_turnover20,market_code\`。
- Fundamental 10：\`yoy_m,yoy_3m,yoy_change1,growth_acceleration,mom_m,log_revenue,season_sin,season_cos,revenue_vol3,market_code\`。
- Valuation 5：\`roe,debt_ratio,log_total_assets,revenue_yoy,market_code\`。

\`34=8+11+10+5\` 是 **model-role ordered slots**，\`27\` 是名稱去重數，不代表剩下七個可刪欄位；同一名稱跨模型讀者需要版本、時點與運算一致性。

| 研究定義／候選 | 主線程式能證明的關係 | C1-A 對應措施 |
|---|---|---|
| \`dollar_liquidity\` vs \`turnover\` | \`factor_factory_v1.build_ohlcv_panel\` 直接賦值 \`dollar_liquidity=turnover\`（同個 research panel） | \`CODE_FORMULA_ALIAS\`，但仍不得假設跨原始表、PG 或量綱相同 |
| \`mean_reversion5\` vs \`ret5\` | \`mean_reversion5=-ret5\` | \`CODE_DERIVED_NEGATION\`，非相等；不能刪研究回測/模型變數 |
| \`turnover_log20\` vs \`log_turnover20\` | 前者在 factory 中是 \`log1p(turnover_mean20)\`；後者為 Precision 模型指定 X | \`POSSIBLE_SEMANTIC_ALIAS\`，未證實 log 定義、daily vs rolling、PIT 與數值完全相同 |
| \`revenue_yoy\` vs \`revenue_growth_12m\` | 同個研究 monthly panel 中直接指派；Precision 另有 \`yoy_m\` | \`CODE_FORMULA_ALIAS_WITHIN_PANEL\`；\`yoy_m\` 不可未檢查口徑直接等同 |
| \`drawdown60\` vs \`drawdown_from_high60\` | 命名不同且未完成相同時點／公式讀回 | \`POSSIBLE_ALIAS_NOT_VERIFIED\` |
| \`vol20/vol60\` vs \`realized_vol20/60\` | 波動年化、報酬定義、窗口 min_periods 需逐一驗證 | \`NOT_PROVEN_EQUIVALENT\` |

**不可碰的資料層：** \`RAW\` 官方/開放來源回應及交易日、\`LABEL_Y\` 前瞻標籤成熟日、\`FEATURE_CANDIDATE\`、\`CONTEXT\` 市場/產業、\`QUALITY\` 缺值與 cohort、\`PIT\` 公告/取得/觀察/有效時間、\`PROVENANCE\` source/manifest/hash/snapshot，以及 valuation 同日 PE/PB 作 label 時不得反向作 X。研究 CURRENT 非 GCP Core canonical；current Iceberg snapshots 不應被當可重建歷史研究輸入的獨立備份。

## 5. 並行工作：C0-Live 唯讀補驗的精確查詢與判定

| Track / ID | 查詢位置與限制 | 要產出的 receipt | 優先 |
|---|---|---|---|
| **L01-PG** | 現有 dev PostgreSQL 的 \`information_schema\` / \`pg_catalog\`；\`control.schema_migrations\` 查 metadata only；\`BEGIN READ ONLY\` + \`statement_timeout\`；私人 schema 只取欄位/constraint | UTC、current role、真正 schemas/tables/views、columns/types、PK/FK/index、migration applied、\`publication.mart_report_index\` 的 CHECK 與有限聚合 | P0 |
| **L02-CATALOG** | \`catalog.iceberg_tables\` 使用 \`catalog_name='janus'\`、\`table_namespace IN ('core','mart')\`，只讀 \`table_name,metadata_location,previous_metadata_location\`；PyIceberg 個表 bounded metadata | 每張表 \`LIVE_EXISTS\`、schema/spec/current snapshot、row count 統計的 evidence source、schema diff、可能權限錯誤 | P0 |
| **L03-READER** | 檢視最新 main 的 API、Mart、research/model code 及既有 Cloud Run/Cloud Scheduler \`list/describe\`（去除 secrets），最近30天 \`control.batch_occurrences/executions\` 的有界彙總 | table→writer→reader→API/UI/Job、最後證據、scheduled vs actually run、只讀查詢時間與 git SHA | P0 |
| **L04-GCS** | 限已確認 dev 六桶，metadata-only 列舉前綴、version/generation/updated/size、Stage 的 48h + valid lease join；不 GET private rows | prefix/objects/bytes、Stage 候選 + held-by-active-lease、manifest/current metadata refs；不把 age 7d 充當 TTL 48h | P1 |
| **L05-X** | 核對 pin 住的研究 release manifest / Core snapshot / 實際 X column contract；只做必要有界數量/缺值/單位檢查 | 34 slots／27 names、schema order、model-input nonnull 與 PIT 隔離、X/Y/context/quality/provenance 資產清冊 | P1 |

**已核對現有只讀工具而不觸發：** [\`.github/workflows/finops-dev.yml\`](../../.github/workflows/finops-dev.yml) 有 \`workflow_dispatch\` 的 \`gcs-storage-footprint\`、\`core-reference-audit\`、\`runtime-references\`、\`iceberg-readback\` 等工作選項；其具體 SQL/Job 行為以主線 script 和 \`ops/finops-*.json\` request 為準，其中某些會執行既有 dev Job 以取得有界 reference。**本輪未 dispatch 工作流**；不得只因工作流名稱含 \`readback\` 就認定無額外變更、沒有成本，或保證能拿到完整 PG catalog。當前工具只提供 GitHub 收據讀取，無直接 PostgreSQL/GCS/Scheduler generic read API；缺資料者原樣 \`BLOCKED\`。

可直接用於下一個有權唯讀環境的 metadata SQL **模板**（**未執行**；使用者/連線與 schema 以當前實際環境為準；每段必須設有小時間限制）：

\`\`\`sql
BEGIN READ ONLY;
SET LOCAL statement_timeout = '15s';
SELECT current_database() AS db, current_user AS reader,
       clock_timestamp() AS receipt_utc;
SELECT table_schema, table_name, table_type
  FROM information_schema.tables
 WHERE table_schema IN ('catalog','core','mart','control','publication','private')
 ORDER BY table_schema, table_name;
SELECT table_schema, table_name, column_name, data_type,
       ordinal_position, is_nullable
  FROM information_schema.columns
 WHERE table_schema IN ('catalog','core','mart','control','publication','private')
 ORDER BY table_schema,table_name,ordinal_position;
SELECT catalog_name,table_namespace,table_name,metadata_location,
       previous_metadata_location
  FROM catalog.iceberg_tables
 WHERE catalog_name='janus' AND table_namespace IN ('core','mart')
 ORDER BY table_namespace,table_name;
COMMIT;
\`\`\`

注意 \`information_schema\` 可能因權限只回傳可見欄位，**空集合並不一定代表 ABSENT**；Iceberg catalog rows 不等於 DuckDB 可讀、snapshot 有效或所有 data files 尚在。PG key/index 應另查 \`pg_catalog\`、最新 migrations；當遇到 permission/role 或 catalog 名稱偏差，要記錄 \`UNAUTHORIZED\`、\`SCHEMA_MISMATCH\` 或 \`UNKNOWN\`，而非一律 0。

## 6. C1-B 入場 gate（目前全部未全部滿足）

對**每一個**候選（不是對整個專案一次核准）需要：

1. **存在性 gate：** Live PG/catalog/manifest 已讀回；\`ABSENT\` 只修文件；有表的現行元資料完整。
2. **依賴 gate：** main writer/reader + 已部署 Job/Service/排程 + 最近30日有界執行證據；舊版 GCS manifest、PG publication/outbox、回滾/研究必要 references 得到保護；Unknown reader 一律阻擋 DROP。
3. **資料契約 gate：** 同鍵/資料日期、數值/單位/欄位差異與 PIT provenance、feature version/ordered schema；若本來是不同用途絕不能強制整併。
4. **可回復 gate：** 受影響表/資料的**獨立可讀**備份或 rebuild receipt、owner、確定版本/SQL/物件 generation、回切流程與驗收 SQL；Iceberg 舊 snapshot 不被默認是可靠備份。
5. **變更 gate：** 單資產、限定範圍、先相容讀/可逆停寫、後監測、最後評估物理清理。大批不可逆真實資料刪除、缺乏回復路徑者另請使用者明確授權。執行前核對最新 SHA 與 drift。
6. **驗收 gate：** 前後表及欄位、reader/API、模型 34-slot contract、月度研究封存、GCS generation/bytes、PG migration/交易與排程讀回都具實際 receipt；partial 不包裝成 full。

目前 C1-B 實體 **DROP/DELETE/TRUNCATE/停排程/停 writer 核准 = 0**。C1-A 允許的是文件性 \`KEEP\`、\`CONSOLIDATE_CANDIDATE\`、\`RETIRE_CANDIDATE\`、\`ALIAS_CANDIDATE\`、\`ABSENT\`（需 Live 證實）、\`RESEARCH\`、\`UNKNOWN\` 的持續分流。

## 7. 後續兩條工作流與停止條件

**路線 A（C1-A 可直接推進的文件工作）**
A1. 將 Mart 11 張、market-volume/ohlcv、因子 alias 逐項建立 owner、source SHA、static dependency、現場需要的 query、rollback 檢查項。
A2. 收到一項 Live receipt 就只更新**該資產**的狀態；標示 \`CODE_CONFIRMED/HISTORICAL_RUNTIME_RECEIPT/LIVE_CONFIRMED/UNKNOWN\`，不要集體升級。
A3. 對真正 \`ABSENT\` 的文字敘述提出文件修正；對仍存在且不再使用者產出 C1-B 提案，不執行實刪。

**路線 B（C0-Live 補驗，待現有安全唯讀執行通道可用）**
B1. 先 L01 PG schema/migrations、L02 Iceberg catalog/snapshots，再 L03 讀者與最近30日 Scheduler/Job。
B2. 再 L04 今日 GCS generation/prefix 和 Stage lease、L05 四模型有界資料契約。
B3. 每次將 receipt 連結、UTC、角色、安全範圍、Git SHA 與差異/錯誤補入 [C0](data-governance-c0-2026-10-23.md)，同步此 C1-A 候選矩陣。

**停止條件：** 若無可行唯讀通道，標 \`BLOCKED\` 而不是創建部署/改 IAM/修改 request 去誘發含寫入的 Job；本 C1-A 作業完成後不自動開 C1-B。後續 **B1 基準線**須以實際清掃是否發生分開標註：若尚未 C1-B，最多稱「清掃前 Live baseline」，不能聲稱「清掃後驗收」。

## 8. 需補但未冒充完成的缺口（下次 AI 指令）

\`GAP-L01\` dev PG arbitrary metadata SELECT；\`GAP-L02\` Iceberg catalog + metadata、table-level snapshot/fields；\`GAP-L03\` Scheduler/Cloud Run live list 及30日 execution 彙總；\`GAP-L04\` 今日 GCS object metadata/48h lease；\`GAP-L05\` pinned model release 的 X/Y/PIT/quality/provenance 對應；\`GAP-XLSX\` 原始治理 Excel Sheet 11–14 仍未有直讀證據；\`GAP-DRIVE\` 既有 Markdown Drive 原文未能以目前 connector 原位 raw bytes 更新（須保留同檔評論串，不能說原文已改）。

**交接給下一位 AI 的單一指示：**「在不變更任何 live 資料、程式、排程、身份權限和 runtime 的前提下，先讀本文件與 C0 續查報告；利用**已授權的現有只讀** PG/Iceberg/GCS/Scheduler 查詢收據逐項消除 GAP-L01～L05，按 C1A-01～08 每筆補寫 current existence、欄位、writer/reader、最近使用與獨立回復證據。只更新 GitHub main 與 janusChatGPT 的治理文件，對未能查到的值如實維持 UNKNOWN/BLOCKED。不得將此工作自動升級成 C1-B 刪表／停寫或 B1 清掃後基準線。」**


---

## 9. C1-A 候選逐項證據升級：實際 dev Core 歷史收據（非當前 Live）

**讀取時間界線：** 已找到 2026-10-17 與 10-18 的 [Core 唯讀 Census #38997408284](https://github.com/tommylin15/janus-omniforge/actions/runs/38997408284)、[#39083283620](https://github.com/tommylin15/janus-omniforge/actions/runs/39083283620)；兩次皆為 dev Jobs \`feature_readiness_inventory\` 的真實 JSON 讀回，而非靜態模型。完整當時九張表 schema、snapshot、行數、分區與 delta 已記錄於 [C0 §14](data-governance-c0-2026-10-23.md)。**沒有 2026-10-23 現時 PG/Iceberg 全清冊，本輪不能宣布 C0-Live PASS。**

| C1-A 候選 | 比原先 CODE_ONLY 更強的新證據（2026-10-18 UTC） | 證據狀態升級 | 目前決策 |
|---|---|---|---|
| **C1A-01 \`market_volume\` vs \`ohlcv\`** | 曾實存兩張 Iceberg Core 表，分別 39,699 / 111,929 個 snapshot-summary records；其 \`stock_name\` vs \`change_percent\` 差異、最早月分區 2026-09 vs 2023-11 明確不同，且在主線有 DQ 後二階段 writer | \`HISTORICAL_LIVE_EXISTS_AND_DIFFERENT_SHAPES\`；\`CURRENT_LIVE_UNKNOWN\` | **不得整表合併/刪除**。僅可規劃個別同欄位來源比對和可逆 reader 優化 |
| **C1A-02 \`mart_scoped_analysis\`** | PG migration 018 明訂 publication index \`table_identifier\` 名稱限制，Retention 維護入口仍列此表；無 10/23 PG applied / Mart catalog | \`STATIC_HARD_CONTRACT\`、\`CURRENT_LIVE_UNKNOWN\` | \`KEEP_DEPENDENCY_PENDING\`，禁 DROP |
| **C1A-03 其他十個 Mart** | 歷史 Core Census **未掃 Mart namespace**；Mart maintenance 一共十一個名稱為程式宣告、不是存在性驗收 | \`STATIC_HANDLE_ONLY\`、\`CURRENT_LIVE_UNKNOWN\` | 十張仍 \`RETIRE_CANDIDATE\`，沒有任何 \`ABSENT\` 或可刪核准 |
| **C1A-04 四模型因子** | 九個 Core 表當時 schema 包含 \`financials.published_at/availability_at/version_at/source_document_sha256\`，並非「未使用的普通因子」；34 slots 仍依 3.8.2 研究 contract | \`HISTORICAL_PIT_COLUMNS_OBSERVED\`、\`MODEL_LIVE_UNKNOWN\` | \`KEEP\` PIT/RAW/QUALITY/Y/CONTEXT/PROVENANCE；可刪欄 = 0 |
| **C1A-05 PG** | Risk DETERMINISTIC 10/23 舊收據與 migration 靜態定義已存在，但**沒有** PG schema/table/field constraints 即時通盤查詢 | \`HISTORICAL_PARTIAL\` | \`KEEP_UNTIL_CURRENT_PG_CENSUS\` |

**另有重要操作修正：** 倉庫 [\`.github/workflows/finops-dev.yml\`](../../.github/workflows/finops-dev.yml) 中的 \`iceberg-readback\` 分支實際僅讀 Scheduler、Cloud Run Job configuration 與 nonterminal executions，**不含 PG catalog/Core/Mart schema**；不能把該入口的 PASS 當成 PG/Iceberg 清冊。有一條 [\`feature-readiness-metadata-census.yml\`](../../.github/workflows/feature-readiness-metadata-census.yml) 可取得 Core 及 bounded row scan，但會以 override args 啟動現有 dev Job 且未涵蓋 Mart/PG 全量，因此**本輪未 rerun/dispatch**；不擅自以採集/寫入工作流替代唯讀盤點。

### 9.1 目前 C1-A 最後必要的當前收據

- **PG：** 本回合未取回 \`pg_catalog / information_schema / control.schema_migrations\` 的即時完整枚舉及 \`publication.mart_report_index\` 的實際 CHECK。要先由既有授權角色 \`BEGIN READ ONLY\` / bounded timeout 執行並輸出 env/as-of/role/schema/keys/index/migrations receipt。
- **Iceberg：** 本回合未取回 \`catalog.iceberg_tables\` **同時涵蓋 core+mart namespace** 的當前 catalog entries，也沒有每張表的實際 current snapshot/schema/partition spec/summary 讀回；直到取得不可標 \`ABSENT\` 或 \`LIVE_CONFIRMED\`。
- **阻擋原因：** 目前連接的 GCP 工具無通用唯讀 PG/Iceberg metadata action，Janus Dev Read-only v2 的 \`janus_sources\` 返回內部錯誤；既有 GitHub 憑證能讀取歷史 Action log，**不等於擁有 direct GCP SQL 授權**。不要將工具限制誤寫成 GCP permission denied。
- **清掃 gate：** \`C1-B NOT_READY\`、**本輪新增批准實刪項目 = 0**；新的歷史證據可用於先保護不應清除的資產，不能反向用來批准破壞性操作。

---

## 10. C0-Live 補驗突破：九 Core＋十一 Mart 實存 Metadata 收據（2026-10-23）

新的既有 dev GitHub WIF 唯讀查詢通道見 [C0 §16–§17](data-governance-c0-2026-10-23.md)，真實執行而非推算：
- [PG/Catalog #39948922788](https://github.com/tommylin15/janus-omniforge/actions/runs/39948922788) 讀到 PG 93 relations、728 cols、379 constraints、149 indexes、66 applied migrations；Iceberg catalog 共 20 entries（Core 9、Mart 11），Core 9 張 schema/spec/snapshot metadata 可讀。 \`information_schema\` 是權限受限檢視，不能推論全庫只有四表。
- [Mart #39949570989](https://github.com/tommylin15/janus-omniforge/actions/runs/39949570989) 以 \`janus-intelligence-mart\` 身分讀到 11/11 張 Mart metadata（共同各 23 fields；共同 \`analysis_date:month\` + \`scope_id:bucket[32]\`）。
- \`mart_alternative_sentiment_v1\`、\`mart_daily_brief_v1\` **Live Catalog / table metadata 存在，但 current snapshot=NULL**，rowcount 一律 \`UNKNOWN/NULL\`，不可宣稱 0 筆或 \`ABSENT\`。其餘九表分別具有 current snapshot，歷史研究/published index/retention 仍須確認。
- Migration 比對發現 Live ledger 缺主線 \`030/031/034\` 同名值、Live \`049_batch_skipped_state\` 與 repo \`049_batch_occurrence_skipped_status\` 命名差異；**不得擅自執行 SQL migrations**。

### 10.1 C1-A 候選即時分類修訂（有明確 Live，而非全部 UNKNOWN）

| C1-A ID | 原候選 | 現時證據分類 | 安全決策 |
|---|---|---|---|
| C1A-01 | \`core.market_volume_v1\` vs \`core.ohlcv_v1\` | \`LIVE_PRESENT_BOTH; DIFFERENT_FIELDS_AND_HISTORICAL_DEPTH\`（10/23 Core 163544 vs 200926；同鍵值 parity 未執行） | CONSOLIDATE_CANDIDATE_ONLY；**禁刪** |
| C1A-02 | \`mart.mart_scoped_analysis_v1\` | \`LIVE_PRESENT_SNAPSHOT_138_ROWS; PG_PUBLICATION_CONSTRAINT_PRESENT\`（約束內容仍待核） | KEEP_DEPENDENCY_PENDING；**禁刪** |
| C1A-03 | 其餘十張歷史 Mart 表 | \`LIVE_CATALOG_PRESENT_ALL\`：八張有 snapshot，兩張無 snapshot（詳 C0 §17） | RETIRE_CANDIDATE，仍缺最近30日 reader/last writer、備份/rebuild、可回復；**十張全部禁刪** |
| C1A-04 | Alias / 候選 X 特徵 | \`34_X_SLOTS_PROTECTED\`；Core financial PIT/provenance 時間欄實存 | KEEP／ALIAS_CANDIDATE；**禁刪欄** |
| C1A-05 | PG publication/control/schema | \`LIVE_METADATA_READBACK\`，且 migration ledger 命名漂移待釐清 | KEEP；禁止自動 migration / schema cleanup |

**本輪沒有 \`ABSENT\` 的 Core/Mart 名稱；沒有達到 C1-B 退役 gate 的表。** 雙表重疊、Mart 最近讀者和資料參照、GCS generation、影響測試及獨立復原仍需真實證據。下一個合理步驟是**以現有唯讀查詢通道有界驗證 Mart reader / publication references 與近30天 Cloud Scheduler/Run receipts**，不是直接 DROP/DELETE。

---

## 11. C1-A 前置 metadata 查詢閘門正式完成（2026-10-23）

[整合唯讀 Workflow #39950278408](https://github.com/tommylin15/janus-omniforge/actions/runs/39950278408) 已 **success**，\`janus_governance_c0_live_metadata_join_v1=PASS\`、離線測試 6 passed。現有 dev WIF 身分分工：\`janus-ingestion-core\` 讀 PG metadata、Core Iceberg、全 Catalog；\`janus-intelligence-mart\` 讀 Mart metadata，再交叉比對同 Git SHA / Catalog name，不擴張 IAM。詳細 93 PG relations、728 PG fields、379 constraints、149 indexes、66 migration values、9 Core、11 Mart 讀回見 [C0 §16–§18](data-governance-c0-2026-10-23.md)。

**C1-A 現在不再因「未知實際 Core/Mart 表數」卡住。** 20 張全在 Live Catalog 有登錄；11 張 Mart Metadata 可讀、其中 \`mart_alternative_sentiment_v1\` 與 \`mart_daily_brief_v1\` 無 current snapshot 而 rowcount=NULL（不推定 0）。真正剩餘 C1-B 閘門是**每個候選的現役讀者／writer/30天 job/scheduler 依賴、publication index reference、同鍵/單位差異、GCS 備份重建和回切收據**；此外 PostgreSQL 66 applied migration 名稱相對 68 code 檔案仍有既知差異需釐清。此次只完成 metadata 查詢入口與有界基準，不進行清掃；**可實體刪除的核准名單 = 空**。


---

## 12. C1-A 讀者依賴驗證：LIVE 參照與逐表決策（2026-10-23）

已透過 **[#39952096357](https://github.com/tommylin15/janus-omniforge/actions/runs/39952096357)**（job \`120408771409\`；Git SHA \`d0ec9d49e8db1ca807948c40fae338a25415e2ac\`；8 個安全測試通過）新增的受控 dev 唯讀聚合，取得 \`publication.mart_report_index\`、\`control.executions\` 最近30日狀態、真實 \`pg_get_constraintdef\`、\`pg_stat_user_tables\` 累計觀測。原始細節與執行時間見 [C0 §19](data-governance-c0-2026-10-23.md)。

### 12.1 讀者與引用的有效證據

1. **硬性契約／真實資料：** \`mart.mart_scoped_analysis_v1\` 是現行 PG \`mart_report_index\` 唯一允許的 table identifier（實際 CHECK 已讀回），**138 筆歷史發佈索引列**全部指它；其中 **1 筆 publishable/complete、137 筆 blocked**。30 日 \`analysis_as_of\` 切片有 **35 筆 blocked**，屬業務日期而非 35 個 API 讀取。
2. **API 程式讀者：** \`packages/web_api/public.py\` 的 \`PostgreSQLPublicIndex.latest\` → \`publication.publishable_mart_reports\`；\`IcebergArtifactReader\` 確認 \`table_identifier == mart.mart_scoped_analysis_v1\` 再按被索引 snapshot 讀 Iceberg。\`packages/admin_api/service.py\` 還存在 \`mart_reports\`、execution lineage、review APIs；**目前部署的 API revision及最近30日是否被叫用仍待 runtime 驗證**。
3. **維護 Reader/Writer：** \`jobs/intelligence-mart/intelligence_mart/retention.py\` 確有 11 個 Mart table handles 的 table_exists/load/scan、可選 apply row delete 與 snapshot compaction 路徑；尚缺最近執行與實際 mode 收據，不能稱 11 張已停用。
4. **PostgreSQL 觀測：** \`mart_report_index\` 累積 seq_scan=187 / idx_scan=678（非30日）、\`mart_report_outbox\` seq_scan=38 / idx_scan=0（非 outbox pending）；具 DB 物件讀取使用跡象，尚無 SQL caller identity。
5. **Control 最近 30 天工作狀態：** \`analysis\` 18 succeeded／8 failed／**41 queued**；\`collection\` 89 succeeded／48 failed／50 partial／**16 running**；共 270 個 requested_at 落在30日的 status rows。queued / running 不等於現有效租約；需另讀 \`claimed_until\` 與實際 Cloud Run Job 交叉確認，防止 cleanup 誤判。

### 12.2 十一張 Mart 清掃候選逐表「有證據」分級（仍不實刪）

| Live Mart identifier | 本次 PG 發布 Index | 現行 GitHub 直接讀者／依賴 | C1-A 本次判定 | C1-B gate |
|---|---|---|---|---|
| \`mart.mart_scoped_analysis_v1\` | **138 references、真實 CHECK、1 publishable** | **PublicMartService/IcebergArtifactReader + Admin Mart API + retention** | **KEEP** | 禁 DROP；舊 snapshot replay 與 API 正向讀回仍待核 |
| \`mart.mart_risk_portfolio_v1\` | 不在此 PG index（index 僅容 scoped） | Mart maintenance；Risk/Owner 隔離與舊研究／報表讀者需獨立查 | **KEEP_PROTECTED_PENDING** | 先驗 Owner/Risk 依賴、無存取洩漏，再談任何退役 |
| \`mart.mart_screening_signals_v1\` | 不在此 PG index | Mart maintenance；screening GCS/PG product reader 還需比對 | **RETIRE_CANDIDATE / UNKNOWN_READERS** | 近30日 actual writer/reader、fallback、重建收據 |
| \`mart.mart_core_alpha_v1\` | 不在此 PG index | Mart maintenance；研究/舊 alpha 需查 | **RETIRE_CANDIDATE / UNKNOWN_READERS** | 同上 |
| \`mart.mart_alternative_sentiment_v1\` | 不在此 PG index | Mart maintenance；**Live 無 current snapshot** | **RETIRE_CANDIDATE / UNKNOWN_READERS** | NULL snapshot 非 0 row/ABSENT，舊 refs/重建先釐清 |
| \`mart.mart_market_regime_daily_v1\` | 不在此 PG index | Mart maintenance；regime 下游待證 | **RETIRE_CANDIDATE / UNKNOWN_READERS** | reader/資料契約與替代方案 |
| \`mart.mart_sector_rotation_daily_v1\` | 不在此 PG index | Mart maintenance；產業輪動下游待證 | **RETIRE_CANDIDATE / UNKNOWN_READERS** | 同上 |
| \`mart.mart_topic_trends_daily_v1\` | 不在此 PG index | Mart maintenance；趨勢/研究下游待證 | **RETIRE_CANDIDATE / UNKNOWN_READERS** | 同上 |
| \`mart.mart_candidate_health_v1\` | 不在此 PG index | Mart maintenance；品質/Admin 下游待證 | **RETIRE_CANDIDATE / UNKNOWN_READERS** | 同上 |
| \`mart.mart_daily_brief_v1\` | 不在此 PG index | Mart maintenance；**Live 無 current snapshot**、簡報/發布舊引用待證 | **RETIRE_CANDIDATE / UNKNOWN_READERS** | NULL snapshot 非 0 row/ABSENT；報告 reader 先釐清 |
| \`mart.mart_llm_narratives_v1\` | 不在此 PG index | Mart maintenance；內容生成結果與歷史引用待證 | **RETIRE_CANDIDATE / UNKNOWN_READERS** | 同上 |

**不成立的推論：** 這個 PG 表由 CHECK 限制僅能引用 scoped analysis，因此其餘十表「不在 mart_report_index」是**結構必然**，不代表全專案零讀取、亦不表示安全退役。沒有對任何 Mart 表證實真正 30 日零讀者（要比對已部署 Job/API、Cloud Scheduler 與日誌）。

### 12.3 下一小階段的精確收斂順序

1. **先釐清 PG status 活躍性：** 41 queued analysis 與16 running collection 查 \`claimed_until\`、\`requested_at\` bucket、Cloud Run Job 執行終態；防止把 stale lease 用作 GCS 48h 保護或將 queued 誤認有效工作。
2. **追蹤已部署 reader：** 讀 \`janus-api\` revision digest、\`janus-intelligence-mart\` 等現役 Job config 與最近30天 executions，以及 \`mart.scoped_analysis\` 的正向 API 是否成功讀取 \`publishable\` snapshot；不要讀 owner payload 或自行 invoke 寫入 Job。
3. **其他十個 Mart 用途：** 檢查所有已部署查詢／研究版本 manifest、GCS artifact refs 與 current snapshot 的必要重建證據，再按每張表更新 \`KEEP/CONSOLIDATE/RETIRE_CANDIDATE\`。不以掃碼查無字串作 Live 無讀者的唯一證據。
4. **發布資料守門：** 138 reference rows 中 1 筆可發布，但是其 \`analysis_as_of\` 較早；現行只保留 current Iceberg snapshot 的治理決策不保證舊 snapshot 還能讀。若實際 API replay 失敗，應先標 \`BLOCKED_PUBLIC_REPORT\` 處理相容問題，而非刪表。

本輪可獨立結案項為 **C1-A 固定範圍 PG reader/reference audit PASS**，非全部 C1-A / C1-B；\`mart_scoped_analysis\` KEEP 已有充分依賴證據，**全部 Table/Field/Object 實刪核准清單仍 0**。

---

## 13. 優先處理 57 筆非終態執行與十 Mart Reader 的 C1-A 分流（2026-10-23）

### 13.1 P0 實機結果（不是推測）

新證據詳見 [C0 §20](data-governance-c0-2026-10-23.md)；PG 聚合已確認最近30日原 **41 analysis queued** 與 **16 collection running** 均 `claimed_until IS NULL`、有效租約 **0/57**；分群為 analysis 5（<48h）/23（2–7d）/13（7–30d），collection running 16（7–30d）。PG controller occurrence 的 `queued_execution_id` 直接關聯也是 **0/57**。這 57 筆應列為 `NONTERMINAL_WITHOUT_LEASE` 待人工／後續有界程式流程處理，不因狀態字串認定活躍，也**不在本輪直接更新 PG status**。

另有 **6 筆 Controller active occurrence** `state.status=running` 且 `state.job=janus-batch-controller`，沒有可直接 GET 的 `state.execution`；它們是獨立集合，須以 `batch`／Controller 執行語意另作核對，不得誤併 57 筆。首次 Cloud Run 30 日全量掃描遇 500 筆分頁上限而 `PARTIAL`；擴充到有界最多1200筆的修正版與十 Mart 程式/部署參照清冊在 [#39956176106](https://github.com/tommylin15/janus-omniforge/actions/runs/39956176106)，**該 Run 完成／讀回前不得預先標 CLOUD_RUN_PASS／MART_READER_PASS**。

### 13.2 C1-A 安全決策與限制

| 實體 | 本次判定 | 不可省略的後續證據 |
|---|---|---|
| 57 PG 非終態 execution | `NO_LEASE_LIVE_CONFIRMED`（該次快照） | 若要更新狀態：真正 queue consumer／polling 的狀態機規則、是否新取得租約、對下游有無影響、受控可復原與明確授權 |
| Stage 超過48h 物件 | `NOT_EVALUATED`，不因57筆 stale 狀態保護 | 當前 generation/updated、`_stage_live_execution_ids` apply 前重讀、GCS 最少一份合法代表引用 |
| Mart specialist artifact retention | `STATIC_POLICY_GAP`：以 status-only 作 active，無 lease predicate | 對比真實 artifact refs、其他有效保護來源、當前 retention mode；需要另案 targeted test/改動/驗收 |
| 其餘十張 Mart 表 | `LIVE_CATALOG_PRESENT / UNKNOWN_ACTUAL_READER` | 已部署 API/Mart revision、目前 main code references、近30日 Job/直接或動態資料表讀者、snapshot/manifest、rebuild/rollback |
| `mart.mart_scoped_analysis_v1` | `KEEP`，具138筆 PG index + API contract | 只核舊 snapshot replay / API 正向可用性，不因其他十張暫無 PG index 就推論無讀者 |

**本輪不能做的事：** 批量把這57筆改 `failed`、刪除 Core/Mart 表、刪除 Stage/GCS 物件、停止既有 Job/Writer 或擴大 IAM／新增付費資源。Stage 與 Mart specialist artifact retention 的保護語意不同，後者的 status-only 差異需要實際影響證據，不把程式檢查缺口寫成已發生資料損失。C1-B 物理清掃核准 = **0**。


### 13.3 最終驗證分級：P0 PASS、十 Mart 讀者仍按資產守門

**最新 Live Workfow：** [#39956176106](https://github.com/tommylin15/janus-omniforge/actions/runs/39956176106)；job `120423747240`，`source_git_sha=1ab6e8667e5f40cc2d7a1a64c5ba7254e9d38c09`，12 offline tests passed、join `status=PASS`、零 data mutation／IAM change／新資源。完整細節及各 Job 確切30日終態計數見 [C0 §20.4](data-governance-c0-2026-10-23.md)。

- **P0 PG lease：`LIVE_PASS`。** 41 queued +16 running＝57/57 `claimed_until IS NULL`，不符合有效 lease 的 Stage 防刪條件；58+ 筆不存在這類推論（6 筆另為 ledger-backup Controller occurrence），Stage apply 前仍需重讀。
- **P0 Cloud Run Job 最近30日清冊：`PASS`。** 既有五個 Jobs 各自完整分頁，並核對 6 筆 Controller occurrence 都是 `ledger-backup`、沒有精確 Execution ref。**PG 57 筆逐筆 Cloud Run exact join 仍無必要對應鍵**，不能據此變更 PG 狀態；ledger-backup 應走自身 poll/reconcile。
- **P1 Mart source-reference/部署清冊：`BOUNDED_PASS`。** 共掃 478 個現行 checkout 檔案；下列十個名稱各出現2個 `LITERAL_OR_HANDLE_ONLY` 引用。API、Mart、Ingestion 三個 dev 部署資源的 revision/digest 已唯讀讀回，但未取得 SQL-level 的**最近30日各表實際 reader/writer**，故不得標 `NO_READERS` 或允許 DROP。

| Mart identifier（皆為 `mart.*`） | code reference hits | 目前可作出的判斷 |
|---|---:|---|
| `mart_screening_signals_v1` | 2 | `RETIRE_CANDIDATE/ACTUAL_READER_UNKNOWN`，screening 的其他 GCS/PG product 需分別看 |
| `mart_core_alpha_v1` | 2 | `RETIRE_CANDIDATE/ACTUAL_READER_UNKNOWN` |
| `mart_risk_portfolio_v1` | 2 | `KEEP_PROTECTED_PENDING`，Risk/Owner 邊界先保留 |
| `mart_alternative_sentiment_v1` | 2 | `RETIRE_CANDIDATE/ACTUAL_READER_UNKNOWN`；catalog live but `current_snapshot=NULL` |
| `mart_market_regime_daily_v1` | 2 | `RETIRE_CANDIDATE/ACTUAL_READER_UNKNOWN` |
| `mart_sector_rotation_daily_v1` | 2 | `RETIRE_CANDIDATE/ACTUAL_READER_UNKNOWN` |
| `mart_topic_trends_daily_v1` | 2 | `RETIRE_CANDIDATE/ACTUAL_READER_UNKNOWN` |
| `mart_candidate_health_v1` | 2 | `RETIRE_CANDIDATE/ACTUAL_READER_UNKNOWN` |
| `mart_daily_brief_v1` | 2 | `RETIRE_CANDIDATE/ACTUAL_READER_UNKNOWN`；catalog live but `current_snapshot=NULL` |
| `mart_llm_narratives_v1` | 2 | `RETIRE_CANDIDATE/ACTUAL_READER_UNKNOWN` |

**必要區別：** 命中兩個程式文字位置是引用線索，不是有兩名讀者，亦不代表有兩次讀取。部署 digest 讀回只證明實機的存在與版本，無自動 source SHA 對映或 request SQL trace。共用 `MartMaintenanceStore` 和 `retention.py` 對全部11表仍有動態讀取／維護路徑，應作實際保留依賴看待；如未有表級遙測，最多保留 `UNKNOWN`，不得依負面文字搜尋授予退役。

**決策：** 將57筆非終態修復留在本輪之外的受控例外，不自動變更 queue/Job。P0 依已定義範圍結案，P1 完成可行的程式參照與部署唯讀盤點；十表退役許可及下一步現役讀者缺口仍 `PARTIAL`。只對具體發現的真實依賴/回復缺口繼續追查，不創造虛構 `0 READERS`。**C1-B 允許 DROP/DELETE 的資產仍 = 0**。
