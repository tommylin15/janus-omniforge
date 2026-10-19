# Janus 因子收錄母體、容量預算與資料保存矩陣

更新：2026-10-19（Asia/Taipei）。狀態：**正式規格對照／既有實作盤點；本文件不是新的資料回補、歸檔搬移或刪除授權，也不是 runtime 完成證據。**

資料治理導航見 [統一入口](data-governance.md)。此矩陣將 [全市場批次契約](full-market-batch-policy.md)、[來源與 Stage/Core](storage-data-and-ingestion.md)、[五角色](specialist-engines.md)、[公開資料清理治理](retention-governance.md) 與 [DRL-01 active TODO](../todo.md) 接在一起；與它們衝突時以明確的 active 決策及實際 main/runtime 為準。涉及實際保留、清除、generation、fence，唯一權威仍是 `retention-governance.md` + 對應程式；私人 Ledger/筆記不得套用公開資料 TTL。

## 1. 計算基準、母體與資料量語意

- **Market Coverage（M）**：TWSE／TPEx 官方有效名冊的全部上市、上櫃**普通股**，不使用歷史 Liquid 500；依實際生效日期取得 membership。2026-10-17 DRL 官方 13 月營收分母 **TWSE 1,096 + TPEx 896 = 1,992 檔**；這是本表估算情境，不是永遠固定的股票數。興櫃、ETF 不納入普通股 coverage 分母，**持有的 ETF 仍必須正常處理行情／估值**。
- **Deep Coverage（D）**：active watchlist ∪ effective holdings 的去重股票聯集；持股離開 watchlist 仍在集合，清倉且未觀察才退出。既有 **50 distinct symbols** 是 MVP 的關注／深度追蹤營運護欄；容量情境取 D=50，並非保證持股聯集永不超過 50，也不是硬將持股剔除。實際 D 每日由資料庫取得，不能以 50 代替實際統計。
- **Private（P）**：依 owner 的交易、成本、股利、現金、損益、筆記等，不按上市櫃普通股數估計，不得寫入公開 Mart。
- **Benchmark（B）**：指數、總經、市場級資料，不按 1,992 檔複製。
- **容量是 planning envelope**：下表數字指近似「股票 × 日／月／季」組合，非 GCS 檔案數、資料庫真實 COUNT、所有特徵欄位總數或已取得的完整 coverage。日頻以每年 **約 250 交易日**、兩年約 500、三年約 750 計；具法人類別、metric、修正版本的資料還會乘上類別數。實際進帳以 `dataset + date + market + symbol + metric + version` 去重且有憑據，絕不為達預算補零或假值。
- **全市場母體不代表全市場多年全補**：DRL-01A 全市場首版最低 **20/21 合格交易日**；持股／關注股 **≥120 日**；5/20/60/120 日指標若所需窗口不足，保持 missing，不能把理論 120 日指標列為已全市場完整可算。
- **品質門檻**：上市 TWSE missing ≤10%、上櫃 TPEx missing ≤30%，按資料集與應到期間分別驗，不降低來源、PIT、價格／金額或私人損益品質 gate。首次抓取與增量、實收筆數、今日可用比率須各自呈現。

## 2. 因子及資料集覆蓋／儲存量規劃

| 因子族群 / 對應 Core 或 derived 資料 | 收錄母體與刷新 | 情境容量（M=1,992、D=50） | **目前保存／清理契約** | 重要邊界 |
|---|---|---|---|---|
| 股票名冊、類型、產業／`stock-profile` | M；名冊版本依生效日期 | 最新約 1,992 檔；歷史版本另計 | Core 一般 365 天；研究要重播須獨立保存已核准輸入 | 保留退市／退出時已知歷史 membership；不可用今天名冊重寫過去 |
| 日 OHLCV：開高低收量、成交值／`ohlcv`、`market-volume` | M，交易日增量 | 一年約 **498,000 股日組**，實際視停牌與缺值而變；MVP 20/21 日約 39,840～41,832 組 | 一般 365 天；D 對 `ohlcv` 保留 1,096 天；`market-volume` 不自動延長 | 持股 ETF 另跟行情、不混股票分母 |
| 每日 PE／PB／殖利率／`valuation` | M 官方可得增量 | 理論一年最多約 498,000 股日組；實收可低於此值 | 一般 365 天；D `valuation` 1,096 天 | 虧損 PE 可合法為 null，不以 0 代替 |
| 三大法人／`institutional` | M，來源允許才更新 | 一年最多約 498,000 股日 × 實收投資人類別數 | Core 一般 365 天 | investor_type 是複合鍵；不能把一股日當成一個類別總數 |
| 融資／融券／借券／當沖／警示／`market-activity` | M，按核准市場批次能力 | 每年最多約 498,000 股日 × 實際 metric 數 | Core 一般 365 天 | 不適用、來源缺漏維持 unavailable |
| 月營收、YoY／財務 Core `financials` | M 摘要；D 可定向補缺 | **13 個月 × 1,992 ≈ 25,896 股月組**；非每月重抓全 13 月 | Core 財務保留每股／statement／source 最新 **12 季**；不是月營收另設 13 月 purge | 13 月是同比計算最低資料窗口；fiscal_month 不可猜測 |
| EPS、損益、資產負債／現金流、財務比較因子／`financials` | M 能得的摘要，D 深度 12 季 | 每股 12 季情境：**23,904 股季組**；每季數個 metric／版本另乘 | 各股／statement／source 最新 **12 季**，保留合法更正 provenance | 首版實測 focus 6 檔 2026 Q1＋Q2；完整四季 TTM 未認證不補算 |
| 公司公告與重大訊息／`events` | M 事件索引，D 按授權深入 | 事件驅動，**不能給固定股日筆數** | 一般 Core 365 天；歷史研究引用不再保護非 current snapshot | 原文與新聞全文、券商研究、社群仍受來源 admission；不因屬 D 自動開始 |
| Benchmark、指數與市場狀態／`benchmark` | B 市場級，每交易日 | **每指數**約 750 日／3 年，不乘 1,992 | 1,096 天 | 指數基準、報酬指數與價格指數不可混稱 |
| 全市場 Market Screening：5/20/60/120 日報酬、RS、量能、波動、排名／Mart derived | M，Core ready 後每日一次、同 input reuse | 每交易日約 **1,992 股日訊號組**；90 曆日約 60～66 交易日，即約 **119,520～131,472** 組 | Mart 分析列 **90 天**；未引用 screening artifact 到期清理 | 這是 Mart 產物；所需回看窗口不足時 individual factor missing |
| 深度技術與風險：MA、KD、ATR、RS、Beta、CVaR、相對強弱／Core + Mart | D，官方資料或 dirty input 更新 | D=50，三年價量約 **37,500 股日組**；特徵按需重算 | D 的 `ohlcv`／`valuation` 1,096 天；輸出 Mart 90 天／報告每股 3 代 | 50 為估算情境；不是所有原始因子長期各存一份 |
| PE／PB 歷史河流、P25/P50/P75、月中位／Core + serving | **目前只指定 6 檔 TWSE D 股票**，2024-10～2026-10（25 曆月） | 近似 **6 × 500 = 3,000 股日估值組**；若每月都有資料，月中位約 **6 × 25 = 150 股月組／每項 PE、PB** | **UI／分位使用 2 年窗口**；Core D `valuation` 1,096 天，不因 UI 縮成 2 年而刪到 2 年 | 每項分別要求 ≥18 個有效月、≥150 個有效日及期間雙端存在；補收／部署／API UI 未全部認證 |
| 五位 Specialist：Fundamental、Valuation、Quant、Risk、Event | D，**dirty dependency** 更新，不是每天五角色全市場重算 | D=50、完整一次最多約 **250 份角色結果**；每股 3 代上限情境約 **750 份角色結果** | 每股最近 **3 代完整分析**；Mart 行 90 天；僅活躍報告引用保護 | 依分析日期與版本留存，並非所有角色每天都有新 generation |
| 模型 training／OOS／evaluation／GCS research derived | 已核准 D 或具 PIT 的 M 歷史研究 cohort，定期有界觸發 | 依 frozen cohort、label 成熟度、request 計；**沒有固定 1,992 × 5 全量** | 最新使用的 OOS／固定 ML 資料保留；無引用過時逾 7 天候選清理 | model/dataset hash 與 lineage 須獨立留存；BigQuery temporary 可重建，不是 canonical |
| 私人持股、交易、現金、成本、配息與損益／PG + Private | P；事件／持股變動或 EOD | owner 實際事件數／持股檔數，不按 1,992 推導 | **不套用公開 7／90／365／1,096 天清理**；Ledger 及 reversal 不就地刪改 | bounded 備份保存政策與交易事實 retention 分開；owner 隔離 |

表中「12 季」不是表示所有股票都已有 12 季完整 EPS；「1,096 天」也不表示所有關注股都已補足 3 年。現行深度歷史估值補收 adapter 最多可詢問 36 月，但**目前 DRL-01D 指定的產品河流僅兩年六檔**，不可把 36 月能力當成當次新回補請求。未核准分 K/Tick／新聞全文／券商／社群不計入預計收錄量，不排程。

## 3. 到期後：Row、Snapshot、研究重播與是否搬區

**沒有獨立歷史區搬遷 Job 或新增 archive bucket。** 2026-10-18 決策以來 Core／Mart **只保留 current Iceberg snapshot**；已撤銷舊 named refs、24h snapshot、外部歷史研究引用保護，不能把已刪的 `snapshot_id` 當成仍可回播。參見 [正式清理契約](retention-governance.md) 和 [新決策](../decision-2026-10-18-current-only-snapshots.md)。

| 類別 | 到期候選 | 主要 guard |
|---|---|---|
| Stage raw/quarantine | **2天（48小時）** | Active execution 及其共用原料保護 |
| Core 一般 rows | 365天 | 來源、date/period、缺值語意；不是全市場已有兩年 |
| Core Deep `ohlcv`／`valuation`、benchmark | 1,096天 | 限符合 Deep/Benchmark 條件之 rows |
| Core 財報 | 最近12季 | symbol/statement/source/版本口徑 |
| Mart 分析 rows | 90天 | live worker + 活躍引用 |
| Specialist 與 OOS | 每股3代、最新使用的 OOS | 無引用且逾7天的過時 artifact 可列候選 |
| Core execution manifest | 90天、活躍執行保護 | 外部歷史 fence 不再保留非 current snapshot |
| Orphan | 非current、年齡≥7天 | catalog pointer/lock/generation/current readback |
| Owner 交易與筆記 | 不套公開 TTL | 私有範圍／備份獨立 |

D07 第一版設定**最近24個月滾動研究窗口**：這是每月訓練/OOS 的目標，不是改 Core row TTL、也不保證所有股票已具完整兩年。若要重現實驗，研究層另保存合法有界 versioned Parquet、日期/cohort、feature/label/schema、來源與 hash，避免依賴已刪 snapshot。嚴格 PIT 不足需標研究限定／insufficient，不為湊視窗填假值或啟動無界補收。

清理先 compact、再 Mart、再 Core。TTL／planned 清理候選、實刪 objects/bytes 與可計費儲存變化須分開記錄；實際週維護節奏見 [資料治理總覽](data-governance.md)。

**不延伸**為可直接刪除任何 canonical rows／私人資料的權限。

## 4. 有時間戳的實測覆蓋 vs 未認證的模型歷史（2026-10-17～19）

| 項目 | 有證據的實測情況 | 不可推論 |
|---|---|---|
| M 的 13 月營收（2025-09～2026-09） | TWSE **1,077/1,096**、TPEx **864/896**，合計 **1,941/1,992**，分市場 PASS | 不等於 25,233 實際 Core row 數／所有 13 個月版次完整 PIT |
| Focus D 價量 | 6 TWSE 各 **135 日**，00697B／00719B 各 **125 日**，8/8 120 日 gate PASS | 不等於市場其餘股票 120 日覆蓋或所有持股 3 年已齊 |
| Focus EPS | 6 股 2026 Q1／Q2 已有合格單季；2026-10-19 Yahoo 2025Q4 六股補收 Stage→Core→serving/API 6/6 PASS（見 DRL-01 結案） | 第三方來源、歷史嚴格 PIT、四季 TTM 可比較仍未認證；不等於全市場歷史完整 |
| DRL-01D 兩年 PE/PB 河流 | 2026-10-19 新版正式 API 6股×PE/PB=12/12 讀回 PASS（此前六股25月補收沿用） | 僅六股估值產品，不能推論全市場兩年 OHLCV、PIT 與成熟標籤完整 |
| GCS Core／Mart 實際物件量與 dataset 細項 | D06 曾有具時間戳的物件統計及有限 orphan 清理 | 無本次新鮮 SQL/Iceberg live COUNT，不聲稱現有總筆數、冷封存量或節省百分比 |

**後續 Admin/資料品質表格的口徑**：對每一 dataset × market × period × tier 列出 `expected_symbols`、`eligible_symbols`、`covered_symbols`、`observed_rows`、`missing_symbols`、`snapshot_id`、`source_as_of`、`retention_policy`、`next_retention_candidate_at`、`protected_reference_count`、`archive_migration_status=not_implemented`、`last_verified_at`；未知應為 null／UNKNOWN。這是既有 ADMIN-V2 A3 / D06 讀取欄位的**契約參考**，不是新建獨立 Admin 頁面或新的 daily job。未驗證的實際 row counts 不得用估算值帶入。

## 5. 程式及驗收入口

- `packages/duckdb_query/iceberg.py` 的 `DuckDBIcebergCore.IDENTIFIERS` / `PARTITIONS` 定義真正的 Core dataset 與鍵。
- `jobs/ingestion-core/ingestion_core/retention.py` 的 `POLICY`、`retained_core_rows`、`maintain_public_data` 負責 Core/Stage；`jobs/intelligence-mart/intelligence_mart/retention.py` 與 `artifact_retention.py` 負責 Mart/成果物。
- `tests/test_data_retention.py` 的 tier/retention/fence 測試需與本表同步。任何改動期限、建立實體歷史區或擴大 dataset 回補必須先核實目前 main/code、runbook、真實 retention dry-run 與引用保護，非本文件單方面批准。
- 實際版控／Job／清理與驗收請依 `../todo.md` 的 DRL-01、D06、ADMIN-V2 不重工整合；執行證據只存 `operations-and-testing.md` 或相應 archive，不在此表累加 checkpoint。


### 2026-10-18 補充：actual Core continuity，勿和容量預算混淆

[Core census #39083283620](https://github.com/tommylin15/janus-omniforge/actions/runs/39083283620) 實際 snapshot records：benchmark759、market-volume39699、ohlcv111929、market-activity135050、valuation16595、financials88131；[逐月 #39083573483](https://github.com/tommylin15/janus-omniforge/actions/runs/39083573483) 指定股票樣本 market-volume 在2026-07/08為0、09為19、10截至16日11個交易日期；market-activity 0/3/14/11；TAIEX 7–10月連續、TPEx指數日數僅39。這不是全股票各日期分母，不能將同一「大盤」畫面所需的不同 dataset 用 TAIEX 完整度替代。EPS、API 與 Ledger 的 2026-10-18 當次缺口已被 2026-10-19 DRL-01 結案的新版讀回部分取代；自然 daily/weekly Ledger 收據仍 NOT_VERIFIED、TTM／嚴格 PIT 未認證。此 Core census 是 10/18 固定歷史截面而非本次 live COUNT。本表保存期不變；資料回補實作及受控驗收詳見 `../todo.md`、`operations-and-testing.md`。
