# Janus — 唯一 Active TODO

更新：2026-10-25（Asia/Taipei）。SEQ-01～03 DOC／CODE／OFFLINE_PASS；SEQ-04既有Dev四Job/API、migration069、PG隔離還原、單一兩小時Scheduler部署與14:30自然Controller tick PASS。Stage48h #40172644132 實刪223件／42,540,741 bytes（#40173298619後驗到期候選0），Private retention #40173273728 刪daily1份／26,044,882 bytes且PG成功，Iceberg現役catalog76／76通過。**2026-10-19當週 weekly 副本已補建成功**：#40175398373 新建1份30,872,328 bytes與原daily SHA-256一致；同run將舊10/25 00:30 backup occurrence從running修復為succeeded，CAS 1筆、outbox 1筆、讀回PASS。剩餘僅10/26新版自然02:30 ingestion→Core→screening、10/26新週首次自然備份驗收及Owner/Admin正向登入 AUTH_REQUIRED。SEQ-04=BOUNDED_CLOSEOUT_PASS／OVERALL_LIVE_PARTIAL；原定未到期自然時點不冒稱成功、不另設長期觀察。

## 唯一順序線

依序 **SEQ-01 → 02 → 03 → 04 → 05 → 06 → 07 → 08**。不再分線派工；舊 UB／RV／D07／D08 是對照ID，不是另一份佇列。
每項固定拆為文件設計、程式開發、測試驗收、部署，完整指示見 [AI逐項指令](execution-cards/sequential-delivery.md)。

| 順序／任務 | 整併舊項 | 目前基線 | 部署歸屬 | AI 指示 |
|---|---|---|---|---|
| SEQ-01 收取、清理與市場分析總控 | UB-01 | DOC／CODE／完整離線217 PASS／Flutter7 PASS；live與部署交SEQ-04 | SEQ-04 | [四階段指示](execution-cards/sequential-delivery.md#seq-01) |
| SEQ-02 持股、買賣與觀察設定快照 | UB-03、4J／4R 的本次增量 | DOC／CODE／OFFLINE_PASS（220 Python、270 API、Flutter User PASS）；live/部署交 SEQ-04 | SEQ-04 | [四階段指示](execution-cards/sequential-delivery.md#seq-02) |
| SEQ-03 日週月備份、保留清理與回復範圍 | UB-04（不是重開 OPS-P0-1） | DOC／CODE／OFFLINE_PASS（234 Python；API270、Mart247、Ingestion209）／LIVE與DEPLOY交SEQ-04 | SEQ-04 | [四階段指示](execution-cards/sequential-delivery.md#seq-03) |
| SEQ-04 基礎批次集中部署與兩小時切換 | UB-05：UB-01／03／04 合流 | **DEPLOY_PASS／STAGE_PRIVATE_CATALOG_PASS／CURRENT_WEEK_WEEKLY_PASS／OLD_0030_RECONCILE_PASS／NATURAL_CONTROLLER_PASS／OVERALL_LIVE_PARTIAL**：四Job與API、migration069／VM／PG還原、2h Scheduler／14:30 Controller自然tick #40170098722 PASS；Stage #40172644132實刪223件/42,540,741 bytes、後驗 #40173298619 PASS；Private retention #40173273728 daily刪1份/26,044,882 bytes且PG retention succeeded；Iceberg catalog current 76/76 PASS；本週10/19 weekly不可變副本 #40175398373 建立1份30,872,328 bytes且SHA-256一致；舊10/25 00:30 backup occurrence單筆CAS running→succeeded及outbox 1筆同run讀回PASS。只有10/26新版首次02:30市場資料鏈、新週10/26自然備份與Owner/Admin登入正向 AUTH_REQUIRED未驗，歷史舊running／本週weekly缺口已結清。 | 本輪已到期可修工項結案；10/26自然驗收及Owner/Admin授權獨立待驗 | [四階段指示](execution-cards/sequential-delivery.md#seq-04) |
| SEQ-05 Valuation 真資料、唯一估值卡契約 | RV-01…06、UB-02 Valuation 子功能 | **LIVE_CORE_ONEOFF_PASS／DOC_CODE_COMMITTED／OFFLINE_PASS／MART_API_LIVE_PENDING／DEPLOY_SEQ-08**：#40172093172真正透過既有Dev Job完成FinMind 2882 PB 2025-10至2026-08共11月11筆、Yahoo 2026Q2 BVPS=69.37 1筆，Stage→Core讀回11/11月、獨立#40172603358讀回兩股24/24有效月及BVPS=69.37，0來源失敗。2330既有FinMind四季EPS直接相加=86.28元，Mart程式標記research approximation。#40172051959分析測試226 passed，FinMind/Yahoo均標為approved_fallback。一次性工作已封存，#40172457154重觸發安全跳過0 mutation；Mart/Fact Pack/API最新版程式未部署，未有新版live報告價帶 | 唯一下一工程入口SEQ-06四模型正式serving、版本及共用快取；其後SEQ-07報告／Owner history／UI接線；最後SEQ-08集中部署Mart／Fact Pack／API／前端及認證讀回。SEQ-05部署仍交SEQ-08；不得重收11個月或重派一次性請求 | [四階段指示](execution-cards/sequential-delivery.md#seq-05) |
| SEQ-06 四模型正式上線模式、版本與共用快取 | UB-02、D07 serving、Risk API/UI、D07-CROSS-JOB-MODEL-CACHE；必要 parity | **ORIGINAL OFFLINE_PASS；2026-10-25 USER_PUBLICATION_APPROVED_FOR_ALL_FOUR；REAL_MODEL_BYTES_LOCAL_RELOAD_PASS；LIVE_REGISTRY_NOT_ACTIVE**：原 serving/快取 #40174399997／#40174400071 PASS；新增 [v26 Core MOPS 五因子 mapping d15e4d70](https://github.com/tommylin15/janus-omniforge/commit/d15e4d70af9d0238822918698be3f0ea9efaa8f6)（已用 source XBRL TWD 及同季 YTD revenue YoY、缺值 fail closed），[CI #40177556379](https://github.com/tommylin15/janus-omniforge/actions/runs/40177556379) SUCCESS。讀取真實 Drive 權重並重載 Quant XGB15、Risk XGB12、Fundamental RC1 XGB15、Valuation v26 PE/PB XGB5；Quant／Val雙頭固定向量誤差0，封包僅本地產生，**未上傳GCS**。GCS [唯讀 #40177858431](https://github.com/tommylin15/janus-omniforge/actions/runs/40177858431)：Risk registry mode=DETERMINISTIC、Quant／Fundamental／Valuation三份 active pointer 不存在；新技術門檻：Risk12 四新增因子服務接線／替換舊8 pin、Quant15 特徵供應與版本、Fundamental15＋5% X-only abstention、Valuation PE/PB 雙頭與 Core 真實日期／單位 parity。批准不是已 ACTIVE，原 Research 封包限制仍保存歷史語意 | **併入 SEQ-08 正式發版前完成 GCS candidate create-only import／hash、四模型 feature parity與必要 serving 修改、Registry／PG／Owner UI 驗收；若必要源資料缺失明列 partial** | [四階段指示](execution-cards/sequential-delivery.md#seq-06) |
| SEQ-07 分析報告、Owner history 與 UI 完整接線 | UB-02、D08、RV-05 合流 | **DOC／CODE COMMITTED／OFFLINE_PASS／DEPLOY_DEFERRED_TO_SEQ-08**：程式 SHA [f9ace32b](https://github.com/tommylin15/janus-omniforge/commit/f9ace32b795e6c1895901e7750f18be2f57da575)。Fact Pack週期報告保存四ML serving版本／狀態與缺值，model／input變更控制重產；Owner專屬持股／觀察股歷史唯讀API有auth／hash／去重；Flutter呈現四角色資料日／版本／缺口、唯一估值區間、報告沿用與歷史，CEO按需及Gateway故障退回事實報告。Python API／契約 #40175446096 275 passed／7 skipped／2 warnings，最新 #40175926343 272 passed／7 skipped／2 warnings；Flutter #40175926335 SUCCESS（widget tests＋PWA build）。真四artifact GCS／Valuation accounting／登入後正向Owner與Gateway live未驗；不宣稱四ML已 ACTIVE | **唯一下一工程入口 SEQ-08：固定SHA/digest 集中部署 Mart／API／Flutter、Owner登入／四模型／2330／2882真資料與rollback驗收** | [四階段指示](execution-cards/sequential-delivery.md#seq-07) |
| SEQ-08 四分析師到報告 UI 集中發布驗收 | UB-02 完成 gate、RV-06、D08 發布 | **READY_FOR_PREDEPLOY_BUT_NO_LIVE_MODEL_REGISTRY**：四模型明確批准（2026-10-25），各UBJ本地已重載；Risk DETERMINISTIC／其餘三pointer MISSING，以 #40177858431 為權威。SEQ-05…07離線交付完成，但不等於四模型具備服務所需15/12/15/5特徵、GCS版本和Valuation雙頭 | 先導入已驗模型至既有Dev GCS candidates且真hash讀回，補Risk12／Quant15／Fund15 abstention／Val PE+PB parity及reader後做型態化驗收；最後受控切Registry＋PG、集中部署Mart／Fact Pack／API／Flutter、2330/2882及Owner登入報告真實讀回。不做第二版研究無界重訓；未知維持partial | [四階段指示](execution-cards/sequential-delivery.md#seq-08) |

### SEQ-04 時段變更決策（2026-10-25；Cloud Scheduler 已切換，live部分待驗）

使用者指定：台北時間每日00:30 PG備份、每日02:30 ingestion、週一至五04:30 market-screening、週一至五06:30 private，Stage每日22:30／週六Iceberg22:30／mobile-ledger依既有條件。**程式契約已部署、原有Cloud Scheduler切換已完成**：唯一入口 `janus-ingestion-daily` 實際 `30 */2 * * *`／Asia/Taipei／ENABLED，HTTP target／OAuth身分未變，沒有新增第二Scheduler；部署與獨立GCP讀回 #40163729460／#40163927739 PASS。此時段設定成功不等於第一次新cron自然觸發成功，後者及批次資料鏈／Stage／Owner／UI仍需有界驗收。

## 階段狀態與接手規則

- SEQ-01 已依使用者授權開工；本輪修正來源失敗與 Mart queue 狀態，並使舊測試遵守現行 EOD／target-only 契約，未重建 Controller／Scheduler。已取得完整離線腳本及 Flutter Admin targeted 的同版 CI SUCCESS 收據；離線階段可交接SEQ-02，待SEQ-04執行集中部署與live。
- 本次文件整理完成，不等於每個任務的設計已審定或工程完成。上表基線來自 main 已提交程式／既有文件收據，沒有新的runtime驗收。
- 每次只執行使用者指定任務／階段；未指定階段時按該任務四階段指示完成可做範圍。遇跨任務集中部署，將部署及live驗收記為 `DEFERRED_TO_SEQ-04/08`，不是PASS；其餘前置交付完成即可往下一順序準備，不造成循環等待。
- SEQ-04結清SEQ-01…04；SEQ-08結清SEQ-05…08。測試驗收分部署前離線／Release與部署後真實驗收，不能在未部署時假稱live PASS。
- 記錄格式：`任務｜文件設計狀態｜程式狀態｜測試狀態（offline/live）｜部署狀態｜SHA/證據｜下一階段`。只在此維護active狀態；Operations保存收據。

### SEQ-05 四階段紀錄（2026-10-25，第四輪：一次性第三方補資料）

`SEQ-05｜DOC=UPDATED／CODE=Core補資料/簡化EPS及Mart→Fact Pack→API COMMITTED／OFFLINE=PASS（[分析CI #40172724791](https://github.com/tommylin15/janus-omniforge/actions/runs/40172724791) 227 passed／1 warning）／LIVE_CORE=PASS（[有界一筆Job #40172093172](https://github.com/tommylin15/janus-omniforge/actions/runs/40172093172)，FinMind PB 11筆、Yahoo BVPS 1筆，Core月份11/11讀回、source_errors=[]）／MART_AND_API_LIVE=NOT_DEPLOYED／DEPLOY=DEFERRED_TO_SEQ-08／唯一下一入口=SEQ-06（四模型正式serving、版本／共用快取、train-serving一致性）→SEQ-07（報告／Owner history／UI完整接線）→SEQ-08（含Valuation Mart/Fact Pack/API在內的集中部署、2330／2882真實登入讀回）。SEQ-05的部署責任交SEQ-08，並非下一個序號直接跳SEQ-08。`

使用者要求「補資料不用太嚴謹，直接做加總」：2330以既有FinMind Core 2025Q3 17.44 + 2025Q4 19.51 + 2026Q1 22.08 + 2026Q2 27.25 = **86.28 TWD/share**，只作`last_four_reported_quarters_simple_sum`研究參考，不宣稱配股調整後、稀釋EPS或法定四季合計。這四筆原本已在Core，沒有重新寫入。2882 Yahoo來源（`https://tw.stock.yahoo.com/quote/2882.TW/profile`）公開2026Q2 BVPS=69.37 元，已隨來源原始回應透過 Stage 入 Core；FinMind `TaiwanStockPER` 2025-10至2026-08 11個月PB最後交易日共11筆已實際入 Core。實際source ID為`finmind`和`yahoo-finance`、角色為核准fallback，不冒充官方來源。Core估值snapshot=3874132956674698219、財務snapshot=6504132269236397893。唯一Dev Job execution `janus-ingestion-core-lwwg5`，GCP範本未變、未增費服務與Scheduler、Owner資料未異動。正常既有Stage 48h清理政策不變。

封存 `ops/seq05-oneoff-quickfill.json` 為 `approved=false/closed_after_success=true`，再由[Noop #40172457154](https://github.com/tommylin15/janus-omniforge/actions/runs/40172457154)讀回 `SKIPPED_ALREADY_COMPLETED/data_mutations=0`。禁止將此一次性工作設為常態排程，或再次重派。獨立二次Dev Core唯讀 [#40172603358](https://github.com/tommylin15/janus-omniforge/actions/runs/40172603358) 終態SUCCESS：2330有效月24、2882有效月24、2882 BVPS=69.37(TWD_per_share)與source=yahoo-finance實際讀回，Core雙表snapshots分別3874132956674698219／6504132269236397893。不是Mart正式發布驗收。

**完成範圍**：兩股估值所需原始資料已具備研究路徑；**未完成**：新的Mart materialization、Fact Pack寫入、API正向登入及前台顯示未部署或驗收，仍依SEQ-08；不能把已進Core直接當成已進Mart。下個工程入口先完成SEQ-06四模型正式serving與離線契約，再完成SEQ-07報告／Owner history／UI；其後在SEQ-08受控部署Mart+API及兩股真實讀回。SEQ-05不再研究補抓來源。詳見[Valuation SPEC](spec/valuation-range.md)。

### SEQ-04 有界實刪新收據（2026-10-25）

- **Stage 48h = LIVE_APPLY_PASS**：[#40172644132](https://github.com/tommylin15/janus-omniforge/actions/runs/40172644132)，原有`janus-ingestion-core` Job execution `janus-ingestion-core-9dd52`。實際 `604 → 381` 件，`73,943,009 → 31,402,268 bytes`，計畫／實刪均223件／42,540,741 bytes，generation-fenced worker與獨立GCS清冊讀回吻合；非dry-run或推算。此次僅Dev Stage，無Core/Mart/Private刪除。
- **首次Private執行失敗已保留歷史、後續修復PASS**：同#40172644132 Private VM回傳exit1，未獲該run清理成功；後續以 #40173273728 單獨重跑Private，實刪daily1份／26,044,882 bytes，daily8→7並讀回10/25 PG retention_status=succeeded。沒有重跑Stage。PG current catalog 76／76通過，Owner/Admin與10/26自然資料鏈仍待驗。
- **本輪已到期有界清理／catalog CLOSEOUT=PASS**：Stage、Private、current pointer與自然Controller tick均有真實收據；整體SEQ-04仍保留下一個02:30收取與週副本、Owner/Admin AUTH_REQUIRED、舊備份occurrence作個別驗收，不列FULL_PASS。詳見[Operations](spec/operations-and-testing.md)。

### SEQ-04 weekly與舊00:30 occurrence 即時修復收據（2026-10-25）

- [#40175398373](https://github.com/tommylin15/janus-omniforge/actions/runs/40175398373) workflow SUCCESS；有界12 tests PASS；由已成功2026-10-19 daily 備份原始generation與PG checksum驗證，原始內容不覆寫，以目標`ifGenerationMatch=0`新建`weekly/2026-10-19.dump` 1件／30,872,328 bytes並下載SHA-256讀回PASS。2026-10-26下一週不能預先建立，保留該週自然首次成功驗收。
- 同run精確將`ledger-backup/2026-10-25/00`在PG backup+retention均succeeded且日期／state匹配的條件下CAS `running→succeeded`、outbox 1筆，PG讀回PASS；不將不同的02:30 occurrence冒充00:30。初次 #40175288842 因pytest缺失中止、實際寫入0，第二次修復PASS。
- **已完成的這兩項從SEQ-04 active blocker移除。** 不建立新Scheduler／Job、不重新備份、無Owner資料變更；本輪只保留10/26自然時點與Owner/Admin授權UI正向驗收。詳細來源以 [Operations](spec/operations-and-testing.md) 為準。

### SEQ-04 四階段紀錄（2026-10-25，進行中）

`SEQ-04｜DOC=UPDATED／CODE=COMMITTED／DEPLOY=PASS（#40163729460、#40163927739）／NATURAL_CONTROLLER=PASS（#40170098722）／STAGE_48H_APPLY=PASS（#40172644132，後驗#40173298619）／PRIVATE_RETENTION_APPLY=PASS（#40173273728）／ICEBERG_CURRENT_CATALOG=PASS（76/76）／WEEKLY_BACKFILL_2026_10_19=PASS（#40175398373，30,872,328 bytes SHA-256 verified）／OLD_LEDGER_BACKUP_0030_CAS=PASS（#40175398373，1列狀態CAS與1筆outbox）／OVERALL=LIVE_PARTIAL（10/26首次新版02:30 ingestion鏈與新週自然備份尚未到期；Owner/Admin正向AUTH_REQUIRED）｜唯一剩餘入口=SEQ-04下一必要自然時點一次驗收，無需重派Stage、重跑備份或新增Scheduler`。

收據判定：Release、migration069／VM、PG隔離還原、四Job 8/8、API 100% 已通過。歷史切換 #40162679929 `permission_denied` 及回復，之後 #40163099454 精確查出 target SA actAs NOT_GRANTED；使用者於Cloud Shell僅授權 `janus-ci` 對指定 `janus-ingestion-scheduler` SA 的 `roles/iam.serviceAccountUser` 並讀回。重新觸發 [#40163729460](https://github.com/tommylin15/janus-omniforge/actions/runs/40163729460) 最終SUCCESS，receipt: `phase=PASS`、`previous_cron=30 * * * *`、`new_cron=30 */2 * * *`、`scheduler_enabled=true`、`target_identity_unchanged=true`、`gcp_new_resources=0`；獨立GCP [#40163927739](https://github.com/tommylin15/janus-omniforge/actions/runs/40163927739) 再讀到同值、target hash一致、IAM update/actAs=GRANTED。14:30自然tick已由#40170098722的Scheduler執行紀錄（HTTP200）、Cloud Run REST最新Controller execution（created UTC06:30:00；start UTC06:30:16；complete UTC06:31:52，CONDITION_SUCCEEDED）證實PASS。首次gcloud list未顯示新execution，已交叉改用Cloud Run REST確認。新版02:30 ingestion需等2026-10-26 02:30 Asia/Taipei自然收取完成後讀回，不能用今天舊版失敗或Controller成功代替。其餘有界驗收維持NOT_VERIFIED，不增添獨立排程。

### SEQ-04 新兩小時自然Controller收據（2026-10-25 14:30 台北；PASS）

- [GitHub唯讀 #40170098722](https://github.com/tommylin15/janus-omniforge/actions/runs/40170098722) completed/success；Scheduler `lastAttemptTime=2026-10-25T06:30:00.865962Z`、cron=`30 */2 * * *`、Asia/Taipei、ENABLED；Cloud Scheduler execution log 06:30 HTTP 200；Cloud Run V2 REST `janus-batch-controller` execution create UTC06:30:00.943455、start UTC06:30:16.601901、complete UTC06:31:52.439218、Completed=CONDITION_SUCCEEDED。首次CLI listing漏新紀錄，交叉用v2 REST得到完整收據。**自然Controller tick=PASS；不是新版市場收取成功的證據**。
- 下一個新版02:30 ingestion自然時點為2026-10-26 02:30（台灣時間）；驗收需讀新occurrence狀態、actual Cloud Run Job與Core data date／artifact，不使用10/25舊失敗推論新版。無須等待24h才能推進其他工作。整體結案判定：**SEQ-04=LIVE_PARTIAL／NOT_CLOSED**；部署與自然Controller tick可獨立標PASS，但必須保留實際未執行的清理apply／現役catalog與資料鏈驗收。Owner／Admin無登入憑證時為`AUTH_REQUIRED／NOT_VERIFIED`，不得拿匿名401作正向驗收。

### SEQ-04 即時有界驗收收據（2026-10-25；不等於全系統live PASS）

- [備份／Controller #40164713512](https://github.com/tommylin15/janus-omniforge/actions/runs/40164713512) workflow SUCCESS。executor timer active/enabled、舊direct timer inactive/disabled；最近六筆每日備份succeeded，2026-10-25最新備份40,595,834 bytes。Control中同日ledger-backup 00:30 occurrence仍running、02:30另一筆succeeded；每日備份狀態與排程occurrence不可混為同一PASS。
- [完整有界唯讀 #40165435450](https://github.com/tommylin15/janus-omniforge/actions/runs/40165435450) workflow SUCCESS，分項：Stage 48h依PG有效lease17及完整GCS inventory452物件得到 `PASS_DRY_RUN`、計畫220物件／42,538,112 bytes、held_active_objects0，實刪0；Private備份retention `DRY_RUN_PASS`：8 daily／2 monthly／0 weekly，計畫刪1 daily、其餘0；最近8份PG daily均succeeded，但8筆retention_status為pending，**不能算清理已apply**。23xx/28xx公共OHLCV各有真資料；API buildSHA/health 200，Owner/Admin未登入皆401；Core/Mart/Private bucket之Iceberg metadata文件各可讀，但沒有驗證PG catalog指到的current snapshot。兩個較大bucket只完成有界metadata樣本，不能冒充完整bucket inventory。
- Live發現：2026-10-25 02:30、07:30 ingestion occurrence為FAILED，歷史failed收據橫跨SEQ04部署前（不能直接證明目前新版失敗）；12:31 analysis-queue仍標running。需以原工作ID／live lease／Job執行收據核對，不大量重派、不刪記錄、不當作已成功。
- 已驗：14:30 Scheduler自然Controller成功（#40170098722，HTTP200與Cloud Run REST completed success）。仍未驗：Stage按原worker fence有界generation刪除與bytes讀回；Private每日retention實際apply／週副本創建及PG欄位轉終態；Iceberg catalog current pointer；Owner／Admin真正登入與snapshot/UI一致性；2026-10-26 02:30新版ingestion→Core產物。既有GCP兩小時配置仍PASS，不重新建Scheduler，不等一整天才開始其它獨立工作。

### SEQ-03 四階段紀錄（2026-10-25）

`SEQ-03｜文件設計=REVIEWED／CONTRACT_UPDATED｜程式開發=COMMITTED（b46e38822410f414d78807f101a93f12479d2c93／246aaac277e5baab1ccfb5eb9c753fbf6cb61570）｜測試驗收=OFFLINE_PASS（CI #40152197002，source 246aaac；234 Python、9 non-fatal warnings；API270／7 skipped、Mart247、Ingestion209）／LIVE_DEFERRED_TO_SEQ-04｜部署=DEFERRED_TO_SEQ-04｜唯一下一入口=SEQ-04／文件設計`。

依AI任務卡逐類列明PG Owner原始資料、Private GCS／Iceberg、Core／Mart current、模型與報告可備份或可重建邊界；原有migration069只新增狀態欄且可重跑，不重作或聲稱已上VM。新程式對daily immutable碰撞fail-closed，週月保留首成功副本與已有archive讀回，隔離PG還原增加現金anchor／觀察設定／Owner孤兒檢查，GCS依賴明示未被PG dump備份；retention週鍵拒絕非週一。stage48h／current-only＋7天 orphan／7-4-6／刪除3-1-1上限不變。先前CI #40151958279 測試因引號判斷過嚴失敗，修正後CI #40152197002 PASS；實際migration069重跑與資料還原仍留SEQ-04。SEQ-04依WI套migration→VM→Controller並實作隔離restore、GCS current files讀回與有界retention apply，未驗不算完成。

### SEQ-02 四階段紀錄（2026-10-25）

`SEQ-02｜文件設計=REVIEWED／CONTRACT_UPDATED｜程式開發=COMMITTED（功能 72361a2910d43eca06f6ef9aaaee220553a40c1e；相容修正 9f0cd4477d0f6cb1fe653b23979e8fd76c6672fe）｜測試驗收=OFFLINE_PASS（220 Python／9 non-fatal warnings；API 270；Flutter User PASS）／LIVE_DEFERRED_TO_SEQ-04｜部署=DEFERRED_TO_SEQ-04｜證據=CI #40151187692 SUCCESS、Flutter #40151028800 SUCCESS；失敗 #40151028971 已修復｜唯一下一入口=SEQ-03／文件設計`。

對照 main 程式確認：交易帳本／修正／沖銷和原有 Private Pipeline、工作區快照／Owner API 已存在。本輪補現金 change_log、觀察清單增刪／排序及現金／券商／投資設定的重算觸發、工作區 payload 的 cash/broker/change 版本、背景 worker 對並行 owner change_version 的完成 fencing，以及 Flutter 關注頁操作後提示。未改 canonical 帳本、成本法、私人資料授權、GCP 排程或 migration；workspace_snapshots 僅 payload 相容擴充。原始 CI #40151028971 的完整離線測試因舊 fixture 未含新版選填 payload 欄位而 219 PASS／1 FAIL；修復後同 SHA `9f0cd44` 的 CI #40151187692 為 `completed/success`，`bash scripts/test-unified-batch.sh` 220 PASS／9 non-fatal warnings，API selective 270 PASS；Flutter User 全流程 #40151028800 `completed/success`（含 Flutter analyze 與 test，來源為功能 commit `72361a2`，後續修正僅 Python 快照選填欄位）。不同測試集不加總。SEQ-02 文件／程式／離線階段可交接 SEQ-03；本任務仍需 SEQ-04 的 Dev Owner／API／UI 讀回才能整項 CLOSED。

### SEQ-01 四階段紀錄（2026-10-25）

`SEQ-01｜文件設計=REVIEWED／CONTRACT_UPDATED｜程式開發=COMMITTED（7ab83e0aab287d10240efe84e4570cc5ff9eec57；CI整合4241bf40b94b5a75ffee235b9ef0b52b5eb5a271）｜測試驗收=OFFLINE_PASS（Python217、Flutter7、Controller99；9項non-fatal warnings）／LIVE_DEFERRED_TO_SEQ-04｜部署=DEFERRED_TO_SEQ-04｜證據=CI #40148605544 SUCCESS（原 #40147708243 FAILURE→#40147914267 SUCCESS）｜唯一下一入口=SEQ-02／文件設計`。

已於 GitHub Actions #40148605544、來源SHA `4241bf40b94b5a75ffee235b9ef0b52b5eb5a271` 執行 `bash scripts/test-unified-batch.sh`（217 passed、9 non-fatal warnings，含 `bash -n`）及 `cd apps/user_app && flutter test test/admin_batch_dashboard_test.dart test/admin_overview_batch_test.dart`（7 passed），另 Controller CI 99 passed。SEQ-01 文件／開發／離線階段已具交接條件；新時段、migration、Dev Runtime／Scheduler 實機驗收依SEQ-04部署後確認，不冒稱live PASS。證據摘要見[Operations](spec/operations-and-testing.md)。

## 四模型正式上線與第二版邊界

Quant、Risk、Fundamental、Valuation **全部列入本次正式serving／版本／報告／UI／部署範圍**；不是只規劃、不以baseline或research-only代替完成。採既有可發布artifact，不要求先調參或重訓；若缺檔，列明角色、必要檔案與影響，不能捏造ACTIVE。CEO是整合層，Event只保留相容事實，沒有第五模型。

原 DATA-RELEASE-PREFLIGHT／FACTOR-FACTORY／D07 X/Y 的必要推論一致性併SEQ-06；全面研究資料重整、四模型調校／新增因子／實驗與VAL-MIN30後續改善移至 [2027年第一季第二版](parking-lot.md#v2-2027-q1)。不阻塞本次正式上線，不建立自動啟動排程。

## 不重開與未授權範圍

C1-A、P0-2、OPS-P0-1、A-CHANGE、D01～D06、FINOPS-AB、研究稽核精簡保持既有有界結案。新備份政策驗收歸SEQ-03／04，不把歷史故障重開。
取消：逐來源稽核、全歷史PIT／名冊／公司行動重建、自然長期觀察、新20日cohort等待、例行週月模型稽核、第五模型、舊GAS/BQ/月度重訓。
暫不做：C1-B實體刪表欄、新付費來源／資源、production環境建立／IAM擴張、站外推播及其他 [Parking Lot](parking-lot.md)。本次「正式上線模式」指既有Dev個人真實服務中的四模型正式運作，不自動授權新建GCP production環境。

## 2026-10-25 分析因子與報告頻率增量（併原順序）

[分析Mart SPEC](spec/analyst-input-mart.md)／[AI驗測WI](runbook-analyst-input-mart-ai.md)。本次CODE／DOC已交付，TEST／LIVE／UI均NOT_VERIFIED，不新增SEQ編號。

| 原項 | 增量與仍未完成條件 |
|---|---|
| SEQ-01 | 15月營收缺口補收、TWD／千元共用；深度target掃描與共用benchmark；離線測試已過，既有Dev Job與真資料讀回由SEQ-04驗測 |
| SEQ-05 | 補真實EPS／BVPS與估值有效月；不因新Mart而捏造已足量 |
| SEQ-06 | Core→analysis artifact已寫；四模型真artifact feature schema、Valuation會計mapping與正式推論接線待完成；必要train/serving parity本版做、調校留Q1 |
| SEQ-07 | 新增週期＋資料變更事實報告及重用狀態；四ML結果、Owner history／API／UI完整接線與日期語意待驗；CEO仍按需 |
| SEQ-08 | 集中驗2330／2882及既有持股觀察股的真實因子覆蓋→模型→報告UI，不能以新程式存在稱PASS |

### SEQ-06 四階段紀錄（2026-10-25）
`SEQ-06｜DOC=UPDATED／CODE=COMMITTED／OFFLINE=PASS（67a158512e7c0fb73d5740ec71a6824923aafda8；#40174399997 SUCCESS、#40174400071 236 passed／1 warning；真模型artifact非本次fixture）／GCS_ACTUAL_QUANT_FUND_VAL=UNKNOWN／RISK=沿既有 ACTIVE gate 無變更／VAL_MODEL_ACCOUNTING=BLOCKED（尚未建立正式一致映射）／DEPLOY=DEFERRED_TO_SEQ-08／下一入口=SEQ-07（報告、Owner history、UI接線）。` 本項保留四個真 ML artifact／schema 可用性證據缺口；不以 deterministic baselines 或 Research Notebook 代替。沒有新增重訓／長期 OOS 稽核等待門檻。API／登入 UI live 一律由 SEQ-08 收據判定。

### SEQ-07 四階段紀錄（2026-10-25）

`SEQ-07｜DOC=UPDATED／CODE=COMMITTED（f9ace32b795e6c1895901e7750f18be2f57da575）／OFFLINE=PASS（Python #40175446096 275 passed／7 skipped／2 warnings；#40175926343 272 passed／7 skipped／2 warnings；Flutter + PWA #40175926335 SUCCESS）／MIGRATION=NOT_REQUIRED（沿既有 private.specialist_product JSONB）／DEPLOY=DEFERRED_TO_SEQ-08／LIVE_OWNER_LOGIN_AND_GATEWAY=NOT_VERIFIED／ARTIFACT_GCS_AND_VAL_ACCOUNTING=沿SEQ-06已知缺口／唯一下一入口=SEQ-08`。首輪Flutter #40175446120、修正過程 #40175734768／#40175871947 失敗，根因依序為測試mock資料放錯、按鈕超出800×600 test viewport；後以report fixture修正、scroll-to-visible及Gateway失效事實報告回退測試修正，最新 #40175926335 成功。未執行Dev部署或修改任何Registry、真實持股、快照與付費API。

### SEQ-06 補充：四模型發佈授權及真權重核對（2026-10-25）

使用者明確核准全部四模型發佈，覆蓋 2026-10-23/24 研究包 `publication_allowed=false` 作為**目前決策授權**；不改寫原研究包歷史狀態、重播或 OOS 效用。已實際在受控本地環境下載並解碼真實 XGBoost UBJ：Quant 15因子 SHA `3fb509cb7ca8aa5e4a0ec3ca9139a1d355995478a624e1043853f59500cbffe9`（8個test vectors重播誤差0）；Risk12研究 refit SHA `e00d302b082fb135991dc4e6f146cf4b9b7dbb56311daae27539564a629e05eb`（只有研究固定cohort checkpoint，非全期正式重訓）；Fundamental XGB15 RC1+5% 拒絕政策 SHA `05fa3167f10c650389c4e481c3e3a7de8a2b70f9133ad867f0404c3eb9758b0c`；Valuation v26 fold2026 PE `56060b37fb1c18efa9ba3e5c7352b10eca12c8d13990bc6031cdfad15d3bc610`、PB `c0984c82039307788e2af4c962a5e7376bdd2b29a30cecfcff557a91811ffe7a`（兩組各5 vectors重播誤差0）。總計四角色五份權重。使用者端已產生兩份本地 zip（四角色 candidate bundle及Valuation PE/PB dual-head bundle），**GitHub/Drive/GCS沒有自動代替它們存放**；model registry 不因 ZIP 存在而被更新。

GCS DEV [#40177858431](https://github.com/tommylin15/janus-omniforge/actions/runs/40177858431) completed/success、gcs_writes=0，精確四指標讀回：Risk `DETERMINISTIC`、Quant/Fundamental/Valuation `POINTER_MISSING`。本次缺口是實際服務與候選模型不相容，而非人工核准待辦：Risk ACTIVE code pin 8X、Quant current analyst X=11 與研究 XGB15不同、Fundamental X=9 與 RC1 XGB15/abstention不同、Valuation 原單頭指標不能同時提供logPE/logPB，且需對正式Core XBRL來源五因子驗證。已加 `valuation_ml_mapping.py` 接真Core MOPS income YTD/balance snapshot（真Core單位TWD、不重乘1000，映射研究 `roe_proxy` 非一般ROE），3項測試及 CI PASS；尚未做Mart live snapshot正向驗收。不得以 User approval 當作Runtime/Serving PASS或不經測試直接覆寫Registry。唯一正式部署入口依舊為SEQ-08。
