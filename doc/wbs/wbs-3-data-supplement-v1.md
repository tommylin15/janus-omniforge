# WBS-3-DATA-SUPPLEMENT-V1 — 補資料第一版

狀態：Completed（依使用者資料優先驗收調整）
模型：【Sol】
更新：2026-10-03

2026-10-02 使用者指定優先執行；本次 pinned dev Core／TWSE／FinMind 試連、時間證據 blocker 與待決方案見 [S0 evidence](../data-supplement-s0-evidence.md)。

結案與真實 dev 驗收見 [完成證據](../archive/wbs-3-data-supplement-v1-completed-2026-10-03.md)；日常維運見 [檢核文件](../runbook-data-supplement.md)。以下原嚴格完整度條件由「使用者最新驗收調整」取代；缺值不偽造。

## 目的

以目前五位分析師／五份 Fact Pack 的真實缺資料 evidence 為起點，先完成「缺口判定 → 既有必要資料修復 → 官方事件／產業資料擴充」的第一版資料補強。

**`WBS-5-MART-AI-PROVIDERS` 2026-10-02 checkpoint 所揭露的資料需求是本 WBS 的最低要求（acceptance floor），不是範例、候選或僅供參考的 research wish list。** S0 必須逐項證實 root cause；S1／S2 必須把其中可由既有／可核准資料路徑解決的必要需求實作到可供五角色使用。若某項最低要求因來源授權、官方資料不存在或其他不可自行解除的 blocker 無法滿足，必須觸發下方 **Stop-and-Discuss Gate**；不得把 `partial`／`blocked` 當成可跳過該要求、繼續下一階段或下一個 WBS 的通行證。

本 WBS 不以「消除所有 null」或「全市場全部歷史 100% 完整」為目標，也不把模型 `missing_information` 未經查證就自動視為 source-level gap。checkpoint 需求先以正式 Core／Fact Pack／provenance／runtime evidence 驗證其 applicability 與 root cause；驗證後屬必要研究輸入者即成為本版最低 acceptance，屬特殊會計不適用欄位才可標 `not_applicable`，不得為消除 null 補造數字。

目前五角色最低依賴維持：

- Fundamental：`financials`
- Valuation：`valuation` + `financials`
- Positioning：`institutional` + `ohlcv`
- Quant：`ohlcv` + `benchmark` + `market-activity`
- Event Risk：`events`

2026-10-02 `2327` 的 `WBS-5-MART-AI-PROVIDERS` bounded GCP checkpoint 是本 WBS 第一組 real-data baseline：五角色第二批均通過 validator，但研究結果均為 `insufficient_data`。該 checkpoint 已證實部分缺口屬 history／metric／semantic／provenance 問題，而不是 provider failure 或「所有資料源都不存在」。

## Stop-and-Discuss Gate

### 使用者最新驗收調整：資料優先

2026-10-02 使用者明確指示「驗收條件放寬點，有資料優先」，取代本文件下方較嚴格的研究完整度要求：

- 先交付目前研究可用的真實資料；12 月／12 季仍為收集目標，實際缺期、缺欄位、同業比較或獨立比對未完成時如實標 `partial`／`unknown`，不再單獨阻擋本版交付。
- 月營收、財報歷史數值可在來源、公司、期別、單位及口徑檢查後用於目前研究。歷史公告時間／原始數值版次未證明時保留 null／unknown，記錄真正取得時間與 hash，不得補造發布日期。
- 目前研究可用不代表歷史 PIT 回測可用。未證明歷史可得性的資料不得倒填至取得前的 as-of，也不得冒充已重建歷次更正值；既有 validator 與 publication gate 不放寬。
- 無法計算的 feature 保留 missing reason，不補零、不讓 LLM 補數值；數值衝突以官方文件核對，不能為增加 coverage 默默採用 fallback。
- 仍須完成真實資料接線、適用測試及 dev 驗收，再做每日增量排程、週六獨立檢查、Admin UI 與操作文件。來源授權、費用、安全與 production 限制維持原規則。

下方原 minimum floor、Stop-and-Discuss 與驗收條件中，以「研究窗口／歷史時間／版次／feature 完整度不足即停止」作為閘門的部分，依上述最新決策改為可交付的明示限制；新費用、授權或安全 blocker 仍須討論。本調整不代表現有程式、Core 或排程已完成。

本節是 `WBS-3-DATA-SUPPLEMENT-V1` 的強制人工決策閘門，優先於一般 WBS「先完成其他可繼續部分」的慣例。

- S0、S1、S2 任一階段，只要有一項 **checkpoint minimum requirement** 或已證實的現行必要 feature 經充分查核後確認無法由目前授權、既有 dev 資源、官方／approved-fallback source 或安全 deterministic 實作自行滿足，立即停止本 WBS 的後續執行。
- 停止後只可整理完成決策所需的最小證據，不得繼續下一個 S 階段、不得先做其他補資料擴張、不得切到下一個 WBS，也不得自行把該要求降級成 `research_enrichment`、`accepted gap`、Parking Lot 或非必要項目。
- 必須回報使用者：無法滿足的精確 requirement、root cause、已驗證 evidence、受影響 role／Fact Pack／daily-operation gate、可行方案、每個方案的授權／費用／PIT／資料品質／維運風險，以及不處理的後果。
- 需要新付費來源、付費 API／subscription、新 GCP 資源、重大權限、外部 credential consent 或其他既定人工授權時，停在此 gate 等待使用者決定；不得繞過授權或以替代 provider 隱藏缺口。
- `partial`／`blocked` 只能描述停下來時的真實狀態，**不是 completion，也不是 skip permission**。
- 只有使用者明確決定採用某個修復方案、調整 requirement、接受特定缺口或把特定項目移出 active scope 後，才能依該決定繼續。
- 尚未證實的 `unknown` 可以繼續做 bounded investigation；一旦確認為無法自行解除的 blocker，就立即觸發本 gate。

## Checkpoint minimum requirement floor

S0～S2 至少必須覆蓋以下 checkpoint 需求；不得在 completion 判定時刪減：

### Fundamental

- `revenue_trend_percent`、`eps_trend_percent` 必須取得足夠跨期合格資料，不能停留在只有 2026 Q2。
- 至少驗證並供應分析師需要的 12 個月營收與 12 季財報研究窗口；若實際 deterministic feature 的 minimum window 較短，仍須把 12 月／12 季作為 checkpoint research depth floor，而不是因此從本 WBS 移除。
- 建立一般業／金融業等適用分類依據，以及單季／累計口徑的 deterministic semantics。
- 現金流量與資產負債資料必須納入可用性／mapping 驗證，支援獲利品質與財務持續性研究。
- 財報 PIT 必須保留權威 `published_at`／可證明的 `availability_at` 語意；無法證明時 fail closed，不得以 fetched/received time 冒充。
- checkpoint 列出的特殊會計 raw fields 必須做 applicability 判定；確實不適用者標 `not_applicable`，不得要求補成數字。

### Valuation

- `roe`、`debt_to_equity` 必須有合格 canonical input、正規化 mapping 或 deterministic derived metric。
- 建立適用同業／產業估值比較基準的 bounded contract；不能只保留單點 PE/PB/殖利率而沒有可比較基準。
- 歷史 valuation observations 的 metric identity／time semantics 必須可追蹤。
- PB、殖利率及其比較基準必須有明確 evidence mapping，不得僅以模型 prose 指稱。

### Positioning

- 現有八個 deterministic 籌碼欄位不得退化。
- 各期間依投資人類別拆分的正規化結果必須可用，且保留原始 source/provenance。
- 量能正規化分母定義與原始基準必須 deterministic、versioned、可重算。
- 至少完成一條可核准的獨立來源／官方 cross-check 設計與驗證；若現有 approved source 無法提供，應明確形成 bounded `source_gap`／authorization blocker，而不是把需求降級成非必要 enrichment。

### Quant

- `return_60d`、`return_120d` 必須可由合格 OHLCV 計算；需要的有效收盤價窗口必須實際存在於 Core／snapshot/read path。
- 20／60／120 日研究窗口的 trading-day semantics、benchmark 對齊與 PIT fence 必須可重跑。
- 第一批 `codex_cli_unavailable` 是 provider worker failure，不得混入資料缺口修復；第二批 Quant 成功執行後的 history gap 才是本 WBS 的資料 baseline。

### Event Risk

- 既有事件不得因 `max_severity=null` 被解讀成無事件或零風險。
- 建立 versioned deterministic event taxonomy／severity mapping，讓 `max_severity` 可由合格 evidence 產生；LLM interpretation 不擁有 canonical severity。
- 事件的 authoritative publication/effective time semantics 必須可稽核。

### Cross-role provenance/time

- checkpoint 的 345 筆 qualified evidence 中 340 筆缺 `published_at`、317 筆缺 `availability_at`，S0 必須逐 dataset 建立 time-semantics matrix並判定哪些欄位是必要、哪些可由官方 publication rule／source contract deterministic 補足、哪些只能 explicit `unknown`。
- 任何 PIT-sensitive feature 若仍缺必要 publication／availability evidence，該 feature 不能以「已有數值」視為滿足最低要求。
- received／record／observed／fetched time 不得冒充 authoritative publication time。

## S0 — Evidence Gap Inventory & Remediation Map

先建立 feature-level、可重跑的 Evidence Gap Matrix，至少覆蓋目前 active AI targets，並以 `2327` 作第一個 pinned baseline。

每列至少保存：

- `analysis_as_of`
- `symbol`
- `role`
- `dataset_id`
- `feature_id`
- `required_history`
- `available_history`
- latest record／observation time
- `published_at` quality
- `availability_at` quality
- `source_id`
- source authorization
- `gap_class`
- `gap_status`
- blocking / non-blocking
- remediation layer
- execution／Core snapshot／provenance evidence
- resolution / unresolved reason

`gap_class` 至少區分：

- `snapshot_composition_gap`
- `history_depth_gap`
- `metric_mapping_gap`
- `provenance_time_gap`
- `semantic_gap`
- `source_gap`
- `authorization_gap`
- `research_enrichment`
- `not_applicable`
- `unknown`

S0 同時建立 dataset time-semantics matrix，明確區分 record/effective time、authoritative publication time、availability time 與 Janus fetched/observed time；不得以 received／record／fetched time 冒充官方發布時間。

### S0 第一組已知 baseline

`2327` checkpoint 已確認：

- Fundamental：`revenue_trend_percent`、`eps_trend_percent` 為 null；28 筆 qualified financial observations、18 個有值 metrics，但 history 僅 2026 Q2。
- Valuation：PE/PB/殖利率已有值；`roe`、`debt_to_equity` 缺合格輸入／mapping。
- Positioning：八個 deterministic 籌碼欄位皆有值；checkpoint 另要求投資人類別拆解、分母定義與 cross-check，依上方 minimum floor 驗證與實作。
- Quant：只有 21 筆 OHLCV；`return_60d`、`return_120d` 缺值屬 confirmed history-depth gap。
- Event Risk：有 5 筆 events，但 `max_severity` 缺值；先判定為 semantic/mapping gap，不把 null 當零風險或沒有事件。
- 345 筆 qualified evidence 中，340 筆缺 `published_at`、317 筆缺 `availability_at`；逐 dataset 判定時間語意，不做欄位硬補。
- 特殊會計項目若對公司／產業不適用，標 `not_applicable`，不得為消除 null 補造數字或新增來源。

S0 不呼叫 LLM 補 canonical facts，也不因 gap inventory 存在就核准新 provider。

## S1 — Existing Required Dataset Remediation

優先處理現行五角色必要的七類 dataset：

- `financials`
- `valuation`
- `institutional`
- `ohlcv`
- `benchmark`
- `market-activity`
- `events`

修復順序以 S0 confirmed blocking gaps 與上方 checkpoint minimum floor 為準，第一版至少處理：

1. OHLCV／benchmark 的 60／120 日必要研究窗口，先判斷 Core 已有但 snapshot/read window 未帶入，還是真的需要 bounded historical fill。
2. Financials 跨期 history，同時滿足現行 deterministic revenue／EPS trend 與 checkpoint 的 12 月／12 季 research depth floor；不得把「全市場所有欄位無缺口」誤當同一要求。
3. `roe`／`debt_to_equity` 先判斷既有 MOPS/Core 是否已有原始欄位、只是 metric normalization 缺失，或可由已核准 canonical inputs deterministic derive；只有證實既有 approved source 無法提供必要 input 時才標 `source_gap`。
4. Financial statement type／industry applicability／single-period vs cumulative semantics、cash-flow／balance-sheet mapping。
5. Events 建立 versioned deterministic severity / taxonomy mapping；LLM interpretation 不擁有 canonical severity。
6. Positioning investor-class normalized breakdown、volume denominator contract 與 bounded independent cross-check。
7. 對會影響 PIT correctness 的 `published_at`／`availability_at` 補足 source contract、mapping 或 explicit `unknown` 語意；不得用 fetched time 代替官方發布時間。
8. Snapshot composition／Core read path 若是根因，優先修 composition/read window，不為已有資料新增外部來源。

若 S0 證實某個**checkpoint minimum requirement 或現行必要 feature** 是真正 `source_gap`，且現有 official／approved-fallback 無法解決，先觸發 **Stop-and-Discuss Gate**。只有使用者明確決定採用並授權某個 bounded source admission／adapter 後，才可把該來源併入 S1；不得自行以「可併入 S1」為理由繼續執行。這個例外不等於開放一般新聞／券商／社群來源擴張。

S1 不要求 TWSE 500 各 dataset 500/500，不為消除已接受 `partial` 逐筆追缺；但不得以「不追求 100%」為理由豁免上方 checkpoint minimum floor。

## S2 — Official Event / Industry Expansion

只有 S0／S1 的 checkpoint minimum floor 沒有未決 Stop-and-Discuss blocker，或所有 blocker 都已取得使用者明確決策後，才可進入 S2。不得因 S1 被標 `partial`／`blocked` 就自行跳到 S2。

S2 做 bounded 官方／已核准研究資料擴充，並負責補足 checkpoint minimum floor 中，單靠現有七類 Core dataset 無法合理完成、但可由官方／已核准事件／產業資料解決的部分。

候選範圍只包含可驗證授權、PIT/time semantics 清楚、且能建立 deterministic contract 的官方／已核准資料，例如：

- 官方公司重大事件／法說／公司行動的結構化擴充；
- 官方月營收／公司營運摘要；
- 官方 sector／industry benchmark、同業分類或產業統計；
- 支援 Positioning cross-check 的官方／已核准 bounded dataset；
- 其他經 source-admission 證明可合法用於 Janus private/internal research，且直接用於 checkpoint minimum requirement 的 bounded dataset。

任何 S2 dataset 要進 Core／Fact Pack 前都必須先定義 source authorization、schema、PIT fields、cadence、retention、provenance、DQ／missing semantics 與 deterministic consumer。沒有 consumer contract 的候選只保留 research note，不建立 production ingestion。

S2 若遇到 minimum floor 無法滿足或需要額外人工授權，同樣立即觸發 **Stop-and-Discuss Gate**，不得以候選資料不足為理由直接結束 S2 或轉往後續 WBS。

S2 不新增付費 API／subscription／GCP resource，除非使用者另行明確授權。

## S0～S2 驗收條件

`WBS-3-DATA-SUPPLEMENT-V1` 完成至少需同時滿足：

1. **2026-10-02 `WBS-5-MART-AI-PROVIDERS` checkpoint 的資料需求為最低 acceptance floor；所有經 runtime evidence 判定 applicable 的項目必須有可用 deterministic input／contract。若出現無法自行解除的 blocker，必須先觸發 Stop-and-Discuss Gate 並取得使用者明確決策；未決 blocker 存在時不得標 Done、不得進下一 S 階段或下一 WBS。**
2. 五角色所有目前 `missing_data`／`insufficient_data` 都有 machine-readable root cause；不再只用籠統 `insufficient_data` 當診斷。
3. `2327` 與代表性 active targets 的 gap matrix 可由真實 dev Core／Fact Pack／provenance 重建，且 pinned as-of replay 結果可稽核。
4. confirmed blocker 可明確路由到 snapshot composition、history、normalization/derived metric、provenance time、semantic mapping 或 true source gap。
5. `not_applicable` 必須有 deterministic applicability evidence；不得把仍未查明的 checkpoint requirement 降級成 `research_enrichment` 或 `not_applicable`。`unknown` 不猜測，但若屬最低要求則會阻擋 WBS completion。
6. S1/S2 修復不放寬 validator、不由 LLM 補 canonical number、不以 provider fallback 隱藏資料不足。
7. 修復後以相同／可比較 pinned as-of input 重跑；`2327` 必須證明 checkpoint 中 confirmed hard gaps 已按預期消失。若仍有最低要求無法滿足，必須有使用者在 Stop-and-Discuss Gate 的明確決策；Fact Pack／interpretation 的 missing/completeness 變化與 immutable lineage 可稽核。
8. 若某項 checkpoint minimum requirement 需要新 source，只有通過 source admission／authorization 且取得必要人工決策的來源可進 executable path；未取得必要授權或決策時立即停在 Stop-and-Discuss Gate，不得降低 requirement、標成 accepted gap 或跳往後續工作。
9. S2 只把通過 source admission 且有 deterministic consumer contract 的官方／已核准資料接入；candidate 不得文件先行寫成 available。
10. 有相稱的 tests、CI／deployment（如有程式變更）、dev live integration evidence；文件完成本身不等於 WBS 完成。
11. 依使用者追加要求，資料取值驗收後納入每日收集排程，並建立獨立的每週六 deterministic 資料品質檢查批次；可檢出缺期、來源失敗、數值／單位／口徑衝突與 PIT 時間證據問題。檢查不依賴 Codex 或 LLM，也不能因每日收集失敗而跳過。
12. Admin UI 顯示最近檢查時間、結果、受影響個股／dataset／欄位、安全的失敗原因及是否需要調整每日排程，並提供檢核文件入口。操作文件須包含重跑檢查、定位每日程式／排程、修復、重建及驗收步驟；異常不自動放寬 validator 或覆寫歷史版本。依使用者最新決定，先不建立 Codex automation／通知或 Email；新增批次、UI 與文件均須以實作及 dev evidence 驗收。

## 不在本版範圍

S3～S6 明確放在 [`../parking-lot.md`](../parking-lot.md)，目前不做、不計入未完成度，也不阻塞五位分析師目前版本的 daily-operation gate；但若 S0 證實其中某類來源是滿足 checkpoint minimum floor 唯一合理且可核准的方式，必須先觸發 Stop-and-Discuss Gate，由使用者明確決定是否把該 bounded 必要 source 拉入 S1/S2；不得自行啟動整個 S3～S6 roadmap。

- S3：News Research Layer。
- S4：Supply-chain Evidence Expansion。
- S5：Broker Research／Consensus／Target Price Source Evaluation。
- S6：Social／Podcast／Alternative-source Expansion。

分 K／Tick 全面收集、未核准 Yahoo executable source、全市場完整歷史無缺口回補與其他既有 deferred expansion 仍依 Parking Lot 邊界處理。
