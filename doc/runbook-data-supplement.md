# 資料補充與週六檢核操作

> **2026-10-24 研究精簡決策優先**：本文涉及獨立資料稽核、逐來源補證、全歷史 PIT／精確時間校準、例行週月稽核及自然驗收等待的要求已取消，不再是待辦或發布前置。依 [研究精簡政策](spec/research-simplification.md)，保留必要日期／單位、基本防洩漏與操作安全；歷史證據不改判 PASS。


更新：2026-10-19。正式資料治理、row retention、current-only snapshot 和排程表請先讀 [統一治理入口](spec/data-governance.md)；總控操作另見 [批次 Runbook](runbook-batch-controller-dev.md)。此檔只管理**補資料模式／來源／佇列／安全重跑與驗收**，不創建另一支 Scheduler 或第二份 TODO。第三方可直接補收的正式核准見 [PROJECT_RULES §1.7](PROJECT_RULES.md)。

## 兩條資料補充機制（不要混成單一路徑）

| 機制 | 執行入口 | 預期行為 |
|---|---|---|
| 每日增量／歷史修復 | 既有 `data_supplement.py::run_backfill`，`JANUS_DATA_SUPPLEMENT_MODE=daily|backfill|fundamental-history|valuation-history` | daily 於08:30補缺與變更；歷史 repair 按已核准股票/月份有界修復 |
| 新增持股／關注背景需求 | `stock_supplement.py::run_pending`，`JANUS_DATA_SUPPLEMENT_MODE=demand`；08:30 daily 亦執行佇列兜底 | API 提交去識別化 symbol demand 後才背景取數，generation/lease 防舊需求重覆；部分資料 ready 不包裝全項 ready |

兩條路徑**共用**來源授權、Stage raw/receipt、合法 schema、Core 版本化與 serving/API readback，但現有 `run_backfill` 的部分 TWSE/MOPS 限制**不等於** `stock_supplement` 的 TWSE/TPEx＋FinMind/Yahoo 規格。新需求的驗收請依 [目前 TODO](todo.md) 的 2026-10-19 收據；不要以舊的「六股 EPS」checkpoint 否定新背景補收工項。

**補收閉環**：確定資料集/股號/合法期別及 Core 現有可用值 → 只對缺口取來源 → Stage raw/hash + source_id/URL/receipt → period/unit/adjustment/來源口徑驗證 → Core 去重/更正版次 → serving/API讀回 → Admin/Readiness 更新與失敗類別。來源未發佈、限流、新上市與ETF不適用，應列 partial/not_applicable，不補零、不把本次抓取時間寫成歷史公告時間；Job terminal success 不等於每檔資料 ready 或自然 Ledger 成功。


本文件對應 `WBS-3-DATA-SUPPLEMENT-V1`。順序為首次回補 → 每日增量 → 週六獨立檢查。使用者採「有資料優先」：缺期與未知公告時間如實呈現；不得把本次取得時間倒填成歷史公告時間。

## 補收來源選擇（2026-10-18 最新）

依 [PROJECT_RULES §1.7](PROJECT_RULES.md)，可直接使用Yahoo等第三方公開資料，無需先窮盡官方來源或重建官方分母。先取已有可用的資料，不指定Firecrawl；優先直接HTTP或既有工具。第三方頁面的單季EPS可原值補入，但必須保存來源URL、取得時間、raw/hash、symbol／季度／單位；累季、年度、預估與單季分開，分割／減資口徑不明不冒稱可比。沿既有來源識別、Stage/Core、冪等與serving驗收，不冒用`mops`；文件核准不代表adapter已部署。下列MOPS程序保留作已實作路徑，不是補收唯一入口；不擴大TODO的股票／期間或增加排程、付費來源。

## 新持股／關注股補收契約（2026-10-18 使用者新增需求）

新增持股或關注股後，目標是立即建立去識別化股號補收請求，由背景工作補齊資料；不等待翌日08:30，也不讓來源HTTP阻塞記帳／關注操作。每日08:30既有data-supplement作漏單、缺期與失敗重試的兜底；依賴批次未成功時可能延後，不承諾08:30所有股票已補完。即時指立即排入背景補收，不保證第三方尚未發布的資料即時存在。

| 資料 | 可直接使用的第三方入口 | 補收邊界 |
|---|---|---|
| 日價量 | FinMind TaiwanStockPrice；Yahoo歷史chart可作後續替代 | 至少120有效交易日；標示供應者價格與還原口徑，不冒稱官方未還原價 |
| 月營收 | FinMind TaiwanStockMonthRevenue；Yahoo股市營收可作後續替代 | 至少13個應到月份供同月YoY；辨識當月欄，不取累計欄冒充 |
| 單季EPS | Yahoo股市單季EPS | 最近12個已發布季度；不混年度／累季／預估，不要求官方股數分母 |
| PE／PB／殖利率 | FinMind TaiwanStockPER | 兩年河流按既有有效日／月份規則驗收；非正PE不捏造 |

可重用既有可用資料，缺口直接取第三方，不必逐檔先找官方。ETF等不適用營收／EPS者標示不適用；來源未發布、限流或新上市歷史不足保留partial。以上是新增需求的驗收契約，**目前六股EPS定向補收不等於這條自動化已完成**；需另驗新增／取消持股與關注、去重佇列、失敗重試、每日兜底及Stage→Core→serving→API讀回。公開控制面只能保存股號及需求狀態，不保存Owner對應、股數或交易內容。

實作路徑（部署狀態依TODO／runtime）：先套 `066_stock_supplement_queue`，再更新 Jobs，最後切換 API。新版本預設啟用；`JANUS_STOCK_SUPPLEMENT_ENABLED=false` 可停用 API 喚醒與 daily 新路徑。記帳／更正／沖銷完成 current_positions 後，以及關注／取消關注的同一交易內，重算去識別化需求聯集。任一持股或關注仍存在就保留需求；最後需求取消才遞增 generation 並取消舊 lease，不刪既有歷史資料。

API 回應後才喚醒既有 ingestion Job，以 `JANUS_DATA_SUPPLEMENT_MODE=demand` 處理最多50股／約20分鐘；單股來源尚未發布、限流或工作失敗保留partial，24小時後重試，每日08:30在原增量前重算聯集、補漏並重排前一日結果。中斷的 running lease 35分鐘後可重新領取；相同股號不重複處理，取消／重加後的舊工作不能結案新 generation。來源HTTP期間不持有Owner交易或佇列的長交易鎖。個別已開始的公共Core寫入不因取消需求回滾；下一個安全邊界停止，舊lease不能覆寫新請求結果。

FinMind使用公開免token入口，不新增訂閱。Core保留月營收月份metric，serving以`canonical_metric`保留映射並顯示`monthly_revenue`；保留元與千元轉換、供應者source_id、實際receipt、raw/hash與原lineage。兩年profile接受既有TWSE／TPEx與核准FinMind資料；第三方profile明示provider版本，不宣稱官方認證。財務serving保存至少1096天，以容納12季；Core的current-only snapshot保留政策不變。

## DRL-01：既有官方 MOPS 市場月份批次回補（2026-10-16 新增）

此程序修補全市場過去僅約5股具13月營收深度的缺口；沿用MOPS同一官方來源、現有Stage/Iceberg及dev Cloud Run Job，不啟用新API／Scheduler／付費供應商，不動Owner帳本。程式 `scripts/gcp/drl01_revenue_history.py`、版本化請求 `ops/drl-01-revenue-history-request.json`、workflow `.github/workflows/drl-01-revenue-history.yml`。

1. 只改現有請求的 `months` 為**不超過兩個遞增月份**（2025-08～2026-09），`market=TWSE`或經核准的`TPEX`、`approved=true`及各安全旗標保持原樣；每次變更 `request_version` 並 commit main。**TPEX `/nas/t21/otc/` 路徑已有相同來源適配程式與測試，但尚未真實 canary，必須先用單月正式Core讀回才可擴到更多月份；TWSE合格證據不能推定TPEX已通過。**
2. 專用workflow與其它writer共用 `janus-dev-runtime-writers`；前一Writer必須已終態後才持續遞交多批請求。GitHub同群只有一個pending位置，過早送下一個會使先前pending取消；取消的工作不可算PASS。
3. 工作流程核准原始HTML archive、ROC年月及千元單位、驗證官方symbol/name／數值，Stage不可變raw及真實receipt後才批次Core寫入 `monthly_revenue`（`TWD_thousands`）。歷史公布時間unknown不得用抓取時間假冒原始官方公告。同值重跑應reuse，按月份的snapshot獨立讀回。
4. 每月收據看 `source_valid_rows`／`after_covered`／`inserted`／`reused`／`quarantine_counts`／`snapshot_id`；上市≥90%、上櫃≥70%分別判PASS，其餘標PARTIAL或ERROR並追原因，不以GitHub步驟成功取代Core讀回。要真正做YoY，仍需每檔**13個連續應到月份**、分市場覆蓋及算式讀回；本項優先求有效資料，不造未知月／缺值。
5. 流程回歸：`tests/test_drl01_revenue_history.py`、`tests/test_feature_readiness_repair.py`與現有官方資料測試。全部月份確認後才算DRL-01B完整覆蓋；定期Data Readiness Ledger需要新版Jobs發布及Admin實機讀回，與此一次性修復不同。

## 首次回補

程式入口：`jobs/ingestion-core/ingestion_core/data_supplement.py` 的 `run_backfill()`；Cloud Run 入口：`runtime_entrypoint.py` 的 `JANUS_DATA_SUPPLEMENT_MODE=backfill`。使用既有 dev `janus-ingestion-core` Job、原 Stage/Core bucket 與 PostgreSQL control/catalog，不新增資源。

先確認 main 的 CI、部署及 Job image 已符合本次版本，並確認沒有 ingestion execution 還在執行。以下為 PowerShell；使用已登入的 gcloud，Secret 由既有 Job 參照，不貼入命令。

```powershell
gcloud.cmd run jobs executions list --job janus-ingestion-core --project gen-lang-client-0593591102 --region us-central1 --limit 5
$sdk = 'C:/Program Files (x86)/Google/Cloud SDK/google-cloud-sdk'
& "$sdk/platform/bundledpython/python.exe" "$sdk/lib/gcloud.py" run jobs execute janus-ingestion-core --project gen-lang-client-0593591102 --region us-central1 --update-env-vars='^|^JANUS_DATA_SUPPLEMENT_MODE=backfill|JANUS_DATA_SUPPLEMENT_SYMBOLS=1102,2327,2330,4958,5876|QUEUE_CONSUMER=false|MART_JOB=|ICEBERG_MAINTENANCE_MODE=' --async --format='value(metadata.name)'
```

Windows 的 .cmd wrapper 可能把 ^|^ 參數解讀成 shell 管線，因此上例直接使用 SDK 的 Python 入口。其他環境可用 gcloud 原生入口。

記下回傳 execution 名稱，查此 execution 的完成狀態，不因等待較久再啟動第二個。無指定 symbols 時，採既有 ingestion 的 first-batch focus 與去識別化 portfolio coverage 股號聯集；上限 50 檔，目前回補 adapter 限已核對的 TWSE 合併財報。

原始回應先 Stage，再驗證公司、期別、單位、報表口徑並寫入 Core。財報與月營收採實際 receipt availability；歷史 publication 與原始數值版次維持 unknown。相同觀測值重跑會 reuse，數值變動新增版次。不得覆寫 immutable 原始收據或既有固定研究 artifact；Core 更新只需保證新的 current snapshot 正確可讀，**不保證**上一版 Iceberg snapshot 在 current-only 清理後仍可重播。

五分析師模型補資料使用同一入口：`backfill` 同時補官方每日 PE/PB/殖利率；只補估值可設 `JANUS_DATA_SUPPLEMENT_MODE=valuation-history`，搭配 `JANUS_DATA_SUPPLEMENT_PRICE_MONTHS=36` 與已核准 Deep Coverage 股號，不重抓完整價量／財報。daily 自動核對最新估值月份，且既有財報缺 `same-filing-comparatives-v1` 時重新解析一次；這是來源／特徵版本更新，不把 receipt 倒填成歷史 availability。模型使用同份財報 EPS／母公司獲利同比，原始跨版本 EPS 口徑未知仍保留缺值。

## B9 Fundamental 官方比較值缺口修復（不含 B7 月度重訓）

可在已驗證的新 ingestion image 上使用既有 Cloud Run Job 的 `JANUS_DATA_SUPPLEMENT_MODE=fundamental-history`（須先完成本版 CI／GHCR 部署）。本模式僅重讀核准 Deep Coverage TWSE 股票最近 **12 個官方財報季度**（上限三年／12 期）；已具有同一上傳版次、同一來源文件及同一期別 **EPS 年增率＋歸母淨利年增率** 完整配對的季別跳過；缺配對或新上傳版次才重新取得 MOPS filing index／inline XBRL。**不重抓月營收、估值、股票價量或 benchmark**，也不建立新 Scheduler、新外部來源或額外付費資源。

操作前確認既有 ingestion Job 沒有 active execution；本模式使用原 Core/Stage、source admission、versioned insert/reuse 與 snapshot fence，不修改歷史收件時間或原有 immutable artifacts。設定的股票必須來自已核准 Deep Coverage；例如既有五檔的 `JANUS_DATA_SUPPLEMENT_SYMBOLS=1102,2327,2330,4958,5876`。如發現官方報表本身沒有合格比較值，允許該季保持缺值而非推定為零，失敗原因記錄在 `failures`，本模式為手動有界修復、不排入每日重試。

`coverage` 現增加 `fundamental_comparative_quarters` 與 `fundamental_missing_comparative_periods`。需分別確認官方財報 12 季可用性、真正雙特徵合格季別數、來源時間分布及 OOS 成熟標籤數。這些是缺口追蹤，不是 Fundamental LightGBM 勝過零訊號／規則基準的證據。重新 evaluation 須由 B9 獨立流程使用同一 Core fence、immutable 成果和 PIT/source authorization，禁止重送 B7 月度 retrain 或升級模型。

## 驗收與失敗處理

1. 執行成功仍須讀取 Core 的財報季數、月營收月數、價格交易日數，以及完整 Core snapshot manifest；不能只看 Cloud Run 成功。
2. 來源失敗或資料不足顯示 partial，保存安全的 dataset、股號、期別與錯誤類別。原始 HTML/JSON 僅在受控 Stage 排查，不得貼入公開 GitHub 或 Admin。
3. 要驗證 Mart consumer 時使用既有 `janus-intelligence-mart` 的 deterministic/AI-disabled 路徑，確認 feature version 2、收件時間、同日行情對齊與 missing reason；本作業不授權額外模型呼叫。
4. 修正程式後跑相關 targeted tests，執行 `/ponytail-review`，commit/push 由現有 dev CI/CD 部署；重跑前確認舊 execution 已結束。

## 每日增量與週六檢查

程式已接線，是否正式啟用以 [TODO](todo.md)／[status](status.md) 與最新 dev evidence 為準。總控定義在 `jobs/ingestion-core/ingestion_core/batch_controller.py` 的 `BATCHES`，沿用既有每小時 :30 總控 Scheduler，不另建 Scheduler：

| 批次 | 台北時間 | 入口／依賴 |
|---|---|---|
| data-supplement | 每日 08:30 | `JANUS_DATA_SUPPLEMENT_MODE=daily`；等待 07:30 ingestion 成功 |
| Mart | 工作日 09:00（下一個 :30 tick 派送） | 等待 ingestion 與 data-supplement 成功；本 WBS 使用 AI-disabled |

每日 `run_backfill(incremental=True)` 先讀 Core：只抓首次缺期、申報上傳時間變更；月營收補缺期並重新核對最新已到期月份，行情依既有交易日曆檢查最近 121 個交易日，只重抓缺失日期所在月份；已由 ingestion 補齊就略過行情與 benchmark。歷史財報完整時只查最近兩年的申報索引，較舊期別僅在缺期時查詢。同值 reuse；新增／修正才送新的 Core ready/Mart 請求，沒有變動就完成檢查。財報按個股合併 Core commit，每筆仍保留各自 Stage provenance。當期尚未公告的月份不算缺期。

`data_quality.py::run_quality()` 已退役，只回 skipped；不重抓、不寫 Stage、不更新品質帳本。

## 收到 Admin 異常後如何處理

Admin 已移除例行品質卡；舊資料只作歷史，不要求調整排程或追查。實際資料錯誤按具體股票／期別處理。

## 修復或重建每日排程

1. 從目前 main 讀 `data_supplement.py`、`financial_publication.py`、`runtime_entrypoint.py` 和 `batch_controller.py::BATCHES`，依上表核對 daily/quality mode、dependency、exclusive guard。週六異常是要求檢視，不直接改動總控或放寬驗收。
2. 先驗證：`PYTHONPATH=.:jobs/ingestion-core:jobs/intelligence-mart python -m pytest -q tests/test_data_supplement.py tests/test_data_quality.py tests/test_batch_controller.py tests/test_duckdb_iceberg.py`（PowerShell 的 PYTHONPATH 分隔符為分號）。Admin 改動加跑 `flutter test test/admin_overview_batch_test.dart` 與 `flutter analyze lib/admin.dart`。
3. 執行 `/ponytail-review` 後 commit/push，由 `.github/workflows/deploy-dev.yml` 部署既有 dev ingestion Job。確認 CI、immutable image 與 Ready；不得建立新資源。
4. 更新既有 `janus-batch-controller` 的 image 為已部署 ingestion 的 immutable image；**保留原 `BATCH_CONTROLLER_MODE` 與 `BATCH_CONTROLLER_NOT_BEFORE`**。若用 `prepare-batch-controller-dev.py` 產生 manifest，其預設是 observe，必須帶回現有值再 replace。不要直接套預設 manifest，也不要以 cutoff 改寫／刪除既有 occurrence。
5. 唯讀核對既有 Scheduler 指向總控且仍為台北時間 `30 * * * *`、active 狀態正確；不要另建第二個 daily Scheduler。確定無 active ingestion／controller 後，跑 daily，再跑 quality，讀回 Core 與 Admin；檢查 `needs_daily_schedule_adjustment` 是否清除，觀察下一個自然 daily／週六 occurrence。
6. 只在實際部署與讀回後更新 evidence。若來源仍不足，保留 coverage/partial 與安全理由；不得把 queued、build 或手動單次成功當成自然排程已驗收。


月營收使用 MOPS 官方歷史彙總 HTML（一般上市 `_0` 與 `-KY` 公司 `_1`），每個市場分類、月份下載一次並共用。採 cp950 解碼，核對公司、期別與千元單位後轉為 TWD；不把取得時間當成歷史公告時間。

五分析師歷史 OOS 依使用者最新核准採資料優先：不要求原始版次／公開時間已證明。Mart 的 `financial_training_history` 只投影訓練時間，Core 實際 receipt／unknown 不變；已知公開／上傳時間優先，缺少採期末後 90 天假設，evaluation 保存政策與依據筆數。正式 daily 資料及每月 retrain 直接使用這個方法。
