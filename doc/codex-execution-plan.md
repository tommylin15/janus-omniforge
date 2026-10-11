# Janus — Codex 作業指示：先產品交付，再 500 檔歷史研究

更新：2026-10-11（Asia/Taipei）

使用者核准順序：**B9 產品功能驗收 → C 組及剩餘產品整合 → 產品交付 → 500 檔歷史研究池與五角色模型研究**。本檔直接交給 Codex 接續；狀態只在 [TODO](todo.md)／[status](status.md) 維護。文件更新不代表功能、模型或部署 PASS。

## 1. 接手指令

```text
請依 doc/codex-execution-plan.md 執行 Janus 當前已授權工作組。
先讀 AGENTS.md、doc/PROJECT_RULES.md、doc/README.md、doc/status.md、doc/todo.md，
再讀 doc/spec/specialist-engines.md、doc/wbs/wbs-5-specialist-engines.md，
及當前切片直接相關 code/tests/workflow/runbook，不預設載入整個 repo。
核對 GitHub main 與 runtime，不把文件或 CI PASS 當成已部署。
先完成 B9 產品功能驗收，不等待五個 ML 全部勝過基準。
同組先集中完成 code/migration/tests/docs，再整合驗收及依既有流程發布。
同一授權組內持續到完成或真實 blocker，不逐檔、逐股票停等。
B0～B8 不重做；僅本次實質改動或新回歸需相應檢查。
完成當前組後回報下一入口；跨組遵循 PROJECT_RULES 授權規則。
本次文件回寫不代表已授權啟動全部工程、研究 Job 或新增費用。
```

## 2. 第一階段：產品交付

### B9 產品功能驗收（既有 B9 產品切片）

1. 盤點五角色最新修復的來源 SHA、tests、部署與實際輸出。區分 code-only、CI PASS、live NOT VERIFIED；不改寫舊 immutable OOS。
2. 完成產品必要資料修復：官方財報 EPS／歸母淨利的比較期與口徑、估值 null／極端值／合法零值、來源時間與缺口。沿用已授權 bounded 回補，不為產品結案擴成 500 檔全套財報／事件研究。
3. 提供可靠基準：Fundamental 財務比較；Valuation 相對估值；Quant 動能／相對強弱／市場排名；Risk 波動／CVaR／beta／回撤；Event 官方事件 parser／rules。必要資料不足時只退化受影響欄位／角色，不造值。
4. 未驗證 ML 不 promotion、不發布勝率；Event classifier_probability 保持 null。DCF／reverse-DCF 缺可信 FCF、股數及核准假設則 unavailable；規則分數、分類信心和上漲機率不混用。
5. 各角色驗證 structured artifact、繁中 rules/templates、source authorization、provenance、analysis/data as-of、missing/stale/partial、immutable persist/readback。規則引擎不硬要求 SHAP，適用 ML 才驗 feature contribution／SHAP。
6. 驗證 active watchlist ∪ effective holdings、持股離榜保留、dirty-only 更新、無變更 reuse、public/private isolation、正常 path 0 LLM API token。市場排名以當日市場池為參照，不只在個人深度池排名。
7. UI／Admin 分別呈現功能可用與模型品質；不把 oos_not_validated 宣稱有效，也不因此隱藏已驗證的可靠基準分析。
8. 現在就盤點並保留可取得的每日 membership、公告版本、發布／首次取得時間與 source receipt。沿用既有授權來源、儲存與 retention，僅補必要留存缺口；不假造過去時間、不提前啟動大規模回補。

**退出條件：**產品必要修復通過對應 tests、CI、GHCR dev 發布、真實 workload、artifact／API readback；正常與缺值狀態可核對，安全及增量不回歸。僅可判定「B9 產品功能 PASS」，模型研究另列 NOT VERIFIED／PARTIAL，禁止簡寫「B9 全部 PASS」。純研究 OOS 增強不阻擋產品；與 serving 共用的改動仍須回歸驗證。

### C 組及剩餘產品整合

B9 產品 gate 通過後，依授權接續 TODO 的 C 組，不等待研究池或 ML champion。

- 完成 On-demand CEO provider/runtime、capability、quota/cooldown、Admin profile、User 分析／重新分析及 immutable history。
- CEO 只使用 validated facts／基準分析及明示缺口；research challenger 不冒充已驗證訊號，LLM 無 canonical number 或 publication authority。
- CEO 僅由使用者明確 request 觸發；page load、Scheduler、dirty update、retrain 不自動呼叫。
- 依 active TODO 收斂剩餘持股頁 UX／migration 050／首屏效能與真實 owner 驗收，不重開已結案 A 組。
- 涉及 UI 必讀 doc/ui/user-app.md、doc/ui/reference/user-app-final/README.md 並實際檢視四張 reference PNG；不另設計資訊架構。
- 產品交付需有真實 authenticated dev 的資料、API、五分析師、CEO、權限／隔離、歷史／freshness 及適用四頁 visual acceptance。B9 通過不等於產品整體結案；Dev Pilot 長期觀察獨立追蹤，不假稱觀察期已完成。

## 3. 第二階段：500 檔歷史研究池與五角色模型

本階段已排入 TODO，依賴產品交付；不刪除模型工作、不預先宣稱五模型有效。先建資料、驗資料、建立基準，再調參。

| 切片 | 交付物 | 驗收／退出條件 |
|---|---|---|
| 歷史研究池 | 目標約 500 檔、各日期當時合資格 membership、來源授權、納入／排除原因、上市／下市與 coverage matrix | 不用今日 500 回填歷史，保留退出股票；無法重建的期間標 blocked_source_history，前瞻累積繼續 |
| 共用資料集 | OHLCV／公司行動與報酬口徑／benchmark／產業／官方財報／估值，按角色取用；immutable snapshot／Parquet | 日期、股號、單位、available-at、缺值、標籤可核對；市場／研究／深度三池分離 |
| 固定研究規格 | 預先定義目標、主要指標、fold、最終未調參時段、基準與成本情境 | chronological walk-forward、label maturity／purge；同樣本同期限比較，研究嘗試留紀錄 |
| 逐角色評估 | baseline/challenger 對照、分期／產業／環境、樣本量及不確定性報告 | 保留無優勢／不穩定／不足；500 檔數量或 fit success 不等於品質 PASS |
| 個別升級 | model/evaluation 版本、來源 lineage、CPU/RSS、回復路徑 | 通過該角色品質與 publication gate，真實 readback 後才明確升級；不自動 promotion |

上述資料／研究／工程交接由執行 Codex 負責；Event ground truth 由真實人工 reviewer 審核，不得虛構 reviewer／人審結果。

| 角色 | 基準與研究目標 |
|---|---|
| Fundamental | 財務規則 vs LightGBM；60／120 日為候選主期限，5／20 日輔助，先查長期限有效樣本。最新官方版／期末+90天投影保留 strict_pit=false，不改 canonical，不宣稱嚴格 PIT |
| Valuation | 相對估值規則 vs LightGBM／CatBoost；中期排序、缺值、產業可比性、train/OOS gap；DCF 另需完整輸入及核准假設 |
| Quant | zero／動能規則／Linear／LightGBM；CatBoost／Qlib 作 challenger；Rank IC／ICIR、spread、turnover、成本後績效／回撤；機率另驗 Brier／校準 |
| Risk | deterministic baseline；Markov vs Gaussian，逐日／月度 log score、尾端、環境、狀態切換穩定性；15/23 勝不等於顯著優勢 |
| Event | 來源允許 training-use 的繁中事件，人審 event/revision ID、分類、方向、時間、reviewer／label version；時間與事件群組防洩漏 holdout，比 rules 的 macro-F1／各類 precision/recall／校準；分類機率不是報酬機率 |

研究投入優先 Quant → Risk；基本面／估值先資料與基準，Event 先人審標籤。500 檔行情不代表五角色資料完整；原 EOD ≤10% 缺漏容忍不自動授予研究集品質 PASS。

## 4. 排程與資源

| 時間／觸發 | 工作 |
|---|---|
| 每交易日 | 行情／財報／公告增量；500 輕量 screening；深度池 dirty 角色更新 |
| 每週六 | 既有補漏／品質檢查；membership／版本留存檢查、事件待審整理，不全量重抓／重訓 |
| 每月第一個週六 10:30 Asia/Taipei | 固定資料後候選訓練／OOS／校準／reconciliation；依成熟資料與角色 gate 訓練，無新增合格資料記 skip/reuse reason |
| 使用者要求 | 已授權 On-demand CEO，與 retrain 分離 |

月度 slot 沿用 B7；新增成熟資料 skip/reuse 的差異須核對實作，未實作列 gap，不宣稱已部署。不重送舊 B7 request；必要新資料驗證走有明確來源版本的受控 B9 入口。

- PyIceberg 為每日 screening／specialist 預設；BigQuery 僅 ML/OOS 明確 opt-in，不自動 cutover，禁止 Storage Read API。
- Iceberg/GCS canonical、PostgreSQL serving、derived research 分離，不建完整 warehouse 複本。
- Mart 維持 1 CPU／1 GiB，以欄位／日期／股票有界批次控制運算，記錄 elapsed／RSS／bytes；不足提出實測，不自行升級。
- 500 檔回補前核對來源 training-use、請求界限、既有成本授權與 retention；新付費服務／IAM 擴權仍依 PROJECT_RULES，研究方向核准不是費用授權。

## 5. 發布、review 與交接

沿用 GitHub Actions → GHCR → Cloud Run、完整 SHA release gate、共用鎖／lease、Job fence／canary、API 候選驗證及 readback；不新增部署路徑、不修改歷史 evidence 使結果過關。

commit/push 前執行 /ponytail-review；環境缺該非系統命令時，依 PROJECT_RULES §1.4，以實際 diff／契約／連結／適用測試檢查替代並明示，不偽稱已執行。

每組交接列：來源 SHA、改動、tests/CI、部署版本、真實 workload／readback、產品功能狀態、模型品質狀態、未決事項、下一入口。文件-only 不部署、不啟動訓練。完成後明確告知停止邊界，不讓使用者猜測是否仍執行。
