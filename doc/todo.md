# Janus — TODO

版本：2.1
用途：只保留未完成工作與目前驗收條件；完成證據、已失效 planning marker 與歷史 checkpoint 移至 archive。

歷史入口：

- [2026-09-26 Product Completeness reprioritization 與 TODO cleanup](archive/todo-cleanup-and-product-completeness-priority-2026-09-26.md)
- [TODO 歷史 checkpoint、退役 WBS 4C 與已完成 checklist（2026-09-23）](archive/todo-history-and-completed-2026-09-23.md)
- [已完成 WBS 0／1／2／4](archive/wbs-completed-through-2026-08-31.md)
- 其他既有完成紀錄保留於 `archive/`；完整 runtime／deployment evidence 見 `spec/operations-and-testing.md`。

## 執行模式：兩條並行主線

Janus 已進入六個月 Dev Pilot observation window，但這不等於 feature freeze 或產品完成。現在分成兩條彼此獨立的主線：

1. **Product Completeness foreground**：補齊目前 dev 真實使用的資料與操作閉環；每次仍只執行一個可獨立驗收的原子項目。
2. **`WBS-8-DEV-PILOT-RUN` operational observation**：持續累積自然 Scheduler／ingestion／analysis、backup／restore、outcome、usefulness、cost、manual intervention、recurring failure 與 security／privacy evidence；沒有新 evidence 時不製造人工 checkpoint。

Observation window 不阻擋 correctness、data-integrity、market coverage、portfolio valuation、User baseline usability 或 Admin operability 修復；但也不自動授權 Production、付費 source、新付費 API／model、新 GCP service、HA／multi-region 或其他仍受 gate 的範圍。

## 模型確認規則

- 每次只取 foreground queue 中的一個原子任務。正式執行前，AI 必須先提醒建議模型與任務名稱，等使用者明確回覆已切換模型後才開始；完成後停止，下一項重新確認。
- 六個月 observation checkpoint 是 evidence 工作，不應為了「下一項」而人工觸發本來應自然發生的 production-like workload；需要執行 bounded repair／acceptance 時仍依各 WBS 的模型與授權規則。
- 每個日曆日第一次 Gemini 串接前，先查官方模型清單，選出當日前三個 Stable model，依序試用；優先 free tier，不自動開啟 paid gate，並受使用者明確授權的 scope／次數上限約束。全部失敗時維持 fail-closed、不得寫 placeholder。

## A. Product Completeness foreground queue

### 1. `WBS-6-PORTFOLIO-COMPLETENESS` — 【Sol】

目標：讓真實個人持股從 ledger → stock master／market coverage → Private Mart → User UI 形成可用閉環，而不是只有 presentation shell。

- [ ] 每筆有效持股都能解析股票代號與可顯示名稱；名稱解析使用 canonical stock master／正式 bounded reader，不由 Flutter hard-code。
- [ ] 對所有真實 active holdings 驗證 market coverage；缺價時保留 affected symbol、price status、valuation date／price date 與安全的 missing reason，不只回傳泛化「資料不足」。
- [ ] Private Mart 產生 per-position shares、average cost、market price／value、unrealized PnL／return 與同幣別 aggregate market value／cost basis／unrealized PnL／return；正式數值不得由 Flutter 或 LLM 重算。
- [ ] aggregate 只有在 canonical contract 允許時才發布；missing／stale／跨 valuation date 不得拼成看似完整的總額，必須明確回報 partial／withheld 與 affected count／symbols。
- [ ] User「持股」與交易相關主要列表優先顯示「股票名稱＋代號」，並顯示估值日、行情日與 missing／stale 狀態。
- [ ] Acceptance 必須使用 authenticated owner 的 GCP dev 真實資料，至少證明目前所有 active holdings 的名稱解析與 coverage 結果；不得用 fixture 假裝 live completeness。

### 2. `WBS-6-MARKET-HOME-DATA` — 【Sol】

目標：建立不依賴 LLM／`mart_daily_brief` 的 deterministic market-home contract。

- [ ] 重用已發布 Core／bounded market readers，提供目前可合法取得的 benchmark、market activity、institutional 等市場 baseline；不因 Daily Brief 缺失而把整個市場首頁視為 unavailable。
- [ ] 每個區塊保留 `as_of`／trade date、freshness、status、coverage 與 provenance；不同資料日期可以並列但不得假裝同一 analysis snapshot。
- [ ] 缺 dataset 時只讓該區塊 missing／partial，不以 0、placeholder 或 LLM 補值。
- [ ] API contract 有 targeted tests、auth／public boundary 與 GCP dev persisted-data acceptance。

### 3. `WBS-6-MARKET-HOME-UI` — 【Luna】

Dependency：`WBS-6-MARKET-HOME-DATA`。

- [ ] 「今日」先呈現 deterministic market baseline 與資料日期／freshness；`mart_daily_brief`、Market Regime、AI summary 等是 enhancement，不是 baseline 可見性的 prerequisite。
- [ ] Mart／AI unavailable 時只顯示「研究摘要尚未就緒」等 bounded state，既有 market baseline 仍可讀。
- [ ] partial／stale／fallback／missing 使用既有 UI state semantics；不把不同日期資料拼成單一「今日分析」。
- [ ] phone／desktop responsive、loading／error 與 authenticated GCP dev browser acceptance 通過。

### 4. `WBS-3-FULL-MARKET-BASE-COVERAGE` — 【Sol】

目標：把既有 bounded canary／少量 symbol acceptance 推進到當日 enabled stock master 的實用基礎 coverage。

- [ ] 以當日 enabled stock master 收集全市場日 OHLCV、PE/PB、法人、融資券／借券／當沖、基本面摘要與官方 benchmark；現有 bounded replay／DQ／quarantine evidence 不等於全市場完成。
- [ ] coverage inventory 能指出 enabled symbols 的 expected／received／missing，並保留 source／snapshot／execution provenance。
- [ ] 真實持股與 watchlist 所需 symbol 不得因 canary universe 限制而長期沒有基礎行情；若 upstream 不支援，必須明確進 missing／blocked，而不是靜默缺資料。
- [ ] replay、成本、runtime、DQ 與 quarantine acceptance 維持既有 WBS 3 規則。

### 5. `WBS-6-FLUTTER-ADMIN-SHELL` — 【Luna】

- [ ] 單一 Flutter codebase 的 Admin workspace、中文主導覽、responsive shell。
- [ ] backend Admin auth／token audience negative tests 通過；Flutter 隱藏控制不作 security boundary。
- [ ] Legacy static Admin 在 parity、browser/runtime acceptance 與 rollback plan 完成前保留。

### 6. `WBS-6-ADMIN-OVERVIEW-BATCH` — 【Luna】

Dependency：`WBS-6-FLUTTER-ADMIN-SHELL`。

- [ ] actionable-issues-first overview，先顯示需要處理的 Core／Mart／failure 問題；正常 execution 不佔首頁主要空間。
- [ ] batch／retry classification、retryable failed item、execution lineage 可操作；partial success 不作 full success。
- [ ] Operator 能不登入 GCP／直接查 DB 就定位近期失敗與安全重跑既有允許的 workload。

### 7. `WBS-6-ADMIN-STOCK-WORKBENCH` — 【Sol】

Dependency：Admin shell、Core persisted readers；AI role-impact／historical role/CIO 功能仍受 Mart contracts dependency。

- [ ] 第一階段先完成代號／中文名搜尋、dataset health、coverage／gap、最近 execution／snapshot 與安全 gap-repair 入口。
- [ ] 技術 lineage 放在進階，不以 raw JSON 作主要 UX；old execution／snapshot immutable。
- [ ] 未完成 Fact Pack／AI role／CIO contracts 時，不顯示或假裝相關 rerun／historical AI capability 已可用。

## B. Dev Pilot operational observation

### `WBS-8-DEV-PILOT-RUN` — 【Sol】

- [ ] 自 `pilot_started_at=2026-09-24T15:29:19Z` 起持續 6 calendar months operational phase；累積 monthly evidence summary、Scheduler／ingestion／analysis、backup／restore、outcome、usefulness、cost、manual intervention、recurring failure 與 security／privacy evidence。
- [ ] 第一份 checkpoint 已記錄於 `pilot-operational-evidence.md`；repair 後下一筆自然 Scheduler execution 仍是 pending evidence boundary，手動 bounded acceptance 不得代替。
- [ ] 沒有實際 post-start evidence 的 category 維持 `not observed`／`unknown`；Entry baseline 不可自動當成狀態未變的證據。
- [ ] 六個月 window 未完成前 Production promotion blocked。

### `WBS-8-PROD-GO-NOGO` — 【Sol】

- [ ] Blocked until Pilot 完整執行 6 calendar months；review data reliability、analysis usefulness、PIT/outcome、operations burden、automation reliability、actual cost/value、security/privacy 與 feature usage，並列出各功能 keep／freeze／remove／productionize。
- [ ] Outcome 為 `GO`／`EXTEND_PILOT`／`NO_GO`；`GO` 只允許開始 production architecture／migration planning，不等於自動 production deploy。

## C. 其他有效 backlog（不在 foreground queue）

### P0／P1 個人化與深度追蹤

- [ ] 【Sol】 個人化分析只在 authenticated-user 邊界內引用公開 `mart_scoped_analysis` 的 symbol scope；不把私人資料寫回公開 Mart。
- [ ] 【Sol】 對已核准行情來源建立分 K／Tick 獨立排程、quota、retention、failure policy 與成本量測；未核准前保持 blocked。
- [ ] 【Sol】 新聞／券商研究／目標價逐一完成來源授權與 provenance 審查後，才可建立 adapter 與 retention policy。
- [ ] 【Sol】 未核准候選來源只保留 disabled／blocked 設定，不建立 adapter、排程或 Admin 審查 UI；取得外部授權與成本核准後另開 WBS。
- [ ] 【Sol】 建立文本正規化、dedup、language、published time、entity-to-symbol 與 source authority Core tables；entity-to-symbol 保留規則／模型版本、confidence、evidence 與人工覆核狀態，sentiment、buzz、AI alert 與投資判讀只寫 versioned Mart。
- [ ] 【Sol】 驗證關注需求變更不改寫歷史 membership；最後一位使用者取消關注後停止新的深度收集，但保留依法可保存的歷史 provenance。MVP 超過 50 個 distinct active symbols 時安全拒絕並顯示 quota。

### P1 — Mart 閉環（Planned；advanced capability）

以下不應先於 Product Completeness foreground；既有 deterministic Mart／Gemini narrator／mart.v1 evidence 保持 current truth。

- [ ] 【Sol】 `WBS-5-MART-FACT-PACKS`：建立 Fundamental／Valuation／Positioning／Quant／Event Risk Fact Pack contract、PIT／missing-data／provenance／evidence、baseline compatibility、hash／version lineage；LLM off 不改 facts、canonical numbers 可 replay、mart.v1 compatibility。
- [ ] 【Sol】 `WBS-5-MART-AI-ROLE-CONTRACT`：五個 structured AI role output、locked system guardrail、versioned methodology prompts、CIO contract；invalid role structured failure、old artifact immutable。
- [ ] 【Sol】 `WBS-5-MART-AI-VALIDATION`：schema、evidence ID、numeric grounding、analysis-as-of time fence、future leakage、missing-data honesty、claim coverage；invalid output 不得 publish，one-role failure 不得宣稱 full success。
- [ ] 【Sol】 `WBS-5-MART-V2-COMPAT`：保留 `mart.v1`、新增 additive artifact／validator contract、規劃 future mart.v2 migration；既有 v1 fixtures／consumer 不破壞，migration 前不升版。
- [ ] 【Sol】 `WBS-5-MART-AI-PROVIDERS`：governed `MartAIProvider`、Gemini／OpenRouter、capability discovery、bounded parameters、billing gate、structured failure；unsupported model／parameter rejection、429／unavailable retry bounds。
- [ ] 【Sol】 `WBS-5-MART-CIO-SYNTHESIS`：validated roles only、CIO synthesis／validator、無 publication authority；publication 仍由 deterministic governance 決定。
- [ ] 【Sol】 `WBS-5-MART-RERUN-CACHE`：single-role rerun、dependency invalidation、content-addressed reuse、immutable artifact lineage；prompt/model 不重算 facts、governance-only 不呼叫 LLM、reuse 有 audit。

### P1 — Admin advanced governance／AI operations

- [ ] 【Sol】 `WBS-6-ADMIN-ANALYSIS-PROFILE`：Production profile versioning、direct new Production、rollback、role／CIO prompt editor、locked guardrail、model picker、per-role override、fixed 5–10 symbols、compare；dependency：Mart role/provider/validation contracts、Admin shell。
- [ ] 【Luna】 `WBS-6-ADMIN-LEGACY-RETIREMENT`：只在 Flutter parity、Admin auth、browser/runtime acceptance、rollback plan 與 foreground Admin slices 全部完成後 deprecate static Admin；legacy 未達 gate 不刪除。
- [ ] 【Sol】 `WBS-8-PILOT-MART-AI-EVALUATION`：收集 role validation pass rate、provider failure／retry／availability、latency、token usage、actual API cost、cache reuse、single-role rerun、manual intervention、rollback、usefulness、deterministic／AI divergence 與 outcome lineage；每筆 evidence 綁 immutable lineage，清楚區分 partial／failure／full success；不是 predictive tuning。

## Pilot Feature Freeze／Deferred

Freeze 只限制**可有可無的 net-new feature expansion**；不限制既有 dev 真實使用所需的 correctness、security、data-integrity、market coverage、portfolio valuation、User baseline usability、Admin operability、cost regression fix 或 Pilot blocker fix。

仍 frozen／deferred：

- Janus 舊 WBS-4C Chat／Agent 工作已退役；不在 Janus Pilot scope 內重開通用助理 runtime、Skills 或 provider 擴張。
- social／Podcast／未核准 alternative-source adapter、extra AI role、額外非必要 analysis dashboard 與純 cosmetic polish。
- Pilot 實際不用的完整 device／A11y matrix；實際使用裝置所需的 release coverage 仍保留。
- 新 GCP service、HA／replica／multi-region／GKE，以及只為架構漂亮而新增 infrastructure。

Supply-chain Intelligence foundation／research planning 仍是明確例外；只允許 ontology、Source Matrix、seed graph、signal contract 與 Pilot measurement／epoch planning。Production ingestion、schema／migration、crawler、未核准 adapter、paid source、tick／high-frequency source、Mart implementation 與新 GCP resource 仍受原 Gate A–E 與 source approval 約束。

## P2 — PIT 與治理校準

- [ ] 【Sol】 PIT outcome／sample payload 寫 GCS／Iceberg；PostgreSQL 只保存有 retention 的索引、排除原因與 audit metadata，避免 Free Tier disk 無界成長。
- [ ] 【Sol】 5／20／60 交易日 outcome pipeline。
- [ ] 【Sol】 relative benchmark、MFE／MAE、coverage。
- [ ] 【Sol】 缺 publication time／provenance 樣本排除。
- [ ] 【Sol】 每個排除保留原因與 ID。
- [ ] 【Sol】 對 weights／40-60 thresholds 做 walk-forward。
- [ ] 【Sol】 建立正式治理 revision 提案。

## P2 — 實機、A11y 與發布

- [ ] 【Luna】 Flutter Android／iOS／Web 的 phone、tablet、desktop breakpoint。
- [ ] 【Luna】 iOS Safari。
- [ ] 【Luna】 Android Chrome。
- [ ] 【Luna】 iPad Safari。
- [ ] 【Luna】 VoiceOver／TalkBack。
- [ ] 【Luna】 WCAG AA contrast。
- [ ] 【Luna】 所有主要控制 ≥44×44。
- [ ] 【Luna】 K 線 pan／zoom／tooltip／替代表格。
- [ ] 【Luna】 Dialog focus trap、Escape、restore、scroll lock。
- [ ] 【Sol】 Dev canary／rollback。
- [ ] 【Sol】 Production 發布前重新決定 PostgreSQL topology、HA、backup、retention 與成本；Free Tier `e2-micro` dev VM 不得直接 promote 為 production。
- [ ] 【Sol】 取得付費儲存／backup 明確授權後，執行 production backup／restore 演練；Free Tier dev 模式不宣稱具備備份保障。
- [ ] 【Sol】 Dev incident runbook。
- [ ] 【Sol】 Production 人工批准。

## P4 — UI 驗收後的資料品質強化（最後執行）

順序 gate：Admin 資料營運中心與 Flutter 主要 User flows 完成自動化、實機與必要 A11y 驗收前，本節保持 blocked，不得提前用 calibration 取代產品完整度修復。

- [ ] 【Luna】 source health telemetry 按 coverage tier 保存 expected／received symbols、success count、latency、freshness、cache age、fallback、schema drift 與合法 empty／unavailable。
- [ ] 【Sol】 建立跨源一致性、null profile、freshness、coverage、schema drift、outlier 與 corporate-action 的完整 DQ ruleset；版本化門檻與例外理由。
- [ ] 【Sol】 校準 market regime、sector rotation、topic uncertainty、candidate health 與 private PnL 的 quality discount；只影響新 Mart revision，不改寫歷史結果。
- [ ] 【Luna】 完成 Admin DQ dashboard、quarantine drill-down、quality revision diff 與 evidence link；不提供 raw payload／object URI 旁路。
- [ ] 【Luna】 以 UI 驗收發現的閱讀誤差、partial／stale 混淆與缺價案例建立回歸集，再決定是否提高 30% development gate。
- [ ] 【Sol】 對 30% gate 做 coverage／錯誤率分析，產出可審查的門檻 revision 提案。
- [ ] 【Sol】 完成 DQ replay、false-positive／false-negative、跨源衝突、資料延遲與 private/public 隔離驗收後，才能提出 production-grade data quality revision。

## Research Context Pilot Evolution roadmap

全部為 `planned`，不新增 Dev Pilot Entry blocker，也不優先於 Product Completeness foreground。

1. [ ] `WBS-3-DATASET-COVERAGE-INVENTORY` 【Sol】 — 先完成 coverage／gap validation，不批准新 source。
2. [ ] `WBS-6-RESEARCH-CONTEXT-CONTRACT` 【Sol】 — dependency：coverage inventory 語意與 bounded context boundary；gate：contract review。
3. [ ] `WBS-4J-PRIVATE-RESEARCH-STATE-CONTRACT` 【Sol】 — dependency：notes／artifacts／Private Core／Mart；先 contract，再決定 schema extension。
4. [ ] `WBS-5-RESEARCH-MART-CONTRACT` 【Sol】 — deterministic signals／Market Regime contract；不在本項定公式。
5. [ ] `WBS-3-RESEARCH-DATASET-GAPS` 【Sol】 — blocked until inventory 證明 Missing／Partial 且個別 source approved；只實作必要 Core gap。
6. [ ] `WBS-6-RESEARCH-CONTEXT-COMPOSITION` 【Sol】 — blocked until semantic、Private Research State 與 Mart contracts；重用 existing `janus-api`。
7. [ ] `WBS-6-RESEARCH-CONTEXT-UI` 【Luna】 — blocked until server composition；gate：UI states／provenance acceptance。
8. [ ] `WBS-6-CHATGPT-MCP-RESEARCH-CONTEXT` 【Sol】 — blocked until MCP contract／adapter 與 server composition；只讀 bounded consumer，無 Drive dependency。
9. [ ] `WBS-5-SUPPLY-RESEARCH-CONTEXT` 【Sol】 — blocked by Supply-chain Gate D／Gate A–E；依已通過 gate 增量納入 indicators。
10. [ ] `WBS-3-NEWS-ALTERNATIVE-SOURCE-REVIEW` 【Sol】 — blocked until Pilot evidence 證明必要性與 source approval／license／cost；優先 official disclosure／financial reporting／company IR／approved news／licensed research，再考慮 social／podcast／alternative data。

## 每張 TODO 的完成證據

完成項目至少附一種可追溯證據：commit SHA、Cloud Build ID、immutable image digest、Cloud Run revision／execution ID、GCS snapshot ID、test report、實機錄影／截圖、治理 revision ID 或 runbook link。文件勾選或 commit 本身不構成功能完成。
