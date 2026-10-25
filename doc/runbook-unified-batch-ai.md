# 統一批次：交接 AI 指令與驗收 WI

> 2026-10-25操作路由：依[唯一TODO](todo.md)與[SEQ四階段AI卡](execution-cards/sequential-delivery.md)逐項啟動。本WI是共用程序，不是額外待辦或自動開工授權。SEQ-04執行基礎批次／快照／備份的部署驗收；C節四模型、完整報告與產品UI條件由SEQ-05…07準備後在SEQ-08執行。不得在SEQ-04冒稱四模型產品已驗。四模型本版全部正式上線，研究調校延至2027 Q1。

本輪狀態：文件／程式交付；以下命令**尚未執行**。不要引用舊PASS替本輪背書。
你是接手的Janus工程AI。直接在 `tommylin15/janus-omniforge main` 完成有界測試→必要修正→部署→runtime驗收，不新增branch／PR，不新增付費資源／IAM。先讀PROJECT_RULES、統一批次SPEC與本文件；使用 recovering-stuck-ci-deploys。
此WI描述後續任務，不代表本輪已觸發或授權跳過任何真實權限阻擋。

## A. 固定版本與離線測試

1. `git fetch origin main`，記錄 `git rev-parse origin/main`、工作目錄差異；不要覆蓋別人的變更。
2. 依repository現有lock安裝測試依賴；不得把缺套件誤判為程式PASS／FAIL。
3. 執行 `bash scripts/test-unified-batch.sh`。這支腳本只跑離線測試及shell語法，不觸發GCP。
4. Flutter於 `apps/user_app` 執行 `flutter test test/admin_batch_dashboard_test.dart test/admin_overview_batch_test.dart`。
5. 有失敗先按新SPEC判斷是程式錯誤或舊fixture；不刪有效assert、不降低Owner／金額／去重／generation安全。
6. 寫入真實測試數量、失敗與修正SHA。作者只編輯過測試來源，未執行；不得假設舊fixture已全部吻合。

必要案例：
- 偶數小時:30、台北/UTC換日、週末／假日；舊supplement/mart pending被superseded；不重派running／ambiguous。
- 私人10／18依市場分析、22獨立補償；原始交易／觀察設定即時讀回。
- 收取順序為補缺→正常Core ready；真實source failure為partial/failed，既有歷史coverage不足不成額外稽核gate。
- market-cycle無每股Job、最多8次queue claim且900秒後不再開始下一項；子步驟本身的HTTP／DB timeout仍有效。未處理完的queue保持待辦，不能聲稱queue已清空。
- Snapshot同owner同內容同ID，不複製全交易歷史；`GET /api/v1/me/workspace-snapshots?valuation_date=YYYY-MM-DD` 必須認證，A不得讀B，查詢日期必要、最多200筆並標明可能截斷。
- 備份daily7／weekly4／monthly6；ISO跨年週一命名、每月首個成功副本不可覆寫；副本碰撞不可改寫daily dump及其hash。
- 清理最新daily超36h／generation drift／未知檔名／權限不足時不得刪；刪除上限3/1/1；備份成功、清理失敗分開。
- migration069重跑安全；Private新表沿既有Iceberg自建schema，須確認pipeline有既有create table能力，不自動grant。
- 四模型各自真實artifact／版本／feature順序／輸出；Event舊相容欄不被算成第五模型。若仍只有baseline，明列UB-02未完成，不宣稱四ML已上線。

## B. 部署前準備（不用 GitHub 業務批次）

1. GitHub只用版本管理及既有CI／image release；不要workflow_dispatch日常備份、清理、收取、報告或新增schedule。
2. 用既有部署lease／受控GCP通道保存：四個Worker與Controller目前immutable digest、同一Scheduler設定、VM目前三支備份程式及retention設定。
3. 唯一Scheduler名稱已有repo證據是 `janus-ingestion-daily`，位置 `us-central1`，project `gen-lang-client-0593591102`。先讀回URL應以 `jobs/janus-batch-controller:run` 結尾；不符合就停止切換並報真實差異，不猜測。
4. 不為取證重新掃描全歷史資料。檢查本次接線所需 schema、現役execution終態及有界備份清冊即可。
5. 先暫停同一Scheduler並等健康在途Job正常終態，不用強制取消來加速。保存原cron後才修改。
6. 以既有PG VM migration程序套用 `infra/postgres/migrations/069_backup_retention_status.sql`；只新增欄位，沒有Owner資料刪除。不得省略或在Controller新程式之前缺欄位啟動。
7. 從同一已測SHA把以下檔案上傳到既有VM的指定暫存路徑：

| repository檔 | VM暫存檔 |
|---|---|
| scripts/gcp/ledger_backup_executor.py | /tmp/janus-ledger-backup-executor.py |
| scripts/gcp/ledger_restore_verify.py | /tmp/janus-ledger-restore-verify.py |
| scripts/gcp/ledger-durability-dev.sh | /tmp/janus-ledger-durability |
| scripts/gcp/private_ledger_backup_retention.py | /tmp/private_ledger_backup_retention.py |
| ops/private-ledger-backup-retention-request.json | /tmp/private-ledger-backup-retention-request.json |

用既有 `gcloud compute scp ... --project=gen-lang-client-0593591102 --zone=us-central1-a --tunnel-through-iap`。
在VM執行 `sudo env GCP_PROJECT_ID=gen-lang-client-0593591102 GCP_ENVIRONMENT=dev bash /tmp/janus-ledger-durability install-controller`。
這是一次部署，不是GitHub備份批次。原direct backup timer應維持退役；若仍active，確認既有Controller backup路徑後停用舊timer，不能兩套同跑。
8. 更新既有ingestion、Mart、Private與Controller到同SHA的image；API也須更新以提供Owner snapshot讀取與Admin節奏。沿既有Job CPU／記憶體／並行上限，不為新流程提高資源。
9. Controller `FINOPS_WEEKLY_MAINTENANCE=true`、`BATCH_CONTROLLER_NOT_BEFORE=<本次切換UTC>`；worker不把 `JANUS_UNIFIED_COLLECTION` 固定在Job全域，透過Controller execution override限定一般收取。
10. 用既有部署lease修改同一Scheduler：
```bash
gcloud scheduler jobs update http janus-ingestion-daily \
  --project=gen-lang-client-0593591102 --location=us-central1 \
  --schedule='30 */2 * * *' --time-zone=Asia/Taipei
```
不得改target／identity或創新Scheduler；讀回後再resume。GitHub備份清理workflow已從main移除；確認沒有另一份外部cron再觸發同業務。

## C. 一次有界端到端驗收

以既有Dev資料選2330、2882、任一既有Owner持股／觀察股；不新增真實交易、不替使用者買賣、不全市場歷史補收。
- 確認一個收取occurrence：增量補收、Stage／Core資料日期與Serving可讀；同資料重跑不複製原始payload。
- 一個市場分析occurrence：screening→四角色／Fact Pack→產品投影；報告有實際資料日期／版本，不能把部分角色缺失當全部成功。
- 四模型輸入／artifact已備齊的前提若不成立，只補實際接線缺口；不改寫研究效用、不重跑取消的來源／PIT稽核。
- 一個私人occurrence：ledger version、觀察設定、快照ID、持股損益與UI一致；不存在行情保留missing/stale。
- CEO長文使用既有授權Gateway做一次按需測試即可；不啟動日常LLM新批次。
- 一個Controller backup request：VM dump及daily／weekly／monthly bytes讀回、DB status＋retention_status；從隔離DB驗證帳本／現金／觀察設定，絕不覆寫live DB。
- retention先dry-run後受控apply，讀回確切generation／objects／bytes與保護副本；週副本尚不足4份時不得造假補日期或強刪。
- Stage 48h dry-run確認有效lease保護；本次必要有界apply依既有授權。Core/Mart週維護重用已存在安全條件，不為驗收大量不可逆刪除。
- UI登入後看今日、個股四角色、唯一估值卡、持股、觀察、Admin批次；顯示資料日期／partial／上次成功，不以request成功取代產物可讀。
- 讀回一次新兩小時Scheduler觸發和Controller occurrence即可；不新增數週自然觀察門檻。

## D. 回復與結案

失敗時先確定queued／running／failed／ambiguous；未超timeout不重派。用原image／cron／VM script回復同一入口，migration新增欄可保留；不刪私人新快照或備份。
更新唯一TODO與Operations，逐項列CODE、TEST、DEPLOY、RUNTIME、UI的PASS／FAIL／NOT VERIFIED。只在上述既定有界條件通過後結案，不追加歷史稽核。
