# Janus — 後續 AI 開發指示

更新：2026-10-15。本文件只保存執行方法；授權與 active queue 唯一入口是 [TODO](todo.md)，證據是 [status](status.md)。2026-10-15 使用者已明確恢復 D01～D05 **合併開發與整批驗收**，D06 獨立、D07／D08 後置；此文件只記方法，現況及未過 gates 仍讀 TODO/status，不能把部分 Release PASS 當整包完成。

## 1. 可直接交給開發 AI 的指示

```text
先確認本次使用者指定工作包與 active TODO 的授權範圍；文件-only 不啟動工程。
恢復工程時，接續該已授權工作包。先讀 AGENTS.md、doc/PROJECT_RULES.md、
doc/README.md、doc/todo.md、doc/status.md、doc/spec/holdings-first.md、
doc/spec/full-market-batch-policy.md、doc/batch-inventory-2026-10-13.md。
涉及 UI 再讀 doc/ui/user-app.md、doc/ui/visual-first-four-pages.md、
doc/ui/reference/user-app-final/README.md，實際檢視四張 PNG。

先檢查 git status、GitHub main、既有未提交 diff 與相關實作／測試。
不得假定新的工作區存在舊會話的未提交改動；以實際 git status／diff 與 main 判斷。
保留其他人的改動，不 reset；遇 main 更新先 rebase／合併並重做受影響文件檢查。

順序一：完整持股頁。TWSE／TPEx 全個股官方 EOD 預先保存並供快速 serving，
持股 membership 跟隨 owner ledger，不受研究批次限制；市場／screening／研究／搜尋均改全上市櫃，coverage 上市缺失率≤10%、上櫃≤30% 各自過關（含邊界）；ETF 既有授權路徑保留。
首屏先讀持久化資料，按需更新合法盤中報價，過期／缺價有明確狀態。
完成 backend 交易前唯讀試算、成交入帳後股數／成本／該筆損益快速更新；
共用 MOVING_AVERAGE／Decimal 規則，處理費稅、版本衝突、冪等及更正。
修復正式重算 queue：取得 terminal SUCCEEDED 與 exact checkpoint 才算成功。
報價刷新、交易試算、帳本保存、報表重算是四種操作，不能互相卡住。

順序二：個股先通用圖表，再整合今日／關注／持股／個股四頁。
預設價格折線＋成交量，可切 K 線；營收／EPS 長條、估值折線、法人正負條及事件時間軸
依正式合格資料呈現。單一主圖、少量控制、來源日期可見、390px 與放大字級可讀。
資料不足明示原因並保留補齊待辦，不能補假點或以所有圖 missing 宣稱完成。
初期不讓五角色健康度、長文或 CEO 擋住基本圖表；不新增複雜指標或新 UI 框架。

以上兩項先完成整套必要 code／migration／tests／docs，再集中驗收；
保留安全與必要開發檢查，不逐股票逐頁發版。不啟動後置模型研究或 CEO 工作來擴大本輪。
驗收覆蓋報價覆蓋率、交易金額與日期／版本、owner 隔離、重送、缺價、stale、
queue 失敗重試、真實 dev 四頁截圖及冷暖 P50／P95／失敗率／quote age。
未達性能目標追查 critical path，不以延長 timeout 充當改善。

每次 commit 或 push 前依 PROJECT_RULES 執行 review；非系統命令不可用時採明示的等價檢查。
不使用 Superpowers，不為模型標記自行要求換模型或建立 branch／PR。
發布沿既有同 SHA 全測試→GHCR immutable digest→0% candidate→自動 auth gate→
Job fence/canary→真實 readback→切流／rollback。不得要求每版人工 OAuth 登入。
新付費資源、重大擴權與其他外部授權遵守 PROJECT_RULES，不自行越界。

交付時分列已修改、已測試、已部署、真實驗收和剩餘 gap；無證據標 NOT_VERIFIED／PARTIAL。
完成持股＋圖表工作包後停止，模型研究依 TODO 與當次授權另啟。
五分析師各自有效、可追溯且符合 publication 後才建立整合分析報告；不承諾精準預測。
```

## 2. 開發定位與集體驗收

| 責任 | 接手入口（先查現況，不假定已完成） | 完成證據 |
|---|---|---|
| 官方全市場報價 | ingestion `first_batch.py`／`__main__.py`、stock master、serving projection、報價 SPEC | 分市場有效名冊對照、全鏈路 coverage、研究池外持股可讀 |
| 損益與交易 | `services/api/private_pipeline.py`、repository／ledger routes、broker profile、private queue | 共用計算與版本測試、成交 readback、queue terminal／checkpoint |
| 快速首屏 | portfolio snapshot／quotes、`public_runtime.py`、`final_ledger.dart`／`final_today_v2.dart` | bounded DB read、無 N+1、冷暖端到端與 API 耗時 |
| 通用圖表 | visual-series／published history、`final_stock_detail.dart`、既有 charts | 真實價量／合法序列、缺口語意、互動與可及性、四頁截圖 |

B0～B8 與歷史 A 組不重新宣告未完成；本次受影響的共用路徑仍需回歸。B9、C 的模型／報告責任不刪除，但舊「先 B9／CEO 才做持股」順序已失效。單一來源缺失只阻塞對應圖表，缺口留 TODO，不讓持股等待無關模型。

## 3. 後置階段：全上市櫃歷史研究池與五角色模型

本階段已排入 TODO，依賴持股＋通用圖表交付（不等待整合報告）；不刪除模型工作、不預先宣稱五模型有效。先建資料、驗資料、建立基準，再調參。

| 切片 | 交付物 | 驗收／退出條件 |
|---|---|---|
| 歷史研究池 | 全上市櫃個股、各日期當時合資格 membership、來源授權、納入／排除原因、上市／下市與 coverage matrix | 不用今日全市場名冊回填歷史，保留退出股票；無法重建的期間標 blocked_source_history，前瞻累積繼續 |
| 共用資料集 | OHLCV／公司行動與報酬口徑／benchmark／產業／官方財報／估值，按角色取用；immutable snapshot／Parquet | 日期、股號、單位、available-at、缺值、標籤可核對；市場／研究／深度三池分離 |
| 固定研究規格 | 預先定義目標、主要指標、fold、最終未調參時段、基準與成本情境 | chronological walk-forward、label maturity／purge；同樣本同期限比較，研究嘗試留紀錄 |
| 逐角色評估 | baseline/challenger 對照、分期／產業／環境、樣本量及不確定性報告 | 保留無優勢／不穩定／不足；全市場股票數量或 fit success 不等於品質 PASS |
| 個別升級 | model/evaluation 版本、來源 lineage、CPU/RSS、回復路徑 | 通過該角色品質與 publication gate，真實 readback 後才明確升級；不自動 promotion |

上述資料／研究／工程交接由執行 Codex 負責；Event ground truth 由真實人工 reviewer 審核，不得虛構 reviewer／人審結果。

| 角色 | 基準與研究目標 |
|---|---|
| Fundamental | 財務規則 vs LightGBM；60／120 日為候選主期限，5／20 日輔助，先查長期限有效樣本。最新官方版／期末+90天投影保留 strict_pit=false，不改 canonical，不宣稱嚴格 PIT |
| Valuation | 相對估值規則 vs LightGBM／CatBoost；中期排序、缺值、產業可比性、train/OOS gap；DCF 另需完整輸入及核准假設 |
| Quant | zero／動能規則／Linear／LightGBM；CatBoost／Qlib 作 challenger；Rank IC／ICIR、spread、turnover、成本後績效／回撤；機率另驗 Brier／校準 |
| Risk | deterministic baseline；Markov vs Gaussian，逐日／月度 log score、尾端、環境、狀態切換穩定性；15/23 勝不等於顯著優勢 |
| Event | 來源允許 training-use 的繁中事件，人審 event/revision ID、分類、方向、時間、reviewer／label version；時間與事件群組防洩漏 holdout，比 rules 的 macro-F1／各類 precision/recall／校準；分類機率不是報酬機率 |

研究投入優先 Quant → Risk；基本面／估值先資料與基準，Event 先人審標籤。全市場行情不代表五角色資料完整；EOD 上市 ≤10%／上櫃 ≤30% 缺漏容忍不自動授予研究集品質 PASS。

## 4. 排程與資源

所有業務定時工作由 Cloud Scheduler 總控，Actions 僅備份清理 schedule。先依批次盤點移除重複入口、以Core-ready／dirty queue與快照減少等待；不能直接讓既有research workflow重播固定500 request。備份timer有驗證交接才停用。


| 時間／觸發 | 工作 |
|---|---|
| 每交易日 | 行情／財報／公告增量；全市場分片 screening；深度池 dirty 角色更新 |
| 每週六 | 既有補漏／品質檢查；membership／版本留存檢查、事件待審整理，不全量重抓／重訓 |
| 每月第一個週六 10:30 Asia/Taipei | 固定資料後候選訓練／OOS／校準／reconciliation；依成熟資料與角色 gate 訓練，無新增合格資料記 skip/reuse reason |
| 使用者要求 | 已授權 On-demand CEO，與 retrain 分離 |

月度 slot 沿用 B7；新增成熟資料 skip/reuse 的差異須核對實作，未實作列 gap，不宣稱已部署。不重送舊 B7 request；必要新資料驗證走有明確來源版本的受控 B9 入口。

- PyIceberg 為每日 screening／specialist 預設；BigQuery 僅 ML/OOS 明確 opt-in，不自動 cutover，禁止 Storage Read API。
- Iceberg/GCS canonical、PostgreSQL serving、derived research 分離，不建完整 warehouse 複本。
- Mart 維持 1 CPU／1 GiB，以欄位／日期／股票有界批次控制運算，記錄 elapsed／RSS／bytes；不足提出實測，不自行升級。
- 全市場回補前核對來源 training-use、請求界限、既有成本授權與 retention；新付費服務／IAM 擴權仍依 PROJECT_RULES，研究方向核准不是費用授權。

## 5. 發布、review 與交接

**2026-10-12 新發布規則：**移除 Github Actions 每版人工 OAuth 登入／consent／A→B→A；持續執行自動 OAuth metadata／PKCE、User／Admin／MCP 401、refresh／token／audience 測試與可安全執行的真實 authenticated readback。取同 SHA 成功 `ghcr-candidate-auth-boundary.yml` 的 `auth_boundary_run`，填到新的 Jobs／API request；腳本檢查成功 run 的 workflow 身分與來源，不再讀歷史人工 `ghcr-owner-acceptance.json` 作 gate。非 OAuth 的 PnL／owner isolation 功能與 rollback 各自照原契約驗收；無證據標 `NOT_VERIFIED`，不要要求每版真人重登。



沿用 GitHub Actions → GHCR → Cloud Run、完整 SHA release gate、共用鎖／lease、Job fence／canary、API 候選驗證及 readback；不新增部署路徑、不修改歷史 evidence 使結果過關。

commit/push 前執行 /ponytail-review；環境缺該非系統命令時，依 PROJECT_RULES §1.4，以實際 diff／契約／連結／適用測試檢查替代並明示，不偽稱已執行。

每組交接列：來源 SHA、改動、tests/CI、部署版本、真實 workload／readback、產品功能狀態、模型品質狀態、未決事項、下一入口。文件-only 不部署、不啟動訓練。完成後明確告知停止邊界，不讓使用者猜測是否仍執行。

## 6. 接手 AI 的工作包格式

D01～D08 具有 [標準化執行卡](execution-cards/README.md)。明確指定工作包後，先在 TODO 確認當次授權，讀取該卡的前置讀回、工程入口、測試／live acceptance、失敗恢復及回報格式；卡片僅是可執行操作指示；D01～D05 本輪已另經使用者明確授權整合執行，其後仍以最新 TODO／真實 dev evidence 判定。

每次只建立一份本輪記錄：工作包／既有WBS、輸入SHA、允許修改範圍、依賴、入口檔案、交付物、測試、live驗收、失敗恢復、未決項。D01～D08與詳細退出條件只查TODO；不得另複製待辦。

確認能力以目前repo／tools為準，不要求已不存在的slash command、固定AI型號或舊request。工程完成報告分列「已修改／已測試／已部署／業務已驗收」；文件-only只報文件檢查。review與讀回後直接同步main，不新增無授權部署。

新增驗收維度見 [系統建置補強](spec/system-development-contract.md)。架構維持既有 PostgreSQL serving＋Iceberg canonical＋有界Jobs；本輪沒有新資源、queue、向量庫、圖表SDK或LLM日常呼叫。
