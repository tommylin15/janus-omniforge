# Janus — 後續 AI 開發指示

更新：2026-10-18。本文件只保存AI路由與共用執行方法；當次授權、暫停、唯一active queue在[TODO](todo.md)，實際證據在[status](status.md)。文件更新不自動恢復工程。

## 1. AI唯一啟動入口與指令路由

先讀AGENTS.md、PROJECT_RULES、README、TODO，確認指定範圍、暫停與依賴；文件-only不得開工。查main及既有證據，已存在能力直接重用，有實質變更才回歸，不重做真人PASS或B0～B8。

| 工項 | 操作指令 | 規格／驗收依據 |
|---|---|---|
| **D07-PRE：Colab 唯一資料整理／訓練（含條件式 FINOPS-C）** | [統一 AI 指令 §4](execution-cards/finops-ingestion-iceberg-ab-and-c-gate.md) | [唯一 TODO](todo.md)、[單一資料/建模流程](colab-d07-modeling-feasibility-2026-10-19.md)、[WBS-5](wbs/wbs-5-intelligence-mart.md)／[WBS-7](wbs/wbs-7-security-finops.md)；BigQuery 只有 Colab 實測大資料瓶頸才前置縮減；不建立平行訓練器 |
| D01、D04～D08 | [任務卡索引](execution-cards/README.md)內相應卡 | 該卡SPEC與TODO |
| D02首屏／快照 | [D02卡](execution-cards/d02-full-market-snapshot-performance.md) | [三層交付](ui/visual-first-delivery.md)，與D03共享數值證據 |
| D03首頁／個股／四頁 | [D03卡](execution-cards/d03-four-page-charts-visual.md) | [A具體版面第5節](ui/visual-first-four-pages.md)、[User App語意](ui/user-app.md)、[B三層交付](ui/visual-first-delivery.md) |
| DRL-01A/B/C/D | 本文件第7節 | TODO子項＋B三層交付；消費端依D02/D03卡 |

UI實際長相按A第5節逐項實作，不能自行換區塊順序、堆重複卡、增導航或將三行事實改健康分數。資料→共用公式→serving/API→現有UI同一功能一起交付，不等全部OOS才顯基本圖表。
FINOPS-AB 與 DRL-01 分別於各自授權範圍優先，已有月營收月份修復與上櫃3個歷史交易日直接PASS；仍需OHLCV窗口、EPS真正Core讀回、13月YoY、定期Ledger實機與合理後置估值河流。D01～D05既有授權及成功證據保留，不重做、不把DRL新需求反向加到D05 gate。
版型只維護A，三層映射只維護B，任務卡保存操作／驗收，TODO保存範圍／狀態。Drive為研究參考，舊逐步指令與此路由不同時以此路由及TODO為準。通用發布／資源／交接依第4～6節。

**2026-10-19 強制 AI 路由：**D07-PRE 與 D07 後續的研究資料清洗/Join、特徵與標籤、ML baseline/challenger fit、24月 rolling/OOS **只能在 Google Colab**，現有 Iceberg Core/PyIceberg 只負責 canonical／受控唯讀原料出口，Janus Mart/Cloud Run 負責單一月度 Controller（首週六10:30）及正式模型驗收、版本/promotion/inference。僅當 Colab RAM/時間／I/O 有實測瓶頸、BQ 前置縮減具效益且已獲必要授權，才容許 BQ SQL → fixed Parquet → Colab；不用 BQML、Cloud Run 另訓練。當前 Mart retrain 程式仍未切換，免費 Colab 無可驗證無人值守，因此先人工啟動留 receipt；未驗則 NOT_VERIFIED，不要承諾已自動化。此決策不擴及每日 Screening、資料 ingestion、canonical 或 D08 報告管線。

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


## 7. 2026-10-16 三層整併接續指令

使用者2026-10-16已明確解除DRL-01暫停並將其提升為最高優先；D01～D05既有授權仍保留，產品後續部署與此資料修復分別驗收。直接把 [三層對照](ui/visual-first-delivery.md) 當共同交付清單，不建立新queue。

1. 查現有實作與證據，將每項功能映射到既有DRL-01A/B/C/D、D02、D03/VF與後置D07/D08；已有可用值、公式、API、圖表直接重用，只有差距才修改。
2. 依序修OHLCV、營收月份、EPS口徑；每一項同步接通「資料→共用計算→serving/API→既有圖表」，不要先抓完整資料再等另一專案畫UI。程式與相依切片完成後合併測試／發布，不逐股逐圖發版。
3. 首版先金額／單值／短期線／正負柱與可驗算事實；缺YoY不藏營收，缺五年不藏PE/PB，累計EPS不硬改單季，延遲價保留參考數字。缺必要公式輸入只停該公式。禁止直接相減累計EPS。
4. 共用同一份source/Core/API數值對照證據，補對應手機／桌面UI與單卡缺值／timeout驗證。只回歸受影響路徑；不重做既有真人PASS或B0～B8。
5. D07另驗因子預測增量，D08另驗報告；不讓ML／CEO阻擋真實基本圖表。不新增資料來源、排程、服務、圖表框架或LLM日常呼叫來完成首版。
6. 依既有發布規則做所需CI／live驗收，回寫TODO與operations。分別報資料可讀、計算可重現、UI可用、模型有效；首版有用不等於整包全部PASS，後續品質改善不擴成另一套待辦。

Drive研究公式保留候選性；當前工程順序與暫停以TODO優先。本指令取代Drive舊「全部分析／OOS完成後才接UI」的串行理解。
