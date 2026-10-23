# Janus — 唯一 Active TODO

更新：2026-10-23。**只列尚未完成的工作與原定驗收，不收納歷史失敗、已結案工程、無具體異常的推測性追查。** 狀態以 GitHub `main`／真實 CI、deployment 與 runtime 為準；結案遵循 [PROJECT_RULES §1.1.1](PROJECT_RULES.md)。

## 1. 現行優先順序

方案A已核准；2026-10-21 使用者啟動 A1～A4 整包實作、一次集中驗收，目前工程進行中，尚未結案。後續產品順序 A-CHANGE → D07-PRE → D07 → D08；D07-PRE現有採集可獨立續作，STAGE-48H 已於 2026-10-23 CLOSED，證據見 Operations。

| 優先 | 工作包 | 已完成 | 尚需完成 |
|---|---|---|---|
| **P0** | **ADMIN-SIMPLIFY｜操作與批次整包** | 2026-10-23 使用者授權全功能盤點、必要重構及整批修改／集中驗收；契約見 [Admin UI](ui/admin.md) 最新章節 | **IN_PROGRESS**：4頁10功能、首頁實用儀表板、白話與詳情分層、日週月／未啟用批次、最新7日紀錄與安全log、時間／耗時／逾期、統一啟停／重算入口；完成實作、targeted／完整CI、同來源dev發布與登入驗收才結案 |
| **P1** | **A-CHANGE｜事實解讀與站內盤前盤後** | 方案、X/Y/時間契約與AI卡已定版；A1～A4 已啟動整合實作 | **集中 targeted/CI、既有 dev 發布與真實 API/UI 驗收；完成前維持 IN_PROGRESS** |
| **P1** | **D07-PRE｜Colab／Drive 資料源** | 21 個月 r1 原始行情研究准入 PASS；Drive v3.1 `CURRENT.json` + 153 個 Parquet 月分區讀回、**格式整併 CLOSED**；v3.5 長期增量／TPEx 空日解析／完整安裝格已上傳原 Drive Notebook ID，原始官方回應＋跨年度本地 15/15 PASS，讀回 SHA256 一致；舊研究 GAS/GCP/BQ 退役 | **官方／第三方補收 PARTIAL：2026-10-22 Colab 官方 264 批最新報告僅剩 TPEx 估值 7 個未達標月（2024-10、2025-01～05、2026-02），v3.5 尚待 Colab 重新執行與品質報告／Parquet 讀回**；Risk 可試訓不等於模型 promotion，歷史 PIT／公司行動與授權／模型發布仍屬 D07 gate |
| **P2** | **D07｜五分析師建模** | Risk XGBoost8 已完成 dev 模型候選上傳／SHA驗證、Core EOD/PIT日期修復、四 Jobs 可回滾部署與 **2026-10-21 真實 shadow 日批 1,720 檔 GCS 讀回 PASS**（[#39781316641](https://github.com/tommylin15/janus-omniforge/actions/runs/39781316641)）；Quant／Fundamental／Valuation 另行建模 | **Risk shadow 本項 CLOSED，不等於正式模型 ACTIVE**；有界公司行動／PIT 防洩漏、實際來源用途與訓練／serving parity、Registry CAS 及後續 API/UI ACTIVE 驗收仍在 D07；**新增前瞻20日成熟與全市場歷史PIT/公司行動完整度已依10/22決策移出首次等待 gate** |
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
- [ ] **Colab四角色獨立Notebook與資料量**：依已完成的四份開發文件／AI指令實作 [Quant](colab-models/01-quant-xgboost.md)、[Risk](colab-models/02-risk-xgboost.md)、[Fundamental](colab-models/03-fundamental-xgboost.md)、[Valuation](colab-models/04-valuation-xgboost.md) XGBoost Notebook；共用Python模組、各自獨立Run all，只讀CURRENT指定Parquet release。採集沿用00，不重抓；列清洗/as-of/X/Y/成熟標籤/OOS與實際原生期數。**Drive 已存在 Quant、Fundamental、Valuation 三份 Notebook；ChatGPT 真實訓練、OOS 與可部署驗收尚未由此項 PASS，Risk 沿既有模型；Event 另議。最新執行順序見本節 D07-THREE-XGB-CHATGPT-PILOT 與 D07-CROSS-JOB-MODEL-CACHE。**。
- [x] **Risk XGBoost8 真實 dev shadow EOD + GCS 讀回**（2026-10-22 CLOSED）：Core 官方 2026-10-21 EOD 補讀執行 [#39778699918](https://github.com/tommylin15/janus-omniforge/actions/runs/39778699918) PASS；完整 Release [#39773463340](https://github.com/tommylin15/janus-omniforge/actions/runs/39773463340)、受控四 Jobs rollout [#39775830718](https://github.com/tommylin15/janus-omniforge/actions/runs/39775830718) PASS；真實 Mart execution `janus-intelligence-mart-5rv6r` 成功；原 [#39779986652](https://github.com/tommylin15/janus-omniforge/actions/runs/39779986652) 的**執行清單比對**誤判改由 exact Execution ID 唯讀讀回，最終 [#39781316641](https://github.com/tommylin15/janus-omniforge/actions/runs/39781316641) 完整 PASS、**1,720 個有效預測**、Core manifest hash/snapshot、模型 SHA `36c77d0168a1d667223ab915c9b08fd2c1c6608f9f7db2fc046204e922854044`、GCS 不可變產物均核對，`SHADOW_UNVALIDATED` 且 `publication_allowed=false`。**只關閉真實 shadow 日批與 GCS 認證**；未正式 promotion、未驗證持續自然日批。後續 promotion gate 僅保留於本節「模型與研究評估」及「Risk訊號及週期閉環」，不再重做 shadow 已 PASS 工項。
- [ ] **Risk XGBoost8 正式模型 promotion／ACTIVE（2026-10-22 依最新有限範圍修訂 gate；尚未切 ACTIVE）**：使用者已要求正式發布；已在原有 Risk dev readback 加入唯讀 promotion preflight，Run [#39783792251](https://github.com/tommylin15/janus-omniforge/actions/runs/39783792251) **COMPLETED/SUCCESS（只代表唯讀查核與4/4定向測試PASS，不是模型啟用）**，真實 GCS 模型 SHA、10/21 Core snapshot 與 **1,720** 筆 shadow 預測讀回 PASS；正式結果 **`BLOCKED_NOT_ACTIVE`**，`publication_allowed=false`，未更新 registry／API／Job。原唯讀 preflight 的嚴格等待證據仍屬舊政策，不作新決策認證。最新本輪必解：① **確證 future leakage** 與實際模型使用窗口公司行動污染（不可查無不放行，無可比資料需排除）；② **開放資料可用性已依使用者最新標準 PASS**：TWSE 11549／TPEx 11370 OGDL 1.0，r1 歷史 API 授權映射列接受限制而非等待 gate；③ 研究／serving 八因子固定向量、prediction parity、hash loader；④ 僅持股+觀察股 union 之每日推論與排除統計；⑤ Registry expected-previous CAS/rollback 的真實可用入口。已檢視歷史 OOS 僅作診斷，新的20日 mature OOS 上線後追蹤；全市場歷史 PIT、全部公司行動不再是首次等待 gate。API/UI與自然日批只能切 ACTIVE 後驗收，不冒稱目前 PASS。先沿用 deterministic 主基準，保留 XGB shadow，無新證據不以使用者授權取代客觀 gate。 **2026-10-23 定向證據**：[Risk #39790661297](https://github.com/tommylin15/janus-omniforge/actions/runs/39790661297) 唯讀 4/4 PASS、真 GCS model SHA 與 1,720 shadow；[Research #39792614846](https://github.com/tommylin15/janus-omniforge/actions/runs/39792614846) 42 tests PASS；[Mart #39793027046](https://github.com/tommylin15/janus-omniforge/actions/runs/39793027046) 240 tests PASS（含 synthetic 八因子與 target union）；[#39794123966](https://github.com/tommylin15/janus-omniforge/actions/runs/39794123966) 只有 plan SUCCESS、tests SKIPPED。新增 Registry generation CAS／rollback 與 PostgreSQL #068、API／UI 第一版服務路徑；**2026-10-23 新驗收**：API 100% 可回滾切流 [#39885037268](https://github.com/tommylin15/janus-omniforge/actions/runs/39885037268) PASS、Core 2026-10-23 目標聯集 8 檔（普通股 6／非普通股 2），六檔因窗口缺口全排除，10/21 EOD 舊驗收路徑則觸發 250,000 列全市場讀取上限；兩次 GCS Registry 已回滾 `DETERMINISTIC`，PostgreSQL **未**切 ACTIVE。已以 `risk-target-acceptance` 和獨立限定 220 日的 `core.ohlcv_v1` 普通股掃描修復，逐檔品質報告保存在 private GCS；完整 Release [#39892375248](https://github.com/tommylin15/janus-omniforge/actions/runs/39892375248) **1,629 Python PASS、Flutter/四映像與 verify PASS**，0% API 候選 [#39893584099](https://github.com/tommylin15/janus-omniforge/actions/runs/39893584099)、OAuth/Owner [#39893763429](https://github.com/tommylin15/janus-omniforge/actions/runs/39893763429) PASS；四 Jobs 真實 rollout [#39893872327](https://github.com/tommylin15/janus-omniforge/actions/runs/39893872327) 仍待終態，**至少一檔真實完整預測、GCS/PG 投影、ACTIVE 以及 API/UI 與回滾讀回尚未 PASS**。先前 ACTIVE 佇列 [#39894174559](https://github.com/tommylin15/janus-omniforge/actions/runs/39894174559) 因同組並行部署取消，需於 Jobs 終態 PASS 後有界重觸發；不冒稱已 ACTIVE。來源 gate PASS；正式未驗證項限真實窗口污染與 PIT、真 UBJ parity、正式 union 排除計數及端到端可逆 serving。仍未切 ACTIVE。證據摘要檔 `risk-formal-promotion-preflight` 見該 Run artifact；依 [Risk Runbook](spec/risk-model-training-retraining-runbook.md) §6 後續定向完成，無需重做已 PASS 的四 Jobs rollout、Core/EOD/shadow。
- [ ] **Risk v2 討論（延後，僅待辦占位，不在 v1 範圍）**：v1 八因子僅個股OHLCV，**未納入官方大盤／Beta、產業指數或產業共振、拆股/減資/除權息正式價格調整**。公司行動缺口是 v1 promotion 的資料安全驗收，不得用 v2 延後決議替代 v1 必要的資料守門。依使用者指示：**先完成本輪 XGBoost v1 安全部署、日批與真實 UI 讀回後，才討論 v2 因子/資料架構**；不預先增加資料採集、重訓或付費服務。
- [ ] **Risk訊號及週期閉環**：已依使用者決定為「每交易日盤後推論、每週缺值健康、每月成熟label相對Rolling20評估、每季檢討重訓」，個股頁 `RiskSignalCard` 已寫入顯示高波動警示橘、緩和青綠、未驗證/過期灰與行情資料日+小字更新頻率；未經validated不可顯示XGB預測數值。Flutter User App獨立CI已PASS（[39699020525](https://github.com/tommylin15/janus-omniforge/actions/runs/39699020525)），仍待完整GHCR Release與四Jobs rollout、API/實機資料讀回、夜批自然執行與retention/完整promotion；深度股票union分批、同Controller接線，不另建cron。A-CHANGE負責使用者事實報告，D07負責模型評估。詳見[Risk手冊](spec/risk-model-training-retraining-runbook.md)、[模型卡](spec/risk-model-card.md)。

完整開發/發布/回收契約見[模型生命週期](spec/model-lifecycle.md)及[AI卡](execution-cards/d07-model-lifecycle.md)。本輪為DOC_UPDATED，未上傳模型或啟用新排程。

模型選型/X/Y/產出唯一見[五分析師](spec/specialist-engines.md)；[D07 唯一任務卡](execution-cards/d07-specialist-b9-oos.md)。Risk沿用既有XGBoost8候選及Rolling20/Ridge比較，其他三角色採XGBoost challenger並按資料與獨立期數判定，不為湊齊五模型而發布。

- [ ] **D07-THREE-XGB-CHATGPT-PILOT（Quant／Fundamental／Valuation）**：Drive 已有三份 `.ipynb`，改在 ChatGPT 可用研究/Python 環境逐角色真實試訓（Colab 非必需），固定 CURRENT Parquet release/manifest/hash、不重抓資料；按角色完成成熟 Y、PIT/來源/公司行動、OOS/baseline、UBJ與train/serving parity、GCS candidate/readback、shadow/CI/受控發布相容證據。Notebook 存在或 training_ready 不等於已訓練/可部署，失敗按實際標示；**不重訓、不提前改 Risk v1**。
- [ ] **D07-CROSS-JOB-MODEL-CACHE（四模型統一效能整合）**：**必須等上述三模型全都達 DEPLOYABLE**，再一次與 Risk v1 整合共用 loader/版本快取；GCS immutable model 為權威，既有 Cloud Run Mart Job 內每角色載入一次。跨 Job execution 不共享 RAM，先實測 GCS+每次單次載入 vs 版本固定 image layer 等零新服務方案；驗 hash/cache invalidation/效能/GCS IO/回滾/Owner與真實 dev 日批，無明顯效益維持原案；不得加新付費常駐服務。唯一規格 [模型生命週期](spec/model-lifecycle.md)／[D07 AI 卡](execution-cards/d07-model-lifecycle.md)。

## 5. D08｜CEO／Admin／Owner 報告

- [ ] **正式整合與驗收**：具來源的有效 Fact Pack → Owner 手動 request → 現有 OmniGateway／Gemini → validator → immutable GCS／PG → Owner history／UI 與 Admin 設定／權限／回滾 readback；LLM 不決定 canonical 數字或最終 publication。

[D08 唯一任務卡](execution-cards/d08-ceo-admin-owner-report.md)。正式報告依賴 D07 有效模型輸出，但**已結案的 FINOPS-AB／D06／舊 B5～B8 不得成為重新施工的前置條件**。

## 6. 已結案、不再列待辦

D01～D05、DRL-01、FINOPS-AB（含 D06）、既定背景持股／關注股補收、Admin v2、舊研究 GCP 工作及排程退役、BigQuery 舊 ML/OOS 中介資源清理，均依已核准的原驗收邊界 **CLOSED／PASS 或 USER_ACCEPTED**。收據保留在 [結案索引](wbs/completed-index.md)／[Operations](spec/operations-and-testing.md)／[archive](archive/d07-gcp-bq-retirement-live-2026-10-20.md)，**不因未列舉所有理論可能性新增待辦**。新缺陷須有實際證據，再依當次工作包處理。

