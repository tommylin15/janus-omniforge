# Janus 最新驗收證據索引


### SEQ-04 本週 weekly 補建及舊備份 occurrence 修復（2026-10-25 16:08 Asia/Taipei；PASS）

- **本週不可變 weekly=PASS**：[GitHub #40175398373](https://github.com/tommylin15/janus-omniforge/actions/runs/40175398373) `completed/success`；12項相關測試通過，透過既有WIF、固定GCS source generation與目的 `ifGenerationMatch=0`，將已成功的 `2026-10-19` daily 備份建立為 `weekly/2026-10-19.dump`。**新建1份、30,872,328 bytes**；新週副本逐位元SHA-256與PG `control.ledger_backup_requests` 原daily大小／checksum完全一致，目的generation `1792915700206005`。未新建daily或執行pg_dump、不覆寫或刪除任何備份。此為**2026-10-19週的真實副本**，不是預先製造下一週 `2026-10-26` 的備份；下週自然首次成功仍獨立待驗。
- **舊00:30 occurrence=PASS**：同run只對 `ledger-backup/2026-10-25/00` 作一次CAS，預先核對原 `running`、本日 `control.ledger_backup_requests` status `succeeded`、retention `succeeded`、有效size/SHA/completed；`cas_updates=1`，同交易補寫 `control.batch_event_outbox` **1筆事件**，實際PG回讀 `status=succeeded`。不是靠另一筆02:30的成功冒充00:30，也沒有重跑備份。
- 失敗嘗試 [#40175288842](https://github.com/tommylin15/janus-omniforge/actions/runs/40175288842) 原因是該Runner未裝pytest，**未進入任何GCP寫入**；修正測試環境後 #40175398373 PASS。由於本次有條件修復已驗PASS，該舊pending occurrence與本週缺失的weekly副本**不得再列為active blocker**。
- 邊界：保留單一兩小時Scheduler、既有VM executor及Dev Jobs，沒有新GCP資源、沒有Owner資料修改、沒有GCS刪除。本輪後SEQ-04仍只因**2026-10-26 02:30首次新版自然 ingestion→Core→screening**和 **2026-10-26新週自然首次備份**以及需本人授權的Owner/Admin正向UI驗收而保留 `LIVE_PARTIAL`；未到期時點不得造PASS。




### SEQ-04 Runtime 有界實作收尾收據（2026-10-25 15:35 Asia/Taipei）

- **Stage 48h實刪與讀回 PASS**：[finops #40172644132](https://github.com/tommylin15/janus-omniforge/actions/runs/40172644132)；實刪223件／42,540,741 bytes、Stage完整庫存604→381件及73,943,009→31,402,268 bytes，與generation-fenced計畫完全一致。獨立後驗[read-only #40173298619](https://github.com/tommylin15/janus-omniforge/actions/runs/40173298619) 再取得381件／31,402,268 bytes、到期候選0件／0 bytes，確定不是只有Workflow宣稱成功。
- **Private daily retention實刪／PG終態 PASS**：[finops #40173273728](https://github.com/tommylin15/janus-omniforge/actions/runs/40173273728)，獨立`phase=private`（**Stage不重派**）、38項受影響回歸測試與release lease gate通過；以現役VM executor既有程式先dry-run後generation條件受控apply，精確刪除**daily1份／26,044,882 bytes**，daily8→7、275,489,335→249,444,453 bytes；monthly2份／417,396 bytes不刪，weekly原有0份不捏造創建。10/25 `control.ledger_backup_requests` backup `succeeded`、retention狀態**`succeeded`**（同run apply後SQL讀回）；其餘較舊7筆retention `pending` 是歷史待整理狀態，不改寫成成功。
- **PostgreSQL current catalog→GCS metadata實際讀回 PASS**：同[run #40173273728](https://github.com/tommylin15/janus-omniforge/actions/runs/40173273728) 以PG SqlCatalog metadata_location為起點，逐筆對應GCS當前metadata及current snapshot；Core20/20 valid、Mart22/22 readable（18有current snapshot、4張合法空表）、Private34/34 valid，**合計76/76、failed=0**，`private_names_exported=0`。這項與先前隨機GCS metadata GET不同，已正式證實catalog current pointer。
- **調整不重做的已驗項**：唯一Scheduler `30 */2 * * *` Asia/Taipei與14:30自然Controller execution #40170098722 PASS；四個既有Jobs/API/migration069/VM與PG隔離還原沿之前證據。此次新增GCP資源0、Scheduler改動0、Owner mutation0、Stage只執行一次、Private單獨重試直到有精確收據。
- **限定例外，不得偷換FULL_PASS**：首次改版後**2026-10-26 02:30**自然ingestion→Core ready→screening尚未發生，屆時單次查對不延伸成多日觀察；原weekly歷史副本0份，下一個有效週副本創建仍待下次排程並讀回；10/25舊00:30 `ledger-backup` occurrence仍標running，雖02:30同日有另一筆succeeded，不作無證據終態修復；Owner／Admin正向登入與workspace快照／UI `AUTH_REQUIRED／NOT_VERIFIED`，匿名401不替代。**本次現在可做的有界清理與catalog項已`PASS`；SEQ-04原定完整產品／下一自然時點及授權條件維持`LIVE_PARTIAL`，不虛報`FULL_CLOSED/PASS`，亦不阻塞SEQ-05等獨立工程。**

### SEQ-04 Stage 48h 真實刪除／generation 讀回（2026-10-25；PASS）

- [有界實際執行 #40172644132](https://github.com/tommylin15/janus-omniforge/actions/runs/40172644132)：`38 passed` 的受影響回歸測試與 release lease gate PASS；以既有 `janus-ingestion-core` 單次 `stage-only-apply`（execution `janus-ingestion-core-9dd52`、Cloud Run operation `22100366-9310-4635-9a79-c909b0de9425`）真實清理。完整Stage inventory **604物件／73,943,009 bytes**；當下有效PG lease數0，dry-run計畫**223物件／42,540,741 bytes**；generation-fenced Worker terminal success，重新完整列舉 **381物件／31,402,268 bytes**，實際減少 **223物件／42,540,741 bytes**，與計畫完全一致，**Stage 48h apply + bytes/readback=PASS**。前次 #40165435450 的候選220件是較早時點，不再拿它當實刪數字。
- 該workflow整體 `failure` 不代表Stage失敗：Private備份 retention 當時dry-run仍有8 daily／2 monthly／0 weekly，計畫刪1 daily；獨立VM調用exit 1，`BLOCKED_VM_RETENTION_EXECUTION`，**Private實刪在該run未獲成功讀回**。後續只修Private，絕不重派本次已成功Stage作業；此行保留為歷史單項收據，後續Private若成功另附新run。

### SEQ-04 14:30 新兩小時自然Controller交叉讀回（2026-10-25；PASS）

- [GitHub Read-only #40169964904](https://github.com/tommylin15/janus-omniforge/actions/runs/40169964904) GCP Scheduler `lastAttemptTime=2026-10-25T06:30:00.865962Z` 且Scheduler executions 06:30有兩筆INFO，但首次CLI executions list未找到新Controller，當時仍標NOT_VERIFIED，未用trigger取代產物。
- [雙路交叉讀回 #40170098722](https://github.com/tommylin15/janus-omniforge/actions/runs/40170098722) completed/success；Scheduler `30 */2 * * *`、Asia/Taipei、ENABLED、14:30自然Attempt；Scheduler execution日誌HTTP 200；Cloud Run V2 REST `janus-batch-controller` execution create UTC `2026-10-25T06:30:00.943455Z`、start `06:30:16.601901Z`、complete `06:31:52.439218Z`，`Completed=CONDITION_SUCCEEDED`。故 **自然Controller tick=PASS**，CLI首輪因列表形態未顯示而漏判，保留此交叉證據。
- **不延伸為市場收取成功**：下一個新版每日02:30 ingestion自然時點為2026-10-26 02:30 Asia/Taipei，需另以Controller occurrence→Cloud Run ingestion execution→Stage/Core日期與產物讀回判斷；2026-10-25 02:30為較早歷史failed，不能當新版結果。Stage/Private有界apply、Iceberg current pointer、Owner/Admin正向仍各自待驗；整體SEQ-04保持LIVE_PARTIAL。


### SEQ-04 集中部署結案判定（2026-10-25；LIVE_PARTIAL／NOT_CLOSED）

- **已獨立PASS**：SEQ-01～03既有離線證據、SEQ-04 Release／migration069／既有VM與隔離PG還原／四個Dev Jobs與API切換、單一Cloud Scheduler兩小時配置、2026-10-25 14:30自然Controller tick（#40170098722），以及 #40165435450 的 Stage／Private **dry-run**、公開API及有界GCS metadata GET。自然tick只需此一次，勿因未做長期觀察阻止其他工項。
- **仍阻止整項結案的實際未驗項**：Stage 48h generation-fenced apply及objects/bytes前後讀回（前次預覽220物件、42,538,112 bytes、實刪0）；Private備份retention apply及immutable generation／保護副本／PostgreSQL `retention_status`終態（前次預覽刪1份daily、實刪0）；PG Iceberg catalog current pointer→現役Core／Mart／Private snapshot實體；00:30 running備份occurrence與相關Job狀態；新版首個2026-10-26 02:30市場收取→Core ready→screening實際資料鏈。原有歷史failed不得當新版成功或失敗。
- **授權限制**：Owner／Admin正向登入、Owner workspace snapshot與UI如缺本人授權session標 `AUTH_REQUIRED／NOT_VERIFIED`，匿名401僅代表拒絕保護，不能列正向PASS。無證據時不可把原定live驗收的缺口包裝為已結案；但不需要新增Scheduler、Job、付費資源或多日自然觀察。本次只更新GitHub文件與判定，未進行GCS實刪、VM retention執行或GCP設定變更。


此頁只索引已取得的有界runtime收據，狀態與唯一後續清單以 [TODO](../todo.md) 為準；本次更新文件及結案判定，沒有新增GCP變更或觸發工作。


### SEQ-04 立即有界資料鏈驗收（2026-10-25）

- [備份／控制器稽核 #40164713512](https://github.com/tommylin15/janus-omniforge/actions/runs/40164713512) `completed/success`：現役VM `janus-ledger-backup-executor.timer` active/enabled、退役 `janus-ledger-backup.timer` inactive/disabled。2026-10-20…25 六筆daily PG備份均succeeded，10/25日期最新檔40,595,834 bytes；同日ledger-backup的00:30 batch occurrence仍running且02:30另一筆succeeded，未宣稱原00:30 occurrence PASS。
- [即時只讀 #40165006883](https://github.com/tommylin15/janus-omniforge/actions/runs/40165006883) 初次readback：Stage有效PG lease 17筆，但自訂ID格式檢查過窄而被誤擋，無資料刪除。修正只要求有界數量，不改正式 `clean_stage` 及Stage有效租約判定。
- [完整有界只讀 #40165435450](https://github.com/tommylin15/janus-omniforge/actions/runs/40165435450) `completed/success`：48h Stage預覽以實際PG有效lease17與**完整**Stage inventory 452物件/73,436,870 bytes呼叫現行 `clean_stage(..., apply=False)`，得到 `PASS_DRY_RUN`；220個符合到期條件，合計42,538,112 bytes，held_active_objects 0；**實際刪除 0，generation-fenced apply未執行**。不得將220或42.5MB當成已釋放空間。
- 同run重用現有Private retention程式的正式 `dry-run`：daily8份/275,489,335 bytes、monthly2份/417,396 bytes、weekly0份；7/4/6策略計畫淘汰**1份daily、0 weekly、0 monthly**，最近daily年齡10.87小時符合36h，`DRY_RUN_PASS`，實刪0。PG `control.ledger_backup_requests` 最近8筆 `status=succeeded`、`retention_status=pending`；需原VM executor後續apply並寫回PG終態，不以備份成功掩蓋retention尚未成功。
- 同run成功有界列表Core 1,500、Mart 935、Private 1,500個warehouse物件，三個bucket皆實際GET／解碼Iceberg `.metadata.json`（含format-version/table-uuid）成功；Mart樣本完整，Core/Private因頁數上限僅部分。**PG Iceberg catalog current pointer／current snapshot對應GCS實體尚未驗證**，不能將任一舊metadata可讀當current保證。未輸出任何Private物件名稱或Owner資料。
- 同run目前API的health與buildSHA均200且SHA符合 `032871a38b1dffd11c7bf0cc833563c0c3091841`，2330與2882公共OHLCV各有真資料列，Owner與Admin未登入端點各回401；真正Owner/Admin登入、snapshot／PnL／watchlist與UI仍需Owner授權驗收。沒有資料寫入、Job派送或Stage/Private GCS刪除。
- 明確殘項：control.batch_occurrences 10/25 02:30及07:30 ingestion為FAILED（是切換前歷史，不推論新版本已失敗），12:31 analysis-queue為running；須按實際lease及execution收據核對，而非盲目重派。（原收據當時尚未確認的）新cron第一次自然tick、下一個新版02:30收取、Stage/Private有界apply及generation/bytes讀回、current Iceberg指標、Owner/Admin正向驗收仍未完成。**本輪完成的是所有可直接進行的唯讀驗收，不代表整體SEQ04 CLOSED**。



### 2026-10-25｜SEQ-04 單一Scheduler兩小時切換成功（DEPLOY PASS／LIVE PARTIAL）

- 使用者於Cloud Shell只對既有 `janus-ingestion-scheduler@gen-lang-client-0593591102.iam.gserviceaccount.com` 設定 `roles/iam.serviceAccountUser`，member為 `janus-ci@gen-lang-client-0593591102.iam.gserviceaccount.com`；由Owner畫面顯示 `add-iam-policy-binding` 與 `get-iam-policy` 綁定讀回成功。專案層級 `cloudscheduler.jobs.update` 已於先前授權；不新增新的Scheduler、Cloud Run Job或Service Account。
- [受控Scheduler切換 #40163729460](https://github.com/tommylin15/janus-omniforge/actions/runs/40163729460) `completed/success`，原本Writer lease、在途Job terminal fence、pause→schedule-only PATCH→resume及rollback已沿用。封存receipt：`phase=PASS`、`previous_cron=30 * * * *`、`new_cron=30 */2 * * *`、`scheduler_enabled=true`、`target_identity_unchanged=true`、`gcp_new_resources=0`、`target_sha256=5b647622b2abbcecbbb1e74e0e9134ac60155d41a0f209115ceae0271aa4b3ea`。目的來源SHA固定 `032871a38b1dffd11c7bf0cc833563c0c3091841`，上游GHCR Release／四Job／API無須重部署。
- [獨立GCP只讀回驗 #40163927739](https://github.com/tommylin15/janus-omniforge/actions/runs/40163927739) `completed/success`，live `janus-ingestion-daily` 為 `30 */2 * * *`、`Asia/Taipei`、`ENABLED`，HTTP target hash與原基準相同；由`janus-ci`執行 `testIamPermissions` 兩項 `cloudscheduler.jobs.update` 及指定target SA `iam.serviceAccounts.actAs` 均 `GRANTED`。讀取最近15筆Controller executions皆終態，但最後一筆為UTC `2026-10-25T04:30:01`（台灣12:30），仍屬切換前、**不可當新兩小時自然觸發PASS**。
- **此段為切換後早期歷史待驗狀態，已由上方 #40170098722 結清自然Controller tick**：原預定時點2026-10-25 14:30 Asia/Taipei（UTC06:30）；SEQ-04 WI其餘已指定的有界Stage48h dry-run/有界apply與generation bytes、GCS/Iceberg current、Owner snapshot及UI、備份保留與Admin視圖，依實際runtime證據分別完成。暫不宣稱SEQ-01～04整體CLOSED，亦不新增第二排程、額外自然等待期或假收據。
- **權限收尾提醒**：現有target SA資源綁定Service Account User具 `actAs` 能力，超出本次僅修改cron；若未來不再由CI更新此Scheduler，應由使用者核准後評估撤銷。撤銷不影響已成功的cron設定，但未授權前不自行修改IAM。


## 歷史收據

- [截至 2026-10-25 整理前的完整收據](../archive/document-cleanup-2026-10-25/operations-and-testing.md)：保留歷次失敗、恢復、來源 SHA 與範圍，不改判歷史結果。
- [更早的 2026-10-15 基線](../archive/documentation-baseline-2026-10-15-operations-and-testing.md)。

維護方式：同一事件的新結果取代本頁摘要時，把完整舊收據移到 archive 並留下連結；不要每次重新追加全部結案歷史。
