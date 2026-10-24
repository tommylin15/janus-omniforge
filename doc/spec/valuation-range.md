# Janus 2.0｜第五角色 Valuation Range（估值參考區間）SPEC

狀態：**APPROVED_DESIGN／NOT_IMPLEMENTED**（2026-10-24 使用者核准；本頁只建立工程契約，不代表資料、程式、部署或 UI 已驗收）。
權威邊界：[PROJECT_RULES](../PROJECT_RULES.md) → 本 SPEC → [WBS 工作線／依賴](../wbs.md) → [唯一 Active TODO](../todo.md) → [實機收據](operations-and-testing.md)。
完整 AI 交接與公式決策：[Drive《第五模型：估值參考區間》](https://drive.google.com/file/d/1M7pxgkeyzK_Joi4C9Z2aTSRCgdV-u5YO/view)；[Janus 2.0 報告](https://drive.google.com/file/d/15sT38MsE96RAwD-aZnAHvOvEINtythPO/view)。Drive 是核准設計參考，GitHub `main`／runtime 才是實作與完成證據。

## 1. 角色與授權邊界

- 第五角色改為 `valuation_range`，**取代 Event／Catalyst 第五模型訓練及模型排程**；保留公告原文、事件時點、公司行動、防重與 A-CHANGE 事實提醒，**不得以角色替換為由刪除現役 event API／資料表**。
- 原四個研究角色 **Quant／Risk／Fundamental／Valuation（相對 PE/PB）** 保留；CEO 是整合層而非第六個模型。第 04 角色研究倍數與殘差，第 05 角色負責前台唯一「參考價格區間」呈現，不能形成兩套 canonical 價帶。
- **首版是可重算的確定性倍數情境，不是 ML 訓練出的未來報酬／信賴區間／交易建議**。不依賴 04 Valuation 成為 DEPLOYABLE，也不以五模型同時 ACTIVE 當開工門檻。
- Research-only 材料不得直接替代正式 Core／serving 的授權、PIT、來源與可得時間；不編造 EPS、BVPS、季報或歷史倍數。新付費或擴權依 PROJECT_RULES §1.3。

## 2. 計算／資料契約（RV-01 至 RV-03）

1. 対上市／上櫃普通股：一般獲利非金融公司使用**連續、同口徑四季單季 EPS 加總的正 TTM EPS**；金融股使用同每股基準、已公告且為正的 BVPS。ETF `not_applicable`。分母未知、重大不可比或虧損不得硬湊成價帶。
2. 取 `as_of` 截止前最近 **60 個月的月末合法有效歷史 PE 或 PB**，預設至少 **24 個有效月**；此為產品起始參數，並非統計獨立樣本充分性保證。必要時 `missing/limited`；不把今天已知財報回填到歷史公告前。歷史倍數若缺 first-observed 證據，不宣稱嚴格 PIT 回測。
3. 固定當前基礎 `B` 與歷史倍數分位 `M25,M50,M75`，輸出 `lower=B*M25`、`mid=B*M50`、`upper=B*M75`；`price_gap_to_reference_mid_pct = P/mid-1`。量化過程和版本固定，只在顯示端四捨五入；`0<lower<=mid<=upper`，缺值採 null 與 reason codes。區間高低只代表相對假設，不代表漲跌機率、目標價或買賣訊號。
4. 輸出保留 `symbol/market/security_type/as_of/calculated_at/price_as_of/financial_period/source_published_at/first_observed_at/schema_version/method_version/method/basis_type/share_basis/window_months/valid_month_count/excluded_reasons/input_refs/input_hash/rights_status/historical_pit_status` 與 `available/limited/missing/stale/not_applicable/blocked_basis/blocked_rights/error` 狀態。使用者端不得假裝缺值為零。
5. 同業倍數、分析師一致預估、forward PE、機器學習價格區間及 DCF 都屬後續研究，不擋首版；不得在未核實授權/口徑前宣稱已有第三方目標價。

## 3. 介接、依賴與相容（RV-04 至 RV-05）

- 將 `valuation_range` 的可重算結果獨立版本化，沿現有固定 Fact Pack／Mart／API／Owner-aware UI 合理最小增量接入；前端只顯示**一條**參考價帶，並附方法、時間、來源、樣本月數、是否適用、與上次變化；不讓 LLM 或 Flutter 自產 canonical number。
- 後端與 A-CHANGE 使用同一個 `as_of`／關鍵變化事件與版本指標；第五角色可以與 A-CHANGE 同時開發，**API/schema/文案定版與真實 UI 驗收必合流**。
- 與現有四角色模型研究共用合格資料與因子契約，但不得修改現行 Risk ACTIVE/Registry 或先觸發四模型重訓。接入前須核對真實 serving reader、相容、保留期、rollback，若不存在具可證依賴的欄位則不假造新表。
- 公開分析只處理合規公有行情／財務資料；Owner 私人持股、現金與成本不能混進公開區間計算。發布只面向授權目標 universe。

## 4. WBS 驗收節點（RV-06）

| 工作項 | 可平行與先後 | 交付證據／完成定義 |
|---|---|---|
| RV-01｜口徑與實際來源覆蓋 | 可立即與 UI、模型研究平行 | EPS/BVPS/PE/PB 的實際 reader、來源授權、時間、缺值與適用性逐檔/抽樣清冊 |
| RV-02｜公式/狀態純函式 | 依 RV-01 schema 可在 fixtures 先行 | 邊界、月數、財務時點、分位、not_applicable、回溯防洩漏 targeted tests |
| RV-03｜實際資料接線 | RV-01 來源契約通過後 | 真實 as-of、sample/hash/provenance readback；不以 mock 當資料覆蓋 |
| RV-04｜Mart/API 契約與相容 | RV-02+03 | 版本、Owner 隔離、遺失、回滾/舊 reader compatible tests |
| RV-05｜UI 與 A-CHANGE 整合 | UI 草圖可先行，正式接線需 RV-04 | 同一價帶、出處與狀態、30 秒理解測試、沒有 duplicated authority |
| RV-06｜dev 有界發布驗收 | RV-01…05 完成 | Git SHA、targeted/CI、已核准 dev deployment、API/Owner 實際讀回、回滾證據；僅文件完成不得稱 PASS |

本頁的 WBS 分派與整體可平行排序在 [WBS 主索引](../wbs.md)；**未完成狀態只維護於 [TODO](../todo.md)**，不要在此維護第二份進度或另立 Event 模型待辦。
