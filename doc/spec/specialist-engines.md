# 五分析師引擎目前契約

日常 Mart 使用 `specialist_runtime`，不使用生成式 LLM；但「日常」不等於每天把五 specialist 全量重算。Market Coverage 在每個交易日 EOD canonical data ready 後跑低成本 screening，Deep Coverage 則依 dirty dependency／input change 增量更新。舊五角色引擎、prompt、compatibility 與 provider daily entry 已刪除；歷史資料僅保留作稽核。後續 On-demand CEO 不在本次驗收範圍。

## 覆蓋與資料

Market Coverage 由 `control.specialist_market_symbols(date)` 取得具 PIT 日期的 liquid-500 membership，最多 500 檔。每個交易日 EOD canonical data ready 後執行一次低成本 screening；篩選回報最新價/量/金額、5/20/60/120 日報酬、規則分數、排序與異常旗標，不自動加入自選股。BigQuery 通過 exact-snapshot fidelity gate 後優先承接這條全市場 cross-sectional compute。

B3 新增獨立 `market-screening` operation：既有 controller 交易日台北 16:30、等待 ingestion／data-supplement、沿用休市日曆；同日 Core date fence 不成立則拒絕。新增 20D 平均成交金額／年化波動、5/20/60/120D 相對 benchmark 強弱、可用官方估值與 cross-sectional ranks。輸入列順序不影響結果／provenance hash。相同 Core manifest hash／snapshot／membership／feature version／date bounds 在昂貴 read 前 reuse，成果與 receipt immutable、90 日 derived retention；不呼叫完整五 specialist／training／CEO。操作與切換限制見 [screening runbook](../runbook-market-screening.md)，完成狀態仍以 runtime evidence 為準。

使用者 2026-10-03 指示：500 檔缺失比例 ≤10%（含恰好 50/500）可接受；超過時標記 `discussion_required`，不中止或直接判整批失敗。每檔最新交易日、價格、成交量及成交金額必須合格且對齊，否則算該檔 EOD 缺失；各歷史窗口另外列缺失比例，模型未訓練不算行情缺失。缺失仍保留 null，PIT/來源不合格資料先排除後計入缺失。

補資料共用既有交易所全市場日期批次，不建立新 fallback 或調度系統。正式 liquid-500 目前為 TWSE-listed-only，依實際 membership 選市場，不自行擴成上市櫃混合池。先使用已有資料與短批次，品質過差先討論，不為了填滿每欄展開複雜歷史補資料。

Deep Coverage 使用既有去識別化資料庫函式取得 active watchlist ∪ effective holdings，去重、離榜持股保留、清倉且不在 watchlist 才退出。完整五 specialist 只對 Deep Coverage 執行，並依 input change／dirty dependency 增量更新，不因每日 screening 而把 500 檔全部深算。成果物不包含 owner、持股數量、成本或損益。

所有輸入以 Core immutable manifest / table snapshot、availability / publication / observation 時點、provenance 與 source authorization 驗證；未合格資料不進特徵。缺資料及未驗證模型明示 partial / blocked，不填假機率。

使用者 2026-10-03 最新指示取代歷史財報的嚴格可用時間門檻：**有官方資料就進行歷史模型驗證**，不因原始數值版次／當時公開時間未證明而禁止 Fundamental OOS。模型回放每期最新取得的官方數值版本，先用 authoritative publication，其次官方申報附件上傳時間；兩者皆缺時，以財報期末後 90 天作明示估計。Core 保留實際取得時間、unknown 與原始數值，不改寫 canonical 歷史；訓練使用有版本的時間投影。成果物保存 `financial_history_policy`、時間依據筆數與 `strict_pit=false`，明示可能包含後續修正與估計時間。這是正式採用的資料優先 OOS 方法，可用於模型比較；報酬標籤成熟／purge、來源授權、股號／期別／單位檢查與私人資料隔離繼續生效。模型是否有效依實際結果，不因放寬而自動 promotion。

## Analytics compute boundary

2026-10-06 起，B 組採 [Iceberg canonical + BigQuery analytics hybrid](../decision-2026-10-06-bigquery-analytics-over-iceberg.md) 作為優先架構。這是 target contract；目前 implementation 是否已切換仍以 `main` code／runtime evidence 判定。

- Core Apache Iceberg V2／GCS 維持 canonical／PIT／provenance/history；既有 PostgreSQL-backed PyIceberg `SqlCatalog` 不因文件決策自動遷移。
- PostgreSQL serving projection 維持 User／Admin request-time hot path；BigQuery 不作 Flutter page-load database。
- Specialist data access 必須先抽象成 exact-snapshot reader；PyIceberg reader 是 reference／fallback，BigQuery adapter 只有在同一 immutable Core snapshot fidelity 可證明後才可逐 workload 切換。
- BigQuery 優先處理**每日盤後** liquid-500 screening、cross-sectional ranking/window/join、OOS/evaluation preprocessing 與 ML training dataset preparation；不預設複製完整 Core warehouse。
- **禁止 BigQuery Storage Read API**：不依賴 `bigquery.readsessions.*`／`google-cloud-bigquery-storage`。小型結果使用一般 query/result API；大型 training input 先在 BigQuery SQL 縮減，再輸出 versioned GCS Parquet artifact 供 Python/ML Job 使用。
- BigQuery intermediate／destination table 預設 bounded／TTL／可重建且屬 derived/research；不要求把每個中間結果再寫回 canonical Iceberg。大型 training/evaluation dataset 以 versioned GCS Parquet 固定，只有已有 publication／retention contract 的成果才永久保存。
- 每個 BigQuery-derived artifact 必須保留可追溯的 Core snapshot identity、analysis_as_of、schema/feature/model version、hash/provenance；不能只保存「latest」語意。
- Query 必須 column/date/symbol/partition bounded，並記錄可取得的 processed/billed bytes、elapsed、fallback 與輸出規模。未知成本不補 0。
- 目前 Google legacy Iceberg external table metadata-URI 路徑不作預設正式解；BigQuery compatibility spike 應優先驗證 Google-supported shared Iceberg/Lakehouse path或其他可證明 exact snapshot 的方案。任何 catalog migration、API enablement、新計費資源或 IAM 擴張仍需人工授權。
- 若 BigQuery 不能保持 exact-snapshot／PIT／provenance contract，該 workload 必須留在 PyIceberg；效能理由不得覆蓋 canonical correctness。

### Exact-snapshot reader contract

`AnalyticsSnapshotReader.read(manifest, requested_symbols, core_snapshot_id=..., row_limit=...)` 回傳 `AnalyticsSnapshot`，包含明確的 Core snapshot identity、datasets 與 read telemetry；`close()` 釋放 reader 持有的 catalog connection。Specialist runtime 透過 `reader_factory` 注入 reader，預設使用 `IcebergSnapshotReader`；`load_core_datasets()` 保留為相容入口。

PyIceberg reference reader 必須先比對 manifest 與要求的 Core identity，再依各 table 的固定 `snapshot_id` 讀取，不改讀 latest。保留 symbol filter、null、原始欄位型別與 `__table_identifier`／`__snapshot_id` provenance；超過總 row limit 必須拒絕，不能悄悄截斷。PIT／source authorization 仍由既有 specialist validation 處理。Runtime 在成功或失敗後都關閉 reader，且拒絕 reader 回傳不同 Core identity。未知 GCS bytes 保持 null；此契約不代表 BigQuery adapter 或自動 fallback 已完成。

## 成果物

新 `specialist.v1.json` 定義 Fundamental / Valuation / Quant / Risk / Event。財務可比值、PE/PB/殖利率、動能、波動/CVaR/回撤/對齊 beta、事件數與嚴重度採確定性計算；中文報告使用規則模板。DCF/reverse-DCF 有嚴格計算函式，但真實 Core 未提供完整每股自由現金流與核准假設時回報缺值。

`specialists/<output_hash>.json` 與 execution manifest 不可變、寫入後讀回驗證；相同 execution replay 只驗證並 reuse。B4 已完成 cross-execution dependency cache：cache identity 納入 symbol/role、accepted + rejected PIT dependency state、feature/engine/model version；只有 dirty specialist 重算，clean role reuse immutable artifact，並保留 source Core snapshot identity。2026-10-07 真實 dev acceptance 在同一 Core snapshot 第二輪達成 0 computed / 25 reused。2026-10-08 B5 ML/OOS data path 已由 BigQuery TEMP staging → versioned Parquet + Cloud Run Mart 真實驗收結案（10,978 rows／499 symbols／immutable hash 相等，見 [B5 結案](../archive/group-b-b5-ml-oos-data-closure-2026-10-08.md)）；月度 reconciliation 與後續模型品質仍未完成；B6 derived artifact cache 已 CLOSED（見 [B6 結案](../archive/group-b-b6-ml-oos-cache-closure-2026-10-08.md)）。

### B6 ML/OOS derived cache

僅對 B5 SQL reduction 的 `core.ohlcv_v1` snapshot/pointer、analysis_as_of、日期邊界、schema/query/feature/model version、label horizon、cohort stride 計算 `b6-ml-oos-dirty-v1` identity；新增來源必須更新 dependency contract，不可默默重用。global Core snapshot 若因非依賴資料表改變，可重用相同 source snapshot 的 immutable Parquet，但一定保留原始 artifact Core identity，另列 requested identity。

快取命中前必須驗證實際 GCS shard SHA256、bytes、manifest、retention 保護與 catalog pointer；掃描上限 128 manifest、驗證 240 秒上限，fail closed。命中才可記本輪 BigQuery billed=0；cache miss 維持原有 1 GiB execution budget／每 query 60 秒；失敗未知 billed bytes 為 null。B4 五 specialist cache 不改變。已由 CI #37708769385（137 PASS）與 live #37708769182（GCS immutable hit verified、BigQuery jobs 0／billed 0、Cloud Run Mart hash readback PASS）驗收 B6 scope。無關 Core 更新和相依資料 dirty invalidation 由 targeted tests 驗證；B7/B8/B9 仍未完成。

## 歷史模型

Linear / LightGBM / CatBoost 使用逐月擴張訓練窗，訓練標籤必須已於測試日前成熟；每 5 個市場交易日建立候選訓練樣本，5/20/60/120 日樣本外 cohort 不重疊，以 benchmark 交易日對齊起訖。至少 100 訓練樣本與三個訓練月份才能 fit。最後三個已成熟月份可獨立校準機率，不能使用當月測試資料；LightGBM/CatBoost 使用原生 Tree SHAP，Linear 使用加總式貢獻，必須重建同一預測。Rank IC/ICIR、decile spread、hit rate、after-cost Sharpe / drawdown / turnover 可計算；不足 10 檔不造出 decile 統計，另列各深度標的時間序列 IC/命中率，校準驗收需至少 30 筆 OOS 機率。30 bps 僅研究敏感度，不是實際券商成本。回測僅 current Deep Coverage，不是歷史母體重建，禁止自動 promotion。

Riskfolio-Lib 計算歷史 CVaR；statsmodels 二狀態 Markov variance challenger 需至少 252 筆 benchmark returns。逐月用此前參數 forward filter（不用事後 smoothing），以 OOS log score 比較簡單 Gaussian 波動基準；至少 30 筆 OOS returns 才標示已評估，沒有自動 promotion 或正式 regime probability 權限。

Fundamental/Valuation 共用既有成熟價格標籤。Fundamental 依上述資料優先時間投影驗證，不再因原始版次／公開時間未知而阻擋；缺必要數值才回報 `insufficient_financial_features`。Valuation 的官方每日估值沿用日期 fence；缺數值回報 `insufficient_pit_financial_features`。Fundamental LightGBM 使用同一份官方財報的當期／去年同期基本 EPS 與歸屬母公司獲利年增率；核對公司、合併口徑、concept、期間與單位，優先單季、其次同期間累計，前期為零則缺值。公式為 `(當期−前期)/abs(前期)×100`，負前期代表相對前期絕對值的改善／惡化。`same-filing-comparatives-v1` 保留比較期間、數值、context 與原文 hash；EPS 僅標示報表內比較，不宣稱跨報表股數可比。原始 EPS 跨版本趨勢仍在股數口徑未知時回報 null。Valuation 使用官方每日 PE/PB/殖利率的 LightGBM／CatBoost。此 bounded baseline 不代表完整財務品質特徵或 DCF 假設已齊備；PPE 支出也不冒充完整自由現金流。

歷史估值沿用既有 Stage/Core ingestion，從 TWSE `BWIBBU` 個股月查詢讀取，僅補 Deep Coverage、最多 36 月；驗證月份、公司名稱、欄位、每日日期與非負有限比例，虧損造成的缺 PE 保留 null。每筆保存官方日期與 Stage provenance，日常 data-supplement 核對最新月份並重用既有資料，月度 specialist-retrain 固定 Core snapshot 後驗證。成功來源與比較特徵直接納入正式模型作法，不依賴獨立驗收腳本。

Quant 增加 Qlib v0.9.7 的單一 DoubleEnsemble bounded adapter，保留 MIT license 與原始來源 SHA；不引入完整 Qlib tracking／data provider。固定三個子模型、20 rounds、seed 17、single thread，保留 sample reweighting 與 feature selection，ensemble 原生 Tree SHAP 必須重建同一預測。IC decay 以同一 OOS signal 對 5/20/60/120 日成熟結果的各股時間序列 Rank IC 評估；不足 20 筆保留 null，重疊長窗口結果不當成獨立報酬樣本。

月度 challenger／OOS 使用 `specialist-retrain` operation；B 組 target schedule 固定為**每月第一個週六台北 10:30**，在 ingestion／data-supplement 成功後執行，沿用 1 CPU／1 GiB Mart Job。B 組實作需同步修改實際 Scheduler／controller definition 並以 runtime readback 驗證；歷史 runtime 只由 operations 保存，不在 active SPEC 重述舊排程。從既有 Core bucket 選最新 immutable manifest 並固定 raw-byte hash，超過 7 天或未來日期拒絕執行；手動重跑同 operation 產生新 execution。資料不足仍回報 insufficient_history，不視為模型通過；不自動 promotion。Event 依標記資料另行驗證，尚未具備的 classifier 不因共同批次而宣稱已重訓。快取／月度 reconciliation 依 active TODO 的後續 WBS 處理。

尚未完成：Fundamental/Valuation 的新版資料回補、資料優先 OOS 與真實 dev readback、台灣繁中 Event 人工標記資料與本機 encoder、歷史 membership replay 與 champion promotion。原生 SHAP、機率校準、regime OOS、Qlib 與金融特徵 evaluator 已有實作；是否已部署、具足夠真實台股資料及有效性，仍以 operations 的 dev／readback 結果判定。這些缺口使 WBS 保持 partial。

## 依賴與資源

LightGBM 4.6.0 MIT、CatBoost 1.2.8 Apache-2.0、Riskfolio-Lib 7.0.1 BSD-3、statsmodels 0.14.5 BSD、NumPy 2.2.6 BSD、scikit-learn 1.7.2 BSD-3。pandas 固定 2.3.3，避免 pandas 3 與 statsmodels 0.14.5 相容性錯誤。全部 Python runtime 依賴 pin version 並 hash lock，模型 fit 固定 seed / single thread，沒有下載遠端模型或執行 upstream 範例。

Cloud Run Job 固定 1 CPU / 1 GiB、單 task、單 parallelism。真實 acceptance 記錄 elapsed_seconds 與 peak_rss_mib；未確認需求前不提高資源。免費 pip-audit 2.10.1 掃描 83 個鎖定依賴，修正 urllib3 三項已知漏洞後固定 2.8.0，重掃沒有已知漏洞。此結果不保證未知漏洞或 container OS 安全；禁止付費 Artifact Analysis。

## 本次核准的簡單補資料

使用者選擇僅補最近 21 個交易日（2026-09-02 至 2026-10-02，扣除週末及官方 09-25/09-28 休市），共用既有 TWSE 全市場日期批次與既有 dev ingestion Job；不新增來源、排程或資源。市場行情中不合格列退出 OHLCV，仍記錄缺失/隔離，不使其他合格列一起失敗。Core manifest 以現有 data mutation lock 擷取所有 public Core table fence，價格更新不丟掉未改變的財報/事件 snapshot；backfill analysis_as_of 採本次接收日期，不假裝當年已接收到資料。Mart PIT 日界線統一採台北時間 EOD。

篩選排名統一使用 5 日報酬的規則分數；20/60/120 日報酬另外列示，不因可用歷史長短而混用不同窗口排名。此分數是 discovery heuristic，不是預測機率；長期歷史或模型驗證不足維持缺值。

使用者後續核准補足長期模型與回測，並再次確認 500 檔仍只補輕量資料。500 檔僅補足 60/120 日篩選窗口所需的市場價格/量/金額與 benchmark，市場補歷史上限 241 個日曆日；不做 500 檔財報/事件或五模型深度分析。多年（最多 36 月）價格、財報與模型/OOS 補足僅限 active watchlist ∪ effective holdings；沿用既有 Stage/Core/Job，缺失 >10% 保留有效資料並先討論。

資料容量沿用既有清理機制：已提交 Stage payload 7 天、一般 Core 行情 365 天、財報 12 季。僅 active Deep Coverage 的 OHLCV、估值與大盤 benchmark 延長到 1096 天，避免多年回測資料被一般清理規則移除；退出深度覆蓋後回歸一般上限。保留政策須由既有 retention Job 執行，不代表設定後立即回收；manifest 引用的歷史 snapshot 仍受保護。
