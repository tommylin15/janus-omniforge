# Janus — 唯一開發待辦

更新：2026-10-18。只保存尚未完成的交付與驗收；真實終態證據見 [status](status.md) 與 [operations](spec/operations-and-testing.md)。

## 執行範圍

**2026-10-17 最新決策：D01～D05 全部 PASS／CLOSED（使用者核准寬鬆驗收）**。既有真人正向驗收、資料讀取、備份與正式發布證據已接受；其餘嚴格量測、獨立補驗及原 D03 後續增補均不再要求，不另留支線或後續待辦。缺少證據的部分記為 USER_ACCEPTED／WAIVED，不偽稱實測通過。結案依據、已接受限制及原始清單見 [結案紀錄](archive/d01-d05-relaxed-acceptance-closure-2026-10-17.md)。

**2026-10-18 最新範圍決策：D06 取消獨立收尾，將其剩餘引用保護／Retention／Orphan／Core・Mart Cleanup 整併 FINOPS-AB；D06 原兩天或長時間等量 I/O 量測由使用者取消，不作交付條件。FINOPS-AB（A 快速節流＋B Ingestion／Iceberg 原地優化＋D06 安全收尾）列最高優先，立即推進；DRL-01 仍由另一個 AI 在既有範圍並行，但共用 main／runtime 不得競爭部署。FINOPS-C（BigQuery 混合運算）必須排在 D07／D08 之前，**開始 C 工程前要重做完整架構／成本／資料一致性評估，正式回寫文件後才可決定 selective cutover**。既有 ADMIN-V2 正在進行，不因本次排列改動已授權範圍；不重開 D01～D05 及 D06 歷史 gate。唯一 AI 執行指令見 [FINOPS-AB／C 卡](execution-cards/finops-ingestion-iceberg-ab-and-c-gate.md)。

A 組及 B0～B8 已結案的範圍不重開；有實質變更才回歸受影響路徑。全市場 Bootstrap／同日 Cached、費稅88筆更正、00719B 身分／估值既有成功證據不重送。研究範圍採各歷史日期全上市櫃；50 關注 quota 仍保留。

以下 `D01～D08` 是本次文件工作包代碼，不取代既有 WBS ID。新增設計補強見 [契約](spec/system-development-contract.md)，不是已實作聲明。

D01～D05 已結案；D01～D08 各有一張供查閱的 [標準任務卡](execution-cards/README.md)；操作程序不代替本 TODO 唯一狀態與當次授權。

| 工作包 | 狀態／次序 | 既有 WBS 責任 | 依賴與退出條件 |
|---|---|---|---|
| [FINOPS-AB CPU／GCS I/O 優先優化](execution-cards/finops-ingestion-iceberg-ab-and-c-gate.md) | **P0／IN_PROGRESS（bounded reads／週批 guarded code／compaction no-op targeted CI PASS；dev Jobs/週批/成本與 D06 安全清理尚未驗收）** | WBS-3／WBS-7（A＋B） | A：每週維護鏈＋跳過無效工作；B：增量查詢、合併提交、dirty-partition；先確認現行 dev digest／成本基線，不新增付費服務 |
| [D06 Iceberg／I/O 歷史證據](execution-cards/d06-iceberg-retention-io.md) | **不再獨立排程；剩餘全部併 FINOPS-AB** | WBS-7／retention（於 AB 驗收） | 477 objects 清理／audit mirror 停用 PASS 沿用；兩天 I/O 比較 `CANCELLED_BY_USER`，不作另一次驗收 |
| [ADMIN-V2 Admin 四頁主要重構](decision-2026-10-17-admin-v2.md) | **IN_PROGRESS；2026-10-18 使用者授權 A1～A5（含 A4-U）工程與受控 dev 驗收**；既有核心契約穩定後，D07／D08 UI 接線之前 | WBS-6-ADMIN-OPERATIONAL-CONVERGENCE | 四頁重構＋總覽使用分析／單一使用者追蹤；影響與工程只在 ADMIN-V2，無 D01～D06 原 gate 變更 |
| [FINOPS-C BigQuery 混合運算](execution-cards/finops-ingestion-iceberg-ab-and-c-gate.md) | **PLANNED；A＋B 驗收後、D07／D08 前；開工前必須重新評估並回寫正式文件** | WBS-5／WBS-7（C） | 先 C-preflight：CPU/RAM、GCS、BQ 實際計費與 PIT/snapshot/cost/rollback、既有配額/IAM；通過後才逐項開發與切換 Screening／Ranking／OOS，未通過 DEFERRED/BLOCKED 並明示決策 |
| [D07 五角色資料與品質](execution-cards/d07-specialist-b9-oos.md) | 後置；FINOPS-C 開工前評估及其處置決議後 | WBS-5-MART-SPECIALIST-ENGINES／RERUN-CACHE（B9） | 全市場歷史母體、逐角色 baseline／OOS；B7 PASS 不代替B9 |
| [D08 CEO／Admin／報告](execution-cards/d08-ceo-admin-owner-report.md) | 後置；FINOPS-C 評估／處置決議及有效角色後 | WBS-5-MART-AI-PROVIDERS／CIO-SYNTHESIS、WBS-6-ADMIN-ANALYSIS-PROFILE、User AI整合 | P0-V技術已PASS；真實 Fact Pack／capability／immutable report／Owner history另驗 |

## FINOPS-AB｜先完成 A＋B，降低 Ingestion Core CPU／GCS I/O（P0；IN_PROGRESS／待 runtime 驗收）
**2026-10-18 FINOPS-AB＋D06 實作 checkpoint（PARTIAL，非結案）：**
- A1：以 `FINOPS_WEEKLY_MAINTENANCE` 守衛將 Compaction → Mart Cleanup → Core Cleanup 週六化；週六以 PG 成功 EOD 和 immutable Core 收據為來源。Worker 追加 GCS manifest digest／當前 catalog Snapshot 正反驗證（`3f1b499`／`0c48497`）。旗標**預設 false**，尚未在 dev 啟用。
- B1：Data Supplement 價量、指數、估值的有界日期／欄位 Iceberg scan 與回歸（`a692739`／`575da35`）；歷史財報合法版本不可因節流刪除。
- B2：financials 寫入重用已載入的 table，避免第二次 layout normalization；去重保留官方文件 hash、特徵版本與來源期間（`da5d3c5`／`de98223`）。完整 dataset/date coalesced commit 尚未完成，不能標 B2 全面 PASS。
- B3：Compaction 無候選分區時不做 Apply，不再掃描停用的 audit mirror；有候選時 Dry-run 計畫可在 Snapshot/metadata pointer 不變下供 Apply 重用，避免第二輪 metadata／manifest planning（`cce7630`、`5e52a10`、`1df26c3`）；僅保留單次 Job process CPU／wall timing，不作兩天比較。
- D06：Retention 沒有 catalog 變更或實際刪除時重用 GCS metadata 清單，避免二次 List（`513479b`／`aff09e0`）。原477 objects cleanup 與 audit mirror 停用沿用已通過收據；真正 Retention fence／受引用清理／PG `core_snapshot_id` 欄位授權仍 BLOCKED/PARTIAL，不可假稱已刪除。
- **已確認 CI：**同源 [Compaction CI #39093460437](https://github.com/tommylin15/janus-omniforge/actions/runs/39093460437) SUCCESS；[前一同源選擇性 CI #39093280201](https://github.com/tommylin15/janus-omniforge/actions/runs/39093280201) SUCCESS；最新 `1df26c3` 選擇性 CI [#39093460444](https://github.com/tommylin15/janus-omniforge/actions/runs/39093460444) 當次仍在執行，必須核對終態。
- **明確阻塞：**DRL-01 並行的 GHCR Jobs rollout [#39090724732](https://github.com/tommylin15/janus-omniforge/actions/runs/39090724732) 因原子 release lease ref HTTP403 而 FAIL，FinOps 不得繞過租約或與另一 AI 競爭發版；因此最新 FinOps 未部署 dev Jobs，未證 Scheduler 週化、live 成本/I/O 效益與 D06 清理。FINOPS-AB 仍 **IN_PROGRESS**，CPU -30%、Metadata I/O -50% 均只保留為目標，未量測不得報達標。原 D06 兩天／長時間量測 **CANCELLED_BY_USER**。

**AI 唯一指令入口：**[FINOPS-AB／C 工程執行卡](execution-cards/finops-ingestion-iceberg-ab-and-c-gate.md) §0–§3 → [Batch Controller Runbook](runbook-batch-controller-dev.md) → [WBS-7](wbs/wbs-7-security-finops.md)。這是整合後**唯一** FinOps active 工項；D06 尚未完成的保護、清理與 readback 歸本工項，已完成的歷史收據沿用不重跑。DRL-01 與 ADMIN-V2 由其他 AI 施工，不修改其專屬檔案／workload，部署鎖競爭則安全等待。

- [ ] **A1 週批＋相依修正：**原 `iceberg-compaction`、`mart-cleanup`、`core-cleanup` 仍在 main 的 `batch_controller.py` 使用每日 23:30 條件；改為每週六 23:30 同一 occurrence chain。週六非交易日要核對最近成功的 immutable EOD Core snapshot；跨日等待、no-work 正常終態、retry fence、unknown/failed、回滾均需測試，不能只加 `weekdays=(5,)`。每日 ingestion／DRL／Private 不減頻；工作必要時延期但不能重派。
- [ ] **A2 低成本跳過與量測：**依具證據的 source cursor、snapshot、dirty/revision 和保留水位，在派送前 skip no_change/no_work；分段記錄 07:30／08:30／14:30／週維護 CPU-seconds、GiB-seconds、elapsed、資料量及可歸因的 GCS operation，避免為判斷 no-work 又全掃倉庫。
- [ ] **B1 Data Supplement bounded reads：**`data_supplement._rows()` 以 date/period/column 規劃，減少無界歷史讀取；120 日價量、官方 EPS、月營收、兩年估值各保持真實合法 coverage 和 PIT／source provenance，不能用缺值補零。
- [ ] **B2 Iceberg Dirty Commit／B3 按需維護：**同一 dataset／日期的安全合併提交、no-op 不寫、新舊財報 version 保護、snapshot reuse；compaction 以 dirty-partition/fence 決定改寫，受保護 Snapshot/orphan/generation 與 rollback 保持。不得因效能優化刪 canonical、research 或 Private 事實。
- [ ] **D06-R1 完整引用保護整合：**在 AB 週維護鏈使用每次重新驗證的 `CORE_RETENTION_FENCE_URI`；核對 PG publication、Core、Mart/ML-OOS、Research、Private、外部引用和 immutable snapshot/generation。任何來源缺權限／過期／unknown fail closed（只可 audit-only）。沿用既有 62 Core／71 Mart／96 Research／495 Private JSON 掃描證據，不盲目重掃。
- [ ] **D06-R2 有界、安全、可回復的清理：**合併 Compaction → Mart Cleanup → Core Cleanup，分別記 dry-run/apply、7日 orphan/generation 防護、受引用 snapshot/execution manifest、回滾／rebuild 路徑與讀回；未授權大量不可逆刪除不執行。no-op 不建立 snapshot，保留真實 objects/bytes/small-file 證據；既有 477 objects 清理與 audit mirror 停用不重播。
- [ ] **AB＋D06 唯一發布與完整驗收：**targeted＋CI、immutable GHCR、受控 Jobs rollout、Controller/Scheduler、真實有界 workload 與 Market/Private/API/DRL 不退步驗收；短窗／同類工作 sample 可量 CPU/RAM/GCS read/write/objects。**原 D06 兩天／長時間等量 I/O 量測取消，不再執行或作硬 gate。** 30% CPU／50% metadata-I/O 僅改善目標，無可歸因數值保持 UNKNOWN，不臆測節省百分比。

## DRL-01｜新版功能資料可用性修復（與 FINOPS-AB 並行；IN_PROGRESS）

**2026-10-17 合併發布完成：**本年度2026 Q1／Q2 EPS與營收、兩項個股修正已於同一完整SHA `becb6a15496959c1f5d3d4985d7b523b652bd3ee` 完整Release→候選→自動auth→Preview→Jobs8／8canary→正式API100%全部PASS；切流前後公開資料讀回PASS，詳見 [證據](archive/combined-drl-stock-release-2026-10-17.md)。這條發布鏈不再是待辦；下方其它DRL-01適用驗收保留原範圍，不代表Ledger／五年河流或真人全量矩陣已通過，也不重開D01～D05豁免。

**AI入口：**[總指令第7節](codex-execution-plan.md)；消費端[D02卡](execution-cards/d02-full-market-snapshot-performance.md)／[D03卡](execution-cards/d03-four-page-charts-visual.md)，長相見[A第5節](ui/visual-first-four-pages.md)。只補同一條資料→分析→UI鏈，不另照Drive重建。

**2026-10-16 最新優先決策：**使用者已明確要求「先優先完成 DRL-01」，因此解除本工項的暫停，優先於 D01～D05 推進；D01～D05 既有授權及已驗證結果保留，不因本次變更重做。資料→計算→畫面的一體交付與品質放寬依 [三層對照](ui/visual-first-delivery.md)；沿用本DRL-01與D02/D03/D07/D08，不新增平行工作包。

- **整併責任：**DRL-01A→價量／RS與風險；B→營收金額／YoY；C→已知口徑EPS／可比TTM；D→後置估值河流。D03/VF-05/07共用資料接圖與事實短句，D02共用serving／效能，D07驗預測效果，D08接有效報告。新增研究因子字典不代表全數納入首版。
- **首版交付：**每項同時記資料讀回、計算口徑、UI呈現及降級；短期先畫短期、一期先顯單值、同比不足仍顯營收、累計EPS明標累計、延遲報價顯參考。精確歷史發布時點未知不阻擋一般顯示；不造數字、不混期間、不放寬owner／金額正確性。整批coverage維持10%／30%，未過門檻不阻擋已有合法單股值顯示。
- **不重工：**既有資料、公式、typed API與圖表先重用；同份數值證據覆蓋DRL-01與D03，UI另補視覺證據。既有真人PASS不重開；此新增切片不反向加進當前D05必過條件。

- **負責：** WBS 3 Ingestion／Core、WBS 5 Mart、WBS 8 QA／dev 驗收；直接服務新版首頁雷達、個股 KD／ATR、營收 YoY、EPS 獲利與情境。Drive 總帳僅存需求與證據，不作第二套正式資料庫。
- [ ] **DRL-01A P0 OHLCV 歷史窗口：** 重用既有核准 TWSE MI_INDEX／STOCK_DAY、TPEx dailyQuotes 來源與 Stage→Iceberg。先全市場≥20/21個有效交易日，再持股／關注股≥120日；分日/市場/片執行、冪等去重與日曆/失敗重試，避免全市場五年盲抓。分市場最低有效覆蓋上市≥90%、上櫃≥70%，公開功能讀回。
- [ ] **DRL-01B P0 月營收 fiscal_month：** 官方當月及上月財務紀錄保留 fiscal_month、fiscal_period_end、period_basis；既有4,011筆營收中3,947筆缺月份，先利用已存在可靠期間欄位與舊來源修復，保留值／provenance，無法確認月份則PENDING。完整13月同月YoY與數據驗收。
- [ ] **DRL-01C P1 EPS 本年度先行上線（2026-10-17 核准縮小gate）：** 首版對六檔目前上市持股／關注股要求 **2026Q1與2026Q2** 真正合格的官方單季EPS（Q1 YTD視為Q1；Q2必須官方明示單季或可核實分子／股數），第三季僅已發布才納入，第四季未到期不要求。每股原來源、單位、季度、provenance、receipt及published serving/API/UI需可稽核；未達仍PARTIAL，不能用累計EPS差分或推估股數。**2025及更早四連季、同比、TTM門檻此次標為`WAIVED_FOR_MVP`，不是資料品質PASS或認證的歷史TTM**；既有`eps_4_comparable`保留實際量測與缺值；單一合法EPS也要可在個股頁顯示且標清期間。首版有用先上線，後續年度歷史只針對需要者補，不新增供應商／工作包。
- [ ] **DRL-01D 兩年 PE/PB 河流（2026-10-17 使用者核准縮小）：** 僅對六檔已核准 TWSE 持股／關注股定向補 2024-10～2026-10 官方25個曆月；有效18個月以上及至少150個有效日、期間兩端皆有資料，才發布「兩年歷史分位」與 P25／P50／P75／月中位河流。PE 與 PB 分別判定；來源不足顯 PARTIAL／PENDING 並保留短期官方 PE/PB。保留 provenance、Core snapshot 與不認證歷史 PIT 的界線。原五年補收請求停用，不增來源／排程／費用；程式及 CI PASS 不等同 dev 補收、API／手機驗收 PASS。
- [ ] **定期 Data Readiness Ledger：** 只使用現有Controller排程，日增量聚合、週詳細稽核；核對固定Core snapshot、資料筆數、分市場有效母體、期數、缺漏與持續增量水位。Drive只保留管理摘要。
- **2026-10-17 使用者限定 DRL-01 前三項（完成可驗證部分後停止，不延伸 Ledger／UI／五年河流）：**
  - **① 月營收：PASS。** 2025-09～2026-09 13個指定月，獨立同檔 Core 實機 [#38997408284](https://github.com/tommylin15/janus-omniforge/actions/runs/38997408284)：TWSE **1,077／1,096（98.27%）**、TPEx **864／896（96.43%）**，均超過90%／70%門檻；TPEx最後2026-07～08官方Stage/Core收據[#38990411743](https://github.com/tommylin15/janus-omniforge/actions/runs/38990411743) PASS。舊「上櫃缺8個月」checkpoint已作廢。2025原公告日未知不倒填為PIT；營收UI／serving另循D03獨立驗收，不重開工作包。
  - **② 已核准持股／關注股120日價量：TWSE 六檔 PASS；兩檔TPEx債券ETF另驗。** 官方 Core [#38997792145](https://github.com/tommylin15/janus-omniforge/actions/runs/38997792145) `1513,2327,2382,3231,3711,5876` 各有**135個有效交易日（6／6）**，已有資料故0新增寫入。債券ETF `00697B,00719B` 不在四碼股票market master／一般batch；官方TPEx dailyQuotes來源與完整OHLCV欄位在read-only [#38998425476](https://github.com/tommylin15/janus-omniforge/actions/runs/38998425476) 二檔source PASS；獨立ETF歷史Stage/Core修復[#38998709152](https://github.com/tommylin15/janus-omniforge/actions/runs/38998709152) 依最終120日讀回判定，**不得把兩檔ETF未驗結果算在6／6或上市櫃股票分母內**。全市場20/21另已讀回TWSE1073／1096、TPEx799／896，[#38988025097](https://github.com/tommylin15/janus-omniforge/actions/runs/38988025097)。
  - **③ 官方4連季EPS：PARTIAL（嚴格驗收不冒稱成功）。** 既有`fundamental-history`補收[#38998082208](https://github.com/tommylin15/janus-omniforge/actions/runs/38998082208) 首段成功，另一次獨立Core snapshot `1036734792492319715` 驗收：1513、2382各**9個分散單季／2025Q4缺／無4個連續季度**，故CI依實際合格閘門保持FAIL。六檔Q3/Q4原始官方MOPS XBRL read-only [#38998787882](https://github.com/tommylin15/janus-omniforge/actions/runs/38998787882) 已可讀基本EPS與歸母盈餘，但**六檔皆缺可證明的加權平均股數分母**（source_failures=0）；不能用累計EPS直接相減或推估股數填單季。優先尋得同一官方版本可核實的單季EPS或分子／分母再定向修復；未符合期間仍null且`PARTIAL`。
  - **技術範圍：**本輪僅針對以上三項的官方來源、Stage/Core、合法季度規則與驗收，無Owner交易／現金／行情成本變更，也不新增市場股票分母、第三方供應商、排程或付費資源；CI／Job執行器成功不等同第四季公式成功。
  - **執行界線：**不接續第四項定期Ledger實機、第五項UI端到端、五年PE/PB或其它D01～D08工程；缺證據的範圍維持PARTIAL或BLOCKED，不能因本次工作重標完成。
  - **2026-10-17 最新執行決策及實際補收：**② ETF歷史 [#38998709152](https://github.com/tommylin15/janus-omniforge/actions/runs/38998709152) 已`SUCCESS`且Cloud Run `janus-ingestion-core-prxnx` Core snapshot `4874890923938554002`兩檔`00697B,00719B`各**125個可證明官方有效行情日（2／2 PASS）**；連同原六檔各135日，**指定8／8檔的120日門檻PASS**，不包含ETF在股票市場分母。③新2026年核准MVP Gate首輪唯讀Core [#39000160070](https://github.com/tommylin15/janus-omniforge/actions/runs/39000160070)：首輪**4／6**（1513、2327、2382、5876），3231、3711已由MOPS補收；獨立 Core 再驗[#39000368842](https://github.com/tommylin15/janus-omniforge/actions/runs/39000368842) **2026Q1／Q2 六檔全部6／6 PASS_CURRENT_YEAR**（Core snapshot `5736520631016782502`）；歷史四連季依然0／6，不屬MVP上線必過門檻。舊2025Q4、四連季和TTM不再阻擋2026Q1/Q2首版，但仍為**NOT_CERTIFIED／WAIVED_FOR_MVP**，沒有轉成事實PASS。
- **結案條件：**現有GitHub實作＋targeted／整體CI，來源授權與Core逐月snapshot、上市10%／上櫃30%門檻，持股／關注120日，官方EPS合理口徑，真實13月YoY，最新同源GHCR受控Jobs部署、serving／Admin／手機／桌面讀回、自然排程及增量重跑。缺值可顯示、單項可獨立PASS；**DRL-01整體必須保留PARTIAL直到上述適用關卡有真實證據**。不新增平行待辦、付費來源或排程，不操作Owner資料。

## D06｜歷史結果（剩餘工項併 FINOPS-AB，不獨立施工）

- [x] 真實 orphan 清理：原 8,343 objects／194,161,764 bytes，已刪 477 objects／2,039,377 bytes，剩餘 7,866 objects／192,122,387 bytes；[#38879585601](https://github.com/tommylin15/janus-omniforge/actions/runs/38879585601) PASS。
- [x] 停用 `ops.batch_events_v1` audit mirror：Jobs rollout [#38875865395](https://github.com/tommylin15/janus-omniforge/actions/runs/38875865395) 8/8 PASS，runtime [#38881471078](https://github.com/tommylin15/janus-omniforge/actions/runs/38881471078) PASS。
- [x] GCS 引用掃描 62 Core／71 Mart／96 Research／495 Private 已有證據，PG publication 共138筆；`core_snapshot_id` 欄位仍有 privilege 缺口，未完成全引用授權刪除。
- [ ] 引用保護、Retention fence、合法 Orphan／Snapshot 清理及讀回：**已轉入 FINOPS-AB 的 D06-R1/R2/唯一驗收**，不另發佈或重複計算。
- [x] 兩天／長時間等量 I/O 比較：**CANCELLED_BY_USER（需求取消，不是量測 PASS）**；不執行、不阻擋 FINOPS-AB 結案。

## ADMIN-V2｜主要重構（IN_PROGRESS，2026-10-18 啟動）

**單一執行入口：**[Admin v2 架構與逐步順序](decision-2026-10-17-admin-v2.md) → [Admin UI](ui/admin.md) → [WBS-6](wbs/wbs-6-api-and-apps.md)。**2026-10-18 使用者已明確授權啟動四頁遷移→總控整合→資料品質→治理→使用分析→完整驗收；取代原文件-only 限制。** 本機實作／targeted 驗證進行中，尚無本版完整 CI、migration／dev 發布與 Admin 真人驗收證據，不宣稱完成。 後續實作排在 D01～D06 與 DRL-01 適用的核心契約／驗收證據穩定後、D07／D08 的 Admin UI 整合之前；不必等待 D06 全面 I/O 優化、2025 以前 TTM、五年河流完成。

- [x] **A0 規格整併（文件）**：六頁→四頁的目標、舊頁功能歸位、A1～A5 工程順序、D07／D08 消費位置及驗收邊界已寫入本 TODO／WBS／UI／兩張卡片；文件完成不代表 Admin 已改版。
- [ ] **A1 四頁 shell 與功能遷移**：總覽／批次／資料品質／系統設定；保留必要搜尋、details、history、Admin authorization。
- [ ] **A2 Controller 營運整合（D01、D02、D04、D05 的影響）**：Private Mart、Snapshot、effective batch/backup/job terminal、受控 retry、已驗證 deployed SHA/digest 的唯讀顯示；不建第二套控制面。
- [ ] **A3 DRL-01 資料品質（含 D02／D03 影響）**：TWSE／TPEx、OHLCV／營收／EPS 合法期間、stock／market 缺口、來源及安全修復；2026 單季 EPS 與歷史 TTM 未認證要區別。
- [ ] **A4 D06／D04 營運治理**：Iceberg objects/bytes、maintenance、cleanup/protected refs、可比負載 I/O、備份與 worker 設定；缺證據維持 unknown。
- [ ] **A4-U 全站＋單一使用者行為分析**：在「總覽 → 使用分析」新增依使用者搜尋／單人 7／30／90 天操作次數、功能活躍時間與有限操作時間線；Flutter allowlist 事件非同步批次、PostgreSQL 每日 user-feature 彙總、短期事件保留、Admin 授權與存取稽核，不直接寫 Iceberg，不阻塞使用者操作。規格見 [Admin v2 §4.1](decision-2026-10-17-admin-v2.md)。安排在 A4 後、A5 前，不新增獨立主頁或其他工作包。
- [ ] **A5 Admin 專屬完整驗收**：Flutter/API targeted、權限與 owner 隔離、CI、受控 dev 發布、真實 batch/data/runtime readback、390px/desktop、rollback；含 A4-U 的 User/Admin 隔離、上報失敗無害、頁面切換效能、容量及保留期驗收。

**禁止擴張：**D01～D06 的 TODO 列、任務卡、完成與驗收條件**保持原樣**；新增 A4-U 只隸屬 ADMIN-V2，User App 只增加共用非阻塞埋點，不更動既有交易、估值或專案資料契約；相關工作只列在此處，亦不建立另一個 DRL、Scheduler、Admin 重算或發布系統。D07 的 VF-09 接「系統設定／AI 模型」；D08 的 CEO/Gateway 接同一容器且正式報告回 User，兩者維持既有模型／業務 gates。

## FINOPS-C｜BigQuery 方案（A＋B 完成後、D07／D08 開工前；PLANNED）

**本段只固定先後順序，不授權直接變更 BigQuery 付費資源、IAM 或切換 production。AI 必讀 [FINOPS 卡 §4](execution-cards/finops-ingestion-iceberg-ab-and-c-gate.md) 與 [原混合架構決策](decision-2026-10-06-bigquery-analytics-over-iceberg.md)。**

- [ ] **C-preflight（開工前強制重評估）：**以 A＋B 最新實測及當下 main/runtime 條件重評全系統 ingestion/Mart CPU、GCS、BQ on-demand billed bytes、免費額度與其他專案共用消耗、catalog/region/權限、PIT/exact-snapshot fidelity、成本、收益、失敗回退。重評報告正式回寫決策文件／WBS／TODO，留影響範圍、證據、成本上下界與 go/no-go/blocked 結論。
- [ ] **C selectively implement（僅在 preflight 合格及必要授權後）：**現有 BigQueryAdapter 優先擴充全市場 Screening／Ranking，其次 OOS／aggregate；同一 immutable Core snapshot 比對 PyIceberg，bounded bytes/cost、query result、fallback、實機帳單與 GHCR/Job readback 全驗收。未通過應明確 DEFERRED/BLOCKED，不跳過 C-preflight 啟動 D07/D08，也不以歷史 B0～B8 PASS 代替此次核准。

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
