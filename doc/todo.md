# Janus — TODO

版本：2.0
用途：只保留未完成工作與目前驗收條件；完成證據移至 archive。

已完成項目與歷史 checkpoint：

- [TODO 歷史 checkpoint、退役 WBS 4C 與已完成 checklist（2026-09-23）](archive/todo-history-and-completed-2026-09-23.md)
- [Janus／omniAgent 舊 WBS 4C 規劃（已取代）](archive/wbs-4c-janus-assistant-plan-superseded-2026-09-23.md)
- [omniAgent 拆分準備包（已取代）](archive/omniagent-split-preparation-superseded-2026-09-23.txt)

- [TODO 完成紀錄（截至 2026-08-31）](archive/todo-completed-through-2026-08-31.md)
- [TODO 完成紀錄（2026-09-02）](archive/todo-completed-2026-09-02.md)
- [TODO 完成紀錄（2026-09-03）](archive/todo-completed-2026-09-03.md)
- [TODO 完成紀錄（2026-09-05）](archive/todo-completed-2026-09-05.md)
- [TODO 完成紀錄（2026-09-06）](archive/todo-completed-2026-09-06.md)
- [TODO 完成紀錄（2026-09-09）](archive/todo-completed-2026-09-09.md)
- [TODO 完成紀錄（2026-09-11）](archive/todo-completed-2026-09-11.md)
- [TODO 完成紀錄（2026-09-12：WBS-5）](archive/todo-completed-2026-09-12-wbs5.md)
- [TODO 完成紀錄（2026-09-13：WBS-6／WBS-7）](archive/todo-completed-2026-09-13-wbs6-wbs7.md)
- [TODO 完成紀錄（2026-09-16：WBS-6 usefulness feedback）](archive/todo-completed-2026-09-16-wbs6-usefulness-feedback.md)
- [TODO 完成紀錄（2026-09-16：WBS-8 outcome collection）](archive/todo-completed-2026-09-16-wbs8-outcome-collection.md)
- [TODO 完成紀錄（2026-09-17：WBS-8 pilot release baseline）](archive/todo-completed-2026-09-17-wbs8-pilot-release-baseline.md)
- [已完成 WBS 0／1／2／4](archive/wbs-completed-through-2026-08-31.md)

## High-Completion Dev Pilot Target（planning marker；不變更正式 Entry Gate）

- 使用者選擇 High-Completion strategy：在不越過 Production、Post-Pilot evidence-dependent work、未核准 data source、frozen scope 與 human approval gates 的前提下，盡可能提高 Dev Pilot Day 1 完成度。
- `High-Completion Target` 是使用者選擇的較高完成度 execution strategy，不改變正式 `Dev Pilot Entry Gate`；未完成 target 中的非正式 blocker，不等同於正式 Entry Gate failure。
- 正式 `WBS-8-DEV-PILOT-ENTRY` Gate 不變；某項即使標記 `【High-Completion Target】`，也不代表其 governance classification 已變成 `Entry Blocker`。正式 `WBS-8-DEV-PILOT-ENTRY` checklist 保持獨立標記與判定。

## 下一步執行佇列

WBS-3 canary 與 bounded full-market 驗收已完成並歸檔。依使用者 2026-09-24 指示，`WBS-6-TRANSACTION-UX-2` 升為目前最高優先的 immediate queue；完成後接續 `WBS-8-CHATGPT-MCP-ACCEPTANCE`，再依正式條件評估 `WBS-8-DEV-PILOT-ENTRY`。此排序不改變 Dev Pilot Entry Gate。

## 模型確認規則

- 每次只取佇列中的一個原子任務。正式執行前，AI 必須先提醒建議模型與任務名稱，等使用者明確回覆已切換模型後才開始；完成後停止，下一項重新確認。
- 每個日曆日第一次 Gemini 串接前，先查官方模型清單，選出當日前三個 Stable model，依序試用；優先 free tier，不自動開啟 paid gate，並受使用者明確授權的 scope／次數上限約束。全部失敗時維持 fail-closed、不得寫 placeholder。
- 下方每個未完成待辦均已標示【Sol】或【Luna】；若一項同時含安全／底層與 UI／CRUD，執行前先依上方佇列拆分，不用單一模型包辦混合範圍。

## P1（私人 P0 後續）— Stage／Core 與 Admin MVP 驗證

- [ ] 【Sol】 【High-Completion Target】 UI 驗收可使用本地瀏覽器／Playwright，或按需啟動既有 GCP dev Cloud Run
  service，以實際 dev URL 驗證 responsive、interaction、API/runtime connectivity
  與安全輸出；既有 dev service 通過人工 billing gate 後可直接啟動，不需逐次
  另行授權。驗收證據須記錄 revision、immutable image digest、測試 URL／時間與
  scale-to-zero 狀態；不得部署 production、提高既有限額或建立新付費資源。
  （2026-09-02：實際 dev URL 的 live Playwright、API/runtime 與安全輸出已通過；
  revision／digest 詳見 operations-and-testing。真人 Google login 仍未執行。）

- [ ] 【Sol】 【High-Completion Target】 第一階段完成定義：營運者只透過 Admin 即可設定已核准來源與去識別化深度追蹤名單、觸發／排程 Collection、查看 Stage／Core／quarantine、定位失敗並安全重跑，不需登入 GCP 或直接查資料庫。

## P0（WBS 4J）— 個人記帳、筆記與關注股 MVP

- [ ] 【Sol】 【High-Completion Target】 個人化分析只在 authenticated-user 邊界內引用公開 `mart_scoped_analysis` 的 symbol scope；不阻擋記帳／筆記／關注股 MVP，也不把私人資料寫回公開 Mart。

## WBS 4C — Janus Chat／Agent 工作已退役

通用 Chat／Agent runtime 不屬於 Janus scope；Janus 保留投資 domain API 與 authenticated read-only MCP／OAuth connector。舊待辦與規劃已封存。

## P1 — 全市場量化網

- [ ] 【Sol】 以當日 enabled 股票 master 收集全市場日 OHLCV、PE/PB、法人、融資券／借券／當沖、基本面摘要與官方 benchmark。（2026-09-16 checkpoint：OHLCV runtime registry、symbol-scoped fan-out、DQ／quarantine summary 與 `core.ohlcv_v1` writer 已接入；targeted tests 27 passed，Cloud Build `16962da0-7706-4a08-83aa-1348404d6d45`／digest `sha256:a8953df49f42a9324adeb3eb7cb622de43e75f7fad56763ce11d2bb2beb75dbc` 已部署既有 dev job。原 5 檔中 stale `2381` 已停用並標記 `delisted`；初次重跑 Cloud Run `janus-ingestion-core-rwt4w`／control execution `cffec813-2054-4a2d-a4b4-05846f5d8c46` 使有效 enabled universe 為 4 檔 `1102`／`2327`／`2330`／`4958`，40 rows、quarantined=0、failed=0、Core snapshot 成功。同日 replay `janus-ingestion-core-scdrp`／control execution `ecd1aef9-c6ec-4e03-ab31-b83506a31cc2` 為 `core_created=0`、`core_reused=40`，runtime 14,795 ms；Stage 32,394 bytes、Core 437 bytes，bounded job 1 vCPU／1 GiB／1800 秒。bounded config 已停用；WBS-3 replay／成本／runtime 切片完成，整體量化網仍待其他 dataset。）

## P1 — 個人關注股深度追蹤

- [ ] 【Sol】 對已核准行情來源建立分 K／Tick 獨立排程、quota、retention、failure policy 與成本量測；未核准前保持 blocked。

- [ ] 【Sol】 新聞／券商研究／目標價逐一完成來源授權與 provenance 審查後，才可建立 adapter 與 retention policy。

- [ ] 【Sol】 未核准候選來源只保留 disabled／blocked 設定，不建立 adapter、排程或 Admin 審查 UI；取得外部授權與成本核准後另開 WBS。

- [ ] 【Sol】 建立文本正規化、dedup、language、published time、entity-to-symbol 與 source authority Core tables；entity-to-symbol 保留規則／模型版本、confidence、evidence 與人工覆核狀態，sentiment、buzz、AI alert 與投資判讀只寫 versioned Mart。

- [ ] 【Sol】 【High-Completion Target】 驗證關注需求變更不改寫歷史 membership；最後一位使用者取消關注後停止新的深度收集，但保留依法可保存的歷史 provenance。MVP 超過 50 個 distinct active symbols 時安全拒絕並顯示 quota。

## P1 — Mart 閉環

本節是本次同步新增的 Mart next-version roadmap；全部 `Planned`，不表示現況已完成，
也不自動開始 implementation WBS。既有 deterministic Mart／Gemini narrator／mart.v1
evidence 保持 current truth。

- [ ] 【Sol】 `WBS-5-MART-FACT-PACKS`（Planned；Pilot M1）：建立 Fundamental／Valuation／Positioning／Quant／Event Risk Fact Pack contract、PIT／missing-data／provenance／evidence、baseline compatibility、hash／version lineage；dependency：Core snapshot、既有 `analysis.py`／`mart.v1`；acceptance：LLM off 不改 facts、canonical numbers 可 replay、mart.v1 compatibility。
- [ ] 【Sol】 `WBS-5-MART-AI-ROLE-CONTRACT`（Planned；Pilot M1）：五個 structured AI role output、locked system guardrail、versioned methodology prompts、CIO contract；dependency：FACT-PACKS；acceptance：schema／lineage fixture、invalid role structured failure、old artifact immutable。
- [ ] 【Sol】 `WBS-5-MART-AI-VALIDATION`（Planned；Pilot M1）：schema、evidence ID、numeric grounding、analysis-as-of time fence、future leakage、missing-data honesty、claim coverage；dependency：ROLE-CONTRACT；acceptance：invalid output 不得 publish、one-role failure 不得宣稱 full success。
- [ ] 【Sol】 `WBS-5-MART-V2-COMPAT`（Planned；Pilot M1）：保留 `mart.v1`、新增 additive artifact／validator contract、規劃 future mart.v2 migration；dependency：FACT-PACKS／ROLE-CONTRACT；acceptance：既有 v1 fixtures／consumer 不破壞，migration 前不升版。
- [ ] 【Sol】 `WBS-5-MART-AI-PROVIDERS`（Planned；Pilot M2）：governed `MartAIProvider`、Gemini／OpenRouter、capability discovery、bounded parameters、billing gate、structured failure；dependency：ROLE-CONTRACT；acceptance：兩 provider contract tests、unsupported model／parameter rejection、429／unavailable retry bounds。
- [ ] 【Sol】 `WBS-5-MART-CIO-SYNTHESIS`（Planned；Pilot M3）：validated roles only、CIO synthesis、CIO validator、無 publication authority；dependency：AI-VALIDATION；acceptance：CIO invalid blocked，publication 仍由 deterministic governance 決定。
- [ ] 【Sol】 `WBS-5-MART-RERUN-CACHE`（Planned；Pilot M3）：single-role rerun、dependency invalidation、content-addressed reuse、immutable artifact lineage；dependency：FACT-PACKS／AI-VALIDATION／CIO-SYNTHESIS；acceptance：無關 role 不重跑、prompt/model 不重算 facts、governance-only 不呼叫 LLM、reuse 有 audit。

## P1 — Admin Governance／Reports

- [ ] 【Luna】 `WBS-6-FLUTTER-ADMIN-SHELL`（Planned；Pilot M4）：單一 Flutter codebase 的 Admin workspace、中文主導覽、responsive shell；dependency：Admin auth contract、現有 User App／static Admin；acceptance：backend Admin auth／audience negative tests、legacy static 保留。
- [ ] 【Luna】 `WBS-6-ADMIN-OVERVIEW-BATCH`（Planned；Pilot M4）：actionable-issues-first overview、batch、retry classification、retry failed item、execution lineage；dependency：ADMIN-SHELL、execution API；acceptance：只重試 retryable failed item、old execution preserved、partial 不作 full。
- [ ] 【Sol】 `WBS-6-ADMIN-STOCK-WORKBENCH`（Planned；Pilot M4）：symbol／中文名 search、dataset health、gap repair、role-impact mapping、affected-role rerun、historical analysis；dependency：ADMIN-SHELL、Fact／Mart readers；acceptance：歷史 facts／roles／CIO 可讀、舊 artifact immutable、rerun lineage 可見。
- [ ] 【Sol】 `WBS-6-ADMIN-ANALYSIS-PROFILE`（Planned；Pilot M5）：Production profile versioning、direct new Production、rollback、role／CIO prompt editor、locked guardrail、model picker、per-role override、fixed 5–10 symbols、compare；dependency：Mart role/provider/validation contracts、ADMIN-SHELL；acceptance：不可覆蓋舊版、rollback audit、unsupported parameter 不送出、comparison 可重現。
- [ ] 【Luna】 `WBS-6-ADMIN-LEGACY-RETIREMENT`（Planned；Pilot M6）：只在 Flutter parity、Admin auth、browser/runtime acceptance、rollback plan 全部完成後 deprecate static Admin；dependency：前四個 Admin slices；acceptance：legacy 未達 gate 不刪除。

## P1 — Pilot Mart AI evaluation

- [ ] 【Sol】 `WBS-8-PILOT-MART-AI-EVALUATION`（Planned；Pilot M6）：收集 role validation pass rate、provider failure／retry／availability、latency、token usage、actual API cost、cache reuse、single-role rerun、manual intervention、rollback、usefulness、deterministic／AI divergence 與 outcome lineage；dependency：WBS-5 AI validation／CIO／rerun-cache、WBS-6 Analysis Profile；acceptance：每筆 evidence 綁 immutable lineage，清楚區分 partial／failure／full success；不是 predictive tuning。

### Six-month relative mapping

repository 尚無正式 `pilot_started_at`，只使用相對月份：M1 contracts／Fact foundation、
M2 provider／AI analyst runtime、M3 CIO／precise rerun、M4 Flutter Admin migration、
M5 Analysis Profile、M6 hardening／evidence／legacy retirement decision。未開始 Pilot，
不得填寫假的 calendar date。

## P1 — FastAPI／Flutter User

- [ ] 【Luna】 `WBS-6-TRANSACTION-UX-2`（In Progress；最高優先、immediate queue；Pilot UX evolution；**非 Dev Pilot Entry blocker**）：Flutter/API 本地實作、targeted tests、dev no-traffic candidate 及匿名 `/health`、`/app/` smoke checks 已完成；待 Chrome authenticated UX／private-flow acceptance。依 `ui/user-app.md` 5.4.1 完成交易記錄 `年份 → 月份 accordion → 單筆 detail`、手機快速新增 FAB、event-type-aware form、持股卡片與報表 presentation；保留 append-only correction semantics、Private Mart canonical valuation／PnL 與 pending-update 文案。若月份 canonical summary 不能由現有 bounded endpoints 組合取得，先定義 typed additive private summary contract，再交由 implementation；不得由 Flutter 自定 realized PnL／fee／tax 公式。acceptance：phone／desktop responsive、cash flow 與 PnL 分離、valuation date／partial／stale／missing 正確顯示、交易成功不假裝 portfolio 已同步、correction 不覆寫歷史、owner isolation 不退化。Private Mart 以各股 quote date 早於 valuation date 標記 stale，且 withheld stale／missing aggregate unrealized PnL。

## P1 — 全系統自動化測試

## P1 — WBS-7 安全、監控與 FinOps

## P1 — Pilot Readiness Gaps

## P1 — ChatGPT MCP Connector（Dev Pilot Enabler）

- [ ] 【Sol】 【High-Completion Target】 `WBS-8-CHATGPT-MCP-ACCEPTANCE`：refresh-token rotation/revocation 已實作；90 天閒置期限及自動加入 `offline_access` 的明確 consent 已部署到 GCP dev `mcp-oauth` 標籤；三工具 discovery、market／positions／performance／trades／investment-profile 實呼、schemas、metadata、unauthenticated challenge、negative input 與 OAuth negative acceptance 通過。90 天閒置期限下，access token 到期後 `janus_sources` 自動換發與 rotation 已由 Cloud Run token endpoint 200、資料庫 refresh token 筆數維持 1 且 `issued_at` 更新、沒有重新授權請求證實。第二個 Google owner `tommylin0119@gmail.com` 的 dev API 與 MCP allowlist 已修正，MCP 標籤切換後 Cloud Build acceptance 通過；已完成 authenticated investment-profile read，待確認該 ChatGPT 授權身分為 B，再比對 B 只讀自己的私人資料、切回 A 仍只讀 A 的資料。此 connector 不得成為 Janus Production Release prerequisite；最新證據見 [`spec/operations-and-testing.md`](spec/operations-and-testing.md)。

## Pilot Feature Freeze／Deferred

以下未完成類型移出 active execution queue，標示為 Pilot feature freeze／deferred；不刪除既有 code 或歷史 TODO。只有 correctness、security、data-integrity、cost regression、Pilot blocker fix 或既有功能維護可例外處理：

- Janus 舊 WBS-4C Chat／Agent 工作已退役；不在 Janus Pilot scope 內重開通用助理 runtime、Skills 或 provider 擴張。
- social／Podcast／未核准 alternative-source adapter、extra AI role、extra analysis dashboard、額外 UI cosmetic polish。
- Pilot 實際不用的完整 device／A11y matrix；實際使用裝置所需的 release coverage 仍保留。
- 新 GCP service、HA／replica／multi-region／GKE，以及為架構漂亮而新增 infrastructure。

Supply-chain Intelligence foundation／research planning 是本 freeze 的明確例外；只允許
ontology、Source Matrix、seed graph、signal contract 與 Pilot measurement／epoch planning。
production ingestion、schema／migration、crawler、未核准 adapter、paid source、tick／
high-frequency source、Mart implementation 與新 GCP resource 仍 frozen／deferred，直到
WBS-5 Gate A–E 及個別 source approval 條件滿足。

## P2 — PIT 與治理校準

Pilot Day-1 outcome collection 已前移至 `WBS-8-PILOT-OUTCOME-COLLECTION`；本節保留
後續 calibration／optimization、artifact hardening 與治理 revision，不把 model tuning
提前成為 Pilot Entry blocker。

- [ ] 【Sol】 【High-Completion Target】 PIT outcome／sample payload 寫 GCS／Iceberg；PostgreSQL 只保存有 retention 的索引、排除原因與 audit metadata，避免 Free Tier disk 無界成長。

- [ ] 【Sol】 【High-Completion Target】 5／20／60 交易日 outcome pipeline。

- [ ] 【Sol】 【High-Completion Target】 relative benchmark、MFE／MAE、coverage。

- [ ] 【Sol】 【High-Completion Target】 缺 publication time／provenance 樣本排除。

- [ ] 【Sol】 【High-Completion Target】 每個排除保留原因與 ID。

- [ ] 【Sol】 對 weights／40-60 thresholds 做 walk-forward。

- [ ] 【Sol】 建立正式治理 revision 提案。

## P2 — 實機、A11y 與發布

- [ ] 【Luna】 【High-Completion Target】 Flutter Android／iOS／Web 的 phone、tablet、desktop breakpoint。

- [ ] 【Luna】 【High-Completion Target】 iOS Safari。

- [ ] 【Luna】 【High-Completion Target】 Android Chrome。

- [ ] 【Luna】 【High-Completion Target】 iPad Safari。

- [ ] 【Luna】 【High-Completion Target】 VoiceOver／TalkBack。

- [ ] 【Luna】 【High-Completion Target】 WCAG AA contrast。

- [ ] 【Luna】 【High-Completion Target】 所有主要控制 ≥44×44。

- [ ] 【Luna】 【High-Completion Target】 K 線 pan／zoom／tooltip／替代表格。

- [ ] 【Luna】 【High-Completion Target】 Dialog focus trap、Escape、restore、scroll lock。

- [ ] 【Sol】 【High-Completion Target—Dev only】 canary／rollback。

- [ ] 【Sol】 production 發布前重新決定 PostgreSQL topology、HA、backup、retention 與成本；Free Tier `e2-micro` dev VM 不得直接 promote 為 production。

- [ ] 【Sol】 取得付費儲存／backup 明確授權後，執行 production backup／restore 演練；Free Tier dev 模式不宣稱具備備份保障。

- [ ] 【Sol】 【High-Completion Target—Dev only】 incident runbook。

- [ ] 【Sol】 production 人工批准。

## P2 — WBS 8 Dev Pilot／Production Readiness

- [ ] 【Sol】 `WBS-8-DEV-PILOT-ENTRY`：Blocked until WBS-3 canary／full-market safety、ledger durability successful restore、outcome collection、usefulness feedback、release baseline、minimum data-safety DQ（required key／type、duplicate、future leakage、freshness、basic coverage、schema drift、適用時的 obvious outlier／corporate-action sanity）與 security／privacy／cost evidence ready；`WBS-5-SUPPLY-INTELLIGENCE-PLANNING` 也必須完成，但不要求六個 domain ingestion-ready。ChatGPT MCP acceptance 完成，或使用者明確決定允許 connector blocked 狀態啟動 Pilot。只有 Entry Gate 通過時記錄 `pilot_started_at`，不新增 staging／production infrastructure；完整 DQ dashboard／tuning／大型 drill-down 留後續。

- [ ] 【Sol】 `WBS-8-DEV-PILOT-RUN`：Entry 完成後開始 6 calendar months operational phase，持續執行 Scheduler／ingestion／analysis，累積 monthly evidence summary、backup／restore、outcome、usefulness、cost、manual intervention、recurring failure 與 security／privacy evidence；不新增 feature roadmap，production promotion blocked。

- [ ] 【Sol】 `WBS-8-PROD-GO-NOGO`：Blocked until Pilot 完整執行 6 calendar months；review data reliability、analysis usefulness、PIT/outcome、operations burden、automation reliability、actual cost/value、security/privacy 與 feature usage，並列出各功能 keep／freeze／remove／productionize。Outcome 為 `GO`／`EXTEND_PILOT`／`NO_GO`；`GO` 只允許開始 production architecture／migration planning。

## P4 — UI 驗收後的資料品質強化（最後執行）

順序 gate：Admin 資料營運中心與 Flutter「關注／記帳／筆記／AI／個股健康」完成自動化、實機與 A11y 驗收前，本節全部保持 blocked，不得提前開工。

- [ ] 【Luna】 【High-Completion Target】 source health telemetry 按 coverage tier 保存 expected／received symbols、success count、latency、freshness、cache age、fallback、schema drift 與合法 empty／unavailable。

- [ ] 【Sol】 【High-Completion Target】 建立跨源一致性、null profile、freshness、coverage、schema drift、outlier 與 corporate-action 的完整 DQ ruleset；版本化門檻與例外理由。

- [ ] 【Sol】 校準 market regime、sector rotation、topic uncertainty、candidate health 與 private PnL 的 quality discount；只影響新 Mart revision，不改寫歷史結果。

- [ ] 【Luna】 【High-Completion Target】 完成 Admin DQ dashboard、quarantine drill-down、quality revision diff 與 evidence link；不提供 raw payload／object URI 旁路。

- [ ] 【Luna】 【High-Completion Target】 以 UI 驗收發現的閱讀誤差、partial／stale 混淆與缺價案例建立回歸集，再決定是否提高 30% development gate。

- [ ] 【Sol】 對 30% gate 做 coverage／錯誤率分析，產出可審查的門檻 revision 提案。

- [ ] 【Sol】 完成 DQ replay、false-positive／false-negative、跨源衝突、資料延遲與 private/public 隔離驗收後，才能提出 production-grade data quality revision。

## Research Context Pilot Evolution roadmap

本 roadmap 全部為 `planned`，不新增 Dev Pilot Entry blocker；完成狀態必須由 repository／acceptance evidence 更新。

1. [ ] `WBS-3-DATASET-COVERAGE-INVENTORY` 【High-Completion Target】 — status: `planned`；dependency: 現有 source registry／adapter／Core publication evidence；gate: Data Source admission；classification: Pilot Evolution。先完成 coverage／gap validation，不批准新 source。
2. [ ] `WBS-6-RESEARCH-CONTEXT-CONTRACT` 【High-Completion Target】 — status: `planned`；dependency: coverage inventory 語意與現有 bounded context boundary；gate: contract review；classification: Pilot Evolution。
3. [ ] `WBS-4J-PRIVATE-RESEARCH-STATE-CONTRACT` 【High-Completion Target】 — status: `planned`；dependency: notes／artifacts／Private Core／Mart 現況；gate: owner isolation／revision review；classification: Pilot Evolution。先 contract，再決定 schema extension。
4. [ ] `WBS-5-RESEARCH-MART-CONTRACT` 【High-Completion Target】 — status: `planned`；dependency: coverage inventory／ResearchContext contract；gate: deterministic／PIT contract review；classification: Pilot Evolution。規劃 deterministic signals 與 Market Regime，不在本項定公式。
5. [ ] `WBS-3-RESEARCH-DATASET-GAPS` — status: `blocked`；dependency: inventory 證明 Missing／Partial 且個別 source approved；gate: Data Source admission／cost／license；classification: Pilot Evolution。只實作必要 Core gap。
6. [ ] `WBS-6-RESEARCH-CONTEXT-COMPOSITION` — status: `blocked`；dependency: semantic、Private Research State 與 Mart contracts；gate: API security／owner scope review；classification: Pilot Evolution。重用 existing `janus-api`。
7. [ ] `WBS-6-RESEARCH-CONTEXT-UI` — status: `blocked`；dependency: server composition；gate: UI states／provenance acceptance；classification: Pilot Evolution。
8. [ ] `WBS-6-CHATGPT-MCP-RESEARCH-CONTEXT` — status: `blocked`；dependency: MCP CONTRACT／ADAPTER 與 server composition；gate: `WBS-8-CHATGPT-MCP-ACCEPTANCE`；classification: Pilot Evolution。只讀 bounded consumer，無 Drive dependency。
9. [ ] `WBS-5-SUPPLY-RESEARCH-CONTEXT` — status: `blocked`；dependency: Supply-chain Gate D；gate: Gate A–E；classification: existing gated work。依已通過 gate 增量納入 indicators。
10. [ ] `WBS-3-NEWS-ALTERNATIVE-SOURCE-REVIEW` — status: `blocked`；dependency: Pilot evidence 證明必要性；gate: source approval／license／cost；classification: Post-Pilot Conditional。優先順序為 official disclosure／financial reporting／company IR／approved news／licensed research／social／podcast／alternative data。

## 每張 TODO 的完成證據

完成項目至少附一種：PR URL、commit SHA、Cloud Build ID、image digest、Cloud Run revision／execution ID、GCS snapshot ID、test report、實機錄影／截圖、治理 revision ID 或 runbook link。
