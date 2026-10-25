# Janus 2.0｜04 Valuation 估值參考區間功能子契約

> **2026-10-24 研究精簡決策優先**：本文涉及獨立資料稽核、逐來源補證、全歷史 PIT／精確時間校準、例行週月稽核及自然驗收等待的要求已取消，不再是待辦或發布前置。依 [研究精簡政策](research-simplification.md)，保留必要日期／單位、基本防洩漏與操作安全；歷史證據不改判 PASS。


狀態：**PARTIAL／RV-01_STATIC_MAPPED／RV-02_CODE_CI_PASS／RV-03_LIVE_INPUTS_READ_WITH_GAPS／RV-04_MART_FACT_PACK_API_OFFLINE_PASS／RV-05_UI_PENDING／RV-06_DEPLOY_DEFERRED**（2026-10-25：兩檔真實來源已取樣；Mart／Fact Pack／API 程式接線完成、離線 CI 通過；UI 及 live 發布未執行）。
權威邊界：[PROJECT_RULES](../PROJECT_RULES.md) → 本 SPEC → [WBS 工作線／依賴](../wbs.md) → [唯一 Active TODO](../todo.md) → [實機收據](operations-and-testing.md)。
已被最新決策取代的歷史 AI 指令（僅供參照公式與 UI，**不可執行第五角色開發**）：[Drive《第五模型：估值參考區間》](https://drive.google.com/file/d/1M7pxgkeyzK_Joi4C9Z2aTSRCgdV-u5YO/view)；[Janus 2.0 報告](https://drive.google.com/file/d/15sT38MsE96RAwD-aZnAHvOvEINtythPO/view)。Drive 是核准設計參考，GitHub `main`／runtime 才是實作與完成證據。

## 1. 角色與授權邊界

- 正式模型僅 Quant／Risk／Fundamental／Valuation。撤銷獨立 `valuation_range`／Event 第五模型、訓練、Registry role 和新排程；04 Valuation 接手本情境功能，保留現役 event API／資料、公告時間、公司行動、修訂去重與 A-CHANGE 提醒。
- 04 保留 PE/PB XGBoost 倍數研究、殘差及比較，同時提供唯一「參考價格區間」。共用財報 EPS/BVPS、歷史倍數、來源時間、單位、PIT、公司行動及 publication/rollback；沒有第五組 canonical 價帶或第五個模型。CEO 仍是整合層。
- 04 的區間子功能是可重算的確定性倍數情境，非 ML 未來報酬／信賴區間／交易建議。**不依賴 04 XGBoost 已 DEPLOYABLE**，但有自己的輸入／算式／授權／發布 gate，不是免費升級成已發布模型。
- Research-only 材料不得直接替代正式 Core／serving 的授權、PIT、來源與可得時間；不編造 EPS、BVPS、季報或歷史倍數。新付費或擴權依 PROJECT_RULES §1.3。

RV-01 已完成 [現役 reader 靜態清冊](../research/valuation-rv01-serving-readers-2026-10-24.md)，真實樣本／BVPS 來源覆蓋仍待補。RV-02 已新增 [純函式](../../packages/valuation_range.py) 及 [16 項測試](../../tests/test_valuation_range.py)，[CI #40096160077](https://github.com/tommylin15/janus-omniforge/actions/runs/40096160077) PASS（已補未來財報季度／period end 排除）；RV-02 目前是內部計算，不代表下列完整介接回傳欄位或發布已完成。RV-03 已新增 [既有 Core/Serving 唯讀接線](../../jobs/ingestion-core/ingestion_core/valuation_range_inputs.py)，及 [13 項 targeted tests](../../tests/test_valuation_range_inputs.py)，[CI #40097413271](https://github.com/tommylin15/janus-omniforge/actions/runs/40097413271) PASS：保留 Core 最後交易日原始日期、只取完整月份與 60 月窗口、從既有 Serving 讀單季 EPS／BVPS、沿用 Control 來源授權；不新增研究補收或每日 Job。直接 Dev 取樣見下方 #40166649960；兩檔都缺正式價帶條件，不能宣稱每日上線。

## SEQ-05 部署前差異與真實樣本收據（2026-10-25）

- **權威依據**：GitHub `main` 上 `packages/valuation_range.py`（RV-02）、`jobs/ingestion-core/ingestion_core/valuation_range_inputs.py`（RV-03）、`jobs/intelligence-mart/intelligence_mart/product_runtime.py`（目前既有 Fact Pack／私人產品）、`services/api/analysis.py`（現有已驗 hash 的產品讀端）。`publication.stock_valuation_five_year` 的「兩年每日分布」不是本功能需要的「60個月逐月月末」，禁止沿用它直接冒充24個月。
- **真正 Dev 取樣已執行**：[`#40166649960`](https://github.com/tommylin15/janus-omniforge/actions/runs/40166649960)，source SHA `8081010afeb07b010baf2605968825036733187c`；沿用既有 `janus-ingestion-core` 的一次唯讀 override，PG Serving／Core 讀取成功、Job 範本指紋不變、資料異動0、Core current snapshot `6880250134433223964`。取樣資料截至2026-10-24，對象限2330與2882；沒有長期覆蓋結論。
- **2330**：245筆Core估值／54筆Serving financial；實際可見月末 PE 共12個（2025-10至2026-09）；原始函式在EPS缺失時提早返回`valid_month_count=0`，但`month_end_observation_dates`清楚顯示12個。單季同口徑四季 EPS 不足，`status=missing`／`four_quarter_eps_missing`，`lower/mid/upper=null`。
- **2882**：18筆Core估值／35筆Serving financial；實際月末 PB 共1個（2026-09）。可用正BVPS缺失，`status=missing`／`bvps_missing`，`lower/mid/upper=null`。兩檔 source authorization 的本次探針結果為true，但不能取代未來其他來源的授權；兩檔「普通股／是否金融業」在診斷腳本由顯式股票代碼配置，**尚未由正式分類reader逐筆獨立驗證**，不得視為發布gate PASS。
- **缺值診斷修復**：`packages/valuation_range.py` 已改為即使 EPS/BVPS 缺失，也先計算實際有效月末倍數個數；缺值的價格仍必須是null，`tests/test_valuation_range_inputs.py` 增加回歸。這項修改已由新CI #40167057471驗證，不回溯改寫上述live收據。
- **RV-04 單一卡片投影元件**：新增`packages/valuation_reference.py:project_reference_card`（`valuation-reference-card.v1`）及`tests/test_valuation_reference.py`；[同版CI #40167057471](https://github.com/tommylin15/janus-omniforge/actions/runs/40167057471) 216 passed／1 warning。只轉換經 RV-02/RV-03 驗證且鎖定 `symbol/as_of/core_snapshot_id` 的一份結果。只有 `available` 且24個月／普通股／來源核准／正財務基礎／有序正區間才保留價格；其他狀態數值一律null。它不是第二個估值公式，也不會寫新Canonical、Registry、服務或排程。**此段為最初RV-04純投影階段收據；後續已接入兩檔 Mart／Fact Pack／API 程式，但未部署，Flutter留SEQ-07，整體仍PARTIAL。**

### SEQ-05 最新｜一次性第三方研究補入與直接加總（2026-10-25）

- **使用者已明確選擇簡化口徑**：本版先以現有FinMind Core四季原始單季EPS直接加總，不再為2330逐季調整股票股數。2025Q3 17.44 + 2025Q4 19.51 + 2026Q1 22.08 + 2026Q2 27.25 = **TTM EPS 86.28 元**。這是研究用 `last_four_reported_quarters_simple_sum`，來源FinMind（四季EPS股數口徑可能不同），不是發行人稀釋EPS或法定TTM財報數字；不得用它宣稱正式稀釋EPS相等。資料原已在Core，不需重抓2330財報。實作 `intelligence_mart/valuation_reference.py:simple_reported_eps` 限2330這筆研究範圍。
- **真實一次性補收已PASS**：[GitHub #40172093172](https://github.com/tommylin15/janus-omniforge/actions/runs/40172093172)，既有Dev Job `janus-ingestion-core-lwwg5`，Stage→Core寫入**FinMind TaiwanStockPER/PBR共11筆**（2882，2025-10至2026-08，每月最後交易日），及**Yahoo 2882 2026Q2已公告BVPS=69.37元1筆**（`TWD_per_share`），皆有Stage原始回應、Core source_id／provenance、獨立snapshot與寫入讀回。估值Core snapshot `3874132956674698219`，財務Core snapshot `6504132269236397893`；指定缺漏月份讀回**11/11**、`source_errors=[]`、`status=CORE_INPUTS_COMPLETE`；Job範本不變、新服務／排程0、Owner變更0。來源屬既有核准fallback `finmind`／`yahoo-finance`，在Mart `facts.py` 明確標成 `approved_fallback` 而非官方。
- **不可再派送**：這是一輪Dev研究補資料，不是新常態資料來源。單次請求 `ops/seq05-oneoff-quickfill.json` 已設 `approved=false, closed_after_success=true`，派送程式遇封存請求則回 `SKIPPED_ALREADY_COMPLETED/data_mutations=0`；若需後續更新應由正常批次或新的有界工作定義，不重複執行同一Job。
- **獨立Live讀回再次PASS**：[唯讀 #40172603358](https://github.com/tommylin15/janus-omniforge/actions/runs/40172603358) 讀到最新 valuation snapshot `3874132956674698219`、financials snapshot `6504132269236397893`；按已確認 TWSE 2025/01/22封關交易日，**2330=24有效PE月、2882=24有效PB月**。2882 Core財務讀回 `metric=bvps, fiscal_year=2026, fiscal_quarter=2, value=69.37, unit=TWD_per_share, source_id=yahoo-finance, share_basis存在`。以上為直接Dev Core讀回，不是尚未部署的Mart成品或API正向驗收。
- **功能狀態分界**：輸入資料補齊及程式碼 `Core→Mart analyst_inputs→specialist_product→authenticated API` 已可供下版批次消費，**但這不等於 Mart 成品已在現有 Dev runtime 發布**。目前沒有新的正式 Fact Pack 成品／API正向登入讀回；仍依 SEQ-08 做受控發布及Mart/Fact Pack/API live readback，Flutter/A-CHANGE依SEQ-07。直到正式Mart寫入驗證前，`Valuation full LIVE=PARTIAL`，不能把offline 86.28或69.37直接當成已上線的價帶。
- **驗測**：簡化研究EPS與來源回歸CI [#40172051959](https://github.com/tommylin15/janus-omniforge/actions/runs/40172051959) 226 passed／1 warning；一次性雲端Job前置單測3 passed並由#40172093172產生實際Core收據。FinMind免費授權限非商業使用並需標示來源；若日後轉商業產品，需重新檢查或更換來源，不能視為無條件商業授權。

### SEQ-05 第二輪｜限定兩檔批次與服務端接線（2026-10-25）

**已提交程式，尚未部署：**

- [`intelligence_mart/valuation_reference.py`](../../jobs/intelligence-mart/intelligence_mart/valuation_reference.py) 只對 TWSE 官方分類可核實的 2330（半導體業、非金融）與 2882（金融保險業）啟動估值子功能，來源為臺灣證交所 [2330](https://www.twse.com.tw/pdf/ch/2330_ch.pdf)／[2882](https://www.twse.com.tw/pdf/ch/2882_ch.pdf) 公司資料。不是依股號推斷，也不自動放寬到其它股票；超出兩檔的正式產業分類reader仍需獨立驗證。只有 official `twse/tpex/mops` 走本次靜態批准來源；第三方須日後另接既有Control live approval，不在此憑來源字串自行准予發價。
- [`analyst_inputs.py`](../../jobs/intelligence-mart/intelligence_mart/analyst_inputs.py) 從同一固定 Core snapshot 的 `financials/valuation/ohlcv` 現有 Mart 資料集呼叫 RV-02/03，輸出 `valuation_reference`（`available/missing/limited/blocked`、真月末樣本數、輸入Hash、來源snapshot、方法版本）；**無每次API請求掃Iceberg、無私人持股資料、無新增模型角色**。
- [`product_runtime.py`](../../jobs/intelligence-mart/intelligence_mart/product_runtime.py) 驗證 `symbol/as_of/core_snapshot_id` 與 card 負向門檻後，附加於既有 immutable `private.specialist_product.payload_json` Fact Pack，沿用原 `content_hash`；不新增表、migration或第二套canonical price。
- [`analysis.py`](../../services/api/analysis.py) 讀回已保存產品時驗證 card 與產品身份；[使用者 API](../../services/api/app.py) 新增需登入 `GET /api/v1/me/analysis/{symbol}/valuation-reference`，只從既有 Fact Pack 回傳唯一價帶／缺值；沒有已發布卡就回 `missing` + null，而不是計算任何參考價格。Flutter 卡片與 A-CHANGE 顯示合流交 SEQ-07／08。
- **歷史離線證據**：[分析產品整合CI #40168671019](https://github.com/tommylin15/janus-omniforge/actions/runs/40168671019) 224 passed／1 warning；[DRL-01 專項CI #40168872520](https://github.com/tommylin15/janus-omniforge/actions/runs/40168872520) 79 passed。包含缺 EPS/BVPS、24月不足、非核准來源、跨symbol/snapshot防護與匿名API401。最新 `main` 的其他變動仍須以各自同SHA CI 結果判斷。
- **來源補收與故障收據**：[原補收 #40168882776](https://github.com/tommylin15/janus-omniforge/actions/runs/40168882776) Cloud Run error code 10、0「完成標記的」slice；但 [獨立唯讀 #40169833008](https://github.com/tommylin15/janus-omniforge/actions/runs/40169833008) 確認原執行 `janus-ingestion-core-tsrqq` 在第一段（2024-10～2025-09）實際把 2330／2882 各228筆估值列寫入Core，並非零寫入。新Valuation Core snapshot `3646694772256767088`：2330共473筆、2882共246筆。失敗最終為應用 `RUNTIMEERROR`／容器exit1；對照原程式，Valuation-only仍以「12季財報／營收／OHLCV」完整性把整批標partial，而 `runtime_entrypoint` 對partial以RuntimeError失敗結束。**此為程式鏈推定根因，缺原始堆疊不可包裝成逐行runtime確認。** 已將估值專用partial判斷與正常收取判斷拆開，保留真來源下載失敗的partial。
- **已防重派**：原 `ops/seq05-valuation-history-request.json` 已封存為`approved=false`；[No-op讀回 #40170642020](https://github.com/tommylin15/janus-omniforge/actions/runs/40170642020) `SKIPPED_ALREADY_PARTIALLY_COMMITTED`、`data_mutations=0`。**不得重新送原本兩股兩段月份。** 剩餘最小 PE/PB 補收僅2882的2025-10～2026-08 **11個月**；真正重跑前重新讀回live Core月末清單、Job image是否含修復，再提交新的一次性有界請求，不沿用目前已消耗的授權請求。功能 image 部署仍受 SEQ-08 集中部署規則約束。
- **已修真實交易日例外**：原嚴格7曆日誤刪2025-01-22（距2025-01-31為9天）；[TWSE春節休市公告](https://eshop.twse.com.tw/en/news/detail/8a82e9e69471d3e8019495d5d9dd0018) 確認1/23～2/2未交易。新`valuation_range.py`與RV-03 adapter僅對 `TWSE + 2025-01-22` 承認真正1月最後交易日，不放寬其他日期。2330現有23個有效月加此例外，**新版計算預期24個月**；2882現有12個有效月加此例外預期13個月，仍缺11個月。此為對已讀回Core的離線分析，Dev正式新函式尚未部署，不是新價帶live PASS。
- **Core 財務來源獨立讀回**：[補充唯讀 #40170316886](https://github.com/tommylin15/janus-omniforge/actions/runs/40170316886)：2330 Core financials 542筆（MOPS/FinMind），含同口徑多季 EPS 但 MOPS `eps_single_quarter` 僅Q2／Q3、Q4為`eps_year_to_date`，來源`share_basis_status=unknown`，以及重覆但未確認股數基準的資料；2882 Core financials 37筆，無 `bvps`。不可把累計EPS當單季、把basic/diluted直接混用、從淨值總額自造BVPS，或只憑 FinMind EPS `unit=null` 補成可發布值。
- **官方補收候選（尚未寫入Core／未核准新source id）**：TSMC單季發行人公告 [2025Q3 EPS 17.44](https://pr.tsmc.com/english/news/3264)、[2025Q4 EPS 19.50](https://pr.tsmc.com/english/news/3281)、[2026Q1 EPS 22.08](https://pr.tsmc.com/english/news/3297)、[2026Q2 EPS 27.25](https://pr.tsmc.com/english/news/3326)，均須依原文核對`diluted/common-share/consolidated/TWD_per_share`一致後才可一次性收檔；FinMind 2025Q4的19.51與發行人稀釋EPS 19.50不同，不得靜默選一個。[Cathay FHC 每股淨值投資人文件](https://www.cathayholdings.com/holdings/-/media/328003db280c4af097620404cf56d3f9.pdf?sc_lang=zh-tw) 有2025年度普通股BVPS=NT$57.0，可作正式`issuer source authorization`與原始文件採集候選，惟未驗證可在目前Control/Serving直接publication。以上不是已收集／Stage或Core變更；數值所有權仍屬來源，LLM不直接寫canonical。
- **離線安全回歸**：[DRL-01 #40170667619](https://github.com/tommylin15/janus-omniforge/actions/runs/40170667619) 81 passed；月末+財報/估值讀取與基準CI按最新同版收據列明。沒有新GCP資源／Scheduler、Owner變更、Registry變更。

### SEQ-05 剩餘最小開發與驗收路徑

1. **有界資料修補（不是全市場回填）**：從已核准／授權且來源可重用的TWSE／MOPS及合格第三方，先針對2330補連續四季可比較、同每股與報表口徑的單季EPS；針對2882補有實際股數基準、TWD/share且已公告的正BVPS。直接核對現有Core／Serving是否本來就有可用原始事實，避免重抓；不得從權益總額猜BVPS、不得把YTD欄位當單季。對倍數資料只補至實際有效月末至少24個月所需的最小歷史缺口；依2026-10-25讀回，2330歷史PE在官方2025春節月末修復後有24有效月；2882歷史PB仍需補2025-10～2026-08的11個月（實際補前重查current）。如授權或欄位口徑不合，維持missing／blocked。
2. **正式資料分類與端到端**：以既有stock identity/industry reader核對`security_type`與`is_financial`，使用現有已確認snapshot及真實財報／月末倍數在批次產生獨立版本化、可讀回的單一卡片；同一`as_of`／`core_snapshot_id`掛入既有Fact Pack，現有API只能讀已發布投影，禁止 request-time Iceberg掃描。需要新增 schema/migration 僅在無法沿用現有`private.specialist_product.payload_json`時才提出。
3. **UI 與A-CHANGE交接**：保留`valuation`一個角色，只呈現一條下中上參考價帶及方法、日期、有效月份、缺值與上次變化；無價格時簡短顯示「資料尚不足」，不產生合理價、交易訊號或AI自算數值。與SEQ-07共用UI與改變提醒的final contract。
4. **離線與上線分界**：按同SHA CI確認RV-02/03/04 targeted tests、負向來源／分類／Owner安全與舊Event讀端相容；2330／2882本次readback是`LIVE_INPUTS_READ_WITH_GAPS`而不是可發布區間驗收。`SEQ-05 DEPLOY=DEFERRED_TO_SEQ-08`，不在本項另開Scheduler、DB、模型role或直接切正式API。

## 2. 計算／資料契約（RV-01 至 RV-03）

1. 對上市／上櫃普通股：一般獲利非金融公司使用**連續、同口徑四季單季 EPS 加總的正 TTM EPS**；金融股使用同每股基準、已公告且為正的 BVPS。ETF `not_applicable`。分母未知、重大不可比或虧損不得硬湊成價帶。
2. 取 `as_of` 截止前最近 **60 個月的月末合法有效歷史 PE 或 PB**，預設至少 **24 個有效月**；此為產品起始參數，並非統計獨立樣本充分性保證。必要時 `missing/limited`；不把今天已知財報回填到歷史公告前。歷史倍數若缺 first-observed 證據，不宣稱嚴格 PIT 回測。
3. 固定當前基礎 `B` 與歷史倍數分位 `M25,M50,M75`，輸出 `lower=B*M25`、`mid=B*M50`、`upper=B*M75`；`price_gap_to_reference_mid_pct = P/mid-1`。量化過程和版本固定，只在顯示端四捨五入；`0<lower<=mid<=upper`，缺值採 null 與 reason codes。區間高低只代表相對假設，不代表漲跌機率、目標價或買賣訊號。
4. 輸出保留 `symbol/market/security_type/as_of/calculated_at/price_as_of/financial_period/source_published_at/first_observed_at/schema_version/method_version/method/basis_type/share_basis/window_months/valid_month_count/excluded_reasons/input_refs/input_hash/rights_status/historical_pit_status` 與 `available/limited/missing/stale/not_applicable/blocked_basis/blocked_rights/error` 狀態。使用者端不得假裝缺值為零。
5. 同業倍數、分析師一致預估、forward PE、機器學習價格區間及 DCF 都屬後續研究，不擋首版；不得在未核實授權/口徑前宣稱已有第三方目標價。

## 3. 介接、依賴與相容（RV-04 至 RV-05）

- 04 Valuation 以 `method_version`／`schema_version` 版本化可重算情境（**不新增模型 role key**），沿現有固定 Fact Pack／Mart／API／Owner-aware UI 合理最小增量接入；前端只顯示**一條**參考價帶，並附方法、時間、來源、樣本月數、是否適用、與上次變化；不讓 LLM 或 Flutter 自產 canonical number。
- 後端與 A-CHANGE 使用同一個 `as_of`／關鍵變化事件與版本指標；04 區間子功能可以與 A-CHANGE 同時開發，**API/schema/文案定版與真實 UI 驗收必合流**。
- 與 04 PE/PB 研究共用一套合格財報、倍數、因子、資料品質與發布契約，但不得修改現行 Risk ACTIVE/Registry 或先觸發四模型重訓。接入前須核對真實 serving reader、相容、保留期、rollback，若不存在具可證依賴的欄位則不假造新表。
- 公開分析只處理合規公有行情／財務資料；Owner 私人持股、現金與成本不能混進公開區間計算。發布只面向授權目標 universe。

## 4. WBS 驗收節點（RV-06）

2026-10-25：以下是內部技術依賴，舊「可平行」不是分派指示。執行順序統一為SEQ-05開發、SEQ-07報告UI合流、SEQ-08集中發布；四階段與模型建議見[AI卡](../execution-cards/sequential-delivery.md)。

| 工作項 | 可平行與先後 | 交付證據／完成定義 |
|---|---|---|
| RV-01｜口徑與實際來源覆蓋 | 可立即與 UI、模型研究平行 | EPS/BVPS/PE/PB 的實際 reader、來源授權、時間、缺值與適用性逐檔/抽樣清冊 |
| RV-02｜公式/狀態純函式 | 依 RV-01 schema 可在 fixtures 先行 | 邊界、月數、財務時點、分位、not_applicable、回溯防洩漏 targeted tests |
| RV-03｜實際資料接線 | RV-01 來源契約通過後 | 真實 as-of、sample/hash/provenance readback；不以 mock 當資料覆蓋 |
| RV-04｜Mart/API 契約與相容 | RV-02+03 | 版本、Owner 隔離、遺失、回滾/舊 reader compatible tests |
| RV-05｜UI 與 A-CHANGE 整合 | UI 草圖可先行，正式接線需 RV-04 | 同一價帶、出處與狀態、30 秒理解測試、沒有 duplicated authority |
| RV-06｜dev 有界發布驗收 | RV-01…05 完成 | Git SHA、targeted/CI、已核准 dev deployment、API/Owner 實際讀回、回滾證據；僅文件完成不得稱 PASS |

本頁 RV-01…06 **全部歸 04 Valuation 子功能**，非第五模型或獨立 publication 工作線。現有五筆 deterministic event artifact 讀端須經相容遷移與 dev 驗收，不可直接刪。整體排序在 [WBS](../wbs.md)，**唯一未完成狀態在 [TODO](../todo.md)**。
