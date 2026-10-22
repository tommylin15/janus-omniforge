# Janus — 唯一 Active TODO

更新：2026-10-21。**只列尚未完成的工作與原定驗收，不收納歷史失敗、已結案工程、無具體異常的推測性追查。** 狀態以 GitHub `main`／真實 CI、deployment 與 runtime 為準；結案遵循 [PROJECT_RULES §1.1.1](PROJECT_RULES.md)。

## 1. 現行優先順序

方案A已核准；2026-10-21 使用者啟動 A1～A4 整包實作、一次集中驗收，目前工程進行中，尚未結案。後續產品順序 A-CHANGE → D07-PRE → D07 → D08；D07-PRE現有採集可獨立續作，STAGE-48H仍由原對話收尾，不阻擋方案A或研究。

| 優先 | 工作包 | 已完成 | 尚需完成 |
|---|---|---|---|
| **P0** | **STAGE-48H** | 48h Stage 清理與自然排程 PASS；**新版 Admin MB／千分位已在正式 dev API 100% 發布**，且回滾演練 PASS | **僅餘新版登入 Admin 六桶全數 `OBSERVED` 與合計容量實機驗收** |
| **P1** | **A-CHANGE｜事實解讀與站內盤前盤後** | 方案、X/Y/時間契約與AI卡已定版；A1～A4 已啟動整合實作 | **集中 targeted/CI、既有 dev 發布與真實 API/UI 驗收；完成前維持 IN_PROGRESS** |
| **P1** | **D07-PRE｜Colab／Drive 資料源** | 官方歷史整市場 Colab 採集器、普通股白名單、每月資料夾/續跑/雜湊及 Risk 資料讀取已實作並有本地 targeted tests；舊 GAS/GCP/BQ 研究路線退出 | **21 個月 Drive r1 完整 SHA／上市90%上櫃70%研究准入、Risk 真實 single-cutoff OOS 及四段 walk-forward 診斷已有收據；Risk 不可 promotion，正式歷史 PIT／公司行動／來源授權／模型發布仍屬 D07 gate** |
| **P2** | **D07｜五分析師建模** | **已選 XGBoost8 為 Risk 正式候選**；本地封存模型及99檔SHA/74,487行OOS重新載入一致；GitHub/Drive重訓手冊及模型卡已建立；個股 Risk 訊號 UI 程式已接入 | **尚未 GCS candidate／Janus Mart模型匯入、每日推論服務啟用／dev發布／資料授權／PIT／公司行動與新前瞻驗證；現役 risk 仍 deterministic，不可稱XGB已上線**。需確認 Flutter CI 後，接既有 Scheduler→Controller→Mart，同批產生及讀回模型訊號，失敗沿規則回退 |
| **P3** | **D08｜CEO／Admin／Owner 報告** | 原 Gateway 技術驗證可重用 | **有效 Fact Pack → CEO 手動請求 → Gateway／validator → immutable 報告與 Owner UI／Admin 管理驗收** |

## 2. STAGE-48H｜自然排程及 Admin 登入操作 PASS，僅餘六桶完整數據

- [x] **每日自然排程 PASS（2026-10-20 18:30 Asia/Taipei）**：[唯讀驗收 #39523200448](https://github.com/tommylin15/janus-omniforge/actions/runs/39523200448) 讀得 Scheduler `janus-ingestion-daily` ENABLED／`30 * * * *`／Asia/Taipei、Controller 18:31:32 tick、Stage-only worker `janus-ingestion-core-qnfjv` 18:33:20 `apply`＋`generation_readback=PASS`、Cloud Run execution terminal PASS；實刪 **1,025 objects／265,691,880 bytes**，週維護設定 `FINOPS_WEEKLY_MAINTENANCE=true` 不變。這是既有自然執行的只讀驗證，本輪 GCP/Stage 刪除操作為零；未單獨直接查詢 Controller PostgreSQL occurrence row，不把該直接查詢冒稱已做。
- [ ] **Admin 六桶完整結果驗收（新版 100% API 發布 PASS；真人登入已 PASS、完整數據仍 PARTIAL）**：2026-10-21 真實 Admin OAuth 截圖確認登入與一鍵盤點可操作，盤點時間 `2026-10-21T01:02:17Z`、狀態 `PARTIAL_NOT_TOTAL`，Stage、Cloud Build 顯示 `BLOCKED`，因此 totals=null；未對所有六桶成功列出 metadata。匿名拒絕 401 與已登入正向觸發均已 PASS，不重驗。後續僅需在已有授權下解決兩桶查詢後重看完整結果；無具體原因前不擴大 IAM。唯讀 IAM 診斷 [#39525449445](https://github.com/tommylin15/janus-omniforge/actions/runs/39525449445)、[拒絕紀錄查核 #39525668778](https://github.com/tommylin15/janus-omniforge/actions/runs/39525668778)：CI 身分無法讀 IAM policy，該時間窗無可用拒絕事件，**不能證實 API 真正拒絕原因**。**新版實機驗收入口**：[Janus dev](https://janus-api-2oo7qbkd5q-uc.a.run.app/app/) → Admin → 資料品質 → 儲存維護 → 一鍵盤點；版號須為 `0b0a42b608143d62f5241d47c2d25e855949f36b`。新版僅更動容量十進位 MB（兩位小數、千分位）／物件數千分位和有界錯誤碼；API 100% 發布 [#39560369519](https://github.com/tommylin15/janus-omniforge/actions/runs/39560369519) PASS，不代表授權 GCS 六桶已全 OBSERVED；成功後才結案。

已完成證據：[GHCR／四 Jobs #39355867356／#39356643823](https://github.com/tommylin15/janus-omniforge/actions/runs/39356643823)、[獨立 readback #39358461946](https://github.com/tommylin15/janus-omniforge/actions/runs/39358461946)、[Stage 實刪 4,927 件／96,321,204 bytes #39355428497](https://github.com/tommylin15/janus-omniforge/actions/runs/39355428497)、[shared raw/provenance #39358645373](https://github.com/tommylin15/janus-omniforge/actions/runs/39358645373)、[48h dry-run 零候選 #39359037869](https://github.com/tommylin15/janus-omniforge/actions/runs/39359037869)。歷史細節集中 [Operations](spec/operations-and-testing.md)，不在 Active TODO 重複列流水帳。此項由原 Stage 對話承接，與 D07-PRE 分開。

## 2A. A-CHANGE｜方案 A

- [ ] A1 有證據的事實模板與跨角色摘要；與模型validated gate分開。
- [ ] A2 版本化觀察、新增/持續/增強/減弱/解除/失效/過期與缺資料狀態、跨日對照。
- [ ] A3 共用facts的站內盤前/盤後，cutoff、休市與資料晚到語意。
- [ ] A4 首頁/個股整合及targeted/CI/dev/API/UI集中驗收，30秒理解測試。

責任WBS-5/6；[唯一SPEC](spec/change-analysis.md)、[AI卡](execution-cards/a-change-analysis.md)。不含推播/日常LLM/新服務，不重開D03；工程須後續明確啟動。

## 3. D07-PRE｜Colab 官方歷史資料採集與每月資料夾

**新架構（2026-10-20）**：GAS 方案已退役，不保留 GAS 安裝、OAuth、Loader 或人工 GAS 實跑待辦。程式：`research/colab/collect_tw_equities.py`、`monthly_folder_io.py`、`run_risk_folder_pilot.py`；Drive 結構：`janusChatGPT/資料源/YYYY-MM/{ohlcv-r1.csv.gz,universe-r1.csv,quality-r1.json,manifest-r1.json}`。官方 TWSE/TPEx 逐日整市場取數，最新公司名冊白名單先排除 ETF 等；來源請求限速，10 平日 checkpoint，完整月封存後驗 hash 並清掉中繼碎檔。資料研究用途 `PROBE`、現行名冊歷史涵蓋限制明確保留。此前 GAS 程式僅存 Git 歷史及舊 Drive 備份，無現役引用。

- [x] **Drive 實際月檔與 SHA 讀回**：2025-01～2026-09 共21個封存 r1 月份，讀回 OHLCV／quality／manifest，股票名冊 SHA 一致；799,468 筆、1,979 檔普通股行情、422 個已收市場交易日。使用者報告 Colab 採集已完成；未取得 Colab console/API 呼叫日誌，不將此延伸宣稱模型已訓練。
- [x] **研究資料門檻（PROBE）**：採上市普通股 ≥90%、上櫃普通股 ≥70%，依每月名冊股票涵蓋及股票交易日涵蓋獨立確認；21個月皆過。最低月度股票比上市94.58%／上櫃92.61%，最低股票交易日比例上市94.20%／上櫃90.79%。原始 `r1` 不改寫。歷史下市母體／PIT／公司行動仍未驗證，列入 D07 正式模型 promotion gate，不再阻擋 Risk 研究 OOS。
- [x] **Risk 真實研究 OOS**（D07-PRE 試點結案，不代表 Colab console/CI/正式模型）：2026-10-21 於研究執行環境讀回 21 個 r1 Drive 月檔，完成市場交易日缺口控制、train maturity cutoff、Rolling20 vs Ridge OOS（354,483 train／181,557 OOS，MAE 改善 8.49%）與四段 walk-forward 診斷（2026 Q1 落後 baseline 7.09%）；正式模型維持 NOT_PROMOTABLE，收據見 [Risk 真實 OOS](archive/d07-risk-oos-real-2026-10-21.md)。相關 targeted/CI 新版驗證收據待補，不宣稱 CI PASS。

[唯一研究資料 SPEC](spec/research-collection-gas-drive-colab.md)；[Colab 執行說明](../research/colab/README.md)。已結案舊 GCP/BQ 研究清理保持 CLOSED，不重開。

## 4. D07｜五角色模型與正式介接

- [ ] **共用X/Y與時間處理**：依[因子時間契約](spec/model-feature-time-contract.md)建立交易日/公告as-of join、公司行動與單位、滾動feature builder、成熟label、版本/增量及訓練/推論同輸入一致性；不每天重抓整段歷史。
- [ ] **模型與研究評估**：Risk v0／v1 的原始普通股同樣本 OOS 已完成；八因子 v1 MAE 0.127537、對五因子 v0 0.133647 改善4.57%，但2026-08 v1 小幅退步，且四段皆為已檢視歷史非新 holdout；收據見 [Risk v1](archive/d07-risk-v1-ohlcv-oos-2026-10-22.md)。**剩餘** Colab 本人重跑/targeted/CI、可比較公司行動與PIT/授權、未使用期間驗證及 Quant／其餘角色各自 OOS；未達 gate 不上線。
- [ ] **Colab整體交付與資料量**：共用notebook與五角色設定，採集/清洗/as-of/X/Y/成熟標籤/OOS；列實收原生期數與建議量差距，延伸歷史前補年度日曆/來源支援；不以不足樣本硬訓練。
- [ ] **XGBoost8 受控部署／每日 Risk 推論（使用者 2026-10-22 要求）**：已凍結研究 cycle `2026Q3-20261022`，本地 XGB UBJ SHA `36c77d0168a1d667223ab915c9b08fd2c1c6608f9f7db2fc046204e922854044`，99檔 hash 全 PASS，重新載入 MAE 0.129701336 一致；**尚缺** GCS candidate 上傳+SHA讀回、合法來源／PIT／公司行動與獨立驗證、正式Core OHLCV欄位及市場日曆feature parity、Mart safe loader及每日Controller接線、CI/dev真實定時job輸出、API/UI readback與rollback。**正式 runtime 現在仍是 deterministic-unpromoted-v1，不能報 ACTIVE。** 無法滿足promotion gate時先做shadow，確定性基準不切換。
- [ ] **Risk訊號及週期閉環**：已依使用者決定為「每交易日盤後推論、每週缺值健康、每月成熟label相對Rolling20評估、每季檢討重訓」，個股頁 `RiskSignalCard` 已寫入顯示高波動警示橘、緩和青綠、未驗證/過期灰與行情資料日+小字更新頻率；未經validated不可顯示XGB預測數值。待Flutter CI、API接真實成熟預測、夜批自然運行、留存/retention與真實UI讀回；深度股票union分批、同Controller接線，不另建cron。A-CHANGE負責使用者事實報告，D07負責模型評估。詳見[Risk手冊](spec/risk-model-training-retraining-runbook.md)、[模型卡](spec/risk-model-card.md)。

完整開發/發布/回收契約見[模型生命週期](spec/model-lifecycle.md)及[AI卡](execution-cards/d07-model-lifecycle.md)。本輪為DOC_UPDATED，未上傳模型或啟用新排程。

模型選型/X/Y/產出唯一見[五分析師](spec/specialist-engines.md)；[D07 唯一任務卡](execution-cards/d07-specialist-b9-oos.md)。Risk沿用現有Ridge試點，其他角色按資料與獨立期數判定，不為湊齊五模型而發布。

## 5. D08｜CEO／Admin／Owner 報告

- [ ] **正式整合與驗收**：具來源的有效 Fact Pack → Owner 手動 request → 現有 OmniGateway／Gemini → validator → immutable GCS／PG → Owner history／UI 與 Admin 設定／權限／回滾 readback；LLM 不決定 canonical 數字或最終 publication。

[D08 唯一任務卡](execution-cards/d08-ceo-admin-owner-report.md)。正式報告依賴 D07 有效模型輸出，但**已結案的 FINOPS-AB／D06／舊 B5～B8 不得成為重新施工的前置條件**。

## 6. 已結案、不再列待辦

D01～D05、DRL-01、FINOPS-AB（含 D06）、既定背景持股／關注股補收、Admin v2、舊研究 GCP 工作及排程退役、BigQuery 舊 ML/OOS 中介資源清理，均依已核准的原驗收邊界 **CLOSED／PASS 或 USER_ACCEPTED**。收據保留在 [結案索引](wbs/completed-index.md)／[Operations](spec/operations-and-testing.md)／[archive](archive/d07-gcp-bq-retirement-live-2026-10-20.md)，**不因未列舉所有理論可能性新增待辦**。新缺陷須有實際證據，再依當次工作包處理。

