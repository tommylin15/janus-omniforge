# Janus — 唯一 Active TODO

更新：2026-10-25（Asia/Taipei）。SEQ-01～03 DOC／CODE／OFFLINE_PASS；SEQ-04 Release、四Job 8/8、API100%、PG migration069/VM及隔離還原、單一兩小時Scheduler部署與獨立讀回PASS。立即有界Dev唯讀驗收：備份VM／Controller #40164713512 PASS、Stage48h完整dry-run #40165435450 PASS、Private備份保留dry-run PASS、2330/2882 Public API及Core/Mart/Private GCS metadata讀回PASS；資料實刪、Iceberg current catalog pointer、Owner/Admin正向登入、新cron自然tick仍NOT_VERIFIED，SEQ-04 整體LIVE_PARTIAL。

## 唯一順序線

依序 **SEQ-01 → 02 → 03 → 04 → 05 → 06 → 07 → 08**。不再分線派工；舊 UB／RV／D07／D08 是對照ID，不是另一份佇列。
每項固定拆為文件設計、程式開發、測試驗收、部署，完整指示見 [AI逐項指令](execution-cards/sequential-delivery.md)。

| 順序／任務 | 整併舊項 | 目前基線 | 部署歸屬 | AI 指示 |
|---|---|---|---|---|
| SEQ-01 收取、清理與市場分析總控 | UB-01 | DOC／CODE／完整離線217 PASS／Flutter7 PASS；live與部署交SEQ-04 | SEQ-04 | [四階段指示](execution-cards/sequential-delivery.md#seq-01) |
| SEQ-02 持股、買賣與觀察設定快照 | UB-03、4J／4R 的本次增量 | DOC／CODE／OFFLINE_PASS（220 Python、270 API、Flutter User PASS）；live/部署交 SEQ-04 | SEQ-04 | [四階段指示](execution-cards/sequential-delivery.md#seq-02) |
| SEQ-03 日週月備份、保留清理與回復範圍 | UB-04（不是重開 OPS-P0-1） | DOC／CODE／OFFLINE_PASS（234 Python；API270、Mart247、Ingestion209）／LIVE與DEPLOY交SEQ-04 | SEQ-04 | [四階段指示](execution-cards/sequential-delivery.md#seq-03) |
| SEQ-04 基礎批次集中部署與兩小時切換 | UB-05：UB-01／03／04 合流 | **DEPLOY_PASS／IMMEDIATE_READONLY_PASS／LIVE_PARTIAL**：四Jobs8/8 #40155713885、API100% #40157972457、PG隔離還原 #40155337207、兩小時Scheduler #40163729460與實機獨立讀回 #40163927739 PASS；備份executor及Controller audit #40164713512 PASS；#40165435450 Stage完整dry-run452筆／過期候選220筆／42,538,112 bytes、有效lease17，無刪除；Private GCS保留dry-run8 daily/2 monthly/0 weekly、計畫刪1份daily；Core/Mart/Private Iceberg metadata有界GET PASS，current catalog pointer尚未驗；2330與2882公開資料及Auth負向PASS。發現舊ingestion多筆FAILED及00:30備份occurrence RUNNING、備份8筆retention_status=pending。Stage/retention實際有界apply、真正current pointer、Owner/Admin正向登入與新cron首次自然tick仍未證實。 | 同SEQ-04有界後續驗收與保留實刪 | [四階段指示](execution-cards/sequential-delivery.md#seq-04) |
| SEQ-05 Valuation 真資料、唯一估值卡契約 | RV-01…06、UB-02 的 Valuation 子功能 | **DOC_REVIEWED／LIVE_INPUTS_READ_WITH_GAPS／CODE_PARTIAL／OFFLINE_CI_PENDING／DEPLOY_DEFERRED_TO_SEQ-08**：#40166649960既有Dev兩股唯讀PASS，但2330僅12個月末PE且缺連續四季EPS、2882僅1個月末PB且缺BVPS，均不可產價帶；月數缺值診斷修復及單一卡片投影與tests已提交，正式分類／有界資料補足／Mart→Fact Pack→API→UI尚未完成 | 仍需本項資料與後端接線；集中部署SEQ-08 | [四階段指示](execution-cards/sequential-delivery.md#seq-05) |
| SEQ-06 四模型正式上線模式、版本與共用快取 | UB-02、D07 serving、Risk API/UI、D07-CROSS-JOB-MODEL-CACHE；FACTOR-FACTORY／X/Y 僅必要 serving 一致性 | 按四模型可發布前提設計；實際接線狀態逐角色確認 | SEQ-08 | [四階段指示](execution-cards/sequential-delivery.md#seq-06) |
| SEQ-07 分析報告、Owner history 與 UI 完整接線 | UB-02、D08、RV-05 合流 | 既有 Fact Pack／Gateway 可沿用；完整整合待做 | SEQ-08 | [四階段指示](execution-cards/sequential-delivery.md#seq-07) |
| SEQ-08 四分析師到報告 UI 集中發布驗收 | UB-02 完成 gate、RV-06、D08 發布 | 未執行；依賴SEQ-05…07 | 本項集中部署 | [四階段指示](execution-cards/sequential-delivery.md#seq-08) |

### SEQ-04 時段變更決策（2026-10-25；Cloud Scheduler 已切換，live部分待驗）

使用者指定：台北時間每日00:30 PG備份、每日02:30 ingestion、週一至五04:30 market-screening、週一至五06:30 private，Stage每日22:30／週六Iceberg22:30／mobile-ledger依既有條件。**程式契約已部署、原有Cloud Scheduler切換已完成**：唯一入口 `janus-ingestion-daily` 實際 `30 */2 * * *`／Asia/Taipei／ENABLED，HTTP target／OAuth身分未變，沒有新增第二Scheduler；部署與獨立GCP讀回 #40163729460／#40163927739 PASS。此時段設定成功不等於第一次新cron自然觸發成功，後者及批次資料鏈／Stage／Owner／UI仍需有界驗收。

## 階段狀態與接手規則

- SEQ-01 已依使用者授權開工；本輪修正來源失敗與 Mart queue 狀態，並使舊測試遵守現行 EOD／target-only 契約，未重建 Controller／Scheduler。已取得完整離線腳本及 Flutter Admin targeted 的同版 CI SUCCESS 收據；離線階段可交接SEQ-02，待SEQ-04執行集中部署與live。
- 本次文件整理完成，不等於每個任務的設計已審定或工程完成。上表基線來自 main 已提交程式／既有文件收據，沒有新的runtime驗收。
- 每次只執行使用者指定任務／階段；未指定階段時按該任務四階段指示完成可做範圍。遇跨任務集中部署，將部署及live驗收記為 `DEFERRED_TO_SEQ-04/08`，不是PASS；其餘前置交付完成即可往下一順序準備，不造成循環等待。
- SEQ-04結清SEQ-01…04；SEQ-08結清SEQ-05…08。測試驗收分部署前離線／Release與部署後真實驗收，不能在未部署時假稱live PASS。
- 記錄格式：`任務｜文件設計狀態｜程式狀態｜測試狀態（offline/live）｜部署狀態｜SHA/證據｜下一階段`。只在此維護active狀態；Operations保存收據。

### SEQ-05 四階段紀錄（2026-10-25，真資料收據與離線開發）

`SEQ-05｜文件設計=REVIEWED／規格與差異回寫｜程式=PARTIAL（RV-02月末樣本缺值診斷修復、RV-04單一卡片嚴格投影模組與targeted tests；批次producer／正式分類／API／UI未接）｜測試=RV-03既有Dev唯讀 #40166649960 INPUTS_READ_WITH_GAPS、OFFLINE_CI #40167057471 PENDING｜部署=DEFERRED_TO_SEQ-08｜本項剩餘=有界EPS/BVPS/PE/PB補足與Fact Pack／API接線，不升級狀態PASS。`

[真實Dev讀回 #40166649960](https://github.com/tommylin15/janus-omniforge/actions/runs/40166649960)：2330 Core245筆/financial54筆，獨立可觀測月末PE=12、缺四季單季EPS；2882 Core18筆/financial35筆，可觀測月末PB=1、缺正BVPS。兩檔皆`status=missing`、`lower/mid/upper=null`，`janus-ingestion-core`模板不變、資料異動0。現有探針對普通股與金融業採顯式symbol設定，正式industry/security-type讀端仍須驗證；此收據不能冒稱估值價格可發布。

本輪最小diff範圍：`packages/valuation_range.py`、`tests/test_valuation_range_inputs.py`、`packages/valuation_reference.py`、`tests/test_valuation_reference.py`、`.github/workflows/analysis-product-ci.yml`、`doc/spec/valuation-range.md`；未修改existing four model Registry、Owner private資料、GCP Scheduler或既有API。詳見[Valuation SPEC 的SEQ-05接手與最小補資料路徑](spec/valuation-range.md#seq-05-部署前差異與真實樣本收據2026-10-25)。

### SEQ-04 四階段紀錄（2026-10-25，進行中）

`SEQ-04｜DOC=REVIEWED／CODE=COMMITTED／RELEASE_AND_SCHEDULER_DEPLOY=PASS（#40163729460、#40163927739）／IMMEDIATE_BOUNDED_READONLY=PASS（備份#40164713512、Stage／GCS／API／PG／Private retention #40165435450）／LIVE=PARTIAL（Stage及retention apply / 新cron自然tick / owner正向 / catalog current pointer 均未驗）｜唯一下一入口=SEQ-04／收斂已證實的有界apply與下一自然tick，不阻塞可獨立進行的SEQ-05前期設計或開發`。

收據判定：Release、migration069／VM、PG隔離還原、四Job 8/8、API 100% 已通過。歷史切換 #40162679929 `permission_denied` 及回復，之後 #40163099454 精確查出 target SA actAs NOT_GRANTED；使用者於Cloud Shell僅授權 `janus-ci` 對指定 `janus-ingestion-scheduler` SA 的 `roles/iam.serviceAccountUser` 並讀回。重新觸發 [#40163729460](https://github.com/tommylin15/janus-omniforge/actions/runs/40163729460) 最終SUCCESS，receipt: `phase=PASS`、`previous_cron=30 * * * *`、`new_cron=30 */2 * * *`、`scheduler_enabled=true`、`target_identity_unchanged=true`、`gcp_new_resources=0`；獨立GCP [#40163927739](https://github.com/tommylin15/janus-omniforge/actions/runs/40163927739) 再讀到同值、target hash一致、IAM update/actAs=GRANTED。最近15次Controller均終態，但全部為切換前記錄，不是新自然tick。剩餘有界驗收維持NOT_VERIFIED，不增添獨立排程。

### SEQ-04 即時有界驗收收據（2026-10-25；不等於全系統live PASS）

- [備份／Controller #40164713512](https://github.com/tommylin15/janus-omniforge/actions/runs/40164713512) workflow SUCCESS。executor timer active/enabled、舊direct timer inactive/disabled；最近六筆每日備份succeeded，2026-10-25最新備份40,595,834 bytes。Control中同日ledger-backup 00:30 occurrence仍running、02:30另一筆succeeded；每日備份狀態與排程occurrence不可混為同一PASS。
- [完整有界唯讀 #40165435450](https://github.com/tommylin15/janus-omniforge/actions/runs/40165435450) workflow SUCCESS，分項：Stage 48h依PG有效lease17及完整GCS inventory452物件得到 `PASS_DRY_RUN`、計畫220物件／42,538,112 bytes、held_active_objects0，實刪0；Private備份retention `DRY_RUN_PASS`：8 daily／2 monthly／0 weekly，計畫刪1 daily、其餘0；最近8份PG daily均succeeded，但8筆retention_status為pending，**不能算清理已apply**。23xx/28xx公共OHLCV各有真資料；API buildSHA/health 200，Owner/Admin未登入皆401；Core/Mart/Private bucket之Iceberg metadata文件各可讀，但沒有驗證PG catalog指到的current snapshot。兩個較大bucket只完成有界metadata樣本，不能冒充完整bucket inventory。
- Live發現：2026-10-25 02:30、07:30 ingestion occurrence為FAILED，歷史failed收據橫跨SEQ04部署前（不能直接證明目前新版失敗）；12:31 analysis-queue仍標running。需以原工作ID／live lease／Job執行收據核對，不大量重派、不刪記錄、不當作已成功。
- 仍未驗：Stage按原worker fence有界generation刪除與bytes讀回；Private每日retention實際apply／週副本創建及PG欄位轉終態；Iceberg catalog current pointer；Owner／Admin真正登入與snapshot/UI一致性；首次新版Scheduler自然tick及新版02:30 ingestion鏈。既有GCP兩小時配置仍PASS，不重新建Scheduler，不等一整天才開始其它獨立工作。

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
