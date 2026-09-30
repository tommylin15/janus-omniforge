# Janus — 五位分析師每日運作 Gate

更新：2026-09-30

## 目的

本文件定義「Janus 的 5 位 AI 分析師已開始天天工作」的最低工程與驗收邊界，避免把「角色 prompt 已存在」、「人工 trigger 跑過一次」或「六個月 Dev Pilot 已啟動」誤認為每日分析閉環已成立。

本文件是既有 active WBS 的里程碑映射，不取代 `todo.md`、`wbs.md` 或各 SPEC。若本文與 active TODO／實作／runtime evidence 不一致，依 `PROJECT_RULES.md` 的權威順序判定。

## 核心結論

**不需要等六個月 Dev Pilot 結束，5 位分析師即可在 dev parallel-live environment 開始每日工作。**

`WBS-8-DEV-PILOT-RUN` 的六個月 observation window 阻擋的是 Production promotion，不阻擋 Product Completeness、Mart capability 與 dev daily analysis workload 的持續開發、部署與真實運作。

要正式宣稱「5 位分析師已經每天上班」，必須完成以下鏈路：

> Product Completeness foreground → `WBS-5-MART-FACT-PACKS` → `WBS-5-MART-AI-ROLE-CONTRACT` → `WBS-5-MART-AI-VALIDATION` → `WBS-5-MART-AI-PROVIDERS` → Daily Scheduler／workload integration → natural daily live acceptance

## Gate 1 — Product Completeness foreground

Mart advanced capability 不應先於目前 Product Completeness foreground。Gate 1 定義為以下七項：

1. `WBS-6-PORTFOLIO-COMPLETENESS`
2. `WBS-6-MARKET-HOME-DATA`
3. `WBS-6-MARKET-HOME-UI`
4. `WBS-3-FULL-MARKET-BASE-COVERAGE`
5. `WBS-6-FLUTTER-ADMIN-SHELL`
6. `WBS-6-ADMIN-OVERVIEW-BATCH`
7. `WBS-6-ADMIN-STOCK-WORKBENCH`

**目前狀態：Gate 1 已於 2026-09-29 完成。** 七項均已有 implementation、tests、deployment／runtime 或各自 acceptance evidence；最後一項 `WBS-6-ADMIN-STOCK-WORKBENCH` 的完成紀錄見 `archive/wbs-6-admin-stock-workbench-completed-2026-09-29.md`。這個判定不包含 `WBS-6-PORTFOLIO-INTRADAY-QUOTE`；該項仍因正式行情來源授權 blocked，但不是 Gate 1 的七項之一，因此不阻擋後續安全且獨立的 Gate 2 工作。

這個 gate 的目的不是要求所有未來功能先完成，而是先讓真實持股、市場 baseline、全市場基礎 coverage 與 operator 可觀測性達到足以支撐每日研究的狀態。

## Gate 2 — 5 位分析師具備可重跑的事實輸入

完成 `WBS-5-MART-FACT-PACKS`：

- Fundamental／Valuation／Positioning／Quant／Event Risk Fact Pack contract 可用。
- PIT、missing-data、provenance、evidence、hash／version lineage 明確。
- LLM 不擁有 canonical facts／numbers；關閉 LLM 不得改變 canonical facts。
- 同一 as-of input 可重跑並追溯來源。

**目前狀態：Gate 2 已於 2026-09-30 完成。** 五份 Fact Pack contract、tests、dev deployment、原 target queue recovery 與 pinned Core／Mart real-data replay 均通過；驗收 snapshot 的缺值仍為 `insufficient_data / blocked`，沒有升格為完整研究或可發布。詳見 [結案紀錄](archive/wbs-5-mart-fact-packs-2026-09-30.md)。後續角色契約的完成判定見下方 Gate 3。

達到此 gate 只代表「分析師有受治理的研究資料」，尚不能宣稱 5 位分析師已開始每日工作。

## Gate 3 — 5 個 structured AI role 正式成立

完成 `WBS-5-MART-AI-ROLE-CONTRACT`：

- 建立 5 個 structured AI role output contract。
- methodology prompt versioned。
- locked system guardrail 生效。
- 每個 role output 有 immutable artifact lineage。
- invalid role 必須 structured failure，不得用 placeholder 假裝成功。

達到此 gate 可以說「5 位分析師角色已存在」，但尚不能說「可靠工作」或「天天工作」。

**目前狀態：Gate 3 已於 2026-09-30 完成。** 五角色／CIO contract、versioned methodology、
locked guardrail、schema／prompt／lineage fixtures、dev deployment 與 pinned 真實 snapshot
的 create-only artifact／structured failure acceptance 均通過；詳見 [結案紀錄](archive/wbs-5-mart-ai-role-contract-2026-09-30.md)。
Gate 4／5／6 仍未完成，沒有啟用 AI provider 或自然每日角色 workload。

## Gate 4 — 每位分析師輸出可被治理驗證

完成 `WBS-5-MART-AI-VALIDATION`：

- schema validation。
- evidence ID／claim coverage。
- numeric grounding。
- analysis-as-of time fence／future leakage guard。
- missing-data honesty。
- invalid output 不得 publish。
- 任一 role failure 不得包裝成 five-role full success。

達到此 gate 後，5 位分析師輸出才具備可被系統接受或拒絕的 deterministic governance boundary。

## Gate 5 — GCP 自主 Codex CLI 批次／受控 fallback 可可靠執行

完成 `WBS-5-MART-AI-PROVIDERS`：

- governed `MartAIProvider` contract。
- GCP 既有 Mart 批次內五個獨立 Codex CLI role invocations，CLI 優先；必要 worker bridge
  須驗證具體介面。Gemini／OpenRouter 只作 profile 明列條件與順序的已核准 fallback。
- 初始人工授權後，headless dispatch／cold-start auth／續期／artifact 回收不依賴本機桌面
  或逐次人工 ChatGPT 操作；auth expired／revoked 留 structured failure／required user action。
- CLI／bridge revision、model／structured-output／sandbox capability discovery、role workspace
  隔離、timeout／process-tree cancel／退出碼與 failure diagnostics／secret redaction。
- bounded parameters。
- unsupported model／parameter fail-closed。
- CLI／worker failure 及 fallback provider 429／unavailable retry bounds；保存每次 attempt、
  fallback reason 與實際 provider／transport／model，不以換 provider 繞過 validator。
- billing／paid gate 仍受使用者明確授權，不因本里程碑自動開啟付費模型或 subscription。

達到 Gate 2–5 後，可宣稱「5 位分析師可以可靠工作」，但還不能宣稱「已經天天工作」。

詳細研究與安全邊界見 [GCP Codex 批次 SPEC](spec/intelligence-and-governance.md#gcp-批次-codex-分析師研究路線active-planning尚未實作)。
Gate 4 的 provider-neutral validator fixtures 可先建立；Gate 5 必須另有 GCP 真實 worker
整合 evidence，不能以 fixtures／本機 CLI／文件對齊代替。

## Gate 6 — Daily Scheduler／workload integration 與 natural live acceptance

要宣稱「5 位分析師已經每天上班」，還必須有實際 dev parallel-live evidence 證明完整日常鏈路：

1. 每日 upstream ingestion／required Fact Pack dependency 完成或進入明確 partial／missing 狀態。
2. Scheduler／既有 approved workload 自然觸發 GCP 內的 Codex CLI five-role batch，
   以 active 關注＋有效持股的去重 symbol 聯集固定 as-of membership／target snapshot，
   在持久化 analysis scope／quota 邊界內自主執行；不把 500 檔 collection
   scopes 自動當成 500×5 個 AI invocations，也不只靠人工 one-off trigger。
3. 5 個 role 各自產生 success 或 structured failure artifact，保存 execution／input／prompt／model／provider／transport／CLI revision／attempt／evidence lineage。
4. validator 決定各 role artifact 是否可接受；partial success 不包裝成 full success。
5. artifact persisted，可供後續 CIO／UI／Admin／evaluation 讀取。
6. 至少完成自然 daily execution 的 live acceptance；手動 bounded run 只能作 repair／acceptance 證據，不能單獨證明「天天工作」。
7. 後續自然日執行持續由 `WBS-8-DEV-PILOT-RUN` 累積 reliability、usefulness、cost、manual intervention、recurring failure 與 security／privacy evidence。

個股範圍與 private isolation 見 [AI target SPEC](spec/intelligence-and-governance.md#五角色個股批次範圍active-planning尚未接線)。
驗收需證明 held-only／watch-only／重疊去重／持股離榜／退出／as-of replay；quota 或
missing-data 未達條件時仍列明 partial／blocked，不把持股保留語意當成無界付費授權。

只有 Gate 1–6 都有 implementation、tests、deployment／runtime、trigger／workload 與 live evidence 時，才可在專案文件中寫：

> **Janus 的 5 位分析師已開始每日自動工作。**

## CIO 與 rerun/cache 的邊界

`WBS-5-MART-CIO-SYNTHESIS` 不是「5 位分析師開始每日工作」的硬前置條件；它是 5 位 validated role outputs 之後的綜合判讀層。若產品定義改成「每天 5 位分析師完成後必須再由 CIO 產出總結」，則 CIO synthesis 需加入 daily completion gate。

`WBS-5-MART-RERUN-CACHE` 也不是第一天啟動 five-role daily run 的硬前置條件，但它是長期成本控制、single-role recovery、dependency invalidation、content-addressed reuse 與 immutable lineage 的重要 operability 工作，應在 daily operation 啟動後優先完成，不得以缺少 cache 為由重算 canonical facts 或破壞 lineage。

## 與六個月 Dev Pilot 的關係

- Five-role daily operation 可在 Dev Pilot 期間啟動。
- 六個月 observation window 不必先完成。
- 啟動後的每日自然 execution 應成為 Pilot evidence 的一部分。
- 六個月 window 未完成前，Production promotion 仍 blocked。
- Dev daily success 不等於 Production readiness。

## 完成語意

| 狀態 | 可使用的說法 |
|---|---|
| `WBS-5-MART-AI-ROLE-CONTRACT` 完成 | 5 位分析師角色已建立 |
| Fact Packs + Role Contract + Validation + Providers 完成 | 5 位分析師已具備可靠執行條件 |
| Daily integration + natural live acceptance 完成 | 5 位分析師已開始每日自動工作 |
| 僅人工 trigger 一次成功 | bounded acceptance 成功，不得稱為天天工作 |
| 任一 role structured failure | partial／failed，不能稱 five-role full success |

