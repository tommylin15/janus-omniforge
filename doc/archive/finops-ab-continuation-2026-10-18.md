# FINOPS-AB 接續證據（2026-10-18）

## 最新部署與compaction（尚未實刪）

- 同源 `dead98d35abc8c38448791494fb97d99f37c660b` [Jobs #39099136306](https://github.com/tommylin15/janus-omniforge/actions/runs/39099136306) PASS，四Jobs兩輪共8/8 canary，reversible d8a57a基準已驗證、設定未漂移、Scheduler恢復。中途#39098978307因另一工作線文件push令source過期，在取得lease前停止；以最新main重新dispatch，未繞鎖。
- [Compaction #39099324026](https://github.com/tommylin15/janus-omniforge/actions/runs/39099324026) PASS，execution `janus-ingestion-core-bt97h`，9表改寫796,583 bytes，audit disabled。Core bucket live inventory 8,437／219,508,719 bytes →8,682／222,685,481 bytes，小檔8,425→8,670；新增替代檔，沒有orphan刪除或snapshot過期，不宣稱已減量。
- 真實bucket政策：Core與Mart versioning enabled、softDelete=0；Core defaultEventBasedHold=true。官方JSON API指出只用ifGenerationMatch不保證移除實際version，因此修正DELETE同時帶generation；Core維護明確opt-in，僅已驗證generation可清event hold，保留temporary hold與metageneration防競爭。小檔入口另GET精確generation確認404；75項targeted PASS，仍待新完整Release/部署。此前477 live objects下降不等於實體版本／billable bytes已釋放，不重播該清單。

## 發布重試

- #39098770305仍在變更前FAIL／PREFLIGHT_BLOCKED_NO_MUTATION，已恢復及釋放。實際唯讀REST證據：retired research Job GET404，execution list HTTP200 `{}`（無executions、無pagination）。修正只容許該已退役名稱Job404＋execution404或精確空物件；有執行／下一頁仍擋，現役Job404仍擋。

- Jobs #39098547758 FAIL／PREFLIGHT_BLOCKED_NO_MUTATION，四Job原設定與Scheduler ENABLED讀回相同，lease已釋放。退役research Job經execution fence雙404允許略過，但config snapshot仍要求存在；已將同樣雙404限定套用到設定快照與恢復，存在時仍保護，不豁免任何現役writer。71項targeted回歸PASS；不是已部署或實刪。

## 最新唯讀盤點（尚未刪除）

- [#39098235692](https://github.com/tommylin15/janus-omniforge/actions/runs/39098235692) SUCCESS，source `93b6a11cc6a42354e762b370e8865a553814a831`，既有固定digest Jobs執行唯讀current-only盤點，零資料寫入。Mart observed `2026-10-18T04:48:08Z`、Core `04:49:41Z`；catalog pointer／Job config讀回相同。
- Core可清理 **6,428 objects／104,572,240 bytes**、舊snapshot **502**；Mart **55／378,759 bytes**、舊snapshot **32**。合計 **6,483／104,950,999 bytes（100.09 MiB）／534舊snapshot**；32已包含在534中。全部候選小於1MiB。
- 已扣current snapshot必要檔、current metadata／metadata log與未滿7日檔案；只計warehouse Iceberg檔案，不含Stage／私有資料。這是compaction前投影，不是實刪收據，也不是billable savings；GCS hold／實際delete權限仍待驗證，後續寫入及compaction可能改變數量。
- 同來源auth boundary [#39097809505](https://github.com/tommylin15/janus-omniforge/actions/runs/39097809505) SUCCESS；完整Release Python **1452 passed、2 deselected**。正式Jobs rollout仍待執行。

## 本輪接續：current-only snapshot 決策與實作（未部署）

- 使用者明確取消歷史引用保護並選擇「只保留目前snapshot；其餘可清理」，權威見 [決策](../decision-2026-10-18-current-only-snapshots.md)／PROJECT_RULES §1.6。先前本頁記載的24小時／named refs／external fence／PG欄位讀權 blocker 已被此決策取代，不代表舊驗收曾PASS。
- Lease成功canary [#39095964666](https://github.com/tommylin15/janus-omniforge/actions/runs/39095964666)，source `d5c08b82fc3cea8776de02837cb10a6228c1c854`：ABSENT→CLAIMED→OWNED→RELEASED→ABSENT，零GCP寫入。先前失敗run取得lease前main已新增workflow commit；新guard在過期source建立tag/ref前停止，以current main新dispatch驗證成功，未擴token權限。檢查與取得間仍有競爭，原子ref與owner readback持續fail closed。
- 同次 selective CI #39095964784 FAIL，3個workflow契約案例因API測試環境未裝PyYAML；已將專案既有6.0.3加入requirements-dev，不停用檢查。此處保留FAIL，後續CI另證。
- 新增估值同月跨股合併；source／Stage／Core reader／Core write／serving分段CPU與wall，以及DuckDB merge／data commit readback timing，明確不是Cloud Run billable或GCS歸因。
- 本機真實Iceberg對照：兩股同月逐筆寫入為2個data files／2 snapshots，合併為1／1，讀回逐列相同；重播不增加snapshot或file。另一真實Iceberg回歸證明舊tag／branch被移除、非current snapshot過期，current ID與資料完全不變；本機證據不冒充dev實刪。
- 最新涵蓋supplement、DuckDB/Iceberg、compaction、retention、controller與lease／workflow回歸 **171 passed**（43.63秒，2個本機ADC quota警告）。Core／Mart停止因publication／研究引用保留歷史snapshot；orphan刪除新增generation清單讀回，仍保留7日與catalog pointer防競爭。
- 尚需本輪同源完整Release、受控Jobs rollout、週維護生效及真實compaction／expiration／objects・bytes實刪讀回。舊477 objects不重計；未量測不填節省百分比。
- source `8e7a455cacb01b4c5d03f604ad51abb47e2956c6` 完整Release #39096898049、compaction CI #39096897766 與selective #39096897726 均因兩個Stage/Core舊留存政策斷言FAIL；資料契約 #39096897727 SUCCESS。已將兩個測試改成current-only與current metadata路徑保護，Stage/Core本機23 passed（tempfile明確放專案.tmp，避開Windows sandbox暫存路徑限制），未部署、不把原FAIL改寫成PASS。
- source `dead98d35abc8c38448791494fb97d99f37c660b` compaction CI #39097205701／selective #39097205661 SUCCESS；完整Release #39097205867 的Python／Flutter gate已SUCCESS，GHCR四映像建置中，尚不當作完整Release PASS。清理入口補上同一runtime writer concurrency／原子lease／Scheduler pause・restore／terminal fence；明確未知執行不釋放租約，另24項targeted checks PASS。
- 同來源完整Release [#39097205867](https://github.com/tommylin15/janus-omniforge/actions/runs/39097205867) 最終所有gate／四映像／匿名digest驗證SUCCESS；[0%候選 #39097582970](https://github.com/tommylin15/janus-omniforge/actions/runs/39097582970) SUCCESS，正式100% baseline未切換。candidate request由Git index提交本次收據，原工作區未提交內容原樣保留。尚需同源auth boundary、Jobs rollout與清理讀回。

狀態：**PARTIAL；不是部署或清理結案**。本次輸入 main `4b1785603aaa23005701f1e72b3377fed1070419`；FINOPS-C、DRL-01、ADMIN-V2 不納入施工。本機既有 ADMIN 檔案與 candidate request 保留、不提交。

## 程式與驗證

- `data_supplement.run_backfill` 同月份 OHLCV 跨股票共用一次 Core write；維持既有最多50股、已接受列、每筆 Stage provenance、部分來源失敗與 commit 失敗回報，不變更既有 source/DQ/PIT/自然排程。
- 新回歸用兩股、兩月證明三份有效來源只有兩次寫入，第一月保留兩份獨立 provenance；一股來源缺失仍 partial；第一月 commit 失敗則記錄該月兩股失敗，第二月仍繼續，Stage 不標全成功。
- 本機 `test_data_supplement.py`、`test_duckdb_iceberg.py`、`test_batch_controller.py`、`test_iceberg_compaction.py`、`test_data_retention.py` 共 **88 passed**（118.34秒）；最終新增 commit 失敗案例另 **1 passed**。既有整合回歸涵蓋重播無新增／更新、合法財報版本、snapshot／retention 防護。初次本機缺 `pytz`，僅安裝至忽略目錄 `.tmp/finops-test-deps`，未修改產品依賴。
- 這是月批 OHLCV 合併，不代表 financials／valuation 全 dataset 合併、A2 各階段 CPU/GCS 歸因或整體 B2 已完成。財報與估值維持既有每股歷史批次。

## 最新唯讀 runtime

本次程式輸出 SHA `3db22b8deeea220306875ebb3f6e71c85939c012` 已推送 main；同源 [selective CI #39095433136](https://github.com/tommylin15/janus-omniforge/actions/runs/39095433136) 與 [資料契約 CI #39095433116](https://github.com/tommylin15/janus-omniforge/actions/runs/39095433116) 均 completed/success。這是 targeted／selective 驗證，不是 full Release、GHCR 發布或 live gate。

以既有本機 GCP identity 唯讀描述四個 dev Job（未派送、未寫入資料或設定），實際 image 均與 `ops/ghcr-jobs-rollout-request.json` 的 `d8a57aa57198e0f383a37125e6b94eb392abe717` rollback baseline 相符：

| Job | GHCR sha256 digest |
|---|---|
| ingestion／controller | `073d7a200a05464542776721d3b3edbc5f6ce438e24e79eb2d39dd24d09ef1d7` |
| Mart | `6a33d77cf9ee55d70fcb62625bd339c377c7b20fe498609a5016d34441df2dc1` |
| Private | `ae91a2f478893cc43840284ca096b0298c6b357f44196d0e818c72c099655d97` |

Scheduler `janus-ingestion-daily`：`ENABLED`、`30 * * * *`、`Asia/Taipei`。這只證明現行喚醒，不證明新週維護旗標已生效。

GitHub main [selective CI #39093581698](https://github.com/tommylin15/janus-omniforge/actions/runs/39093581698) SUCCESS，只對本次輸入版本有效，非新修改或完整 Release gate。

## 真實 blocker 與恢復入口

- [Jobs rollout #39090724732](https://github.com/tommylin15/janus-omniforge/actions/runs/39090724732) 重新確認 `completed/failure`；allowlist 錯誤為 `bounded_release_lease_atomic_lease_claim_rejected_or_unavailable_ref_http_403_integration_permission`。目前 GitHub `refs/tags/janus-ghcr-deploy-global-v1` 查無 ref；不是被占用，不應刪租約或用本機 token 代替 Actions 繞過 fence。失敗 run 已宣告 Contents write，仍須查明 Actions integration／repository policy 的 ref 建立拒絕；不自行擴權。
- D06 publication `core_snapshot_id` 欄位讀權與完整外部引用 fence，仍沿原證據維持 BLOCKED／PARTIAL；本次不重掃既有62／71／96／495份 JSON、不重刪477個物件、不偽造新鮮完整 fence。
- 權限問題解除後：協調 DRL／ADMIN 共用發布來源 → 同 SHA full Release／GHCR → 原子 lease → 受控四 Jobs／rollback → 明確週維護設定與合法來源驗證 → 新鮮完整 retention fence／有界 dry-run 與合法 apply → Core／PG／Mart／Private 讀回。原兩天量測仍 CANCELLED_BY_USER；短窗無可歸因數值時節省百分比 UNKNOWN。
