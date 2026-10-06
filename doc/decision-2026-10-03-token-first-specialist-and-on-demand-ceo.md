# Janus 決策 — Token-first 五分析師與 On-demand CEO

更新：2026-10-06（B 組 cadence／BigQuery 邊界對齊）
狀態：**Active / Approved**

## 1. 決策摘要

Janus 的主要目標順序固定為：

1. **先最小化 LLM token／API 成本與無謂重算。**
2. 在上述前提下，最大化可回測、可校準、可重跑的分析與預測品質。
3. 生成式 LLM 只用於真正需要自然語言推理的少數情境，不作每日主運算引擎。

因此，原先「5 個 specialist 每日以 Codex CLI／OpenRouter／Gemini 執行，再由 CIO 合成」的 active planning **停止作為目標產品架構**。既有 Codex CLI、OpenRouter、Gemini provider/router、validator、artifact lineage、credential/free-gate 等已完成成果保留，不刪除，但降級為 **On-demand CEO / rare escalation runtime**。

**Codex／ChatGPT 工程 agent 在後續實作中不得把 5 個 specialist 再做成 5 個生成式 LLM workers。**

---

## 2. 目標架構

```text
Canonical / PIT Data
        │
        ├────────────── Market Coverage ≈ 500
        │                ├ cheap deterministic screening
        │                ├ full-universe Quant inference where cheap
        │                ├ basic Fundamental / Valuation / Risk features
        │                └ event metadata flags
        │
        └────────────── Deep Coverage = active watchlist + effective holdings
                         │
                         ├ Fundamental Engine   Python/SQL + LightGBM
                         ├ Valuation Engine     Python + LightGBM/CatBoost
                         ├ Quant Forecast       Qlib + LightGBM/DoubleEnsemble
                         ├ Risk / Regime        Riskfolio-Lib + statsmodels/ML
                         └ Event / Catalyst     parser + local multilingual classifier
                                      │
                                      ├ structured outputs
                                      ├ SHAP / deterministic explanations
                                      └ plain-language specialist reports (0 API token)

User opens Stock Detail
        │
        ├ existing CEO report -> read persisted immutable report
        │
        └ authorized user explicitly clicks Analyze / Re-analyze
                    │
                    └ On-demand CEO synthesis
                         approved route: Codex CLI -> OpenRouter -> Gemini
                         validated inputs only
                         new immutable execution/report
```

日常正常狀態：**五分析師 0 LLM API token；CEO 0 call，除非有權限的使用者主動按分析。**

---

## 3. Coverage 分層

### 3.1 Market Coverage（約 500 檔）

500 檔仍保留，目的是發現新機會，不是做 500×5 深度分析。

每個交易日 EOD canonical data ready 後維護低成本 screening；若 input identity 未變則 reuse：

- return 5/20/60/120D
- volume / turnover / RVOL / volatility
- relative strength / sector relative strength
- drawdown / beta / liquidity
- revenue YoY / MoM、基本 valuation percentile 等便宜欄位
- event metadata / material-event flag
- full-universe Quant inference / cross-sectional rank（在成本可忽略時）

輸出至少包含 `screening_score`、`candidate_rank`、`anomaly_flags`、freshness、input identity。B 組 BigQuery path 通過 exact-snapshot fidelity gate 後，優先承接這條全市場 cross-sectional compute。

500 檔 **不得** 自動觸發 500×5 深度 specialist 或 500×5 LLM role invocations，也不得因 screening candidate 自動加入使用者 watchlist。

### 3.2 Deep Coverage

Deep Coverage = `active watchlist ∪ effective holdings`，去重後計算。

- Watchlist 既有 50 active distinct-symbol quota 維持。
- 持股永遠進 Deep Coverage，即使離開 500 市場池或使用者移出 watchlist。
- 清倉且不在 watchlist 才退出後續 Deep Coverage；歷史 artifacts 不覆寫。
- 全部 deeper specialist engines 使用 public/canonical data；不得把 user-to-symbol、持股數量、成本或私人交易內容混入公開 specialist artifact。

Market screening 的候選只顯示為 Discovery Candidate；由使用者決定是否加入 watchlist 後才升級 Deep Coverage。

---

## 4. 五分析師 production 選型

### 4.1 Fundamental Engine

**Primary：Python/SQL deterministic financial features + LightGBM**。

建議 framework：`microsoft/qlib` 作 model/workflow adapter；canonical features 仍由 Janus PIT Mart 提供。

典型特徵：revenue acceleration、EPS/revision、margin、ROE/ROIC、FCF conversion、inventory/receivable、debt/liquidity、capex、earnings quality。

模型輸出為 structured score/probability，不可發明 canonical financial numbers。

### 4.2 Valuation Engine

**Primary：Python deterministic valuation + LightGBM/CatBoost supervised layer。**

Python 計算 PE/PB/EV、FCF yield、historical/peer percentile、DCF、reverse DCF、scenario sensitivity。ML 只學 valuation/growth/quality 組合對 future excess return 的歷史關係。

LightGBM 與 CatBoost 必須以 Janus Taiwan PIT walk-forward OOS benchmark 選 champion；文件不預先宣稱 CatBoost 一定勝出。

### 4.3 Quant Forecast Engine

**Primary challenger：Qlib DoubleEnsemble；LightGBM 保留 baseline。**

第一版至少比較 Linear / LightGBM / CatBoost / Qlib DoubleEnsemble。預測目標優先為：

- 5/20/60/120D expected excess return
- `P(outperform benchmark)`
- downside / return quantiles（模型能力足夠時）
- cross-sectional rank

不得以 exact future stock price 作主要成功指標。

### 4.4 Risk / Regime Engine

**Primary：Riskfolio-Lib + statsmodels/ML regime model。**

Riskfolio-Lib 負責 volatility、CVaR、drawdown、factor/concentration/correlation/portfolio contribution 等 deterministic/optimization risk outputs。Regime 第一版可用 statsmodels Markov switching 或 bounded LightGBM classifier，依 OOS evidence 選用。

### 4.5 Event / Catalyst Engine

**Primary：rule/parser + local multilingual encoder classifier。**

不直接採舊英文 FinBERT 為 production 主模型。正式 runtime 優先使用 Hugging Face Transformers 的 multilingual encoder（XLM-R 類）fine-tune Janus 台灣／中文 financial event taxonomy。

輸出例如 `event_type`、`direction`、`materiality`、`novelty`、`confidence`、`evidence_refs`。

只有 `materiality` 高且 local classifier confidence 低的少數文件，才允許進入 approved LLM escalation；不得因 NLP 困難就重跑整支股票的五角色 LLM。

---

## 5. 白話文報告：預設 0 token

五分析師的日常白話報告由 structured outputs + SHAP/rule-based explanation + deterministic templates 產生。

原則：

- 數字只來自 deterministic/PIT outputs。
- SHAP/feature contribution 可說明主要正負驅動。
- Template 可組成「基本面偏正向／估值偏高／中期量化偏多」等人類可讀摘要。
- 不需要 LLM 也能提供 why/risk/what-changed。
- 不把 confidence 說成獲利機率，除非該欄本身就是經校準的 probability。

生成式 CEO 報告則負責處理跨角色衝突、scenario、thesis、invalidation condition 與綜合文字推理。

---

## 6. Incremental / Dirty Graph：有資料變才算

五分析師不是固定每日全重算，也不是固定每月才更新數據。

每個 specialist artifact 至少保存：

- symbol / analysis_as_of
- input snapshot/content hash
- feature version
- engine/model version
- output hash
- computed_at / freshness / status

當新的 Core/PIT data 到達時：

1. 比對 watermark/snapshot/input hash。
2. 只 invalidate 受影響的 dependency。
3. 只更新受影響 symbol + specialist。
4. 無變更的 artifact reuse，不做無謂 Python/ML inference。
5. 舊 artifact immutable。

典型依賴：

- 新月營收/財報 -> Fundamental；必要時 Valuation。
- 新 EOD price -> cheap Valuation refresh、Quant、Risk。
- 新 event -> Event；其他角色不因 event metadata 本身被強制重算。
- 只有某一 role dirty 時，不重跑其他 4 role。

CEO 報告不因任何 upstream change 自動重跑；只標記「報告後已有新資料／material change」，由使用者決定是否重新分析。

---

## 7. Model retraining cadence

「每月」主要指 model retraining / calibration / OOS evaluation / reconciliation，不是所有 specialist outputs 每月才更新。第一版固定 **每月第一個週六 10:30（Asia/Taipei）**；不另設每週六 500×5 全量模型排程。

第一版：

- Quant / Risk-regime / 有 ML 部分的 Fundamental/Valuation：每月建立 challenger/retrain。
- Event classifier：有足夠新 labeled data 或 drift/performance degradation 才 retrain，不硬性每月重訓。
- 同一月度批次做 calibration／OOS evaluation／cache dependency reconciliation：確認 expected input identity、cached identity、model version、orphan/missed invalidation。
- 如 feature drift、Rank IC、calibration、Brier、top-decile spread 等惡化超門檻，可提前訓練 challenger。

任何新模型都必須先 walk-forward OOS + PIT/future-leakage guard；**training 成功不等於自動 promotion**。

---

## 8. Forecast evaluation / champion-challenger

至少追蹤：

- Rank IC / ICIR / IC decay
- top-decile future excess-return spread
- hit rate
- Brier score / probability calibration
- Sharpe / max drawdown
- turnover / after-cost performance
- regime stability

Janus 不以「報告文字看起來合理」當預測模型 acceptance。

GitHub 開源 framework 是 implementation accelerator，不是準確度證明；production champion 必須以 Janus 自己的 Taiwan PIT OOS evidence 決定。

---

## 9. On-demand CEO 與帳號權限

### 9.1 Google Login capability

保留現有 Google OIDC User/Admin boundary。新增 DB-backed user capability，例如：

`ceo_analysis.request`

- Admin UI 可對已存在的 Janus user identity 授予/撤銷 capability。
- Flutter 顯示/隱藏按鈕不是 security boundary；backend 每次 POST 必須驗證 authenticated user + capability。
- 不把 raw Google token / secret 存進一般 DB 或 Admin UI。

### 9.2 User Stock Detail

有 capability 的使用者在個股頁看到：

- 最新 CEO report
- analysis time / data as-of
- provider/model/profile/version
- 報告後有哪些新資料/哪個 specialist dirty
- `進行 CEO 分析` 或 `重新分析`
- immutable history

無 capability 的帳號不得呼叫 command API。

### 9.3 CEO execution

建議 command boundary：

`POST /api/v1/me/analysis/ceo`

Backend 至少做：auth、capability、symbol validity、approved profile、in-flight duplicate guard、quota/cooldown、execution creation。

CEO route 保留現有 approved provider routing：

`Codex CLI -> OpenRouter -> Gemini`

但它不再是五 specialist 的 daily route。Provider/fallback/billing/secret/audit 既有治理全部保留。

CEO 只讀最新 validated specialist outputs / Fact Pack / provenance，不取得使用者私人持股數量、成本、交易等 private data；若日後要做個人化 portfolio advice，另建 owner-scoped Private capability，不能污染公開 symbol-level CEO report。

### 9.4 報告保存

重新分析一定建立新 immutable execution/report，禁止覆蓋：

- requested_by_user_id：audit metadata
- trigger=`user_manual`
- symbol/scope
- analysis_as_of / input identities
- provider/model/profile/prompt/route version
- report artifact hash
- status / validation lineage

symbol-level public research report 可被同一系統後續重用；不要因不同使用者按同一支股票就無條件產生相同重複報告。私人帳號只控制「誰有權觸發」，不改變公開 symbol analysis 的 canonical content。

---

## 10. WBS / TODO 重映射

後續 Codex 應依下列語意實作；舊 WBS 中與「每日五 LLM workers」衝突的描述視為已被本決策取代，直到文件完全 convergence：

1. `WBS-5-MART-SPECIALIST-ENGINES`（新增）
   - 500 market screening + Deep Coverage 5 engines
   - GitHub framework adapters、structured outputs、SHAP/template explanations
   - PIT/OOS benchmark、champion/challenger

2. `WBS-5-MART-RERUN-CACHE`
   - 升級成 dirty dependency graph / content-addressed reuse / incremental invalidation；月度 retrain／calibration／OOS evaluation／reconciliation 固定每月第一個週六 10:30（Asia/Taipei）。

3. `WBS-5-MART-AI-PROVIDERS`
   - 保留現有成果，但 scope 改為 On-demand CEO / rare escalation provider runtime；**不得再把 completion 定義成每日五 Codex role workers。**

4. `WBS-5-MART-CIO-SYNTHESIS`
   - 產品語意改為 `CEO Analysis`；只在 authorized user manual request 執行，讀 validated inputs，仍無 publication authority。

5. `WBS-6-ADMIN-ANALYSIS-PROFILE`
   - 管理 specialist champion/model/version/evaluation + CEO provider route/profile + user capability + quota/cooldown；不得只做五 role prompt/model picker。

6. Admin operational convergence
   - Job Control Center 顯示 data ingestion、screening、dirty specialist updates、monthly retrain/reconciliation、CEO on-demand executions、provider usage/cost/audit。

7. User operational convergence / Final Visual
   - Stock Detail 加入 persisted specialist plain-language results、CEO latest/history、新資料 freshness 與 authorized Analyze/Re-analyze action。

既有 `WBS-5-MART-FACT-PACKS`、AI role contract、validator、Mart v1 compatibility 的完成歷史不可改寫；它們可作為 legacy/additive contracts 與 audit evidence。新的 specialist structured contract應 additive/versioned，不覆寫歷史 artifact。

---

## 11. 明確禁止事項

- 不把 5 specialist 做成 5 個每日生成式 LLM agent。
- 不讓 500 檔自動變成 500×5 LLM calls。
- 不因每日日行情變動而自動重跑 CEO。
- 不用 LLM 計算/補 canonical numbers。
- 不把 model retraining 與每日 inference 混為一談。
- 不把 GitHub benchmark 成績直接當台股 production 準確度。
- 不覆寫舊 CEO report；re-analysis 建新 immutable artifact。
- 不用 Flutter UI 隱藏按鈕取代 backend capability enforcement。
- 不新增/提高付費 provider、API、GCP resource 而未取得使用者明確授權。

---

## 12. Codex 開工讀取順序

涉及本架構的實作，Codex 最少先讀：

1. `doc/PROJECT_RULES.md`
2. `doc/todo.md`
3. **本文件**
4. 對應 `doc/wbs/wbs-5-intelligence-mart.md` / `wbs-6-api-and-apps.md`
5. `doc/spec/intelligence-and-governance.md`
6. 涉及 User UI 時再讀 `doc/ui/user-app.md` 與 Final Visual Contract；涉及 Admin 讀 `doc/ui/admin.md`
7. 最後才看目前 code/tests/runtime evidence

若舊 WBS/SPEC 段落仍寫「daily five Codex analysts」，而本文件與 active TODO 已明確改為 token-first specialist engines + on-demand CEO，**以本決策與 active TODO 為新需求；但舊實作/完成狀態仍以 GitHub/runtime evidence 如實保留，不得假裝已重構完成。**

## 使用者後續指示

2026-10-03 使用者明確要求刪除舊五角色，不留兼容入口，取代此前保留舊每日引擎的過渡安排。Shared CEO auth/routing 可保留；不因此延伸執行下一個 CEO WBS。Mart 配置固定 1 CPU／1 GiB，若實際跑不動先提出配置建議。

500 檔品質採使用者後續指定的 10% 缺失容忍（含邊界），超過先回報討論，不直接判整批失敗；補資料採最小的既有官方市場批次，禁止為補齊每欄加入複雜流程。這取代全數齊備才可接受的解讀，不改寫個別未知值。
