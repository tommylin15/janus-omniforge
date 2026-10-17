# Janus — 唯一開發待辦

更新：2026-10-16。只保存尚未完成的交付與驗收；真實終態證據見 [status](status.md) 與 [operations](spec/operations-and-testing.md)。

## 執行範圍

**2026-10-17 本對話最新分工：DRL-01 由另一個 AI 持續執行；本對話優先整合 D01～D05，先集中完成相依工程，再合併驗收與受控發布。** 保留各工項獨立 acceptance、既有真人 PASS 與安全限制；不重送 DRL-01 修復、不以其新增歷史資料需求擴大本輪 D05 gate。共用 main／runtime 發布前須核對最新來源與執行中工作，避免覆蓋另一個 AI 的變更或競爭部署。

**2026-10-16 使用者已授權 D01～D05 全部連續工程與實際驗收，D04 包含既有替代路徑與最小 IAM 授權試行；先前只限 API 切流的暫停命令已失效。** 持股畫面、現金交易連動、重算按鈕三項真人正向 PASS，不重做。新完整 GHCR Release [#38889743874](https://github.com/tommylin15/janus-omniforge/actions/runs/38889743874) Python 1322 passed、Flutter PASS、四映像/digest PASS，但尚未新版實際 dev 部署。D02 [快照→API #38890365233](https://github.com/tommylin15/janus-omniforge/actions/runs/38890365233) PASS；D03 [正式圖表 API #38889906057](https://github.com/tommylin15/janus-omniforge/actions/runs/38889906057) 16/18 available、2 EPS missing。D04 [現有 GCS 備份隔離還原 #38889312080](https://github.com/tommylin15/janus-omniforge/actions/runs/38889312080) PASS；但 VM IAP policy get、SSH 目前均拒絕，沒有 IAM 變更，不能停止舊 timer 或假稱新 executor 已交接。所有工作包依其獨立 gate 判斷，**不以 CI/備份還原當整體完成**。

A 組及 B0～B8 已結案的範圍不重開；有實質變更才回歸受影響路徑。全市場 Bootstrap／同日 Cached、費稅88筆更正、00719B 身分／估值既有成功證據不重送。研究範圍採各歷史日期全上市櫃；50 關注 quota 仍保留。

以下 `D01～D08` 是本次文件工作包代碼，不取代既有 WBS ID。新增設計補強見 [契約](spec/system-development-contract.md)，不是已實作聲明。

D01～D08 各有一張獨立可供 AI 執行的 [標準任務卡](execution-cards/README.md)；操作程序不代替本 TODO 唯一狀態與當次授權。

| 工作包 | 狀態／次序 | 既有 WBS 責任 | 依賴與退出條件 |
|---|---|---|---|
| [D01 持股交易／完整估值](execution-cards/d01-holdings-trading-valuation.md) | **PASS**；產品第1項 | WBS 4J／6 | 新版正式商品報價、共用費稅與試算、交易版本／冪等、完整估值及 Owner 重算 E2E |
| [D02 快照／首屏](execution-cards/d02-full-market-snapshot-performance.md) | PARTIAL；產品第2項 | WBS 3／6 | D01資料契約；首頁與持股 snapshot 真實生成／readback、冷暖效能 |
| [D03 圖表／四頁](execution-cards/d03-four-page-charts-visual.md) | PARTIAL；產品第3項 | WBS-6-USER-FINAL-VISUAL-CONVERGENCE 非 AI 範圍 | D01／D02；VF-00～08、真實資料／四頁截圖、可及性 |
| [D04 總控／備份交接](execution-cards/d04-controller-backup-handoff.md) | **PASS**（清理整合完成；VM timer 保留） | WBS 3／7 | 無重複排程、同源總控；備份清理移至 Batch Controller |
| [D05 產品集中發布](execution-cards/d05-integrated-release-dev.md) | PARTIAL；第5項 | WBS 8／CI-CD | D01～04適用條件通過；完整SHA release、candidate、自動auth、Jobs fence、Preview、功能證據、正式dev切流讀回 |
| [D06 Iceberg／I/O](execution-cards/d06-iceberg-retention-io.md) | PARTIAL；獨立已授權 | WBS 7／retention | 既有 Jobs／cleanup 終態、完整引用保護、真實 objects／bytes／等量 I/O 驗收 |
| [D07 五角色資料與品質](execution-cards/d07-specialist-b9-oos.md) | 後置；產品交付後 | WBS-5-MART-SPECIALIST-ENGINES／RERUN-CACHE（B9） | 全市場歷史母體、逐角色 baseline／OOS；B7 PASS 不代替B9 |
| [D08 CEO／Admin／報告](execution-cards/d08-ceo-admin-owner-report.md) | 後置；有效角色後 | WBS-5-MART-AI-PROVIDERS／CIO-SYNTHESIS、WBS-6-ADMIN-ANALYSIS-PROFILE、User AI整合 | P0-V技術已PASS；真實 Fact Pack／capability／immutable report／Owner history另驗 |

## DRL-01｜新版功能資料可用性修復（目前最高優先；IN_PROGRESS）

**AI入口：**[總指令第7節](codex-execution-plan.md)；消費端[D02卡](execution-cards/d02-full-market-snapshot-performance.md)／[D03卡](execution-cards/d03-four-page-charts-visual.md)，長相見[A第5節](ui/visual-first-four-pages.md)。只補同一條資料→分析→UI鏈，不另照Drive重建。

**2026-10-16 最新優先決策：**使用者已明確要求「先優先完成 DRL-01」，因此解除本工項的暫停，優先於 D01～D05 推進；D01～D05 既有授權及已驗證結果保留，不因本次變更重做。資料→計算→畫面的一體交付與品質放寬依 [三層對照](ui/visual-first-delivery.md)；沿用本DRL-01與D02/D03/D07/D08，不新增平行工作包。

- **整併責任：**DRL-01A→價量／RS與風險；B→營收金額／YoY；C→已知口徑EPS／可比TTM；D→後置估值河流。D03/VF-05/07共用資料接圖與事實短句，D02共用serving／效能，D07驗預測效果，D08接有效報告。新增研究因子字典不代表全數納入首版。
- **首版交付：**每項同時記資料讀回、計算口徑、UI呈現及降級；短期先畫短期、一期先顯單值、同比不足仍顯營收、累計EPS明標累計、延遲報價顯參考。精確歷史發布時點未知不阻擋一般顯示；不造數字、不混期間、不放寬owner／金額正確性。整批coverage維持10%／30%，未過門檻不阻擋已有合法單股值顯示。
- **不重工：**既有資料、公式、typed API與圖表先重用；同份數值證據覆蓋DRL-01與D03，UI另補視覺證據。既有真人PASS不重開；此新增切片不反向加進當前D05必過條件。

- **負責：** WBS 3 Ingestion／Core、WBS 5 Mart、WBS 8 QA／dev 驗收；直接服務新版首頁雷達、個股 KD／ATR、營收 YoY、EPS 獲利與情境。Drive 總帳僅存需求與證據，不作第二套正式資料庫。
- [ ] **DRL-01A P0 OHLCV 歷史窗口：** 重用既有核准 TWSE MI_INDEX／STOCK_DAY、TPEx dailyQuotes 來源與 Stage→Iceberg。先全市場≥20/21個有效交易日，再持股／關注股≥120日；分日/市場/片執行、冪等去重與日曆/失敗重試，避免全市場五年盲抓。分市場最低有效覆蓋上市≥90%、上櫃≥70%，公開功能讀回。
- [ ] **DRL-01B P0 月營收 fiscal_month：** 官方當月及上月財務紀錄保留 fiscal_month、fiscal_period_end、period_basis；既有4,011筆營收中3,947筆缺月份，先利用已存在可靠期間欄位與舊來源修復，保留值／provenance，無法確認月份則PENDING。完整13月同月YoY與數據驗收。
- [ ] **DRL-01C P1 EPS 本年度先行上線（2026-10-17 核准縮小gate）：** 首版對六檔目前上市持股／關注股要求 **2026Q1與2026Q2** 真正合格的官方單季EPS（Q1 YTD視為Q1；Q2必須官方明示單季或可核實分子／股數），第三季僅已發布才納入，第四季未到期不要求。每股原來源、單位、季度、provenance、receipt及published serving/API/UI需可稽核；未達仍PARTIAL，不能用累計EPS差分或推估股數。**2025及更早四連季、同比、TTM門檻此次標為`WAIVED_FOR_MVP`，不是資料品質PASS或認證的歷史TTM**；既有`eps_4_comparable`保留實際量測與缺值；單一合法EPS也要可在個股頁顯示且標清期間。首版有用先上線，後續年度歷史只針對需要者補，不新增供應商／工作包。
- [ ] **DRL-01D 後置，五年PE/PB河流：** 只定向持股／關注股補五年，不做全市場5年無需求回補；真達五年跨度再顯歷史分位，否則PENDING但短期PE/PB照常顯示。
- [ ] **定期 Data Readiness Ledger：** 只使用現有Controller排程，日增量聚合、週詳細稽核；核對固定Core snapshot、資料筆數、分市場有效母體、期數、缺漏與持續增量水位。Drive只保留管理摘要。
- **2026-10-17 使用者限定 DRL-01 前三項（完成可驗證部分後停止，不延伸 Ledger／UI／五年河流）：**
  - **① 月營收：PASS。** 2025-09～2026-09 13個指定月，獨立同檔 Core 實機 [#38997408284](https://github.com/tommylin15/janus-omniforge/actions/runs/38997408284)：TWSE **1,077／1,096（98.27%）**、TPEx **864／896（96.43%）**，均超過90%／70%門檻；TPEx最後2026-07～08官方Stage/Core收據[#38990411743](https://github.com/tommylin15/janus-omniforge/actions/runs/38990411743) PASS。舊「上櫃缺8個月」checkpoint已作廢。2025原公告日未知不倒填為PIT；營收UI／serving另循D03獨立驗收，不重開工作包。
  - **② 已核准持股／關注股120日價量：TWSE 六檔 PASS；兩檔TPEx債券ETF另驗。** 官方 Core [#38997792145](https://github.com/tommylin15/janus-omniforge/actions/runs/38997792145) `1513,2327,2382,3231,3711,5876` 各有**135個有效交易日（6／6）**，已有資料故0新增寫入。債券ETF `00697B,00719B` 不在四碼股票market master／一般batch；官方TPEx dailyQuotes來源與完整OHLCV欄位在read-only [#38998425476](https://github.com/tommylin15/janus-omniforge/actions/runs/38998425476) 二檔source PASS；獨立ETF歷史Stage/Core修復[#38998709152](https://github.com/tommylin15/janus-omniforge/actions/runs/38998709152) 依最終120日讀回判定，**不得把兩檔ETF未驗結果算在6／6或上市櫃股票分母內**。全市場20/21另已讀回TWSE1073／1096、TPEx799／896，[#38988025097](https://github.com/tommylin15/janus-omniforge/actions/runs/38988025097)。
  - **③ 官方4連季EPS：PARTIAL（嚴格驗收不冒稱成功）。** 既有`fundamental-history`補收[#38998082208](https://github.com/tommylin15/janus-omniforge/actions/runs/38998082208) 首段成功，另一次獨立Core snapshot `1036734792492319715` 驗收：1513、2382各**9個分散單季／2025Q4缺／無4個連續季度**，故CI依實際合格閘門保持FAIL。六檔Q3/Q4原始官方MOPS XBRL read-only [#38998787882](https://github.com/tommylin15/janus-omniforge/actions/runs/38998787882) 已可讀基本EPS與歸母盈餘，但**六檔皆缺可證明的加權平均股數分母**（source_failures=0）；不能用累計EPS直接相減或推估股數填單季。優先尋得同一官方版本可核實的單季EPS或分子／分母再定向修復；未符合期間仍null且`PARTIAL`。
  - **技術範圍：**本輪僅針對以上三項的官方來源、Stage/Core、合法季度規則與驗收，無Owner交易／現金／行情成本變更，也不新增市場股票分母、第三方供應商、排程或付費資源；CI／Job執行器成功不等同第四季公式成功。
  - **執行界線：**不接續第四項定期Ledger實機、第五項UI端到端、五年PE/PB或其它D01～D08工程；缺證據的範圍維持PARTIAL或BLOCKED，不能因本次工作重標完成。
  - **2026-10-17 最新執行決策及實際補收：**② ETF歷史 [#38998709152](https://github.com/tommylin15/janus-omniforge/actions/runs/38998709152) 已`SUCCESS`且Cloud Run `janus-ingestion-core-prxnx` Core snapshot `4874890923938554002`兩檔`00697B,00719B`各**125個可證明官方有效行情日（2／2 PASS）**；連同原六檔各135日，**指定8／8檔的120日門檻PASS**，不包含ETF在股票市場分母。③新2026年核准MVP Gate首輪唯讀Core [#39000160070](https://github.com/tommylin15/janus-omniforge/actions/runs/39000160070)：首輪**4／6**（1513、2327、2382、5876），3231、3711已由MOPS補收；獨立 Core 再驗[#39000368842](https://github.com/tommylin15/janus-omniforge/actions/runs/39000368842) **2026Q1／Q2 六檔全部6／6 PASS_CURRENT_YEAR**（Core snapshot `5736520631016782502`）；歷史四連季依然0／6，不屬MVP上線必過門檻。舊2025Q4、四連季和TTM不再阻擋2026Q1/Q2首版，但仍為**NOT_CERTIFIED／WAIVED_FOR_MVP**，沒有轉成事實PASS。
- **結案條件：**現有GitHub實作＋targeted／整體CI，來源授權與Core逐月snapshot、上市10%／上櫃30%門檻，持股／關注120日，官方EPS合理口徑，真實13月YoY，最新同源GHCR受控Jobs部署、serving／Admin／手機／桌面讀回、自然排程及增量重跑。缺值可顯示、單項可獨立PASS；**DRL-01整體必須保留PARTIAL直到上述適用關卡有真實證據**。不新增平行待辦、付費來源或排程，不操作Owner資料。

## D01｜持股交易與正式損益

- [x] **P0 Owner 2026-10-14 backend 全持股估值／總未實現損益**：TPEx dailyQuotes、migration 061、SHA 285848 Release／API 0%／OAuth／四 Jobs rollout PASS；00697B + 00719B 同日官方資料已持久化。MCP readonly 8/8 市價、市值可用，Private Mart readonly #38732675488 驗 8/8 未實現 PnL、單一總計 aggregate_status=available、missing=0、affected=0、總市值／總 PnL／報酬非空，ledger v354 未變；最終 gate #38733406224 PASS。原 #38730741579 FAILED 是舊 schema 缺 `stale_price_count` 使驗收腳本誤判，修正後不再次重算、不編造欄位。後續新日期、UI、交易按鈕／queue、正式 App 屬 P1。
- [x] **現金交易連動真人正向驗收**：使用者 2026-10-16 回報「現金交易連動驗收完成」，記為 `USER_CONFIRMED_PASS`（8eb 正式 dev）。owner-scoped cash／migration 062 工程與正式部署原證據維持；本次沒有測試新增交易，也沒有新的逐筆資料或金額收據。
- [x] **現金進階一致性／失敗場景**：D01 進階場景測試 25 tests 全部 PASS（local 2026-10-17）。包含股利處理（4 tests）、REVERSAL（4 tests）、更正交易（4 tests）、競態/冪等（4 tests）、Owner 隔離（4 tests）、邊界案例（5 tests）。工程入口：`services/api/trade_calculation.py`、`services/api/trade_fees.py`、`services/api/private_recalc_queue.py`、`tests/test_d01_advanced_scenarios.py`。
- [x] backend 唯讀試算及正式保存共用 MOVING_AVERAGE／Decimal／商品費稅，券商折扣與規則快照可追溯；表單自動費稅／一字搜尋及ETF／Enter／競態拒絕均有新版驗收。
- [x] 買入、加減碼、部分／全部賣出、零股、股利、更正、作廢、歷史補登、超額賣出拒絕、未知保存結果與冪等；不同 owner／ledger／broker version 不混用。既有費稅 apply 不重送。
- [x] **重新計算損益按鈕真人正向驗收**：使用者 2026-10-16 已明確回報驗收完成（`USER_CONFIRMED_PASS`）。後端雙 Worker 佇列 #38828798196 的 synthetic 技術驗收另有 PASS；不聲稱這次回報附有 enqueue／Worker terminal／checkpoint 的新 run ID。
- [ ] **重算操作稽核與異常路徑（獨立）**：如後續需要，補齊本人實際點擊 request ID→Worker terminal→同 ledger checkpoint／UI PnL 的可查收據，以及失敗／重送／timeout 狀態及冷暖等待時間；沒有資料就維持 NOT_VERIFIED，不重跑真人正向驗收。
- [ ] operational股數／成本／該筆損益可即時呈現；行情更新、帳本保存、正式報表重算互不阻塞。首次完整估值不以市場10%／30%容忍代替。

## D02｜全市場、快照與效能

**AI入口：**[D02卡](execution-cards/d02-full-market-snapshot-performance.md)／[總指令路由](codex-execution-plan.md)。首頁增補沿此工項共用snapshot，版型見[A第5節](ui/visual-first-four-pages.md)。

- [ ] 完成全市場跨搜尋／關注／screening／研究入口的剩餘驗收；固定官方當日分母、TWSE≤10%／TPEx≤30%逐資料集判定；舊500 artifacts不重標全市場。
- [ ] 首頁快照批次caller、migration057初始補建、serializer、freshness／版本與持股DB-first snapshot真實readback；無N+1／首屏Iceberg掃描。
- [ ] 暖首屏P95≤2秒、冷主資訊P95≤5秒、暖試算≤500ms、保存至新版股數／成本可見≤2秒；每暖情境≥30樣本，冷樣本不足明示，timeout計入失敗。端到端與API分開。
  - 最新 9f690 固定 Preview 公開 market-home 暖路徑 #38853879877：30/30、P50 48.11ms、P95 57.70ms，**只算 public API 子項 PASS**；authenticated holdings snapshot／recalc／手機視覺效能仍未驗，不得外推。


## D03｜四頁與通用圖表

**AI入口：**[D03卡](execution-cards/d03-four-page-charts-visual.md) → [A具體版面第5節](ui/visual-first-four-pages.md) → [B三層交付](ui/visual-first-delivery.md)。不得只讀工項名稱自由設計。

- [ ] **D03後續增補（等DRL-01恢復，不擴當前D05 gate）**：首頁資產短摘要／三則事實異動／TAIEX；個股三行事實→對應圖表、單一主圖、支持疑點、既有筆記延續。沿VF-02/05/06/07與D02，不新建工作包；手機／桌面位置、尺寸、字級、按鈕與狀態依A第5節，資料依DRL-01，模型依D07。已存在部分只補差距。

- [ ] VF-00～01：source→Core→serving→API→UI coverage matrix，財報期別／available-at、事件時間、typed owner read path。
- [ ] VF-02～06：今日個人相關異動／TAIEX fallback、關注價格與異動、持股單一市值Hero及同時點貢獻、個股短價量與圖表捷徑；模型未驗證不占主畫面。
- [ ] VF-07～08：官方營收／單季EPS／PE-PB／法人／事件及可比Private Mart歷史趨勢；六類資料逐類驗收，不以全missing或假線結案。
- [ ] 390×844與desktop authenticated截圖、文字放大／鍵盤／讀屏、loading／empty／gap／stale／partial、當日行情與累計損益分列；新語意見系統補強契約。

VF-10高階同業／估值河流／還原價仍屬有條件後續構想，不是本次產品必過gate。

## D04｜總控與備份

- [x] Cloud Scheduler總控唯一業務排程；Actions只保留既有備份清理schedule。研究前瞻留存、dirty owner、snapshot／dispatch lag／重試冪等真實驗收。
- [x] D04：備份清理已從 GitHub Actions 移至 Batch Controller（`ledger_backup.py` cleanup_old_backups()），保留政策 7 天（至少保留 3 個）。GitHub Actions `private-ledger-backup-retention.yml` 已停用排程。VM timer `janus-ledger-backup-executor.timer` 已恢復啟用（ENABLED）。新增 4 個清理邏輯單元測試。

## D05｜整合發布

- [x] **P1 8eb API 正式可逆 100% 切流及獨立讀回**：同源完整 Release #38856837257、0% #38857279864、auto OAuth #38857441171、Preview #38857524000、四 Jobs #38857643226 PASS；[正式可逆 promotion #38865075071](https://github.com/tommylin15/janus-omniforge/actions/runs/38865075071) PASS、[獨立 live readback #38865347217](https://github.com/tommylin15/janus-omniforge/actions/runs/38865347217) PASS；唯一 canonical 100% revision `janus-api-00517-ciq`、完整 build SHA、Preview、健康及負向 Owner/cash auth、immutable image/tags 全部確認，9f690 revision `janus-api-00512-zal` 保留回滾。此項僅 API 發布驗收，不表示使用者功能 E2E PASS。
- [x] **真人持股畫面正向驗收**：使用者 2026-10-16 明確回報「真人持股畫面驗收完成」，以 `USER_CONFIRMED_PASS` 接受新版持股畫面的基本真人操作流程；與 8eb 發布 #38865075071、獨立 runtime #38865347217 的技術驗收分開存證。
- [ ] **持股視覺特殊場景與效能（獨立）**：真缺價小計／涵蓋檔數、延遲與跨日參考市值、手機 390px／桌面 authenticated 截圖、文字可及性及 P95 均需其各自受控證據；使用者人工正向確認不等於這些量測完成。舊截圖推算 TWD 15,210,800、約 1,702.2 萬元屬歷史估算，不是現時合格值。
- [ ] **P1 尚需的獨立工程驗收**：新版 8eb 已在正式 App 100% 發布並獨立讀回 PASS；使用者 2026-10-16 確認持股畫面、現金交易連動、重算按鈕三項真人正向 **USER_CONFIRMED_PASS**，不再重列未操作。餘下只保留確有要求的特殊缺價／stale／partial 呈現、trade/owner/refund/reversal 安全與冪等、回溯到 ledger／Worker terminal 的機器可稽核證據、390px/desktop 截圖與冷暖 P95、10/16 夜批 Private Mart 最新 EOD／PIT readback；缺證據維持各自 PARTIAL／NOT_VERIFIED，**不得反向推翻已完成的基本人工驗收**。
- [ ] 無需每版人工OAuth登入；自動auth與owner隔離仍驗。metadata／401不代表正向PnL或UI PASS。不要以舊來源的API／Jobs證據交叉替代。

## D06｜Iceberg、引用及I/O

- [x] 真實縮減 Core 小檔：基線 8,343 objects／194,161,764 bytes、其中 <1 MiB 8,336；CI orphan 清理 [#38879585601](https://github.com/tommylin15/janus-omniforge/actions/runs/38879585601) **PASS**，實刪 477 objects / 2,039,377 bytes，剩餘 7,866 objects / 192,122,387 bytes / 7,859 小檔。
- [x] **停用稽核鏡像 Jobs Rollout**：來源 `740e54c2` 完整 Release [#38873919415](https://github.com/tommylin15/janus-omniforge/actions/runs/38873919415)、0% [#38874649205](https://github.com/tommylin15/janus-omniforge/actions/runs/38874649205)、OAuth [#38875256474](https://github.com/tommylin15/janus-omniforge/actions/runs/38875256474) 均 SUCCESS；Jobs rollout [#38875865395](https://github.com/tommylin15/janus-omniforge/actions/runs/38875865395) **PASS**（8/8 canaries）。
- [x] **Runtime 驗證 `iceberg_audit_disabled=true`**：[#38881471078](https://github.com/tommylin15/janus-omniforge/actions/runs/38881471078) **PASS**；14 天 1,208 events、原四時段估 51 個非空批次、預期避免 102 次 logical table scans、`estimated_batch_reduction_percent: 100.0`。
- [x] 已完成 GCS JSON 引用掃描（62 Core、71 Mart、96 Research、495 Private，無略過）；PG publication 讀取 138 rows（core_snapshot_id column privilege 仍 BLOCKED）。
- [ ] 等量時間窗 I/O 量測：停用生效後需用相同日期股票數、負載、時間窗比較 ReadObject/GetObjectMetadata，未量測不報節省百分比。詳見 [D06證據](archive/d06-finops-2026-10-16.md)。

## D07｜五角色及模型品質

- [ ] 前瞻留存membership／公告版本／publication／first-observed；全市場歷史研究保留退出股票，不用今天名冊回填。無法重建區間標blocked_source_history。
- [ ] VF-09角色狀態視覺化、五角色structured artifacts／繁中規則說明、missing／provenance／隔離、dirty/reuse與真實artifact/API讀回；正常0 LLM token。可靠baseline與ML品質分開。
- [ ] Quant→Risk優先；基本面／估值先修資料，Event先合法training-use及真實人審標籤。預登記時間切分、成熟標籤／purge、baseline、成本情境、主要指標與不確定性；逐角色升級，無優勢維持baseline。
- [ ] 明確分離財報strict_pit=false研究比較與嚴格PIT publication；核對舊B9診斷硬編碼blockers，不能刪掉guard或把歷史診斷當永久無法研究。
- [ ] 月度成熟資料skip/reuse、model/evaluation版本／回復／漂移；specialist變更只標CEO stale，不自動呼叫LLM。

## D08｜CEO及分析產品

- [ ] 接續既有OmniGatewayGeminiProvider與已通過P0-V技術鏈，不重建串接；部署前核對Janus實際endpoint／audience／allowlisted model。上游專案成功不代表Janus已切正式route。
- [ ] Admin模型／profile／evaluation／immutable history／rollback／capability、provider health／quota／cooldown／usage及安全audit；核對052與每日50／300秒實際readback。
- [ ] 真實有效五角色Fact Pack→新手動request→Gateway→Gemini→完整validator→immutable GCS／PG→authenticated Owner history；timeout／cancel／未知終態不得盲重送或擅自fallback。
- [ ] CEO只解釋validated numbers，無canonical／publication決策權；thesis／衝突／情境／失效條件／unknowns有來源。User顯示freshness、歷史及permission-aware操作，五角色有效後才整合報告。

## 完成與歷史

每項交付列implementation、tests／CI、deployment、migration、workload／business readback及剩餘gap。沒有適用證據維持PARTIAL／NOT VERIFIED。
原重複工作、舊授權及收據完整保存於 [整編前TODO](archive/documentation-baseline-2026-10-15-todo.md)；歷史不再形成另一份執行佇列。未排程構想統一見 [Parking Lot](parking-lot.md)。
