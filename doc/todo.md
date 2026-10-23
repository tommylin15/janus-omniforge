# Janus — 唯一 Active TODO

更新：2026-10-23。**只列尚未完成的工作與原定驗收，不收納歷史失敗、已結案工程、無具體異常的推測性追查。** 狀態以 GitHub `main`／真實 CI、deployment 與 runtime 為準；結案遵循 [PROJECT_RULES §1.1.1](PROJECT_RULES.md)。

## 1. 現行優先順序

方案A已核准；2026-10-21 使用者啟動 A1～A4 整包實作、一次集中驗收，目前工程進行中，尚未結案。後續產品順序 A-CHANGE → D07-PRE → D07 → D08；D07-PRE現有採集可獨立續作，STAGE-48H 已於 2026-10-23 CLOSED，證據見 Operations。

| 優先 | 工作包 | 已完成 | 尚需完成 |
|---|---|---|---|
| **P0** | **ADMIN-SIMPLIFY｜操作與批次整包** | 2026-10-23 使用者授權全功能盤點、必要重構及整批修改／集中驗收；契約見 [Admin UI](ui/admin.md) 最新章節 | **IN_PROGRESS**：4頁10功能、首頁實用儀表板、白話與詳情分層、日週月／未啟用批次、最新7日紀錄與安全log、時間／耗時／逾期、統一啟停／重算入口；完成實作、targeted／完整CI、同來源dev發布與登入驗收才結案 |
| **P1** | **A-CHANGE｜事實解讀與站內盤前盤後** | 方案、X/Y/時間契約與AI卡已定版；A1～A4 已啟動整合實作 | **集中 targeted/CI、既有 dev 發布與真實 API/UI 驗收；完成前維持 IN_PROGRESS** |
| **P1** | **D07-PRE｜Colab／Drive 資料源** | 21 個月 r1 原始行情研究准入 PASS；Drive v3.1 `CURRENT.json` + 153 個 Parquet 月分區讀回、**格式整併 CLOSED**；v3.5 長期增量／TPEx 空日解析／完整安裝格已上傳原 Drive Notebook ID，原始官方回應＋跨年度本地 15/15 PASS，讀回 SHA256 一致；舊研究 GAS/GCP/BQ 退役 | **官方／第三方補收 PARTIAL：2026-10-22 Colab 官方 264 批最新報告僅剩 TPEx 估值 7 個未達標月（2024-10、2025-01～05、2026-02），v3.5 尚待 Colab 重新執行與品質報告／Parquet 讀回**；Risk 可試訓不等於模型 promotion，歷史 PIT／公司行動與授權／模型發布仍屬 D07 gate |
| **P2** | **D07｜五分析師建模** | Risk XGBoost8 已完成 dev 模型候選上傳／SHA驗證、Core EOD/PIT日期修復、四 Jobs 可回滾部署與 **2026-10-21 真實 shadow 日批 1,720 檔 GCS 讀回 PASS**（[#39781316641](https://github.com/tommylin15/janus-omniforge/actions/runs/39781316641)）；Quant／Fundamental／Valuation 另行建模 | **Risk shadow CLOSED、Risk dev 首次 Registry／PG ACTIVE 資料面 PASS，Owner 正向 UI NOT_VERIFIED**；有界公司行動／PIT 防洩漏、實際來源用途與訓練／serving parity、Registry CAS 及後續 API/UI ACTIVE 驗收仍在 D07；**新增前瞻20日成熟與全市場歷史PIT/公司行動完整度已依10/22決策移出首次等待 gate** |
| **P3** | **D08｜CEO／Admin／Owner 報告** | 原 Gateway 技術驗證可重用 | **有效 Fact Pack → CEO 手動請求 → Gateway／validator → immutable 報告與 Owner UI／Admin 管理驗收** |

## 2. ADMIN-SIMPLIFY｜整批修改後集中驗收

2026-10-23：UI、API／Controller 與佇列限定執行已實作；本地 Python 103 項、Flutter 36 項 PASS。Windows ASGI 路由測試因事件迴圈阻塞未取得結果，保留於 Linux 完整 CI 執行。即時喚醒與指定執行停止的兩項最小 IAM 權限已套用並讀回；尚待完整 Release、同來源部署及正向驗收。

- [ ] 依 [Admin UI 最新契約](ui/admin.md) 完成全功能盤點、保留／移除／合併，更新四頁十功能與白話操作。
- [ ] 首頁以可操作的工作／資料健康／損益更新取代 Core／Mart 數量與 AI placeholder。
- [ ] 批次按日／週／月／手動／未啟用階層呈現，最近7天每工作最新執行與安全log、時間、耗時及可信逾期判斷。
- [ ] 統一手動收集／補資料／分析／重算／備份／清理入口，實作 allowlist／依賴／冪等／隔離／稽核的啟動、停止本次與暫停後續；不安全或未實作項目明示原因。
- [ ] 完成相關回歸、手機／桌面、完整CI／同來源dev發布／回滾及登入Admin正向集中驗收，保留失敗與真實blocker，不因文件或build成功宣稱完成。

## 2A. A-CHANGE｜方案 A

- [ ] A1 有證據的事實模板與跨角色摘要；與模型validated gate分開。
- [ ] A2 版本化觀察、新增/持續/增強/減弱/解除/失效/過期與缺資料狀態、跨日對照。
- [ ] A3 共用facts的站內盤前/盤後，cutoff、休市與資料晚到語意。
- [ ] A4 首頁/個股整合及targeted/CI/dev/API/UI集中驗收，30秒理解測試。

責任WBS-5/6；[唯一SPEC](spec/change-analysis.md)、[AI卡](execution-cards/a-change-analysis.md)。不含推播/日常LLM/新服務，不重開D03；工程須後續明確啟動。

## 3. D07-PRE｜Colab 單一 Parquet 研究資料與缺口補收

**2026-10-22 最新狀態**：Drive `JanusDataset_v3_202610/canonical/CURRENT.json` 指向 v3.1.0 research-only Parquet release，已核對 153 個分區檔及 manifest；**Parquet 格式整併 CLOSED**。**官方／第三方補收仍 PARTIAL**：官方估值 50/72（TPEx 缺 22 個月份）、income 24/32、balance/cashflow 各 22/32；2026Q3 的財報尚在公告預留期，不能稱失敗。新版 [`00_資料收集.ipynb` v3.3](https://drive.google.com/file/d/1403NtnW0sQ5VuATycDiFvEsHztOvlMvH/view) 已上傳，內含只補缺、`BUDGET_PAUSED` 斷點及動態繁中研究准入表，16 cells／7 modules 解析與本地 targeted 6/6 PASS。**未執行新版 v3.3 Colab 實機補收，故不可關閉補收**。
- [x] `PARQUET-MERGE`：模型資料唯一 Parquet 入口、版次 manifest 與現況 Drive 檔案讀回（只關閉格式整併）。
- [x] `COLLECT-NOTEBOOK-LONGTERM`：v3.3 同一份 Notebook 支援台灣時間上月截止、2027/03 自動至 2027-02、所有新增月份/市場/資料類型增量補缺、年度普通股名冊 revision 與舊檔保留；6/6 本地 targeted PASS，Drive 上傳/metadata 讀回。此項只關閉程式交付；Colab 實際新月份補收仍屬下項。\n- [x] `TPEx-VALUATION-ADAPTER-v3.4`：22 月 TPEx 估值錯誤根因定位為舊 JSON envelope 無法辨識時，同來源兩次失敗即略過其他月份。改用官方歷史日期 HTML 整市場表格核對日期，保留 checkpoint/原始 hash；確認 parser schema failure 才啟用有界 FinMind 歷史備援，不繞過拒絕/限流；本地 TPEx 7/7 ＋原跨年度 7/7 PASS，Drive [原 Notebook](https://drive.google.com/file/d/1403NtnW0sQ5VuATycDiFvEsHztOvlMvH/view) 原 ID 改為 v3.4 且 SHA 讀回，v3.3 有封存備份。**本項只關閉工程交付，不代表 22 月已補齊。**\n- [x] `COLLECT-NOTEBOOK-v3.5-REPAIR`：原 Drive v3.4 安裝格只剩單行 import（確為 Notebook 檔案缺陷）；從可查前版恢復 10 行包含 pip、Drive 掛載與 ROOT。Drive raw TPEx 2025-05-30／2026-02-27 具正確日期、`<tbody>` 空、`共0筆`，改作明確無資料往前有界查日，不能當 schema 不符。真實原始 3 檔測試＋其他修復 8/8、跨年度回歸 7/7 PASS；Drive 原 ID 更新/下載 SHA256 一致，v3.4 封存可回復。**此項僅關閉程式修復，7 月真實補收未結案**。\n- [ ] `COLLECT-GAP`：用 v3.5 Notebook 定向完成 TPEx 估值剩餘 7 個未達標月（2024-10、2025-01～05、2026-02），已達標的其餘月份不得重抓；真正缺口可依門檻有限 FinMind 補缺，季財報依新報告各自獨立檢查；核對 `reports/驗收總表.csv`、`模型試訓準入.csv`、`逐期缺口與原因.csv`。BUDGET_STOP 不視為來源失敗，尚待 Colab 實機補跑。

**舊 r1 月資料格式與原證據（保留參考）**：

**新架構（2026-10-20）**：GAS 方案已退役，不保留 GAS 安裝、OAuth、Loader 或人工 GAS 實跑待辦。程式：`research/colab/collect_tw_equities.py`、`monthly_folder_io.py`、`run_risk_folder_pilot.py`；Drive 結構：`janusChatGPT/資料源/YYYY-MM/{ohlcv-r1.csv.gz,universe-r1.csv,quality-r1.json,manifest-r1.json}`。官方 TWSE/TPEx 逐日整市場取數，最新公司名冊白名單先排除 ETF 等；來源請求限速，10 平日 checkpoint，完整月封存後驗 hash 並清掉中繼碎檔。資料研究用途 `PROBE`、現行名冊歷史涵蓋限制明確保留。此前 GAS 程式僅存 Git 歷史及舊 Drive 備份，無現役引用。

- [x] **Drive 實際月檔與 SHA 讀回**：2025-01～2026-09 共21個封存 r1 月份，讀回 OHLCV／quality／manifest，股票名冊 SHA 一致；799,468 筆、1,979 檔普通股行情、422 個已收市場交易日。使用者報告 Colab 採集已完成；未取得 Colab console/API 呼叫日誌，不將此延伸宣稱模型已訓練。
- [x] **研究資料門檻（PROBE）**：採上市普通股 ≥90%、上櫃普通股 ≥70%，依每月名冊股票涵蓋及股票交易日涵蓋獨立確認；21個月皆過。最低月度股票比上市94.58%／上櫃92.61%，最低股票交易日比例上市94.20%／上櫃90.79%。原始 `r1` 不改寫。歷史下市母體／PIT／公司行動仍未驗證，列入 D07 正式模型 promotion gate，不再阻擋 Risk 研究 OOS。
- [x] **Risk 真實研究 OOS**（D07-PRE 試點結案，不代表 Colab console/CI/正式模型）：2026-10-21 於研究執行環境讀回 21 個 r1 Drive 月檔，完成市場交易日缺口控制、train maturity cutoff、Rolling20 vs Ridge OOS（354,483 train／181,557 OOS，MAE 改善 8.49%）與四段 walk-forward 診斷（2026 Q1 落後 baseline 7.09%）；正式模型維持 NOT_PROMOTABLE，收據見 [Risk 真實 OOS](archive/d07-risk-oos-real-2026-10-21.md)。相關 targeted/CI 新版驗證收據待補，不宣稱 CI PASS。

[唯一研究資料 SPEC](spec/research-collection-gas-drive-colab.md)；[Colab 執行說明](../research/colab/README.md)。已結案舊 GCP/BQ 研究清理保持 CLOSED，不重開。

## 4. D07｜五角色模型與正式介接

- [ ] **共用X/Y與時間處理**：依[因子時間契約](spec/model-feature-time-contract.md)建立交易日/公告as-of join、公司行動與單位、滾動feature builder、成熟label、版本/增量及訓練/推論同輸入一致性；不每天重抓整段歷史。
- [ ] **模型與研究評估**：Risk v0／v1 的原始普通股同樣本 OOS 已完成；八因子 v1 MAE 0.127537、對五因子 v0 0.133647 改善4.57%，但2026-08 v1 小幅退步，且四段皆為已檢視歷史非新 holdout；收據見 [Risk v1](archive/d07-risk-v1-ohlcv-oos-2026-10-22.md)。**剩餘** Risk：有界來源授權／PIT防洩漏／公司行動污染與訓練serving一致性實證、targeted CI、CAS/rollback 與可發布判定；新前瞻20日成熟改成上線後月度回收，不再屬 Risk 首次 promotion 等待；其餘角色各自 OOS 不在本輪。
- [ ] **Colab四角色獨立Notebook與資料量**：依已完成的四份開發文件／AI指令實作 [Quant](colab-models/01-quant-xgboost.md)、[Risk](colab-models/02-risk-xgboost.md)、[Fundamental](colab-models/03-fundamental-xgboost.md)、[Valuation](colab-models/04-valuation-xgboost.md) XGBoost Notebook；共用Python模組、各自獨立Run all，只讀CURRENT指定Parquet release。採集沿用00，不重抓；列清洗/as-of/X/Y/成熟標籤/OOS與實際原生期數。**Drive 三份 Notebook 已存在。Quant v3.6 於 2026-10-23 完成 ChatGPT 真 OHLCV 試訓／OOS／UBJ 本地重載（研究範圍 PASS、非 DEPLOYABLE）；Fundamental／Valuation 仍待試做，三者的正式發布 gate 均不可據此判 PASS。詳見 [Quant 真資料研究收據](research/quant-v36-chatgpt-realdata-2026-10-23.md)；Risk 沿既有模型；Event 另議。**
- [x] **Risk XGBoost8 真實 dev shadow EOD + GCS 讀回**（2026-10-22 CLOSED）：Core 官方 2026-10-21 EOD 補讀執行 [#39778699918](https://github.com/tommylin15/janus-omniforge/actions/runs/39778699918) PASS；完整 Release [#39773463340](https://github.com/tommylin15/janus-omniforge/actions/runs/39773463340)、受控四 Jobs rollout [#39775830718](https://github.com/tommylin15/janus-omniforge/actions/runs/39775830718) PASS；真實 Mart execution `janus-intelligence-mart-5rv6r` 成功；原 [#39779986652](https://github.com/tommylin15/janus-omniforge/actions/runs/39779986652) 的**執行清單比對**誤判改由 exact Execution ID 唯讀讀回，最終 [#39781316641](https://github.com/tommylin15/janus-omniforge/actions/runs/39781316641) 完整 PASS、**1,720 個有效預測**、Core manifest hash/snapshot、模型 SHA `36c77d0168a1d667223ab915c9b08fd2c1c6608f9f7db2fc046204e922854044`、GCS 不可變產物均核對，`SHADOW_UNVALIDATED` 且 `publication_allowed=false`。**只關閉真實 shadow 日批與 GCS 認證**；未正式 promotion、未驗證持續自然日批。後續 promotion gate 僅保留於本節「模型與研究評估」及「Risk訊號及週期閉環」，不再重做 shadow 已 PASS 工項。
- [x] **Risk XGBoost8 首次 dev Registry／PostgreSQL ACTIVE 與真實持股／觀察股預測（2026-10-23 資料面 PASS）**：沿用核准 risk-xgboost8-2025h2-v1，未重訓／未增資源。Risk 專用 pinned OHLCV 讀取／八因子逐檔品質、GHCR [#39892375248](https://github.com/tommylin15/janus-omniforge/actions/runs/39892375248) 1,629 Python／Flutter／Release PASS、四 Jobs [#39893872327](https://github.com/tommylin15/janus-omniforge/actions/runs/39893872327) PASS。首次 ACTIVE [#39896276392](https://github.com/tommylin15/janus-omniforge/actions/runs/39896276392) 真實 canary、GCS Registry generation CAS、PG append-only ACTIVE Job 全部 SUCCESS。獨立唯讀 [#39898282552](https://github.com/tommylin15/janus-omniforge/actions/runs/39898282552) PASS：2026-10-21 EOD 目標 union 8 檔，6/6 普通股 READY／6 筆真實預測、非普通股排除 2 檔、普通股排除 0 檔；OHLCV 900 列，Core provenance／GCS 不可變 bytes hash PASS、Registry 目前 ACTIVE、PG activation 執行及 log PASS、API 100%／health／未登入拒絕 PASS。此任務只關閉 model serving 及 GCS/PG 啟用資料面；不能當作 Owner 登入 UI、前瞻 20-session OOS 或自然盤後日批已驗收。
- [ ] **Risk v2 討論（延後，僅待辦占位，不在 v1 範圍）**：v1 八因子僅個股OHLCV，**未納入官方大盤／Beta、產業指數或產業共振、拆股/減資/除權息正式價格調整**。公司行動缺口是 v1 promotion 的資料安全驗收，不得用 v2 延後決議替代 v1 必要的資料守門。依使用者指示：**先完成本輪 XGBoost v1 安全部署、日批與真實 UI 讀回後，才討論 v2 因子/資料架構**；不預先增加資料採集、重訓或付費服務。
- [ ] **Risk XGBoost8 Owner 正向 API/UI 與實際回滾演練（ACTIVE 後）**：唯讀 #39898282552 只驗證 Registry／GCS／PG job 收據與 API 100%／匿名拒絕；須使用既有 Owner 登入 session 正向讀回最新個股分析 row（確認 10/21 的 XGB 有效預測不被較新 deterministic row 蓋過）、first_release_approved 狀態、RiskSignalCard 與 ETF exclusion／逐股 fallback。再有界測試 PG/GCS Registry 回 DETERMINISTIC 後 API 立刻隱藏 XGB，以及可還原 ACTIVE／再讀回。沒有真人登入正向證據前維持 NOT_VERIFIED，不因此撤回已通過的資料面 ACTIVE。
- [ ] **Risk訊號及週期閉環**：已依使用者決定為「每交易日盤後推論、每週缺值健康、每月成熟label相對Rolling20評估、每季檢討重訓」，個股頁 `RiskSignalCard` 已寫入顯示高波動警示橘、緩和青綠、未驗證/過期灰與行情資料日+小字更新頻率；未經validated不可顯示XGB預測數值。Flutter User App獨立CI已PASS（[39699020525](https://github.com/tommylin15/janus-omniforge/actions/runs/39699020525)），仍待完整GHCR Release與四Jobs rollout、API/實機資料讀回、夜批自然執行與retention/完整promotion；深度股票union分批、同Controller接線，不另建cron。A-CHANGE負責使用者事實報告，D07負責模型評估。詳見[Risk手冊](spec/risk-model-training-retraining-runbook.md)、[模型卡](spec/risk-model-card.md)。

完整開發/發布/回收契約見[模型生命週期](spec/model-lifecycle.md)及[AI卡](execution-cards/d07-model-lifecycle.md)。本輪為DOC_UPDATED，未上傳模型或啟用新排程。

模型選型/X/Y/產出唯一見[五分析師](spec/specialist-engines.md)；[D07 唯一任務卡](execution-cards/d07-specialist-b9-oos.md)。Risk沿用既有XGBoost8候選及Rolling20/Ridge比較，其他三角色採XGBoost challenger並按資料與獨立期數判定，不為湊齊五模型而發布。

- [ ] **D07-THREE-XGB-CHATGPT-PILOT（Quant／Fundamental／Valuation）**：Drive 已有三份 `.ipynb`，改在 ChatGPT 可用研究/Python 環境逐角色真實試訓（Colab 非必需），固定 CURRENT Parquet release/manifest/hash、不重抓資料；按角色完成成熟 Y、PIT/來源/公司行動、OOS/baseline、UBJ與train/serving parity、GCS candidate/readback、shadow/CI/受控發布相容證據。**Quant：真實研究試訓／OOS／UBJ 重載 PASS**（21 Parquet、799,468 原始列、90,498 OOS、Brier 0.240060 vs 基準 0.243168；block 20d CI 涵 0、PIT/復權/校準尚未滿足，**NOT DEPLOYABLE**，證據見 [Quant 研究收據](research/quant-v36-chatgpt-realdata-2026-10-23.md)）。Fundamental／Valuation 真實試訓與三者的可部署 gate 尚待，失敗按實際標示；**不重訓、不提前改 Risk v1**。
- [ ] **D07-CROSS-JOB-MODEL-CACHE（四模型統一效能整合）**：**必須等上述三模型全都達 DEPLOYABLE**，再一次與 Risk v1 整合共用 loader/版本快取；GCS immutable model 為權威，既有 Cloud Run Mart Job 內每角色載入一次。跨 Job execution 不共享 RAM，先實測 GCS+每次單次載入 vs 版本固定 image layer 等零新服務方案；驗 hash/cache invalidation/效能/GCS IO/回滾/Owner與真實 dev 日批，無明顯效益維持原案；不得加新付費常駐服務。唯一規格 [模型生命週期](spec/model-lifecycle.md)／[D07 AI 卡](execution-cards/d07-model-lifecycle.md)。

## 5. D08｜CEO／Admin／Owner 報告

- [ ] **正式整合與驗收**：具來源的有效 Fact Pack → Owner 手動 request → 現有 OmniGateway／Gemini → validator → immutable GCS／PG → Owner history／UI 與 Admin 設定／權限／回滾 readback；LLM 不決定 canonical 數字或最終 publication。

[D08 唯一任務卡](execution-cards/d08-ceo-admin-owner-report.md)。正式報告依賴 D07 有效模型輸出，但**已結案的 FINOPS-AB／D06／舊 B5～B8 不得成為重新施工的前置條件**。

## 6. 已結案、不再列待辦

D01～D05、DRL-01、FINOPS-AB（含 D06）、既定背景持股／關注股補收、Admin v2、舊研究 GCP 工作及排程退役、BigQuery 舊 ML/OOS 中介資源清理，均依已核准的原驗收邊界 **CLOSED／PASS 或 USER_ACCEPTED**。收據保留在 [結案索引](wbs/completed-index.md)／[Operations](spec/operations-and-testing.md)／[archive](archive/d07-gcp-bq-retirement-live-2026-10-20.md)，**不因未列舉所有理論可能性新增待辦**。新缺陷須有實際證據，再依當次工作包處理。

