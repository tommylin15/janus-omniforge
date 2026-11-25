# AI-REF-01｜四模型退場清冊與現況引用盤點

> **盤點基準 SHA**：`933a077d32a158dd6435f4beef01a1ab71d590c8`（`main`）  
> **盤點日期**：2026-11-25  
> **對應規格**：[api-stock-analysis-v2](../spec/ai-stock-analysis-v2.md) / [PROJECT_RULES §0.6](../PROJECT_RULES.md#06-廢除四模型轉向-api--確定性計算--ai-結構化分析2026-11-23-最新決策)

---

## 1. 盤點範圍與總覽

依 2026-11-23 治理決策，正式廢除原四個 ML／預測模型（`01 Quant`、`02 Risk`、`03 Fundamental`、`04 Valuation`）的訓練、推論與 Model Registry 升版依賴，全面轉向「外部 API 數據 + 後端確定性計算 + AI 結構化分析（`StockInsightV2`）」。

以下為目前 codebase 中對四模型分數、`four_model_serving`、`specialists`、`validated` gate 與舊版 `observations` 的精確引用清冊與預計退場處置（行號依 `933a077d` 實測）：

---

## 2. 後端核心與 Mart 管線

### 2.1 `packages/analysis_product.py`
- **L20–L44**：引用 `MartSpecialistV1` 與 `specialists.digest`，驗證五種 specialist role 与 `unvalidated model signal` gate。
  - **處置**：`AI-REF-03/05` 期間保持現有 v1 產品讀寫驗證不動，新增 `StockInsightV2` 獨立驗證管線。
- **L56、L67**：預設回傳 `"model_quality": "NOT_VERIFIED", "llm_api_tokens": 0`，註明 Mart registry 隔離規範。
  - **處置**：v1 相容保留；`StockInsightV2` 改以 `generation_meta.mode` 與 `quality_gate` 描述品質。
- **L85–L100、L118–L128、L140、L155–L189**：組裝 `specialists[]`、`risk` 角色保留規則與 `validated_role_artifact_hashes` 雜湊比對。
  - **處置**：v1 讀路徑維持只讀相容（Additive v2 原則），待 AI-REF-05/06 完成後停止依賴四模型分數。

### 2.2 `jobs/intelligence-mart/intelligence_mart/specialists.py`
- **L14–L16、L43–L54、L332–L356**：定義 specialist 版本常數與 `"model_status": "oos_not_validated"`、`MartSpecialistV1.model_validate(payload)`。
  - **處置**：`AI-REF-03` 停用四模型 ML 預測推論，保留純 PIT 確定性基本指標與 `validated_inputs`。
- **L94、L197、L255–L269**：`validated_inputs(datasets, symbol, as_of, snapshot, *, preserve_financial_basis=False)`（公開 Core 資料清洗／品質閘門）。
  - **處置**：**保留並重用**，作為 AI-REF-03 `AIAnalysisInput` 確定性事實來源。

### 2.3 `packages/change_analysis.py`
- **L10–L12、L22–L96**：既有變化狀態機 `observations()`（`new`/`ongoing`/`strengthened`/`weakened`/`resolved`/`invalidated`/`expired`/`pending`）與去重規則。
  - **處置**：**保留並擴充**，作為 `deterministic_fallback` 與 `secondary_insights` 基礎。
- **L101–L174**：`fact_snapshot()`（引用 `validated_inputs` 產出確定性事實清單）。
  - **處置**：**保留並重用**。
- **L177–L197**：`session_view()` 輸出 `observations` 列表與 `rule_version`。
  - **處置**：於 `AI-REF-02` 維持既有欄位 100% 相容，並於有 `insight_v2` 時以 Additive 方式掛載輸出。

### 2.4 `services/api/analysis.py`
- **L13、L43**：匯入 `packages.analysis_models`（`DEFAULT_MODELS`, `MODEL_OPTIONS`, `validated_models`）。
  - **處置**：於 `AI-REF-05` 維持向後相容讀路徑；新洞察改讀 `control.stock_insight_v2_snapshots`。
- **L54、L70、L102、L116–L131、L180–L187、L214–L327、L405–L409**：讀取 `private.specialist_product`、`four_model_serving`、`validated_role_artifact_hashes`、`observations`、`model_quality`。
  - **處置**：`AI-REF-05` 對 `/api/v1/me/analysis/{symbol}/changes` 與 `/api/v1/me/today-changes` 以 Additive v2 擴充 `insight_v2` / `insight_v2_preview`，保留舊版 `observations` 等相容欄位不破壞舊 Client。

### 2.5 其他 Mart / API 檔案之四模型依賴清單（待 AI-REF-03 統一停用推論）
- `jobs/intelligence-mart/intelligence_mart/four_model_serving.py`（L259）
- `jobs/intelligence-mart/intelligence_mart/seq08_native_serving.py`（L14、L232）
- `jobs/intelligence-mart/intelligence_mart/product_runtime.py`（L42、L84–L86、L119、L155–L156）
- `jobs/intelligence-mart/intelligence_mart/specialist_runtime.py`（L135–L136、L321，共 64 處）
- `packages/model_timeline.py`（L42–L63）、`packages/stock_report_policy.py`（L50）

---

## 3. 前端 Flutter App（`apps/user_app/lib/`）

- **`final_analysis.dart`**：
  - **L234**：檢查 `request['specialist_freshness'] == 'stale'`。
  - **L262、L276**：讀取 `baseline['specialists']` 與 `baseline['four_model_serving'][role.key]` 渲染四模型卡片。
  - **處置**：`AI-REF-05` 移除四模型分數卡，改渲染 `StockInsightV2`（30 秒速讀 + 單一 AI 變化卡 + 6 大主分類圖表）。
- **`stock_insights.dart`**：
  - **L90、L136–L138**：組裝 `baseline['specialists']` 並傳入 `seq08_native_model` 給 `RiskSignalCard`。
  - **處置**：`AI-REF-05` 改由 `insight_v2` 驅動風險覆核狀態（`review_status`：`OK` / `WARN` / `REVIEW`）。
- **`risk_signal_ui.dart`**：
  - **L6–L99**：讀取 `specialist['seq08_native_model']` 判斷 `validated`（`ACTIVE_PREDICTED`/`ACTIVE_CACHED`），未驗證時顯示「模型尚待驗證／未啟用新版預測模型」。
  - **處置**：`AI-REF-05` 替換或降級為確定性 T1–T5 覆核提示卡，不再顯示「未啟用新版預測模型」。
- **`final_changes.dart`**：
  - **L12、L22**：讀取 `data['observations']` 篩選變化狀態。
  - **處置**：`AI-REF-05` 優先讀取 `data['insight_v2']`，無 `insight_v2` 時回退渲染舊版 `observations`。
- **`final_today_v2.dart`**：
  - **L1168**：檢查 `model_validation_status != 'validated'` gate，隱藏或降級顯示。
  - **處置**：`AI-REF-05` 改讀 `insight_v2_preview`（30 秒速讀與 `primary_insights[0]`），移除對 `model_validation_status == 'validated'` 的強制阻擋。
