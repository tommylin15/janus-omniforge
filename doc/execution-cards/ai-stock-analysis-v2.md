# API + AI 個股分析重構工程卡（AI-REF-01 ～ AI-REF-06）

更新：2026-11-25（決策日期：2026-11-23）。依 [正式 SPEC](../spec/ai-stock-analysis-v2.md) 與 [PROJECT_RULES](../PROJECT_RULES.md)（§0.6）執行；唯一進度與驗收狀態在 [TODO](../todo.md)。本輪僅同步規格與工程卡（`DOC_ONLY`），未授權修改程式、未執行測試、migration 或部署。

## 順序與責任

| ID／優先 | 工作項目 | 前置依賴 | 驗收與退出條件（Definition of Done） | 回退方式 |
|---|---|---|---|---|
| **AI-REF-01**／P1 | 現況盤點、治理同步與四模型退場清單 | 無 | 鎖定最新 `main` SHA；產出四模型分數與 `validated` gate 精確行號清冊；保留舊 client 相容欄位 | 純盤點與文件更新，零風險 |
| **AI-REF-02**／P1 | 雙層資料契約與持久化 Schema 落地 | AI-REF-01 | `AIAnalysisInput`、`LLMInsightDraft`、`StockInsightV2` 單元測試通過；Additive v2 保留舊 `observations` 讀路徑 | Migration 可降版；保留 v1 讀取路徑 |
| **AI-REF-03**／P1 | 確定性計算層、T1–T5 引擎與外部 API Adapter | AI-REF-02 | 停用四模型推論；T1–T5 單元測試覆蓋金融／ETF／農曆年／澄清重訊例外；外部 API 強制 `llm_input_allowed` 並保護 `last-success` | 關閉外部 Adapter 旗標，退回純 Core 事實 |
| **AI-REF-04**／P1 | Gemini Hydrogen 分析引擎與 5 道防線 | AI-REF-03 | Prompt `v2.1.0` 與 5 道 Post-Validation 100% 攔截幻覺 ID／亂算數值／指令禁語；中性新聞零誤殺；快取命中隔日轉 `ongoing` 且 LLM=0 | `AI_SYNTHESIS_ENABLED=false` 全面走 `deterministic_fallback` |
| **AI-REF-05**／P1 | API Additive v2 擴充與 Flutter UI 重構 | AI-REF-02、AI-REF-04 | `/changes` 與 `/today-changes` 新增 `insight_v2`；390px／200% 字級無溢出；非母體個股 Page Load 零 LLM 呼叫 | UI 功能旗標切回舊版卡片 |
| **AI-REF-06**／P1 | 10 檔代表樣本實測、防幻覺驗收與 Dev 驗證 | AI-REF-05 | [SPEC §6](../spec/ai-stock-analysis-v2.md#6-驗收測試矩陣targeted-test-matrix) 全數通過；Owner 隔離通過；記錄 Token 消耗與費用收據 | 回滾至上一個穩定 Dev Revision |

## 開工指令（由使用者指定工項後使用）

```text
你是 Janus / OmniForge 工程師。請先讀取 GitHub repo `tommylin15/janus-omniforge`（main 分支）之 `AGENTS.md`、`doc/PROJECT_RULES.md`、`doc/todo.md`、`doc/spec/ai-stock-analysis-v2.md` 與 `doc/execution-cards/ai-stock-analysis-v2.md`。

本次任務：執行【AI-REF-01 與 AI-REF-02】（同步廢除四模型治理基準、盤點四模型退場點、落地 `AIAnalysisInput` / `LLMInsightDraft` / `StockInsightV2` 三層契約與測試）。
規則：
1. 先記錄目前 main 最新 SHA，並盤點 `packages/analysis_product.py`、`specialists.py`、`change_analysis.py` 與 `apps/user_app/lib/final_*.dart` 中所有依賴四模型分數與 `validated` gate 的精確行號。
2. 嚴格區分 `LLMInsightDraft`（LLM 輸出）與 `StockInsightV2`（後端展開 `evidence_refs[]`、`secondary_insights`、`more_count` 後之 API 契約），維持 Additive v2 向後相容（保留舊 `observations`）。
3. 核准 LLM 為 Gemini Hydrogen（以 `JANUS_LLM_MODEL` 環境變數管理）；第一階段批次母體為「使用者自選／持股去識別聯集」；非母體個股於 Page Load 嚴禁呼叫 LLM。
4. 公共個股分析嚴禁引入 owner 持股、成本或現金；未實測部署者一律誠實標註 `NOT_VERIFIED`。
5. 完成後請嚴格依照 Drive `janusChatGPT/AGENTS.md` 第 5 節【每次回報標準模板】回報。
```

## 相關邊界

- 本工作包正式廢除原四模型（`01 Quant`、`02 Risk`、`03 Fundamental`、`04 Valuation`）訓練、推論與 Registry 升版依賴；不重開已結案研究或訓練排程。
- 未經實際測試、CI、Dev 部署與真實讀回驗證，一律維持 `DOC_ONLY`／`NOT_VERIFIED`，不得宣稱完成。
