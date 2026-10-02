# WBS-3-DATA-SUPPLEMENT-V1 — 補資料第一版

狀態：Active / Planned
模型：【Sol】
更新：2026-10-02

## 目的

以目前五位分析師／五份 Fact Pack 的真實缺資料 evidence 為起點，先完成「缺口判定 → 既有必要資料修復 → 官方事件／產業資料擴充」的第一版資料補強。

本 WBS 不以「消除所有 null」或「全市場全部歷史 100% 完整」為目標，也不把模型 `missing_information` 自動視為 source-level gap。只有經 Core／Fact Pack／provenance／runtime evidence 證實會阻塞目前研究 contract 的缺口，才進 S1 修復；研究強化需求與不適用欄位不得冒充 blocker。

目前五角色最低依賴維持：

- Fundamental：`financials`
- Valuation：`valuation` + `financials`
- Positioning：`institutional` + `ohlcv`
- Quant：`ohlcv` + `benchmark` + `market-activity`
- Event Risk：`events`

2026-10-02 `2327` 的 `WBS-5-MART-AI-PROVIDERS` bounded GCP checkpoint 是本 WBS 第一組 real-data baseline：五角色第二批均通過 validator，但研究結果均為 `insufficient_data`。該 checkpoint 已證實部分缺口屬 history／metric／semantic／provenance 問題，而不是 provider failure 或「所有資料源都不存在」。

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
- Positioning：八個 deterministic 籌碼欄位皆有值；模型提出的類別拆解／交叉驗證先列 `research_enrichment`，不得自動列 source blocker。
- Quant：只有 21 筆 OHLCV；`return_60d`、`return_120d` 缺值屬 confirmed history-depth gap。
- Event Risk：有 5 筆 events，但 `max_severity` 缺值；先判定為 semantic/mapping gap，不把 null 當零風險或沒有事件。
- 345 筆 qualified evidence 中，340 筆缺 `published_at`、317 筆缺 `availability_at`；逐 dataset 判定時間語意，不做欄位硬補。
- 特殊會計項目若對公司／產業不適用，標 `not_applicable`，不得為消除 null 補造數字或新增來源。

S0 不呼叫 LLM 補 canonical facts，也不因 gap inventory 存在就核准新 provider。

## S1 — Existing Required Dataset Remediation

只處理現行五角色必要的七類 dataset：

- `financials`
- `valuation`
- `institutional`
- `ohlcv`
- `benchmark`
- `market-activity`
- `events`

修復順序以 S0 confirmed blocking gaps 為準，第一版至少處理：

1. OHLCV／benchmark 的 60／120 日必要研究窗口，先判斷 Core 已有但 snapshot/read window 未帶入，還是真的需要 bounded historical fill。
2. Financials 跨期 history，使現行 deterministic revenue／EPS trend 有最低必要歷史；`minimum_required_history` 與較深的 `desired_research_history` 必須分開，不把「完整 12 月／12 季全市場回補」自動升格成 blocker。
3. `roe`／`debt_to_equity` 先判斷既有 MOPS/Core 是否已有原始欄位、只是 metric normalization 缺失，或可由已核准 canonical inputs deterministic derive；只有證實既有 approved source 無法提供必要 input 時才標 `source_gap`。
4. Events 建立 versioned deterministic severity / taxonomy mapping；LLM interpretation 不擁有 canonical severity。
5. 對會影響 PIT correctness 的 `published_at`／`availability_at` 補足 source contract、mapping 或 explicit `unknown` 語意；不得用 fetched time 代替官方發布時間。
6. Snapshot composition／Core read path 若是根因，優先修 composition/read window，不為已有資料新增外部來源。

若 S0 證實某個**現行必要 feature** 是真正 `source_gap`，且現有 official／approved-fallback 無法解決，可把該 bounded source admission／adapter 提前併入 S1；仍須遵守 source authorization、費用與外部授權 gate。這個例外不等於開放一般新聞／券商／社群來源擴張。

S1 不要求 TWSE 500 各 dataset 500/500，不為消除已接受 `partial` 逐筆追缺，也不要求所有公司 12 月／12 季無缺口。

## S2 — Official Event / Industry Expansion

在 S0/S1 已把現行 hard blockers 分清楚後，第一版再做 bounded 官方／已核准研究資料擴充。目標是補充公司事件與產業背景，而不是直接引入新聞／券商／social。

候選範圍只包含可驗證授權、PIT/time semantics 清楚、且能建立 deterministic contract 的官方／已核准資料，例如：

- 官方公司重大事件／法說／公司行動的結構化擴充；
- 官方月營收／公司營運摘要（若現行 Fundamental contract 決定採用）；
- 官方 sector／industry benchmark 或產業統計；
- 其他經 source-admission 證明可合法用於 Janus private/internal research 的 bounded dataset。

任何 S2 dataset 要進 Core／Fact Pack 前都必須先定義 source authorization、schema、PIT fields、cadence、retention、provenance、DQ／missing semantics 與 deterministic consumer。沒有 consumer contract 的候選只保留 research note，不建立 production ingestion。

S2 不新增付費 API／subscription／GCP resource，除非使用者另行明確授權。

## S0～S2 驗收條件

`WBS-3-DATA-SUPPLEMENT-V1` 完成至少需同時滿足：

1. 五角色所有目前 `missing_data`／`insufficient_data` 都有 machine-readable root cause；不再只用籠統 `insufficient_data` 當診斷。
2. `2327` 與代表性 active targets 的 gap matrix 可由真實 dev Core／Fact Pack／provenance 重建，且 pinned as-of replay 結果可稽核。
3. confirmed blocker 可明確路由到 snapshot composition、history、normalization/derived metric、provenance time、semantic mapping 或 true source gap。
4. `not_applicable` 不要求補值；`research_enrichment` 不阻塞目前五角色最低 contract；`unknown` 不猜測。
5. S1 修復不放寬 validator、不由 LLM 補 canonical number、不以 provider fallback 隱藏資料不足。
6. 修復後以相同／可比較 pinned as-of input 重跑，證明預期的 Fact Pack missing/completeness 變化及 immutable lineage；不要求所有角色一定變成 full success，無法補的 source-level missing 仍保持 structured partial／blocked。
7. S2 只把通過 source admission 且有 deterministic consumer contract 的官方／已核准資料接入；candidate 不得文件先行寫成 available。
8. 有相稱的 tests、CI／deployment（如有程式變更）、dev live integration evidence；文件完成本身不等於 WBS 完成。

## 不在本版範圍

S3～S6 明確放在 [`../parking-lot.md`](../parking-lot.md)，目前不做、不計入未完成度，也不阻塞五位分析師目前版本的 daily-operation gate：

- S3：News Research Layer。
- S4：Supply-chain Evidence Expansion。
- S5：Broker Research／Consensus／Target Price Source Evaluation。
- S6：Social／Podcast／Alternative-source Expansion。

分 K／Tick 全面收集、未核准 Yahoo executable source、全市場完整歷史無缺口回補與其他既有 deferred expansion 仍依 Parking Lot 邊界處理。