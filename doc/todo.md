# Janus — 唯一 Active TODO

更新：2026-10-21。**只列尚未完成的工作與原定驗收，不收納歷史失敗、已結案工程、無具體異常的推測性追查。** 狀態以 GitHub `main`／真實 CI、deployment 與 runtime 為準；結案遵循 [PROJECT_RULES §1.1.1](PROJECT_RULES.md)。

## 1. 現行優先順序

方案A已核准；2026-10-21 使用者啟動 A1～A4 整包實作、一次集中驗收，目前工程進行中，尚未結案。後續產品順序 A-CHANGE → D07-PRE → D07 → D08；D07-PRE現有採集可獨立續作，STAGE-48H仍由原對話收尾，不阻擋方案A或研究。

| 優先 | 工作包 | 已完成 | 尚需完成 |
|---|---|---|---|
| **P0** | **STAGE-48H** | 48h Stage 清理與自然排程 PASS；**新版 Admin MB／千分位已在正式 dev API 100% 發布**，且回滾演練 PASS | **僅餘新版登入 Admin 六桶全數 `OBSERVED` 與合計容量實機驗收** |
| **P1** | **A-CHANGE｜事實解讀與站內盤前盤後** | 方案、X/Y/時間契約與AI卡已定版；A1～A4 已啟動整合實作 | **集中 targeted/CI、既有 dev 發布與真實 API/UI 驗收；完成前維持 IN_PROGRESS** |
| **P1** | **D07-PRE｜Colab／Drive 資料源** | 21 個月 r1 原始行情研究准入 PASS；Drive v3.1 `CURRENT.json` + 153 個 Parquet 月分區讀回、**格式整併 CLOSED**；v3.5 長期增量／TPEx 空日解析／完整安裝格已上傳原 Drive Notebook ID，原始官方回應＋跨年度本地 15/15 PASS，讀回 SHA256 一致；舊研究 GAS/GCP/BQ 退役 | **官方／第三方補收 PARTIAL：2026-10-22 Colab 官方 264 批最新報告僅剩 TPEx 估值 7 個未達標月（2024-10、2025-01～05、2026-02），v3.5 尚待 Colab 重新執行與品質報告／Parquet 讀回**；Risk 可試訓不等於模型 promotion，歷史 PIT／公司行動與授權／模型發布仍屬 D07 gate |
| **P2** | **D07｜五分析師建模** | **已選 XGBoost8 為 Risk 正式候選**；本地封存模型及99檔SHA/74,487行OOS重新載入一致；GitHub/Drive重訓手冊及模型卡已建立；個股 Risk 訊號 UI 程式已接入 | **dev GCS candidate 已完成上傳、雙SHA與manifest讀回（#39701774716）；現有16:30 Controller→Mart Risk shadow接線、XGB CPU依賴及個股UI已提交／targeted CI PASS**；完整GHCR Release曾因非Risk測試／Flutter警告失敗，目前修復再驗收；**Cloud Run四Jobs第一版 rollout #39716949831 與修正版 #39736336587 都已 PASS；一次性真實 Risk shadow #39738317081 已開始執行，尚未取得成功預測列數／GCS 驗收**。ML正式仍受合法來源/PIT/公司行動/新前瞻OOS gate限制，現役 Risk deterministic，絕不把shadow包裝成user已上線 |
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
- [ ] **模型與研究評估**：Risk v0／v1 的原始普通股同樣本 OOS 已完成；八因子 v1 MAE 0.127537、對五因子 v0 0.133647 改善4.57%，但2026-08 v1 小幅退步，且四段皆為已檢視歷史非新 holdout；收據見 [Risk v1](archive/d07-risk-v1-ohlcv-oos-2026-10-22.md)。**剩餘** Colab 本人重跑/targeted/CI、可比較公司行動與PIT/授權、未使用期間驗證及 Quant／其餘角色各自 OOS；未達 gate 不上線。
- [ ] **Colab四角色獨立Notebook與資料量**：依已完成的四份開發文件／AI指令實作 [Quant](colab-models/01-quant-xgboost.md)、[Risk](colab-models/02-risk-xgboost.md)、[Fundamental](colab-models/03-fundamental-xgboost.md)、[Valuation](colab-models/04-valuation-xgboost.md) XGBoost Notebook；共用Python模組、各自獨立Run all，只讀CURRENT指定Parquet release。採集沿用00，不重抓；列清洗/as-of/X/Y/成熟標籤/OOS與實際原生期數。**本輪完成文件與AI指令，Notebook實作/使用者Colab訓練仍未完成；Event另議**。
- [ ] **XGBoost8 受控部署／每日 Risk 推論（使用者 2026-10-22 要求）**：已凍結研究 cycle `2026Q3-20261022`，本地 XGB UBJ SHA `36c77d0168a1d667223ab915c9b08fd2c1c6608f9f7db2fc046204e922854044`，99檔 hash 全 PASS，重新載入 MAE 0.129701336 一致；**已完成** GCS private Drive→dev Mart候選SHA讀回（Actions [39701774716](https://github.com/tommylin15/janus-omniforge/actions/runs/39701774716)）、99檔模型週期包已存Drive、Mart pinned-hash loader/8因子Core mapping/16:30既有批次shadow wiring/immutable risk-shadow GCS讀回程式（實機尚未PASS）、相關CI PASS；**已驗證並可沿用** 完整 GHCR Release [#39710294843](https://github.com/tommylin15/janus-omniforge/actions/runs/39710294843)（source `a3a3b306`，含 Risk 八因子/Core欄位/Controller shadow）、API 0% 候選 [#39710808920](https://github.com/tommylin15/janus-omniforge/actions/runs/39710808920)、安全邊界 [#39711001211](https://github.com/tommylin15/janus-omniforge/actions/runs/39711001211)、四Job readonly rollback baseline [#39702260947](https://github.com/tommylin15/janus-omniforge/actions/runs/39702260947)。**已完成** 既有四Job受控 rollout [#39716949831](https://github.com/tommylin15/janus-omniforge/actions/runs/39716949831) `completed/success`（`jobs-rollout` PASS 並保存 `ghcr-jobs-rollout-receipt`，無需重做）；**實際首輪失敗，已定向修正並重送**：手動 EOD [#39717807039](https://github.com/tommylin15/janus-omniforge/actions/runs/39717807039) `completed/failure`，GCP execution `janus-intelligence-mart-rnj4v` 在 `market_screening.py:253` 因**指定2026-10-21不等於最新Core快照資料日**而 `VALUEERROR` fail-closed；結構化 GCP error readback [#39719341597](https://github.com/tommylin15/janus-omniforge/actions/runs/39719341597) PASS。已補正式Core日期讀取（最新快照/age≤7/不得今日盤中）、單元測試、日期實際注入、依真實日期檢查GCS，**二輪驗收已讀回** [#39719792973](https://github.com/tommylin15/janus-omniforge/actions/runs/39719792973) `completed/failure`，但 Core 日期解析 5/5 測試 PASS、GCS 真實最新 Core **2026-10-22**；當時台灣尚未收盤，因此正確 fail-closed、**沒有新增 Mart execution**。已改為從不可變 Core 清單選取最近且已完成交易日之快照，SHA驗證後經現有 Mart `market-screening-acceptance` 操作一次性推論（不更新 Scheduler／正式模型）；**第三輪實機已查明** [#39720298156](https://github.com/tommylin15/janus-omniforge/actions/runs/39720298156) `completed/failure`，Core 2026-10-21 immutable SHA/PIT日期選擇均已通過；受限 traceback [#39733625497](https://github.com/tommylin15/janus-omniforge/actions/runs/39733625497) 證明 Risk `_eligible_price_rows` 因同一股票日期**重複 Core 行情版本** fail-closed。已改成僅相同OHLCV數值的重複行可去重、衝突版本隔離整檔股票、不補值不選猜測版本，新增回歸測試。完整GHCR Release [#39734125861](https://github.com/tommylin15/janus-omniforge/actions/runs/39734125861) PASS；四Job rollback baseline [#39734816957](https://github.com/tommylin15/janus-omniforge/actions/runs/39734816957) PASS；0% candidate [#39735939853](https://github.com/tommylin15/janus-omniforge/actions/runs/39735939853) PASS；source boundary [#39736188577](https://github.com/tommylin15/janus-omniforge/actions/runs/39736188577) PASS；**修正版四Job受控rollout** [#39736336587](https://github.com/tommylin15/janus-omniforge/actions/runs/39736336587) `completed/success`，`jobs-rollout` step PASS 並有 `ghcr-jobs-rollout-receipt` artifact；正式 dev 四支 Job 更新已完成，這不代表 XGB 正式 promotion。 **2026-10-22 本輪接續**：已把 `.github/workflows/risk-v1-manual-shadow-once.yml` 鎖定到修正版 release `c4799bc9`／Release #39734125861、rollout head `5a2107ec`／#39736336587，並以 `ops/risk-v1-manual-shadow-request.json` 觸發 [真實一次性 shadow 驗收 #39738317081](https://github.com/tommylin15/janus-omniforge/actions/runs/39738317081)；新 workflow/request 讀回一致，對應 CI [#39738316901](https://github.com/tommylin15/janus-omniforge/actions/runs/39738316901) PASS。該次驗收已由 `PENDING` 轉為 `IN_PROGRESS`（已進入真實 Mart one-shot execution），仍非 Mart 成功收據；會 fail closed，不能視為模型 ACTIVE。正式 promotion 還須新前瞻20交易日成熟 outcome、官方公司行動／歷史 PIT、來源權利及 Registry CAS／API UI 讀回；在真實 PASS 前不得改 publication_allowed。一次GitHub部署lease ref讀回競態已定向修復並經獨立實機復原 [#39735578726](https://github.com/tommylin15/janus-omniforge/actions/runs/39735578726) PASS，未改API流量。**尚缺** 修正版rollout終態、手動Job SUCCESS、GCS 實際有效股票數／資料日期及已核 shadow 收據、正式Core官方市場日曆/公司行動/PIT/來源授權與未使用期驗證、API正式user模型promotion。**正式 runtime 現在仍是 deterministic-unpromoted-v1，不能報 ACTIVE。** 無法滿足promotion gate時先做shadow，確定性基準不切換。
- [ ] **Risk v2 討論（延後，僅待辦占位，不在 v1 範圍）**：v1 八因子僅個股OHLCV，**未納入官方大盤／Beta、產業指數或產業共振、拆股/減資/除權息正式價格調整**。公司行動缺口是 v1 promotion 的資料安全驗收，不得用 v2 延後決議替代 v1 必要的資料守門。依使用者指示：**先完成本輪 XGBoost v1 安全部署、日批與真實 UI 讀回後，才討論 v2 因子/資料架構**；不預先增加資料採集、重訓或付費服務。
- [ ] **Risk訊號及週期閉環**：已依使用者決定為「每交易日盤後推論、每週缺值健康、每月成熟label相對Rolling20評估、每季檢討重訓」，個股頁 `RiskSignalCard` 已寫入顯示高波動警示橘、緩和青綠、未驗證/過期灰與行情資料日+小字更新頻率；未經validated不可顯示XGB預測數值。Flutter User App獨立CI已PASS（[39699020525](https://github.com/tommylin15/janus-omniforge/actions/runs/39699020525)），仍待完整GHCR Release與四Jobs rollout、API/實機資料讀回、夜批自然執行與retention/完整promotion；深度股票union分批、同Controller接線，不另建cron。A-CHANGE負責使用者事實報告，D07負責模型評估。詳見[Risk手冊](spec/risk-model-training-retraining-runbook.md)、[模型卡](spec/risk-model-card.md)。

完整開發/發布/回收契約見[模型生命週期](spec/model-lifecycle.md)及[AI卡](execution-cards/d07-model-lifecycle.md)。本輪為DOC_UPDATED，未上傳模型或啟用新排程。

模型選型/X/Y/產出唯一見[五分析師](spec/specialist-engines.md)；[D07 唯一任務卡](execution-cards/d07-specialist-b9-oos.md)。Risk沿用既有XGBoost8候選及Rolling20/Ridge比較，其他三角色採XGBoost challenger並按資料與獨立期數判定，不為湊齊五模型而發布。

## 5. D08｜CEO／Admin／Owner 報告

- [ ] **正式整合與驗收**：具來源的有效 Fact Pack → Owner 手動 request → 現有 OmniGateway／Gemini → validator → immutable GCS／PG → Owner history／UI 與 Admin 設定／權限／回滾 readback；LLM 不決定 canonical 數字或最終 publication。

[D08 唯一任務卡](execution-cards/d08-ceo-admin-owner-report.md)。正式報告依賴 D07 有效模型輸出，但**已結案的 FINOPS-AB／D06／舊 B5～B8 不得成為重新施工的前置條件**。

## 6. 已結案、不再列待辦

D01～D05、DRL-01、FINOPS-AB（含 D06）、既定背景持股／關注股補收、Admin v2、舊研究 GCP 工作及排程退役、BigQuery 舊 ML/OOS 中介資源清理，均依已核准的原驗收邊界 **CLOSED／PASS 或 USER_ACCEPTED**。收據保留在 [結案索引](wbs/completed-index.md)／[Operations](spec/operations-and-testing.md)／[archive](archive/d07-gcp-bq-retirement-live-2026-10-20.md)，**不因未列舉所有理論可能性新增待辦**。新缺陷須有實際證據，再依當次工作包處理。

