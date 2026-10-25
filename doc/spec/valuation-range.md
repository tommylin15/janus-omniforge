# Janus 2.0｜04 Valuation 估值參考區間功能子契約

> **2026-10-24 研究精簡決策優先**：本文涉及獨立資料稽核、逐來源補證、全歷史 PIT／精確時間校準、例行週月稽核及自然驗收等待的要求已取消，不再是待辦或發布前置。依 [研究精簡政策](research-simplification.md)，保留必要日期／單位、基本防洩漏與操作安全；歷史證據不改判 PASS。


狀態：**PARTIAL／RV-01_STATIC_MAPPED／RV-02_CODE_CI_PASS／RV-03_CODE_CI_PASS_LIVE_PENDING／RV-04…06_NOT_IMPLEMENTED**（2026-10-24：第五模型撤銷、功能併入 04；已開始程式，仍未接真實資料、API、UI 或部署）。
權威邊界：[PROJECT_RULES](../PROJECT_RULES.md) → 本 SPEC → [WBS 工作線／依賴](../wbs.md) → [唯一 Active TODO](../todo.md) → [實機收據](operations-and-testing.md)。
已被最新決策取代的歷史 AI 指令（僅供參照公式與 UI，**不可執行第五角色開發**）：[Drive《第五模型：估值參考區間》](https://drive.google.com/file/d/1M7pxgkeyzK_Joi4C9Z2aTSRCgdV-u5YO/view)；[Janus 2.0 報告](https://drive.google.com/file/d/15sT38MsE96RAwD-aZnAHvOvEINtythPO/view)。Drive 是核准設計參考，GitHub `main`／runtime 才是實作與完成證據。

## 1. 角色與授權邊界

- 正式模型僅 Quant／Risk／Fundamental／Valuation。撤銷獨立 `valuation_range`／Event 第五模型、訓練、Registry role 和新排程；04 Valuation 接手本情境功能，保留現役 event API／資料、公告時間、公司行動、修訂去重與 A-CHANGE 提醒。
- 04 保留 PE/PB XGBoost 倍數研究、殘差及比較，同時提供唯一「參考價格區間」。共用財報 EPS/BVPS、歷史倍數、來源時間、單位、PIT、公司行動及 publication/rollback；沒有第五組 canonical 價帶或第五個模型。CEO 仍是整合層。
- 04 的區間子功能是可重算的確定性倍數情境，非 ML 未來報酬／信賴區間／交易建議。**不依賴 04 XGBoost 已 DEPLOYABLE**，但有自己的輸入／算式／授權／發布 gate，不是免費升級成已發布模型。
- Research-only 材料不得直接替代正式 Core／serving 的授權、PIT、來源與可得時間；不編造 EPS、BVPS、季報或歷史倍數。新付費或擴權依 PROJECT_RULES §1.3。

RV-01 已完成 [現役 reader 靜態清冊](../research/valuation-rv01-serving-readers-2026-10-24.md)，真實樣本／BVPS 來源覆蓋仍待補。RV-02 已新增 [純函式](../../packages/valuation_range.py) 及 [16 項測試](../../tests/test_valuation_range.py)，[CI #40096160077](https://github.com/tommylin15/janus-omniforge/actions/runs/40096160077) PASS（已補未來財報季度／period end 排除）；RV-02 目前是內部計算，不代表下列完整介接回傳欄位或發布已完成。RV-03 已新增 [既有 Core/Serving 唯讀接線](../../jobs/ingestion-core/ingestion_core/valuation_range_inputs.py)，及 [13 項 targeted tests](../../tests/test_valuation_range_inputs.py)，[CI #40097413271](https://github.com/tommylin15/janus-omniforge/actions/runs/40097413271) PASS：保留 Core 最後交易日原始日期、只取完整月份與 60 月窗口、從既有 Serving 讀單季 EPS／BVPS、沿用 Control 來源授權；不新增研究補收或每日 Job。直接 Dev 真資料讀回未完成（現有 Janus readonly connector 內部錯誤），還不能判定個股有效覆蓋或宣稱每日運作。

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
