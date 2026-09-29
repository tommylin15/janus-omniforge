# Janus — 五位分析師每日運作 Gate

更新：2026-09-29

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

**目前狀態：未完成；這是下一個可執行 foreground WBS。**

達到此 gate 只代表「分析師有受治理的研究資料」，尚不能宣稱 5 位分析師已開始每日工作。

## Gate 3 — 5 個 structured AI role 正式成立

完成 `WBS-5-MART-AI-ROLE-CONTRACT`：

- 建立 5 個 structured AI role output contract。
- methodology prompt versioned。
- locked system guardrail 生效。
- 每個 role output 有 immutable artifact lineage。
- invalid role 必須 structured failure，不得用 placeholder 假裝成功。

達到此 gate 可以說「5 位分析師角色已存在」，但尚不能說「可靠工作」或「天天工作」。

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

## Gate 5 — Provider runtime 可可靠執行

完成 `WBS-5-MART-AI-PROVIDERS`：

- governed `MartAIProvider` contract。
- Gemini／OpenRouter 等已核准 provider 的 capability discovery。
- bounded parameters。
- unsupported model／parameter fail-closed。
- 429／unavailable retry bounds。
- billing／paid gate 仍受使用者明確授權，不因本里程碑自動開啟付費模型或 subscription。

達到 Gate 2–5 後，可宣稱「5 位分析師可以可靠工作」，但還不能宣稱「已經天天工作」。

## Gate 6 — Daily Scheduler／workload integration 與 natural live acceptance

要宣稱「5 位分析師已經每天上班」，還必須有實際 dev parallel-live evidence 證明完整日常鏈路：

1. 每日 upstream ingestion／required Fact Pack dependency 完成或進入明確 partial／missing 狀態。
2. Scheduler／既有 approved workload 自然觸發 five-role analysis，而不是只靠人工 one-off trigger。
3. 5 個 role 各自產生 success 或 structured failure artifact，保存 execution／input／prompt／model／provider／evidence lineage。
4. validator 決定各 role artifact 是否可接受；partial success 不包裝成 full success。
5. artifact persisted，可供後續 CIO／UI／Admin／evaluation 讀取。
6. 至少完成自然 daily execution 的 live acceptance；手動 bounded run 只能作 repair／acceptance 證據，不能單獨證明「天天工作」。
7. 後續自然日執行持續由 `WBS-8-DEV-PILOT-RUN` 累積 reliability、usefulness、cost、manual intervention、recurring failure 與 security／privacy evidence。

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

