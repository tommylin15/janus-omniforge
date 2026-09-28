# Janus — TODO

版本：2.1
用途：只保留未完成工作與目前驗收條件；完成證據、已失效 planning marker 與歷史 checkpoint 移至 archive。

歷史入口：

- [2026-09-26 Product Completeness reprioritization 與 TODO cleanup](archive/todo-cleanup-and-product-completeness-priority-2026-09-26.md)
- [WBS-3 Liquid-500 rotation completed (2026-09-27)](archive/wbs-3-liquid-500-rotation-completed-2026-09-27.md)
- [WBS-6 Portfolio Completeness completed (2026-09-27)](archive/todo-completed-2026-09-27-wbs6-portfolio-completeness.md)
- [WBS-6 Market Home Data completed (2026-09-27)](archive/wbs-6-market-home-data-2026-09-27.md)
- [WBS-6 Market Home UI completed (2026-09-27)](archive/wbs-6-market-home-ui-2026-09-27.md)
- [TODO 歷史 checkpoint、退役 WBS 4C 與已完成 checklist（2026-09-23）](archive/todo-history-and-completed-2026-09-23.md)
- [已完成 WBS 0／1／2／4](archive/wbs-completed-through-2026-08-31.md)
- 其他既有完成紀錄保留於 `archive/`；完整 runtime／deployment evidence 見 `spec/operations-and-testing.md`。

## 執行模式：兩條並行主線

Janus 已進入六個月 Dev Pilot observation window，但這不等於 feature freeze 或產品完成。現在分成兩條彼此獨立的主線：

1. **Product Completeness foreground**：補齊目前 dev 真實使用的資料與操作閉環；以使用者指定的整個 WBS 為工作與驗收單位，將可合併項目批次完成，不在每個 dataset／內部原子步驟間停等。遇到真實外部 blocker 時，繼續完成其他獨立條件並如實標記未完成部分。
2. **`WBS-8-DEV-PILOT-RUN` operational observation**：持續累積自然 Scheduler／ingestion／analysis、backup／restore、outcome、usefulness、cost、manual intervention、recurring failure 與 security／privacy evidence；沒有新 evidence 時不製造人工 checkpoint。

Observation window 不阻擋 correctness、data-integrity、market coverage、portfolio valuation、User baseline usability 或 Admin operability 修復；但也不自動授權 Production、付費 source、新付費 API／model、新 GCP service、HA／multi-region 或其他仍受 gate 的範圍。

## 模型確認規則

- 每次只取 foreground queue 中的一個 WBS。正式執行前，AI 必須先提醒建議模型與 WBS ID／名稱，等使用者明確回覆已切換模型後才開始；開始後完成該 WBS 的整體 acceptance scope，不在其內部 datasets／原子步驟間重複停等。遇到需使用者決策的 blocker 時，先完成其餘可繼續部分；完成整體或只剩無法自行解除的 blocker 後停止，下一個 WBS 再重新確認。
- 六個月 observation checkpoint 是 evidence 工作，不應為了「下一項」而人工觸發本來應自然發生的 production-like workload；需要執行 bounded repair／acceptance 時仍依各 WBS 的模型與授權規則。
- 每個日曆日第一次 Gemini 串接前，先查官方模型清單，選出當日前三個 Stable model，依序試用；優先 free tier，不自動開啟 paid gate，並受使用者明確授權的 scope／次數上限約束。全部失敗時維持 fail-closed、不得寫 placeholder。

## A. Product Completeness foreground queue

### 1. `WBS-3-FULL-MARKET-BASE-COVERAGE` — 【Sol；ID 保留，範圍修訂為週量 500 檔】

Dependency：`WBS-3-LIQUID-500-ROTATION`。本 ID 的舊「所有 enabled 股票全市場」驗收條件由使用者於 2026-09-27 改為每週有效的 500 檔；不得把 500 檔結果宣稱為所有上市／上櫃股票完整 coverage。

2026-09-28 完整 bounded replay 仍為 **partial**：effective 500、OHLCV 499/500、TWSE valuation 362/364、MOPS financials 336/500。TPEx 官方估值 adapter 完成 GCP dev 驗收（workflow `36379062350`／execution `janus-ingestion-core-nkq8x`）：135/136，缺 `3718`；官方同日原始回應亦無此代號，依使用者指示停止追補。TPEx 三大法人 adapter 亦完成 GCP dev 定向驗收（workflow `36381307608`／execution `janus-ingestion-core-rpkp9`）：effective 500 中 TPEx institutional 136/136，missing 0，Core 新增 408 筆。融資券／借券／當沖及其餘缺口未完成。詳見 [`operations-and-testing`](spec/operations-and-testing.md)。

依使用者 2026-09-28 指示，停止追補 `3718` 的 TPEx 估值；仍保留其有效 500 membership 與 expected／missing，不將 135/136 改寫成 136/136。

- [ ] 對有效 500 檔收集日 OHLCV、PE/PB、法人、融資券／借券／當沖、基本面摘要與官方 benchmark；市場型 endpoint 必須單次抓取、批次快取、依 symbol 分配。來源缺少合規批次路徑時標 blocked，不以 500 次逐檔請求冒充完成。
- [ ] coverage inventory 能指出有效 500 檔的 expected／received／missing，並保留 source／snapshot／execution provenance；其餘 enabled 股票標示不屬本週基礎 coverage。
- [ ] 新增個人 watchlist 時由後端檢查有效 500 檔版本；既有項目離榜不自動刪除。真實 active holdings 即使離榜，仍須由正式行情補齊路徑估值或明示 missing／blocked。
- [ ] replay、成本、runtime、DQ 與 quarantine acceptance 維持既有 WBS 3 規則。

### 2. `WBS-6-FLUTTER-ADMIN-SHELL` — 【Luna】

- [ ] 單一 Flutter codebase 的 Admin workspace、中文主導覽、responsive shell。
- [ ] backend Admin auth／token audience negative tests 通過；Flutter 隱藏控制不作 security boundary。
- [ ] Legacy static Admin 在 parity、browser/runtime acceptance 與 rollback plan 完成前保留。

### 3. `WBS-6-ADMIN-OVERVIEW-BATCH` — 【Luna】

Dependency：`WBS-6-FLUTTER-ADMIN-SHELL`。

- [ ] actionable-issues-first overview，先顯示需要處理的 Core／Mart／failure 問題；正常 execution 不佔首頁主要空間。
- [ ] batch／retry classification、retryable failed item、execution lineage 可操作；partial success 不作 full success。
- [ ] Operator 能不登入 GCP／直接查 DB 就定位近期失敗與安全重跑既有允許的 workload。

### 4. `WBS-6-ADMIN-STOCK-WORKBENCH` — 【Sol】

Dependency：Admin shell、Core persisted readers；AI role-impact／historical role/CIO 功能仍受 Mart contracts dependency。

- [ ] 第一階段先完成代號／中文名搜尋、dataset health、coverage／gap、最近 execution／snapshot 與安全 gap-repair 入口。
- [ ] 技術 lineage 放在進階，不以 raw JSON 作主要 UX；old execution／snapshot immutable。
- [ ] 未完成 Fact Pack／AI role／CIO contracts 時，不顯示或假裝相關 rerun／historical AI capability 已可用。

### 5. `WBS-6-PORTFOLIO-INTRADAY-QUOTE` — 【Blocked：正式行情來源授權】

- [ ] 先確認持股即時行情供應者的帳戶資格、使用／保存／雲端展示條款、quota 與費用；未核准前不啟用新來源或把盤後價稱為即時價。
- [ ] Shioaji 一次性連線探測（2026-09-27）：既有 Secret 標為 `simulation=true`，模擬環境登入、2330 合約查詢及單檔 Quote 訂閱／取消成功；相同憑證切 `simulation=false` 登入回 `BadRequestError`（含 permission 訊息）。週末無交易時段報價，尚未證明正式環境授權、即時報價到達、保存／雲端展示權利或費用；正式帳戶資格需另確認。
- [ ] 經核准後只訂閱真實持股所需 symbol；後端保留報價時間／來源／freshness 並計算盤中市值，不覆蓋正式盤後 Core OHLCV／Private Mart。User UI 約每 10 分鐘與手動更新都讀同一最新持久化／受控快取，失聯時顯示 stale。

## B. Dev Pilot operational observation

### `WBS-8-DEV-PILOT-RUN` — 【Sol】

- [ ] 自 `pilot_started_at=2026-09-24T15:29:19Z` 起持續 6 calendar months operational phase；累積 monthly evidence summary、Scheduler／ingestion／analysis、backup／restore、outcome、usefulness、cost、manual intervention、recurring failure 與 security／privacy evidence。
- [ ] `pilot-operational-evidence.md` 已記錄 Checkpoint 001（自然 Scheduler failure、calendar repair 與 bounded dataset acceptance）及 Checkpoint 002（deployment-controller consolidation、canonical bounded deployment acceptance 與獨立 post-acceptance verification）；repair 後下一筆自然 Scheduler execution 仍是 pending evidence boundary，兩類手動／bounded acceptance 都不得代替自然 Scheduler recovery evidence。
- [ ] 沒有實際 post-start evidence 的 category 維持 `not observed`／`unknown`；Entry baseline 不可自動當成狀態未變的證據。
- [ ] 六個月 window 未完成前 Production promotion blocked。

### `WBS-8-PROD-GO-NOGO` — 【Sol】

- [ ] Blocked until Pilot 完整執行 6 calendar months；review data reliability、analysis usefulness、PIT/outcome、operations burden、automation reliability、actual cost/value、security/privacy 與 feature usage，並列出各功能 keep／freeze／remove／productionize。
- [ ] Outcome 為 `GO`／`EXTEND_PILOT`／`NO_GO`；`GO` 只允許開始 production architecture／migration planning，不等於自動 production deploy。

## C. 其他有效 backlog（不在 foreground queue）

### P0 — User App Final Visual Convergence（presentation acceptance overlay）

本節不改變目前 foreground queue 的執行順序；它固定 User App 的最終 presentation target，並要求所有相關 User WBS 在各自 dependency 完成時向同一成品收斂。權威 contract：`ui/user-app.md` 與 `ui/reference/user-app-final/README.md`。

- [ ] 【Luna】 `WBS-6-USER-FINAL-VISUAL-CONVERGENCE`：依固定路徑 `today.png`／`watchlist.png`／`ledger.png`／`stock-detail.png` 完成四頁 final presentation convergence；目前 PNG binary 尚待由可寫 binary 的 Git／GitHub 環境補入，未補入前不得宣稱 visual reference binary 已完成。
- [ ] 【Luna】 Today Final：deterministic market baseline first；Mart 研究區塊可獨立 partial／unavailable；request bounded、不得永久 spinner；390×844 級手機 hierarchy 與 final contract 一致。
- [ ] 【Luna】 Watchlist Final：canonical name＋symbol、persisted recent price/date、held state、target price、pending note、500 admission／50 quota／離榜保留；card presentation 與 stock-detail navigation 完整。
- [ ] 【Luna】 Ledger Final：aggregate market value／unrealized PnL／return／YTD realized／valuation status、持股／紀錄／報表、append-only trade UX；Flutter 不自行計算 canonical PnL。
- [ ] 【Luna】 Stock Detail Final：依固定 primary order 顯示持股、筆記、健康度、白話摘要、why／risk、籌碼、事件、evidence；K 線／Fact Pack／五角色／CIO 只在 dependency 可用時放進 advanced section，不以 placeholder 冒充。
- [ ] 【Sol】 Cross-screen live acceptance：targeted／golden／screenshot regression + GCP dev 真實 authenticated owner／persisted data browser screenshot；四頁一致視覺語言、loading／empty／error／partial／stale／missing 不破版，sample mock data 未進 canonical runtime。

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
