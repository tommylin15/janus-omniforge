# Janus 最新驗收證據索引

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
