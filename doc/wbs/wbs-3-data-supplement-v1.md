# WBS-3-DATA-SUPPLEMENT-V1 — 補資料第一版

狀態：Active / Planned
模型：【Sol】
更新：2026-10-02

## 目的

以目前五位分析師／五份 Fact Pack 的真實缺資料 evidence 為起點，先完成「缺口判定 → 既有必要資料修復 → 官方事件／產業資料擴充」的第一版資料補強。

**`WBS-5-MART-AI-PROVIDERS` 2026-10-02 checkpoint 所揭露的資料需求是本 WBS 的最低要求（acceptance floor），不是範例、候選或僅供參考的 research wish list。** S0 必須逐項證實 root cause；S1／S2 必須把其中可由既有／可核准資料路徑解決的必要需求實作到可供五角色使用。若某項最低要求因來源授權、官方資料不存在或其他不可自行解除的 blocker 無法滿足，WBS 必須維持 `partial`／`blocked`，不得只因完成盤點而標 Done。

本 WBS 不以「消除所有 null」或「全市場全部歷史 100% 完整」為目標，也不把模型 `missing_information` 未經查證就自動視為 source-level gap。checkpoint 需求先以正式 Core／Fact Pack／provenance／runtime evidence 驗證其 applicability 與 root cause；驗證後屬必要研究輸入者即成為本版最低 acceptance，屬特殊會計不適用欄位才可標 `not_applicable`，不得為消除 null 補造數字。

目前五角色最低依賴維持：

- Fundamental：`financials`
- Valuation：`valuation` + `financials`
- Positioning：`institutional` + `ohlcv`
- Quant：`ohlcv` + `benchmark` + `market-activity`
- Event Risk：`events`

2026-10-02 `2327` 的 `WBS-5-MART-AI-PROVIDERS` bounded GCP checkpoint 是本 WBS 第一組 real-data baseline：五角色第二批均通過 validator，但研究結果均為 `insufficient_data`。該 checkpoint 已證實部分缺口屬 history／metric／semantic／provenance 問題，而不是 provider failure 或「所有資料源都不存在」。

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

若 S0 證實某個**checkpoint minimum requirement 或現行必要 feature** 是真正 `source_gap`，且現有 official／approved-fallback 無法解決，可把該 bounded source admission／adapter 提前併入 S1；仍須遵守 source authorization、費用與外部授權 gate。這個例外不等於開放一般新聞／券商／社群來源擴張。

S1 不要求 TWSE 500 各 dataset 500/500，不為消除已接受 `partial` 逐筆追缺；但不得以「不追求 100%」為理由豁免上方 checkpoint minimum floor。

## S2 — Official Event / Industry Expansion

在 S0/S1 已把現行 hard blockers 分清楚後，第一版再做 bounded 官方／已核准研究資料擴充。S2 同時負責補足 checkpoint minimum floor 中，單靠現有七類 Core dataset 無法合理完成、但可由官方／已核准事件／產業資料解決的部分。

候選範圍只包含可驗證授權、PIT/time semantics 清楚、且能建立 deterministic contract 的官方／已核准資料，例如：

- 官方公司重大事件／法說／公司行動的結構化擴充；
- 官方月營收／公司營運摘要；
- 官方 sector／industry benchmark、同業分類或產業統計；
- 支援 Positioning cross-check 的官方／已核准 bounded dataset；
- 其他經 source-admission 證明可合法用於 Janus private/internal research，且直接用於 checkpoint minimum requirement 的 bounded dataset。

任何 S2 dataset 要進 Core／Fact Pack 前都必須先定義 source authorization、schema、PIT fields、cadence、retention、provenance、DQ／missing semantics 與 deterministic consumer。沒有 consumer contract 的候選只保留 research note，不建立 production ingestion。

S2 不新增付費 API／subscription／GCP resource，除非使用者另行明確授權。

## S0～S2 驗收條件

`WBS-3-DATA-SUPPLEMENT-V1` 完成至少需同時滿足：

1. **2026-10-02 `WBS-5-MART-AI-PROVIDERS` checkpoint 的資料需求為最低 acceptance floor；所有經 runtime evidence 判定 applicable 的項目必須有可用 deterministic input／contract，或有無法自行解除的明確 external blocker。只完成分類不得標 Done。**
2. 五角色所有目前 `missing_data`／`insufficient_data` 都有 machine-readable root cause；不再只用籠統 `insufficient_data` 當診斷。
3. `2327` 與代表性 active targets 的 gap matrix 可由真實 dev Core／Fact Pack／provenance 重建，且 pinned as-of replay 結果可稽核。
4. confirmed blocker 可明確路由到 snapshot composition、history、normalization/derived metric、provenance time、semantic mapping 或 true source gap。
5. `not_applicable` 必須有 deterministic applicability evidence；不得把仍未查明的 checkpoint requirement 降級成 `research_enrichment` 或 `not_applicable`。`unknown` 不猜測，但若屬最低要求則會阻擋 WBS completion。
6. S1/S2 修復不放寬 validator、不由 LLM 補 canonical number、不以 provider fallback 隱藏資料不足。
7. 修復後以相同／可比較 pinned as-of input 重跑；`2327` 必須證明 checkpoint 中 confirmed hard gaps 已按預期消失或轉成有證據的外部 blocker，Fact Pack／interpretation 的 missing/completeness 變化與 immutable lineage 可稽核。
8. 若某項 checkpoint minimum requirement 需要新 source，只有通過 source admission／authorization 的來源可進 executable path；未取得必要授權時 WBS 保持 `partial`／`blocked`，不得降低 requirement 來結案。
9. S2 只把通過 source admission 且有 deterministic consumer contract 的官方／已核准資料接入；candidate 不得文件先行寫成 available。
10. 有相稱的 tests、CI／deployment（如有程式變更）、dev live integration evidence；文件完成本身不等於 WBS 完成。

## 不在本版範圍

S3～S6 明確放在 [`../parking-lot.md`](../parking-lot.md)，目前不做、不計入未完成度，也不阻塞五位分析師目前版本的 daily-operation gate；但若 S0 證實其中某類來源是滿足 checkpoint minimum floor 唯一合理且可核准的方式，只把該 bounded 必要 source 拉入 S1/S2，不等於整個 S3～S6 roadmap 啟動。

- S3：News Research Layer。
- S4：Supply-chain Evidence Expansion。
- S5：Broker Research／Consensus／Target Price Source Evaluation。
- S6：Social／Podcast／Alternative-source Expansion。

分 K／Tick 全面收集、未核准 Yahoo executable source、全市場完整歷史無缺口回補與其他既有 deferred expansion 仍依 Parking Lot 邊界處理。