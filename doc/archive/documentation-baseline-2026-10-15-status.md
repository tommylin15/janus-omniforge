> 歷史快照：2026-10-15 文件整編前。不是 active queue；相對連結已隨搬移校正。

# Janus Current Status

## 2026-10-15 FinOps Iceberg 專項續工（其餘產品 WBS 仍沿用暫停 checkpoint）

此段是使用者明確恢復「Iceberg 壓縮與受引用保護清理、CORE_RETENTION_FENCE_URI 引用盤點」**兩項**工作，不擴張至其他產品 WBS，亦未切換正式 API 流量。

- 已驗證既有四支 Jobs rollback／Scheduler 及完整 Canary [#38676820532](https://github.com/tommylin15/janus-omniforge/actions/runs/38676820532) PASS：8 canaries，舊映像不可變 digest。
- 一次性真實 `compact-nightly` [#38684081267](https://github.com/tommylin15/janus-omniforge/actions/runs/38684081267) PASS：9 個 Core tables，重寫 9,429,711 bytes，audit table 已重寫；Core GCS **8,162→8,225** live objects，1 MiB 以下 **8,157→8,218**，本次過期 snapshot／orphan 刪除 0。這是重寫成功，尚非 GCS 物件縮減成功。
- 新版 `retention-dry-run` [#38684726748](https://github.com/tommylin15/janus-omniforge/actions/runs/38684726748) PASS：74 個預計到期 Snapshot、403 個預計孤兒檔；Core GCS 8,225→8,226 是不可變報告產生，不是清除。一般 `retention-apply` 仍因無完整 `CORE_RETENTION_FENCE_URI` 被封鎖。
- 唯讀跨桶研究引用 [#38684978645](https://github.com/tommylin15/janus-omniforge/actions/runs/38684978645) 及存證 [#38685692925](https://github.com/tommylin15/janus-omniforge/actions/runs/38685692925)：Core execution manifests 60 份，外部識別的 Core IDs 6（已讀 Mart 69 文件、Research 77）；Research 19 個 oversized 未完整讀取，Private payload／PostgreSQL publication index 未全面驗證；**90 日以上 Core manifests 為 0**。僅保存 `PARTIAL_NOT_AUTHORIZED_FOR_DELETION` GitHub Artifact（SHA256 與 source generation），不生成假完整 deletion fence。
- 專用 `ops.batch_events_v1` 安全清理實作：不碰市場／財務／PIT／ML/Research，走 snapshot expiry + 7 日以上 generation-fenced orphan 刪除；相關 Iceberg CI [#38685350471](https://github.com/tommylin15/janus-omniforge/actions/runs/38685350471)、完整 GHCR Release [#38685404805](https://github.com/tommylin15/janus-omniforge/actions/runs/38685404805)、0% candidate [#38685839070](https://github.com/tommylin15/janus-omniforge/actions/runs/38685839070)、自動 OAuth boundary [#38686018183](https://github.com/tommylin15/janus-omniforge/actions/runs/38686018183) 均 PASS。四 Jobs 受控 rollout [#38686125420](https://github.com/tommylin15/janus-omniforge/actions/runs/38686125420) 與一次性 audit-cleanup [#38686337134](https://github.com/tommylin15/janus-omniforge/actions/runs/38686337134) 須依最新 runtime 終態讀回後才能判完成。
- GCS 方法級小時觀察 [#38685092023](https://github.com/tommylin15/janus-omniforge/actions/runs/38685092023) OBSERVED，已有 5 分鐘對齊的 `ReadObject`、`GetObjectMetadata` 小時彙整；但新舊窗口不等量且包含一次性 compact workload，成本節省率仍 `unknown`，不能以累積七日與一小時數字直接推算百分比。


## 2026-10-15 使用者要求暫停（PAUSED）

後續開發、部署、Job 派送及驗收均暫停；本次只保存既有程式進度、更新文件並同步 GitHub。正式 API 100% 流量保持原版本，固定 Preview／四 Jobs 已驗證來源為 `4d058c47ac62ad7328f9f7c0e9fcd4ef4f1ac7b1`。

費稅回補已 PASS：88 筆 append-only 更正，ledger 176→352，折扣0.4／profile3，8 筆持股股數不變。00697B 身分已補齊但仍缺價，完整持股損益仍 PARTIAL。TPEx 缺價修正、057 初始快照補建及 VM 隔離還原工具已保存原始碼及 targeted tests，尚未部署／執行。原備份 timer 仍 active，新 executor 尚未安裝。

恢復後仍依 1～5 順序接續；不啟動後置模型研究。本次不變更 Release 請求；費稅操作請求回到 ledger352 的唯讀 preview。詳細證據、測試與接手入口見 [暫停交接](pause-checkpoint-2026-10-15.md)。

## 2026-10-15 費稅 88 筆更正與 Mart352 PASS；00697B 缺價根因修正待整合發布

- 154 筆有效交易的 preview [#38679664257](https://github.com/tommylin15/janus-omniforge/actions/runs/38679664257) PASS，88 筆需更正。首次 apply #38680407739 因專用 workflow 缺 Pydantic，停在 pre-GCP 測試，沒有交易寫入；隔離測試依賴後在無 API 依賴環境 27 PASS。正式 apply [#38680770336](https://github.com/tommylin15/janus-omniforge/actions/runs/38680770336) **PASS**：append-only 更正 88 筆，ledger 176→352、券商 profile=3／折扣0.4，既有 Private Mart 重建與零待更正檢查通過。MCP 正向讀回 8 筆、ledger352、股數不變、全部商品身分 available；00697B 仍缺價，因此完整估值／PnL 尚未標 PASS。操作請求已準備回到新 checkpoint 的唯讀 preview，不重送 apply。
- 同來源四 Jobs rollout [#38676820532](https://github.com/tommylin15/janus-omniforge/actions/runs/38676820532) **PASS**，四 Job 各2次、8 canaries全部成功，Scheduler恢復、正式APItraffic不變。00697B 官方主檔 migration060 [#38679346846](https://github.com/tommylin15/janus-omniforge/actions/runs/38679346846) PASS。固定 Preview 公開 API [#38677467684](https://github.com/tommylin15/janus-omniforge/actions/runs/38677467684) 30/30、P50 65.1ms／P95 72.1ms／max6673.38ms；不是登入畫面或冷啟動 P95。
- 缺價根因：TPEx盤中日期分支漏匯入timedelta，加上14:30前一律拒絕EOD讀取，阻擋新持股的前一交易日官方收盤。已補匯入、只拒絕handoff前的當日資料、跨handoff重抓快取，保留PIT cutoff；65項整合 targeted tests PASS，待新完整Release／candidate／Jobs及owner reconcile。
- 備份盤點：既有VM operator IAP可用，原timer enabled/active，controller backup requests排隊、executor尚未安裝。已補既有container內獨立臨時DB還原／權限隔離／完整性檢查／清理，不用Cloud Build或新資源；10備份相關tests、Bash語法檢查PASS。尚未安裝／產生新controller備份／真實restore／停原timer，不能標交接完成。

## 2026-10-15 交易單字搜尋已發布固定 Preview，歷史費稅尚未套用

- 正式 Preview 已更新至 `4d058c47ac62ad7328f9f7c0e9fcd4ef4f1ac7b1`：完整 Release [#38674231933](https://github.com/tommylin15/janus-omniforge/actions/runs/38674231933)、0% candidate [#38674767979](https://github.com/tommylin15/janus-omniforge/actions/runs/38674767979)、OAuth／private boundary [#38674988598](https://github.com/tommylin15/janus-omniforge/actions/runs/38674988598)、固定 Preview [#38675180575](https://github.com/tommylin15/janus-omniforge/actions/runs/38675180575) 均 PASS。外部 HTTP 讀回 `/app/build-id.txt` 為新 SHA，`/api/v1/me/journal/instruments?q=2` 未登入 401。代號／名稱第一字下拉、ETF、Enter、未選取攔截與舊請求競態都有 Flutter 回歸；未冒充已登入瀏覽器畫面驗收，正式 API traffic 未切換。
- 059 已套用，新的 pg_attribute／ACL 強制驗收區段也以真實 `janus_control` 成功執行。唯讀確認本人券商設定已有折扣 0.4；ledger／profile checkpoint 已與舊 170 不同，回補不得沿用舊版本。
- 四 Jobs rollout [#38675277641](https://github.com/tommylin15/janus-omniforge/actions/runs/38675277641) FAIL／RECOVERY_REQUIRED：private／mart 首次 canary PASS 後，即時 2-task 私人重算在 Scheduler PAUSED 期間啟動，execution fence 阻擋 ingestion 更新及回滾。精確 readback 該重算後續 2 Tasks SUCCEEDED；已補 mutation／canary 前有界限 drain，73 相關 tests PASS，exact owner／tag／receipt recovery [#38676493330](https://github.com/tommylin15/janus-omniforge/actions/runs/38676493330) PASS，恢復 c8e8 原四 Jobs／Scheduler，API／Preview 不變、ledger writes=0；修正後同來源 rollout 已重新受控派送，待新收據。新增受控 fee-repair 操作／workflow，目前請求僅 `preview`；來源、配置、版本、scope、未知執行保留鎖等 36 tests PASS。須等 rollout PASS 再派送 preview，固定數量及版本後才 apply／Mart／零待更正讀回。歷史交易尚未回補，1～5 仍 PARTIAL。
- MCP 持股已改用工具上限 20（初次 50 超界，不能當作 OAuth 失敗），成功讀回 8 筆、ledger=176；其中 00697B 主檔缺失。已核對櫃買官方公告證櫃債字第10600159891號（2017-06-23 上櫃，元大美債7-10），新增 060 bounded instrument／provenance migration；僅補主檔，不加入 1988 檔股票母體、不更改本人交易。相關 migration／搜尋 tests 36 PASS，尚待 rollout 結束後套用及 Mart 讀回。
- 舊 queue canary #38653931699 exact artifact request 唯讀核對為 SUCCEEDED／attempt=1／task=0，worker 與 artifact 相符，requested ledger=170，verify 通過標記存在；目前 active requests=0、dispatch=false。原 workflow 的 cleanup 無收據依然保留 FAIL，但已證實沒有殘留 active queue，不新 seed、不偽造原 run PASS。

## 2026-10-15 交易搜尋已同步；059 owner 遷移與讀回通過

- 來源 `3d8ad504890a6f0e84cbe1a7a23befd44d6108c8` 的完整 [Release #38673398380](https://github.com/tommylin15/janus-omniforge/actions/runs/38673398380) PASS：Python／隔離 PostgreSQL、Flutter、四個 GHCR immutable images 及匿名 pull 均通過。此來源包含單字代號／名稱搜尋、ETF、未選取輸入攔截、正式 Admin 入口與首頁快照整合。尚未部署此來源／切換 API。
- 059 已沿用既有 operator IAP／postgres owner 執行，SQL SHA256 `af312332fd054506896999607c9f30e50a67d358e2c51ff1397a31e254a4d93a`，transaction COMMIT；owner 讀回 JSONB 欄位、public API 無 ledger SELECT、private API 無 schema CREATE、059 marker 均 true。初次 bootstrap 權限失敗及 Windows 換行 checksum 攔截保留為歷史失敗，均未回補交易。原 SELECT acceptance 在 control 的 information_schema 不可見；後續改為 pg_attribute 並以 SQL exception 強制中止不合格 migration。
- 搜尋追加鍵盤 Enter 選取及舊請求較慢回傳的回歸，交易 Flutter 3 PASS；後續修改需以新 SHA 完整 Release 驗證。本人折扣／歷史費稅回補及 1～5 其餘真實驗收仍未完成。

## 2026-10-15 自動費稅 full CI PASS；失敗 rollout 已恢復；059 與產品驗收接續中

- 自動費稅來源 `62d95bec42fe56ade9858376d1221fbb8b2321a1` 完整 Release [#38668985924](https://github.com/tommylin15/janus-omniforge/actions/runs/38668985924) PASS：Python／隔離 PostgreSQL **1206 PASS／2 legacy deselected**、Flutter／web build、四個 immutable GHCR image／public pull PASS。本人折扣及歷史費稅**尚未在 dev 寫入**，不能將 CI 當回補完成。
- 單純 stale lease recovery [#38669383890](https://github.com/tommylin15/janus-omniforge/actions/runs/38669383890) FAIL：原 FinOps rollout #38663858991 留下 Scheduler PAUSED 與部分新映像。後續 exact receipt SHA256／owner／tag、全頁 execution fence、匿名 baseline pull、正常新 lease 的受控 rollback [#38669986461](https://github.com/tommylin15/janus-omniforge/actions/runs/38669986461) **PASS**：恢復來源 `c8e8a7415be48b291a347dcc115d7834db6696a8` 原四 Jobs／配置及 Scheduler ENABLED，正式 API traffic 未變、ledger writes=0。原失敗不抹除。
- Migration 059 [#38670778671](https://github.com/tommylin15/janus-omniforge/actions/runs/38670778671) 執行失敗，exact ingestion execution `janus-ingestion-core-d79bq` 證實 `InsufficientPrivilege: must be owner of table ledger_events`；已用既有 operator IAP 唯讀確認 owner=postgres，連線成功；059 修正為既有 DB owner 路徑，不擴充應用角色權限，尚未重送或回補歷史交易。舊 queue canary #38653931699 的 artifact 為 UNKNOWN，保存 seed／worker／verify execution，但 cleanup 無收據；須讀回 exact request 終態及 cleanup，不能盲目新 seed。
- 交易搜尋已接上新增／更正表單，支援代號／名稱第一字下拉及已登記 ETF；修改文字後需重新選定。主檔搜尋／登入邊界 Python 22 PASS，交易 Flutter 3 PASS；尚未部署。
- 後續原始碼補上正式 `final_visual.dart` Admin 設定入口及首頁批次快照接線；快照共用 API 的 Decimal／partial／missing serializer，讀取不接受過期 freshness 或未來日期。相關 Python 29 PASS、Admin Flutter 5 PASS；尚待新 SHA full Release／實際快照與 Owner 驗收。前版 CI 不替新原始碼背書。


## 2026-10-15 本輪 1～5 已授權；自動費稅開發中（PARTIAL）

- 使用者新增本人折扣 0.4、自動證交稅、交易表單移除兩項輸入，並授權更正全部既有有效交易後依序完成 1～5；後置模型研究不啟動。已補共用費稅、Admin 本人券商設定、規則快照、Migration 059、原子 append-only 更正與同日交易更正排序。真實 ledger 回補尚未執行。
- 本機相關 Python 78 PASS／5 個隔離 PostgreSQL tests SKIP（沒有 CI DSN）；Flutter targeted 23 PASS。新 SQL replay 與整批失敗回滾仍須 GitHub 隔離 PostgreSQL 實測；完整 Release 已準備請求，未取得新 CI／部署 PASS。
- 唯讀重新核對：舊 queue canary #38653931699 已終態 FAIL，cleanup fence 報 `execution_not_terminal`；不能沿用舊「進行中」文字或盲目重送。FinOps Jobs rollout #38663858991 同樣 FAIL 且 recovery 未確認終態。最近 Private Pipeline executions 已讀到兩 Task SUCCEEDED，但這不是 queue checkpoint／cleanup 或完整四 Jobs 發版 PASS；部署鎖與其餘 Jobs 還需核對。

以下依原日期保留歷史證據；後續原始碼不自動繼承舊版本 runtime PASS。



## 2026-10-15 03～05 最新工程接續：官方 ETF 身分修復 PASS；正式重算驗收進行中

- **官方 TPEx 00719B 身分缺漏：FIXED／LIVE READBACK PASS。** 櫃買中心證券商品規格確認 `00719B` 為上櫃債券 ETF「元大美債1-3」（2018-02-01 上櫃）。用 `infra/postgres/migrations/058_official_held_etf_identity.sql` 及獨立 `control.official_instrument_identity_provenance` 記錄官方 URL／類型／上市日，單筆且 idempotent；**不納入 1988 檔股票母體**，不動 ledger／費用／價格。既有 dev ingestion Job 执行 [#38652846263](https://github.com/tommylin15/janus-omniforge/actions/runs/38652846263) 真實 migration PASS（SQL SHA256 `f97f4377b16a471fc6a299b7c05db7703a7c92d23876e322bf8cc0d008450b98`；3 targeted tests PASS），GCP API traffic／Job image 不變。單 Owner Private Mart 重算與 price／identity／PnL／ledger checkpoint [#38653250200](https://github.com/tommylin15/janus-omniforge/actions/runs/38653250200) PASS（14 tests，execution `janus-private-pipeline-lkldw`），獨立 Janus MCP Owner 唯讀讀回：00719B `stock_name=元大美債1-3`、`identity_status=available`、估值日與 price date 2026-10-14、ledger version 170；**沒有新增、修改或刪除任何正式交易**。舊 `stock_master_not_found` checkpoint 是歷史，不再是目前阻塞。
- **03 Private Recalc queue 真實 canary：IN_PROGRESS，尚未 PASS。** 新建 `scripts/gcp/private_recalc_ghcr_canary.py` 重用 048 的 seed／兩 Task Worker／verify／cleanup，只用 Cloud Run v2 執行層 overrides、release lease、all-page fence；真正 GCP dev worker 來源仍 `1e9c31d...`。第一次 [#38653790215](https://github.com/tommylin15/janus-omniforge/actions/runs/38653790215) 在 **pre-GCP pytest import** 因 PYTHONPATH 錯誤 FAIL，確定未派 GCP Job／未 seed；已最小修復並送出第二輪 [#38653931699](https://github.com/tommylin15/janus-omniforge/actions/runs/38653931699)，最後觀察 `in_progress`。它會以既有 Owner 衍生 Mart 刷新驗證 queue 但**不寫 canonical ledger**；未取得完整 SUCCEEDED／checkpoint／idle／cleanup 收據之前不得判 PASS，亦不等於瀏覽器手動重算按鈕到 API 的完整正向驗收。
- **04 四頁與效能：PARTIAL，05 正式 API 100% 切流：NOT STARTED。** 固定 Preview [#38566991297](https://github.com/tommylin15/janus-omniforge/actions/runs/38566991297) 仍為同來源舊正式 API 以外的驗證標籤；公開 market-home 30/30 P50=46.76ms、P95=97.97ms、最慢 9.376s，只證明 GitHub Runner→API，未證真實 authenticated 手機 390×844、四頁、冷啟動與保存／試算各自 P95。既有 canonical API 保持 100% 原 traffic，不因 ETF／queue 修復提前 promotion。更多前置 PASS 仍見下方 01／02 checkpoints。


## 2026-10-15 最新實證：全市場 Bootstrap＋Cached PASS；持股與產品驗收 PARTIAL

**截至 2026-10-15 的工程接續（取代下方舊快照的「Jobs rolling／Bootstrap pending／migration 057 未部署／已暫停」描述，不覆寫原歷史收據）。**

- **完整 Release 與最新版 dev：PASS（限定已核實範圍）**：官方 TPEx 指定日估值資料修復來源 `1e9c31d148db540ee06cac5ccccd8fac8d619511`，完整 Python 1163 PASS／2 舊項排除、Flutter 90 PASS、四 GHCR immutable images／anonymous pull [#38565636734](https://github.com/tommylin15/janus-omniforge/actions/runs/38565636734) PASS；Migration 057 [#38555862109](https://github.com/tommylin15/janus-omniforge/actions/runs/38555862109) PASS；0% Candidate [#38566380979](https://github.com/tommylin15/janus-omniforge/actions/runs/38566380979) PASS、自動 OAuth／負向 private boundary [#38566632955](https://github.com/tommylin15/janus-omniforge/actions/runs/38566632955) PASS；四 Jobs 兩輪 canary [#38566821108](https://github.com/tommylin15/janus-omniforge/actions/runs/38566821108) PASS，固定 Preview [#38566991297](https://github.com/tommylin15/janus-omniforge/actions/runs/38566991297) PASS。正式 canonical API 流量尚未切換。
- **01 全市場 bootstrap：業務 PASS**：[ #38575674367](https://github.com/tommylin15/janus-omniforge/actions/runs/38575674367)，交易日 2026-10-13，官方有效名冊 TWSE 1095＋TPEx 893＝1988；TWSE 官方 OHLCV 1093／1095，TPEx 官方 OHLCV 868／893、TPEx 指定日估值 886／893，其他必要 dataset 也各依 TWSE ≤10%／TPEx ≤30% gate PASS；`staged=20`、`serving_published=88455`，immutable coverage hash `sha256:153aa6ad0f91f143dc6bdc0f73d2d2a8bcbb966e759f1b9cb2b5ae35854110d9`。沒有將次日 OpenAPI 估值冒充指定日。來源資料有缺漏的股票仍保留完整身份與 missing semantics。
- **02 same-day Cached：業務 PASS**：[ #38651225144](https://github.com/tommylin15/janus-omniforge/actions/runs/38651225144)，從已驗證 Bootstrap 收據回讀 data date 2026-10-13 並固定 `INGESTION_DATE`，必要 coverage records 17／17 cache hits、`staged=0`、`serving_published=0`、1988 名冊、獨立 immutable inventory hash `sha256:19d4ecb7e31b5f24181943b9960f916ba9bd68897b998795abac4aa50477350a`，未更動正式 API 流量或永久 Job config。驗收腳本與日期固定回歸測試已提交；與 Bootstrap 不同日期的 cached 不算 PASS。
- **重複 Bootstrap 的歷史失敗保留**：成功 01 後的獨立重複執行 [#38575717874](https://github.com/tommylin15/janus-omniforge/actions/runs/38575717874) 終態 FAIL、遺留 immutable lease；一次性有界復原 [#38651024199](https://github.com/tommylin15/janus-omniforge/actions/runs/38651024199) PASS、原 Git ref 404。這不是 cached 的失敗，且不能抹除其歷史記錄。
- **03 Owner 真實唯讀讀回：PARTIAL**：已授權 Janus MCP 於 2026-10-15 查得持股 6 筆、價格皆為 available，年度 PnL 與 positions 共用 ledger version 170，沒有新增／修改任何交易；但仍有 1 檔合法持股商品 `identity_status=missing`（`stock_master_not_found`），交易存檔、加減碼／更正、Private Worker 正式重算 request 的本輪動作到讀回整條路徑沒有新的真人／受控寫入證據，不能標 PASS。Owner 數值或身分資訊不寫入公開文件。
- **04 固定 Preview 公開首頁 API 部分效能 PASS、整體 PARTIAL**：[ #38651716425](https://github.com/tommylin15/janus-omniforge/actions/runs/38651716425)，GitHub runner 到 `/api/v1/public/market-home` 30／30 HTTP JSON 正常，P50=46.76 ms、P95=97.97 ms、最慢單次 9376.24 ms。這是 server/network 公開暖讀取的觀測，**不能冒充冷啟動 P95／手機 390×844 實測／登入 Owner UI 四頁驗收**，單筆 9.38s 需列為效能風險。
- **05 正式 dev 切流：NOT STARTED**；保持正式 API 既有 100% 路由。只有 Owner 交易、正式重算、隔離、UI 冷暖效能適用 gate 成立，才能使用原受控 API promotion 流程；不因 01／02 PASS 或 Preview PASS 直接切流。五分析師 OOS／CEO 真實 publication 繼續獨立後置。


## 2026-10-14 全市場驗收受控接續：Jobs 未終態，bootstrap 單次請求已排隊

- 第 01 關完整 Release #38552314315 來源 `61796cbc2cd973d694e1d203e7ea9e8af07804c1` PASS（Python 1156、Flutter 90、GHCR 四映像與 anonymous pull）。057 #38555862109 PASS；0% candidate #38556011007 attempt2 PASS；同來源自動 OAuth/private boundary #38557372000 PASS。**正式 API traffic 未切換。**
- 四 Jobs [#38557540516](https://github.com/tommylin15/janus-omniforge/actions/runs/38557540516) 仍處於 rollout/canary `in_progress`，未取得全部八次 canary 與 Scheduler 最後恢復收據，**不可宣稱 Jobs PASS**。
- 建立一次性、明確核准的既有全市場 acceptance 入口；其 `on.push` 只接收 `ops/full-market-acceptance-request.json` 單次請求，仍使用 `full-market-dev-acceptance.yml` 的原 Cloud Run Job override、writer concurrency、read-only candidate boundary 與 immutable release provenance，沒有新增 Scheduler／cron。使用成功的四 Jobs Run 作硬性前置證據，來源與 release/boundary IDs 必須一致；Jobs FAIL 時 bootstrap 不准執行。修復 verified business PASS 才以 `--safe-to-release` 釋放本次 owner lease，失敗或未知保持鎖與收據。相關 tests 含不同市場 10%／30% 邊界與 lease guard，[selective CI #38559013399](https://github.com/tommylin15/janus-omniforge/actions/runs/38559013399) PASS。
- 全市場 **bootstrap 單次請求已送出、仍排隊**：[Run #38559419684](https://github.com/tommylin15/janus-omniforge/actions/runs/38559419684)；請求來源與驗證門檻同上述 Release，固定 TWSE ≤10%／TPEx ≤30%，含分市場 receipts、官方名冊、Stage/Core provenance 與不可造假缺值。此段不是 bootstrap PASS；cached 尚未觸發，需先有 bootstrap PASS 才能受控執行。任何未終態不盲目重送。


## 2026-10-14 接續 dev 第 01／02 關卡：CI、057、候選、OAuth PASS；Jobs ROLLING

- **完整 CI／GHCR Release：PASS**：來源 `61796cbc2cd973d694e1d203e7ea9e8af07804c1`、Run [#38552314315](https://github.com/tommylin15/janus-omniforge/actions/runs/38552314315)：Python 1156 PASS／2 legacy deselected，Flutter 90 PASS／analyze／web build PASS，四份固定來源 GHCR image publish 與匿名 pull PASS；先前動態歸檔路徑兩項失敗不再重現。後續 ops-only main commits 不等於這四份 image 的來源 SHA。
- **Migration 057：PASS**：[受控 Job #38555862109](https://github.com/tommylin15/janus-omniforge/actions/runs/38555862109)，執行 `janus-ingestion-core-h2rvs`，收據 migration=`057_home_market_snapshot`、sql_hash=`10656633d94dbf1b996c5122ec589647179725ec97eb17a23977d00224bc9643`、status=PASS；未改 image／traffic。資料內容及首頁冷讀延遲仍需後續 live 驗收。
- **歷史部署鎖：受控復原 PASS**：來源 [#38537012683](https://github.com/tommylin15/janus-omniforge/actions/runs/38537012683) 的失敗全市場執行殘留 immutable lease，致首次候選 [#38556011007](https://github.com/tommylin15/janus-omniforge/actions/runs/38556011007) attempt 1 `lease_busy`，`gcp_writes=0`。單次有界 [#38556905741](https://github.com/tommylin15/janus-omniforge/actions/runs/38556905741) 實際核對 exact owner/tag、全部 Job execution 終態／Jobs Ready、Scheduler ENABLED、API 原 100% 路由 unchanged、legacy writer fence，15 tests PASS 後才刪除**該筆**舊 Git ref；GitHub readback 404，GCP runtime 0 寫入。不是通用 force-unlock 或可重用 waiver。
- **0% API Candidate：PASS**：原 Run #38556011007 attempt 2 恢復後成功，同來源 immutable GHCR API digest、health、build-id、負向授權、100% canonical traffic 未變；**OAuth/private boundary：PASS** [#38557372000](https://github.com/tommylin15/janus-omniforge/actions/runs/38557372000)，僅自動 metadata／PKCE／Owner/Admin/MCP 負向權限，不冒充真人登入或本人持股計算 PASS。
- **四 Jobs 發布：IN_PROGRESS／未驗收**：[受控 rollout #38557540516](https://github.com/tommylin15/janus-omniforge/actions/runs/38557540516)，來源 61796cbc，使用目前已部署來源 `085456e3cdf2075cc399977dfe4c2414340fdae8` 的四份公開 GHCR immutable image 及既有設定 hash 作 reversible baseline。待兩輪各四 Jobs canary、執行終態、Scheduler ENABLED、digest／config readback、回復能力 receipt 真正 PASS 後才允許標示 Jobs 完成。**API 正式 100% promotion、全市場 bootstrap／cached、持股 Owner 真實操作與 UI／P50-P95 均未由本輪宣稱通過**。


## 2026-10-14 分市場 coverage 新決策：CODE／SPEC UPDATED，LIVE NOT VERIFIED

使用者最新指示：**上市 TWSE 缺失率維持 ≤10%；上櫃 TPEx 放寬至 ≤30%**，均含邊界，必要資料依市場／資料集／期間及事前固定官方適用名冊獨立判定，不合併分母。核心 `coverage_receipt`／cache、Cloud Run business receipt 驗收與邊界測試已修改；`ALL` 個人持股外部報價不繼承放寬標準，仍須完整。以先前固定 893 檔上櫃名冊的唯讀樣本試算，法人 120／893、融資 91／893、當沖 170／893 缺漏均低於新 30%；**歷史 bootstrap #38537012683 的 FAIL 紀錄不改寫，也不等於新來源 bootstrap/cached PASS**。使用者先前暫停部署／批次仍有效，最新完整 CI、migration 057、正式流量及 Owner 驗收均未因政策修改而通過。


## 2026-10-14 使用者要求暫停並同步全部進度：PAUSED／PARTIAL

已保存本輪與另一 AI 的 main 變更；完整交接見 [暫停 checkpoint](full-market-pause-2026-10-14.md)。現有 runtime 為 `085456e…`，四 Jobs 兩輪 8 canary PASS／設定與 Scheduler readback PASS，固定 Preview PASS；正式 API 流量未切換。全市場 bootstrap #38537012683 FAIL，官方名冊 1988 檔已建立，但上櫃法人／融資／當沖仍超過 10% 或適用資格待證明，cached 未執行。

另一 AI 的 workflow 歸檔、診斷 CLI、首頁預聚合／057 與分片寫入皆已提交。057 尚未部署，不能聲稱已消除 cold latency 或真實 <5 ms。新完整 Release #38542355436 為 1154 Python PASS／2 路徑 FAIL，Flutter PASS、映像發布 SKIP；最後兩個動態路徑已修，相關 55 PASS，修正後完整 CI 尚未重跑。畫面／交易保存效能與備份 IAM／還原交接尚未完成。暫停後不新派送 Release 或 dev 操作。

## 2026-10-14 工作流治理收斂 PASS／統一診斷 CLI PASS／全市場與持股 P0 回歸 PASS（ACTIVE／PARTIAL）

- **GitHub Workflows 大刀闊斧收斂與歸檔：PASS**：原 117 份工作流完成系統化治理，89 份歷史探測、前置診斷、前 500 母體研究排程安全移入 `.github/workflows/archive/`，並建立 [`archive/README.md`](../../.github/workflows/archive/README.md) 索引清冊。目前保留 28 份核心 Workflows，對齊四大核心管線（PR/Commit CI、核心 Release/Deployment、備份清理 Cron、受控手動運維），消除非預期定時排程。
- **本機靜態診斷 CLI 已提交**：[`ops/diagnose.py`](../../ops/diagnose.py) 只掃描 workflow／SQL 檔名、檢查兩份規格存在，並輸出固定 CEO 目標值；沒有連線 PostgreSQL、GCP 或 Gateway，不能證明 migration 已套用、資料健康或實際模型配置。
- **P0 優先工作包（全市場官方報價、持股損益即時試算、首屏效能）**：
  - **首屏寫入時預聚合與快照投影：實作／單元測試 PASS，runtime PARTIAL**：首頁單主鍵快照已提交；057 未在 dev 執行，真實 cold latency 與 <5ms 尚未量測。
    - 資料庫層：新增 Migration [`057_home_market_snapshot.sql`](../../infra/postgres/migrations/057_home_market_snapshot.sql)，建立 `control.home_market_snapshot` 單列儲存表與 `publication.home_market_snapshot` security-barrier 視圖，支援 `janus_public_api` 讀取。
    - 生成層：於 `StockServingProjection` 實作 `materialize_home_market_snapshot`；目前只有單元測試呼叫，尚未接入正式批次完成路徑，不能宣稱自動產生首頁快照。
    - 讀取層：於 `packages/web_api/core.py` 及 `services/api/public_runtime.py` 貫徹 Fast Path 主鍵讀取（`SELECT payload_json WHERE snapshot_id = 1`），保留未命中時平滑降級。
    - 測試驗收：新增專屬單元測試 `tests/test_home_market_snapshot.py`（3 PASS），關聯市場與 Serving 回歸測試（31 PASS）全數綠燈。
  - 後端 Python 回歸：全市場名冊與 Serving 測試 23 PASS；持股 TPEx、重算隊列與 Daily Change 19 PASS（合計 42 PASS）。
  - 前端 Flutter 測試：`apps/user_app` 執行 `flutter test`，90 tests 全數 PASS。
  - 下一階段：待新版本整體 dev 部署後，進一步執行 Cloud Run 候選、0% candidate、四 Jobs canary 與真實 Owner 端到端截圖及冷讀取效能驗收。

## 2026-10-14 全市場／總控／持股交易／四頁整合：ACTIVE／PARTIAL

使用者已恢復本工作包；最終 runtime 來源為 `085456e3cdf2075cc399977dfe4c2414340fdae8`。migration 054～056 PASS；完整 Release [#38530995776](https://github.com/tommylin15/janus-omniforge/actions/runs/38530995776) PASS（Python 1149、Flutter 90／analyze／web build、四個 immutable GHCR image／匿名 pull），0% candidate [#38531845062](https://github.com/tommylin15/janus-omniforge/actions/runs/38531845062) 及自動 OAuth／private boundary [#38532482767](https://github.com/tommylin15/janus-omniforge/actions/runs/38532482767) PASS。固定 Preview [#38533380447](https://github.com/tommylin15/janus-omniforge/actions/runs/38533380447) PASS；四 Jobs [#38533451889](https://github.com/tommylin15/janus-omniforge/actions/runs/38533451889) 已完成兩輪共 8 次 canary PASS，exact digest／設定與 Scheduler readback PASS。正式 API 流量未切換。

新版包含今日頁圖表優先／研究收合、未知交易重送保留冪等 key、已登記 ETF 持股價格與 cached snapshot／來源 proof；普通股 coverage 分母不含 ETF。新版 Preview 公開 `/market-home` 本機 Windows 網路 API-only 暖讀 30 次、0 失敗、P50 375 ms／P95 437 ms；第一筆 484 ms 單列，未強制 cold start，不能當手機端到端或 cold P95。真實全市場 bootstrap／cached business receipt、持股／試算／保存效能與四頁 authenticated screenshot 尚未完成。使用者已指定既有測試帳號，保存量測須確認該 owner 後才寫入；Chrome 控制前輪因無法辨識網址被工具停止，不能聲稱 UI 已驗收。備份 executor install 仍缺 CI `compute.instances.get`；原備份 timer 保留，未擴 IAM、未完成還原及交接。

使用者已明確要求完成全市場與總控底層、持股交易效能、通用圖表／四頁，再集中測試及 dev 驗收。此為本輪最新授權；下方 CEO 獨立任務的「持股暫停」及舊文件停止敘述只代表其原記錄時點。

- 本機已補 migration 054～056、全市場雙來源名冊／分市場 coverage、screening 分片、公開 PostgreSQL 首屏與法人／月營收／單季 EPS 圖表、交易唯讀試算／版本檢查／移動平均成本、更正及重送 guard、獨立 Private Mart 鎖、手機入帳 owner queue，以及總控備份 executor／還原後交接。
- 集中 Python 回歸 258 PASS／3 個隔離 PostgreSQL tests SKIP（本機無 CI DSN）；其後快取 receipt／scope／失敗守門等修正相關回歸 145 PASS／3 SKIP，最後 scope tests 11 PASS。這些測試有重疊，不累加成總測試數。
- 四頁／表單 Flutter 全套 88 PASS；Dart analyze `--no-fatal-infos` exit 0，只有既有 info；workflow YAML、備份 Bash 語法及 diff whitespace 通過。Linux 全 Release、真實 PostgreSQL、新 SHA dev deployment／coverage／queue／備份還原／四頁及效能驗收尚未完成，不標本工作包 PASS。
- 原 00719B 與 CEO 技術 PASS 維持各自範圍；後置模型研究／CEO 報告不由本輪啟動。最新 acceptance 見 [TODO](../todo.md) 及 [持股優先契約](../spec/holdings-first.md)。
- 首次完整 Release [#38507925978](https://github.com/tommylin15/janus-omniforge/actions/runs/38507925978)：Flutter PASS；Linux Python 1140 PASS／4 FAIL（真實 PostgreSQL 交易 tests 通過）。4 個舊契約／fixture 已同步並得到相關 33 PASS；必須由新 SHA 完整 Release 重驗，不以此結果部署。
- 新 SHA `6326d16412c8eb61bb0618b7a394b18ba5017d14` 完整 Release [#38508422835](https://github.com/tommylin15/janus-omniforge/actions/runs/38508422835) PASS：1144 Python PASS（含隔離 PostgreSQL 交易 tests）、Flutter test/analyze/web build PASS、四個 GHCR immutable image／匿名 pull PASS。runtime 尚待 migration、0% candidate、boundary、四 Jobs canary、四頁及效能實測，不標整包完成。
- `6326d16` 0% candidate [#38509014971](https://github.com/tommylin15/janus-omniforge/actions/runs/38509014971) 與自動邊界 [#38509314083](https://github.com/tommylin15/janus-omniforge/actions/runs/38509314083) PASS。migration 054 [#38509014739](https://github.com/tommylin15/janus-omniforge/actions/runs/38509014739) FAIL：DDL 已執行，但 control 身分執行 publication ACL 驗收查詢受拒；已修為既有 publication 身分驗收並補兩條執行路徑測試，23 PASS，待新完整 Release。備份 executor install [#38509036396](https://github.com/tommylin15/janus-omniforge/actions/runs/38509036396) IAM BLOCKED（CI 缺 `compute.instances.get`），VM 未寫入／原備份 timer 保留，不擴 IAM、不宣稱備份交接完成。
- 修正版 SHA `74803b8c422cb564bec85bdcae8ddae7fa347957` 完整 Release [#38509708320](https://github.com/tommylin15/janus-omniforge/actions/runs/38509708320) PASS（Python／Flutter／四映像及 public pull）；後續 runtime gates 一律改用此 SHA。054 冪等重驗 [#38510059974](https://github.com/tommylin15/janus-omniforge/actions/runs/38510059974) 尚在執行。
- 054 [#38510059974](https://github.com/tommylin15/janus-omniforge/actions/runs/38510059974) 與 055 [#38510396930](https://github.com/tommylin15/janus-omniforge/actions/runs/38510396930) PASS。首次全市場 runtime 前另補當日 scope 日期守門：昨收可用於今天名冊，但不得把今天名冊回標為昨天 PIT 分析。相關 42 PASS；尚未更新四 Jobs，將由後續新完整 Release SHA 取代 `74803b8` 作最終 runtime 驗收來源。


## 2026-10-14 Janus P0-V 跨專案技術驗收 PASS／真實 Owner CEO 報告 PARTIAL

- **完整五角色合成 Fact Pack 真實模型與 CEO Validator：PASS**：[Janus #38490887562](https://github.com/tommylin15/janus-omniforge/actions/runs/38490887562) SUCCESS，使用已部署 `janus-ceo-analysis` 原 image（SHA `a05f1f4dea80ecbd947829cd2751e1253f822cee`）及原服務身分，僅單輪 `RunJob.containerOverrides.env` 指向新私有 0% Gateway `p0v-market2048-00d45861`；original ID-token audience 不變。原生 29.5–32 KiB 合成五角色 `_prompt` → Gemini Flash-Lite → `execute_ceo`／CEO JSON Schema／hash／numeric/evidence validation PASS；回覆判定為合成資料不足 `PARTIAL`，不具正式 publication authority。請求上限 1、沒有失敗盲重試、正式 DB/GCS CEO writes=0、永久 Job 更新=0、四排程 Jobs／API／Gateway 正式流量不變；global lease 於 terminal 後安全釋放，結果 artifact 已上傳。
- **獨立前置真實證據**：omniAgent 新候選 [#38488277144](https://github.com/tommylin15/omniAgent/actions/runs/38488277144) PASS、[Gemini 503 恢復後的單次真實可用性 #38488547115](https://github.com/tommylin15/omniAgent/actions/runs/38488547115) PASS；Janus 完整離線 CEO Fact Pack CI [#38490691563](https://github.com/tommylin15/janus-omniforge/actions/runs/38490691563) PASS。原 2026-10-13 測試 [#38422168730](https://github.com/tommylin15/janus-omniforge/actions/runs/38422168730) 因 Gemini upstream HTTP 503 FAIL，是歷史失敗而非本次成功的替代證據。
- **技術 gate 結論：PASS**（真實 LLM 呼叫／完整合成 CEO 業務 validator＋既有 #38372494501 隔離 PostgreSQL Owner API／GCS 技術 contract）；**真實五 Specialist 模型品質及使用者 Owner capability 手動請求 → GCS/PG canonical report → API 歷史讀回仍 NOT VERIFIED／PARTIAL**。不得以合成資料 PASS 當作真實分析上線。持股／Private Recalc P0 仍 PAUSED BY USER，未動正式流量／永久 CEO Job。

### 2026-10-13 歷史接線與失敗證據（保留，不覆寫）

這項任務只處理 CEO Gateway，**持股／Private Recalc P0 仍維持 PAUSED BY USER**。完整 acceptance [CEO P0-V 文件](../ceo-omniagent-p0v-integration.md)，未完成項目見 [TODO](../todo.md)。

- **Code/full GHCR**：[ #38363636133](https://github.com/tommylin15/janus-omniforge/actions/runs/38363636133) PASS，實作 SHA `b63bf350213fa7c3933724fa38006d8ab7b8033f`；四既有 GHCR 映像、額外 CEO image、Python／Flutter/full release tests 及 public digests 皆 PASS。
- **API 0% candidate**：[ #38364240675](https://github.com/tommylin15/janus-omniforge/actions/runs/38364240675) PASS；舊正式 API 100% 流量不變；並不代表本來源 API 已正式切流。
- **真正 Mart SA 專用市場呼叫身分**：[ #38366833454](https://github.com/tommylin15/janus-omniforge/actions/runs/38366833454) PASS（既有 CEO Job 原執行身分 impersonate market-mart 專用 SA，向 Gateway signed invalid-body probe 得到預期 400；model calls 0，無 DB write）。前次 janus-ci `iam.serviceAccounts.getIamPolicy` 拒絕只代表 CI 讀政策能力不足，已被**更有權威的實際 Worker IAM 正向驗證**釐清。
- **CEO Job-only 版本化部署＋postdeploy signed canary**：[ #38367279461](https://github.com/tommylin15/janus-omniforge/actions/runs/38367279461) PASS；同來源 immutable CEO image，原 SA／Secret refs／VPC／1CPU1Gi／無 Scheduler，只有 CEO Job 更新；新版執行成功讀回、global lease released。未改四排程 Jobs、Janus API 100% 或 omniAgent Gateway 正式流量。
- **已部署 Worker 真實 Gemini Flash-Lite JSON 回路**：[ #38367878942](https://github.com/tommylin15/janus-omniforge/actions/runs/38367878942) **PASS**：一次 synthetic、非個人輸入的 Janus Router→Gateway→Gemini→Router 往返；CEO Pydantic schema、五份 synthetic Specialist hashes、模型身分與 request/result bound 通過；GCP Job terminal 及 lease release PASS。**沒有**真正 Owner 資料、`validate_ceo_output` 的完整 baseline/evidence/numeric policy live acceptance，也**沒有**GCS/PG report history 或 User API authenticated readback。
- **P0-V 73-case 隔離業務契約與真實 GCS／PG readback**：[ #38372494501](https://github.com/tommylin15/janus-omniforge/actions/runs/38372494501) **PASS**（2026-10-13，workflow HEAD `eae20a8859991bb5ef95735e03556313e5389d7c`；五合成角色 full CEO validator 與 negative cases、CI 隔離 PostgreSQL report write→API history／owner isolation、真實 dev CEO Job 的 GCS acceptance-only create/readback/delete、真實 PG JSONB non-writing roundtrip、zero model calls／zero canonical rows／lease release 均成功）。原先 GCP test [#38371376749](https://github.com/tommylin15/janus-omniforge/actions/runs/38371376749) 因正式 PG 缺 `CREATE TEMP` 權限而 **FAIL**；唯讀錯誤類別 [#38372150846](https://github.com/tommylin15/janus-omniforge/actions/runs/38372150846) 為 `InsufficientPrivilege`，已改為不用增加正式 DB grant 的安全讀回測試；**不能將 PG readback 說成真實 private.ceo_requests 寫入**。
- **上游 32 KiB market-mart Gateway 已驗證，Janus 繼續驗收**：[omniAgent #38389373782](https://github.com/tommylin15/omniAgent/actions/runs/38389373782) 0% candidate `ghcr-965b05542a35` 已真實送入 29,987 B CJK／60,150 B JSON 得到 Gemini 回覆；Life／Chat 各保持 8 KiB。Janus adapter／Job template 已改為受限 32 KiB＋128 KiB envelope；本次新來源 CI／Worker rollout／完整 CEO JSON+evidence validator **尚待通過**，512 output tokens 仍可能阻礙。P0-V PARTIAL，不動四排程 Jobs、正式流量或真實 Owner 報告。
- **最新 P0-V full 32 KiB Janus Gateway status（PARTIAL）**： [#38392237542](https://github.com/tommylin15/janus-omniforge/actions/runs/38392237542) 全套 GHCR PASS；新 0% Gateway URL + CEO Job immutable SHA 及 signed canary [#38394294374](https://github.com/tommylin15/janus-omniforge/actions/runs/38394294374) PASS（前 rollout [#38392891696](https://github.com/tommylin15/janus-omniforge/actions/runs/38392891696) operation wait timeout FAIL，但 [#38393696263](https://github.com/tommylin15/janus-omniforge/actions/runs/38393696263) terminal/lease recovery PASS）。完整五角色 synthetic 30KiB 原生 `_prompt` → `execute_ceo` 無模型、帶完整 hash/metrics/evidence 的 CI [#38401261530](https://github.com/tommylin15/janus-omniforge/actions/runs/38401261530) PASS，修正第一次驗收 [#38394571293](https://github.com/tommylin15/janus-omniforge/actions/runs/38394571293) pre-provider `KeyError`。第二次真實 Gateway [#38401658102](https://github.com/tommylin15/janus-omniforge/actions/runs/38401658102) **FAIL**，原部署鎖正常釋放、無 canonical write；Janus [#38402397865](https://github.com/tommylin15/janus-omniforge/actions/runs/38402397865) `provider_unavailable`，同時段 Gateway [#38402703001](https://github.com/tommylin15/janus-omniforge/actions/runs/38402703001) HTTP **502**、[ #38402961256](https://github.com/tommylin15/janus-omniforge/actions/runs/38402961256) `market-mart failed:gemini_execution_failed` 耗時 **20,558 ms**。此安全代碼不足以區分 upstream HTTP error／模型空文字／finishReason／其他原因，**不得直接推論 512 tokens 不足或再盲送模型**。需跨 omniAgent 邊界取得受限 safe subtype，再有界修復＋重新驗收；P0-V 不得宣稱完成，Owner CEO 報告 NOT VERIFIED。
- **2026-10-13 market-mart 2,048-token 修復已部署、Janus 真實 E2E 仍 PARTIAL**：omniAgent 專屬 2,048 output cap（其他專案 512）、安全 failure subtypes 及私有 0%-traffic 候選 [#38409577652](https://github.com/tommylin15/omniAgent/actions/runs/38409577652) PASS；Janus 完整合成五角色離線原 Prompt／CEO validator [#38421876332](https://github.com/tommylin15/janus-omniforge/actions/runs/38421876332) PASS。一次性 `RunJob.containerOverrides.env` 指向新 2048 候選的真實完整模型驗收 [#38422168730](https://github.com/tommylin15/janus-omniforge/actions/runs/38422168730) **FAIL**（不變更永久 CEO Job image/env／正式流量；全數 execution terminal、global lease released；無正式 PG／GCS CEO writes）。[ #38423028775](https://github.com/tommylin15/janus-omniforge/actions/runs/38423028775) safe Gateway diagnostic = HTTP 502／`provider_unavailable`，881 ms；[ #38423305926](https://github.com/tommylin15/janus-omniforge/actions/runs/38423305926) 確認 Google Gemini 上游 **HTTP 503**。該次沒有 Gemini 有效回覆可供 CEO JSON/hash/evidence 驗證；不得將 2048 cap 變更或 CI／Gateway deployment PASS 視作完整 CEO 技術 PASS。下一步先取得 provider 正常服務的正向證據，不能盲目重送同一個 request。
- **剩餘 gate**：由真正具 capability 的使用者發起**新的**手動 CEO 分析（不得重送舊失敗 request）；通過 validated Fact Pack 原始大小 ≤32KiB、Gemini market-mart 2,048 output max token 限制（目前真正阻塞為 upstream HTTP 503）、完整 `validate_ceo_output`、immutable GCS/PG report hash/readback 和 Owner API history。未核實仍為 **PARTIAL**，不宣稱正式報告上線，且不因合成 schema PASS 自動 promotion。

---
**2026-10-13 最新合併開發授權：P0-1 至 P1-2 一次完成相依開發，再整合測試／真實驗收。** 本指示取代之前「只更新文件後停止」。先掃全文件，將有效500個股任務與資料收集改全上市櫃；歷史證據／識別字保留且不冒充全市場PASS。P2模型研究與P3報告不由本次自動啟動。

## 2026-10-13 全市場／總控盤點；文件完成後停止

使用者取消全部 500 檔母體限制，改全上市櫃個股、缺失率 ≤10% 即過 coverage；所有業務批次以 Cloud Scheduler 總控，Actions 只保留備份清理定時工作。本輪已查 repo／dev 主區 Scheduler／Jobs 與 GitHub workflow metadata，見 [盤點](../batch-inventory-2026-10-13.md)。**依最新指示只完成文件並停止；未提交／推送／部署／停用排程。研究 workflow 試改已還原，現存研究 cron 仍是待移除項，VM backup timer live 未查。** 原先未驗證程式改動保留，功能仍 PARTIAL。

## 2026-10-13 文件整理與最新產品順序

先持股報價／交易損益／效能，再通用圖表及四頁整合，五分析師有效後才建整合報告。本節取代下文歷史暫停與 B9→C→產品順序；原失敗證據保留。此次完成需求／文件整理，未執行程式測試、部署或 live 驗收；工作區既有跨層修改仍未驗證，不能當 main／live 成果。見 [文件盤點](../documentation-review-2026-10-13.md)、[AI 指示](../codex-execution-plan.md)。

## 2026-10-13 三項優先工作已恢復／開發中

使用者指定 P0 持股／手動重算、持股首屏效能、四頁視覺整合優先，一次開發完再集中驗收。官方報價擴為上市、上櫃全部個股，研究 500 admission 不變；本段取代下方暫停控制，歷史 evidence 不改寫。

- 唯讀原失敗 queue 查詢已取得 `FAILED / LOCKNOTAVAILABLE`；active requests=0、dispatch=false，未重送重算。程式檢查發現 batch controller 與 private Mart 共用 advisory key `(1835102836,3)`，server `lock_timeout=5s`；私有寫入需獨立鎖、有界等待及實際並行驗收。
- 全市場 EOD Core／serving、首頁 PostgreSQL read model、法人圖與四頁刷新正在開發；未測試／未 commit／未部署，整體仍 PARTIAL。
- 本次實際只做根因調查，尚無新版本 live acceptance；既有 PASS／FAIL 仍依下方來源 SHA 區分。

## 2026-10-13 暫停交接：持股／手動重算 P0 PARTIAL（使用者要求暫停）

**最新權威入口：[持股 P0 暫停交接／需求、證據及接續順序](../p0-holdings-recalc-pause-handoff-2026-10-13.md)**；active acceptance 見 [TODO](../todo.md)。使用者已明確要求停止執行，只整理文件；**不得自行啟動新的 Job／重算、GCP deployment、cleanup 或正式切流**，下一次收到繼續指示先 readback GitHub `main`／runtime。

- **目前驗收分層**：00719B 單一真實 Owner 官方 TPEx EOD／Private Mart PnL／checkpoint [#38257614968](https://github.com/tommylin15/janus-omniforge/actions/runs/38257614968) **PASS**；來源 `50eda171ef6ffb3971a4d140ad09bac870ead6c1` 完整 GHCR／Candidate／自動 OAuth／四 Jobs 8 canary [#38273250472](https://github.com/tommylin15/janus-omniforge/actions/runs/38273250472)／[#38273927543](https://github.com/tommylin15/janus-omniforge/actions/runs/38273927543)／[#38274131449](https://github.com/tommylin15/janus-omniforge/actions/runs/38274131449)／[#38274299751](https://github.com/tommylin15/janus-omniforge/actions/runs/38274299751) **PASS**；同來源固定 Preview [#38322429759](https://github.com/tommylin15/janus-omniforge/actions/runs/38322429759) 與官方市場公開資料唯讀 readback [#38322598975](https://github.com/tommylin15/janus-omniforge/actions/runs/38322598975) **PASS**。以上**均不代表手動 owner queue E2E 已完成**。
- **真正阻塞：Private Recalc queue E2E [#38274621290](https://github.com/tommylin15/janus-omniforge/actions/runs/38274621290) FAIL**。原始 Worker 安全日誌 [#38322879209](https://github.com/tommylin15/janus-omniforge/actions/runs/38322879209)：兩個 Task 中一個 `processed=1, succeeded=0, failed=1`，另一個 `processed=0`；Cloud Run 容器 SUCCESS ≠ owner 重算 SUCCESS。最後 verify Job FAIL。清理收據 [#38323214910](https://github.com/tommylin15/janus-omniforge/actions/runs/38323214910) `status=succeeded`／`active_request_failed=false`，不代表完成或刪除測試紀錄。根本例外類別與 owner 讀回尚 **UNKNOWN**，不得憑猜測重送。
- **最新 Release 僅建置完成、未部署**：安全彙總例外類別與測試修正的來源 `42ae0ff27d057c22d0b240c25322cf546808e261`，完整 [#38323413135](https://github.com/tommylin15/janus-omniforge/actions/runs/38323413135) **SUCCESS**（Python／Flutter／四 GHCR image／public pull）。**尚無該 SHA 的 Candidate、Jobs、Preview、Owner queue live 或正式 traffic PASS**，不能把新版診斷／重算宣稱已上線。
- **正式服務／UI**：既有正式 API 上次受控切流 [#38262691942](https://github.com/tommylin15/janus-omniforge/actions/runs/38262691942) PASS，當時來源 `b1bc785906212b8d2860b1521affb83930d09f04`；後續沒有本 P0 的新版正式流量切換證據。Preview 現為 `50eda...`（公開 readback PASS）。持股頁常駐重算按鈕、序列化 9 秒狀態輪詢的 Flutter 測試 PASS，但 **authenticated 390×844／desktop screenshot、按鈕→Worker→PnL 終態、其他持股／缺價隔離與冷啟動 P95 均未全驗收**。現行正式流量與 Preview identity 下次恢復前仍需重查。
- **下一入口**：先唯讀核實原失敗佇列的 `error_code`／ledger checkpoint／dispatch／殘留，再定位 Private Mart 業務例外；按需求最小修復、targeted tests、完整 Release、受控 deployment、單 owner 成功 queue E2E、真實 Owner UI、正式流量／回滾驗收。**暫停期間不執行以上工作**。

---

**歷史 checkpoint（2026-10-12，當時狀態）：個人持股 P0 PARTIAL／當時固定 Preview 已更新、正式 API 尚未切換；以本頁 2026-10-13 最新段落為準。** 研究 500 與 owner 持股分離、Ledger 買賣更新 membership、00719B TPEx 官方 EOD、Private Mart 串接及持股兩列視覺在整合原始碼 `0b0855c0fdeba0294bb0bb09bf33906216d779fa` 實作；完整 [Release #38224456544](https://github.com/tommylin15/janus-omniforge/actions/runs/38224456544)、0% [candidate #38225156313](https://github.com/tommylin15/janus-omniforge/actions/runs/38225156313)、[自動 OAuth #38225390463](https://github.com/tommylin15/janus-omniforge/actions/runs/38225390463)、[Job-only IAM #38226365438](https://github.com/tommylin15/janus-omniforge/actions/runs/38226365438) 與四 Jobs 可回滾同源 8/8 canary [#38226618808](https://github.com/tommylin15/janus-omniforge/actions/runs/38226618808) **全部 SUCCESS**，舊版 Jobs 成功不再視為待驗。PostgreSQL Migration 053 [#38244531637](https://github.com/tommylin15/janus-omniforge/actions/runs/38244531637) PASS。其後 00719B Owner 重算 [#38246053781](https://github.com/tommylin15/janus-omniforge/actions/runs/38246053781) FAIL；單 Owner 唯讀 Mart 讀回 [#38250985026](https://github.com/tommylin15/janus-omniforge/actions/runs/38250985026) **PASS**，證實持股 shares／cost、市價、市值、未實現 PnL／return、相同 ledger checkpoint 與 aggregate `available` 已持久化，但舊 Iceberg `mart_user_positions` 缺 `price_status`／`price_date`，不能將缺 metadata 當作缺 PnL 數值。相容 schema evolution／回歸測試已寫入 main，修正版完整四 GHCR 映像 [Release #38251449161](https://github.com/tommylin15/janus-omniforge/actions/runs/38251449161) PASS（來源 `b1bc785906212b8d2860b1521affb83930d09f04`），同源 API 0% [candidate #38253341992](https://github.com/tommylin15/janus-omniforge/actions/runs/38253341992) PASS、自動 OAuth／私有負向驗證 [#38253596061](https://github.com/tommylin15/janus-omniforge/actions/runs/38253596061) PASS；**新版四 Jobs 同源受控 rollout [#38253861084](https://github.com/tommylin15/janus-omniforge/actions/runs/38253861084) SUCCESS**（所有必要步驟通過，舊版成功證據仍保存）。其後單一實際 00719B Owner Private Mart 寫入及正式報價／price metadata／PnL／ledger checkpoint 驗收 [#38257614968](https://github.com/tommylin15/janus-omniforge/actions/runs/38257614968) **PASS**，執行 `janus-private-pipeline-hp7pk`，同來源 `b1bc785906212b8d2860b1521affb83930d09f04`，不更動交易帳本、未修改其他 Owner。00719B 本次受限驗收可標 PASS。固定 Preview 同源 tag 發布 [#38259811978](https://github.com/tommylin15/janus-omniforge/actions/runs/38259811978) **PASS**，公開 live readback 初次 [#38260082698](https://github.com/tommylin15/janus-omniforge/actions/runs/38260082698) 於 `GET /api/v1/public/market-home` 冷讀 **28s Timeout／FAIL**；唯一有界唯讀重試 [#38260612716](https://github.com/tommylin15/janus-omniforge/actions/runs/38260612716) **PASS**：同源 Flutter build SHA、正式 100% 流量不變、TAIEX 30 筆官方歷史至 2026-10-12，市場活動／法人 `available`，2327／2330 五組估值各 30 點，owner 未登入 401，market 首讀 11,334 ms／暖讀 49 ms，估值暖讀 78 ms。**冷啟動效能分布仍 PARTIAL**，不可用一次成功替代 P95 或抹掉第一次 timeout；整體持股 P0／Owner 390×844 與 desktop 真實登入截圖、500 檔外持股與 UI 無價多檔隔離的真實可視驗收、正式 API 100% 切流均尚未完成。盤中 TPEx 不冒充 MIS tick，價格使用官方可用 EOD／provenance，未認證的券商持股變化不推定。

**2026-10-12 首頁視覺優先固定 Preview 更新／真實市場 readback PASS（本輪範圍），正式 App／整體四頁仍 PARTIAL。** 同源 SHA `8b515f10fa2d4784235446185ad0c9d1337cbbdd`：今日首頁以官方 Core TAIEX 30 個有效收盤日畫 5／20／30 筆切換及放大圖，市場活動及三大法人改長條／數字卡；公開 `/market-home` 將歷史日期、source、provenance 於同一請求回傳，盤中 MIS 與收盤歷史分開，缺資料不造假。首次 cold 首屏等待上限 24s 且獨立區塊不阻塞，但這**只防過早 timeout，沒有證明效能 SLO**。全套 GHCR Release [#38206654851](https://github.com/tommylin15/janus-omniforge/actions/runs/38206654851) PASS；Cloud Run 0% candidate [#38207011213](https://github.com/tommylin15/janus-omniforge/actions/runs/38207011213) PASS；自動 OAuth／owner-private negative [#38207164718](https://github.com/tommylin15/janus-omniforge/actions/runs/38207164718) PASS；固定 Preview [#38207239328](https://github.com/tommylin15/janus-omniforge/actions/runs/38207239328) PASS；同源固定 Preview live TAIEX／估值公開 readback [#38218147437](https://github.com/tommylin15/janus-omniforge/actions/runs/38218147437) PASS：TAIEX 30 個已發布有效點、`history_as_of=2026-10-12`、source `taiex`、市場活動／法人皆 available，正式流量 100% 前版且 owner 未登入 read fence PASS。該一次冷請求 **19,198 ms**，同一 public `/market-home` 暖請求 **66 ms**；不是 P50／P95，**效能仍 PARTIAL**。四頁真實 Owner 390×844 screenshot、首屏耗時分布、正式 100% 切流、VF-07 季財報／月營收／法人可比歷史與 VF-08 私有跨日估值、B9 研究品質仍未完成。本段不聲稱整體 WBS／模型品質結案。

**2026-10-12 四頁視覺化第二輪：完整 Release／dev 0% 候選／自動 OAuth／固定 Preview／已發布圖表 readback 均 PASS，正式 App／整體產品仍 PARTIAL。** 來源 SHA `2ebc875953209875123d4cba04659661e68d1685`：個股 A→B→A 舊回應隔離、估值 null 日期斷線與重繪、合法點數守門、官方事件去重／公告和生效日時間軸。完整 GHCR [#38197376475](https://github.com/tommylin15/janus-omniforge/actions/runs/38197376475) Python＋Flutter＋四映像匿名 digest PASS；Cloud Run [0% candidate #38197718590](https://github.com/tommylin15/janus-omniforge/actions/runs/38197718590) PASS；自動 OAuth／私有未登入負測 [#38197849073](https://github.com/tommylin15/janus-omniforge/actions/runs/38197849073) PASS；[固定 Preview #38197920240](https://github.com/tommylin15/janus-omniforge/actions/runs/38197920240) PASS；[公開真實資料 readback #38198005001](https://github.com/tommylin15/janus-omniforge/actions/runs/38198005001) PASS（2327 PE/PB/殖利率及 2330 PE/PB 各 30 點、資料日 10/08，重複暖請求 83 ms；單次速度**不是**整體 P95）。正式 `janus-api` 仍為前版 100%；四 Jobs [#38188900482](https://github.com/tommylin15/janus-omniforge/actions/runs/38188900482) rollout PASS 但來源 SHA 不同，不可推論本輪一致性。**仍未完成**：VF-00 全涵蓋/PIT、官方月營收/EPS/法人可比序列、私有持股跨日趨勢、四頁 authenticated Owner 截圖、手機/P50/P95、產品 C/B9、同源正式流量切換；不得宣稱產品結案。詳細見 [四頁視覺 B 工單](../ui/visual-first-delivery.md)。

**2026-10-12 發版 OAuth 政策：**每版 GitHub Actions 不再以人工 Google OAuth 登入／consent／A→B→A 為必經 gate；同來源自動 OAuth metadata／private 授權負測仍需 PASS。Jobs／API promotion 改核 `auth_boundary_run`，舊人工 owner receipt 僅留歷史。這次是規則／程式變更，不等同新版已完成 traffic promotion 或完整 Owner 資料驗收。


**2026-10-11 最新順序決策：B9 產品功能驗收 → C 組及剩餘產品整合 → 產品交付 → 500 檔歷史研究池／五角色模型研究。** 可靠計算／規則先服務；ML 品質獨立保留 NOT VERIFIED／PARTIAL。這是文件與驗收邊界更新，不是功能／部署／模型 PASS。接手見 [Codex 作業指示](../codex-execution-plan.md)。


更新：2026-10-11（Asia/Taipei）
證據優先：GitHub `main`、GitHub Actions／live runtime；已完成記錄放 archive，active acceptance 見 [TODO](../todo.md)。

## CEO 第一階段修正／052 live evidence（2026-10-11）

- **程式／完整 Release：PASS，live CEO report：NOT VERIFIED。** Gemini `_prompt` 加完整 JSON schema、帶真實五份 specialist hashes 的 insufficient-data 範例、schema field-only validation audit；未驗證輸出仍 fail closed，歷史不改寫。API/Flutter Admin 將每日額度上限由 20 改為 50、冷卻仍 300 秒，並加模型／PostgreSQL 負向測試。
- [Analysis CI #38141015494](https://github.com/tommylin15/janus-omniforge/actions/runs/38141015494) SUCCESS；[完整 GHCR Release #38141150467](https://github.com/tommylin15/janus-omniforge/actions/runs/38141150467) SUCCESS（source SHA `93a0f9f49c2645d7eee610aa1dec9e061b6d9260`，Python 1051 passed／2 deselected；Flutter 73 passed／build；四映像 public pull/digest）。此後 `main` 僅有 052 migration request 等操作／文件更新；不把 GHCR 映像存在當成新 worker 已部署。
- **[Migration 052 #38141163200](https://github.com/tommylin15/janus-omniforge/actions/runs/38141163200) PASS**：`janus-ingestion-core-vhkbj` 執行成功，SQL hash `724aed33da1d752c3ce63bd8e2e911a2034eabbc742a5bed15ce1d401db0990e`，未更換 Job image／API traffic；只放寬 DB constraint，不自行更改原 Owner capability revision。
- **尚未結案**：新的 CEO 專用 GHCR image 與既有 dev worker 版本一致性尚未接受本來源驗收；API 新候選／Admin owner capability 50 的 live readback、至少一次有效 Gemini CEO report hash＋immutable history readback 仍缺。先前 `invalid_structured_output` BLOCKED 請求不可覆寫／重送。正式 dev API 100% 流量與四排程 Jobs 保持原有發布 gate；不因上述 PASS 宣稱第一階段全程 PASS。

## 下一步：B9 產品功能驗收（模型研究後置；B0～B8 不重做）

- **B0～B6：CLOSED／PASS**。完整過往驗收入口見 [TODO B 組摘要](../todo.md) 與對應 `archive/group-b-*`；不重跑已通過 reader、500 screening、Deep Coverage／cache、ML/OOS Parquet path。
- **B7 月度執行機制與 derived-cache freshness：CLOSED／PASS（本次最新 Core）**。月度 retrain/OOS 原執行、25 specialist refs、immutable artifact readback 已由 [#38027085666](https://github.com/tommylin15/janus-omniforge/actions/runs/38027085666) 驗收，不再重跑。先前 B6 的 historical source fence 已透過獨立 PyIceberg current-source refresh 收斂：[#38056677635](https://github.com/tommylin15/janus-omniforge/actions/runs/38056677635) **34 targeted tests PASS，Core `sha256:687fae3e…`、11,432 ML/OOS rows、new reconciliation `pass/current/exact-core`，新 manifest／GCS create-only receipt bytes readback PASS**。原先月度 `partial` 保留原始歷史、不覆寫；本次 `retrained=false`、無 CEO／BQ／promotion。完整證據見 [B7 freshness 結案](group-b-b7-derived-cache-freshness-closure-2026-10-10.md)。
- **B8：CLOSED／PASS（已核准的 dev 固定 Core 同源效能／FinOps／backend 選路／有界故障回退）**。Screening/日常 Specialist **PyIceberg 預設**；ML/OOS 只有明確 opt-in 才用 BigQuery，無 cutover。500 screening [#38029803051 attempt 2](https://github.com/tommylin15/janus-omniforge/actions/runs/38029803051) 36 targeted tests、同源 parity PASS（BQ 此輪較慢）；ML/OOS equal-run [#38033560821](https://github.com/tommylin15/janus-omniforge/actions/runs/38033560821) 10,978 rows／0 differences、兩輪 BQ billed 40 MiB、兩條路徑 sink 不同故優劣 inconclusive。[B8 B5 最終整合／GCS live #38037557795](https://github.com/tommylin15/janus-omniforge/actions/runs/38037557795) **SUCCESS：44 tests**，B5 正式 CLI PyIceberg 預設＋BQ 明確 opt-in、BQ 運作故障安全 fallback、BQ export 已啟動後禁止競寫；真實 74,999 Core source → 10,978 ML/OOS 與 immutable Parquet 零差，並以新版 B5 CLI 真實驗證 10,978 rows B6 cache hit（無新的 BQ jobs）。故障為受控注入，非實際 BQ outage；**未部署新 Mart image**，因既有 Job 只執行 PyIceberg Specialist／ML/OOS Parquet consumer，非此 B5 standalone 產製 CLI；不宣稱 fresh-Core cache-miss live materialization。B7 新 Core derived-cache freshness 已另於 #38056677635 PASS，B9 quality 仍 NOT VERIFIED；不重訓、不改 canonical。詳見 [B8 結案](group-b-b8-closure-2026-10-10.md)。
- **B9：ACTIVE／PARTIAL（模型品質 NOT VERIFIED）**。B7／B8 已結案，不重跑月度 retrain。新增獨立唯讀品質稽核，[GitHub Actions #38061999283](https://github.com/tommylin15/janus-omniforge/actions/runs/38061999283) 對同一 Core fence 的 **25 份 specialist／29 組 OOS evaluation** immutable GCS bytes readback **PASS**（9 targeted tests；無重訓／promotion）；新版 OOS v5 逐筆 PIT lineage 已有 [Mart CI #38062072521](https://github.com/tommylin15/janus-omniforge/actions/runs/38062072521) **143 tests PASS**，但 v5 live output 尚未驗收。但目前 5-symbol Deep Coverage 的跨股票 Rank IC／after-cost 為缺值，Event classifier OOS、歷史 membership replay、各角色 champion-vs-baseline 尚未達品質驗收，**B9 不得標 PASS**。逐角色數值、缺口與 evidence 見 [B9 品質證據](../b9-quality-evidence.md)；C 組依最新決策待 B9 產品功能 gate 通過後按授權啟動，不等待研究品質結案。
- **B9 品質實測補強（2026-10-10）**：[B9 #38063424389](https://github.com/tommylin15/janus-omniforge/actions/runs/38063424389) 以更新的唯讀 per-model scorecard 取得 12 targeted tests／25 specialist／29 OOS immutable GCS readback PASS；[selective CI #38063424379](https://github.com/tommylin15/janus-omniforge/actions/runs/38063424379) SUCCESS。真實同 OOS 5 日 Fundamental/Valuation/Quant 共七模型的 MSE 均不優於 zero-excess-return baseline；Risk 月度 OOS 15/23 月優於 Gaussian（8/23 未優於）；Event classifier OOS 缺失。詳細見 [B9 診斷](../b9-quality-evidence.md)。**研究分析功能可用≠模型品質 PASS；不可 promotion，B9 仍 ACTIVE／PARTIAL。**
- **GHCR CI/CD：PASS（目前核准的 dev 發布範圍）**。四 Jobs 8/8 canary 與 API 新→舊→新 traffic rollback 的真實證據見 [2026-10-10 CI/CD 結案](cicd-ghcr-api-promotion-2026-10-10.md)。四項額外／歷史檢查由使用者 [豁免](../parking-lot.md)，不列待辦、不冒充技術實測 PASS，亦不重開舊 AR/GCS 清理。

- **B9 Fundamental（2026-10-11，程式修復階段）**：同份官方財報 EPS／歸母淨利比較值的 period-basis 去重與 OOS PIT/source lineage 已分離修復；新增只補官方缺漏比較值的 `fundamental-history` ingestion mode，以及同窗 zero/rule/LightGBM walk-forward MSE 對照。獨立 [#38097863145](https://github.com/tommylin15/janus-omniforge/actions/runs/38097863145) 47 targeted tests PASS（7 warnings），**尚未部署／真實回補／新 Core OOS readback**；不能宣稱財報缺口已消除、ML 優於規則或 B9 PASS。細節見 [B9 品質證據](../b9-quality-evidence.md)。不同 SHA 的後續 B9 其他角色改動仍須分別驗收。

## 2026-10-11 合併產品工作包

使用者已授權 B9 產品、C 組及剩餘持股／首屏先整套開發，再集中驗收及發布正式 dev。目前 **ACTIVE／PARTIAL；整批 live acceptance／正式發布尚未完成**。新來源 `2c920782bc45736ffb0749d7ec0800d19f0ab153` 的 [完整 Release #38118061761](https://github.com/tommylin15/janus-omniforge/actions/runs/38118061761) PASS：1044 Python tests（2 legacy deselected）、Flutter、四公開 GHCR 映像與匿名拉取；migration 050／051 已執行。受限 CEO Job 及其 Job-only API IAM／費用已取得使用者明確授權。

[0% 候選 #38118406366](https://github.com/tommylin15/janus-omniforge/actions/runs/38118406366)／[受限 worker 更新 #38118539210](https://github.com/tommylin15/janus-omniforge/actions/runs/38118539210)／[兩次基準 runtime 與固定 preview #38118621503](https://github.com/tommylin15/janus-omniforge/actions/runs/38118621503) 均 PASS，兩次實際 execution 終態成功、無 LLM，發布租約已釋放。候選／preview 為 `janus-api-00465-feq`（0%）；正式 dev 仍 `janus-api-00457-wed`（100%），四排程 Job 未更新。新版 A 登入、390px 持股版本修正、候選 MCP OAuth／PKCE／redirect／未登入 401／三個唯讀工具宣告已實測；未呼叫 ledger write。先前有界持股 latency 僅代表當次暖請求，Today 冷啟動觀測另保留，不宣稱全站首屏效能 PASS。

既有候選的 owner／MCP／基準 runtime 與歷史失敗證據見 [產品候選 checkpoint](product-b9-c-holdings-checkpoint-2026-10-11.md)。先前專用憑證修復路徑已由下方 Gemini 最小上線 checkpoint 取代；目前仍缺有效 CEO 報告／不可變 history、四排程 Jobs canary／rollback 與 API 正式切流，不標整批完成。500 檔歷史與模型研究仍後置。

## 其他 active work

- **持股頁 UX／首屏加速**：ACTIVE；固定頁首、價格漲跌語意、migration 050／API latency／Flutter 真實 Owner UI acceptance 仍在 [TODO](../todo.md)。
- **B 組**：B7 月度機制／freshness 與 B8 均已結案，下一工程入口為 B9 產品功能驗收；模型品質列產品交付後研究；不重做 B7／B8。
- **C 組**：依本次授權與 B9 產品及剩餘產品整套開發、集中驗收，不等待五個 ML 勝出；範圍為 On-demand CEO provider/runtime、capability/quota、Admin profile、User 分析／重新分析、final AI-dependent visual acceptance；不得把 A 組 CLOSED 當成 C 組完成。
- **Dev Pilot 長期 evidence**：依 [bounded pilot ledger](document-cleanup-2026-10-25/pilot-operational-evidence.md) 持續觀察；不得將單次 successful workload 視為整個觀察視窗完成。

完整未完成清單只以 [todo.md](../todo.md) 為準；未排程構想見 [parking-lot.md](../parking-lot.md)。

### CEO 最小上線路徑更新（2026-10-11）

**Gemini 已連上並回應，但回傳內容未通過 CEO 報告格式檢查，尚未產生報告。** 來源 `a60db85e179c61896f047fb8c89d1e855fbc1e12` 的完整 Release、CEO image build 與 worker 部署均成功；唯一一次 Gemini 真實呼叫已終止，沒有重送。原有失敗紀錄保留。

使用者指定沿用 `janus-runtime-bundle` 的 Gemini API key 與已確認的 AI Studio Free tier，CEO 只用 `gemini-3.5-flash-lite`；omniAgent 統一 AI 入口後置。專用 `janus-mart-codex-auth` 已依要求刪除，Shared Secret 未讀取／修改。下一步先修正提示詞，明列必填 JSON 欄位與範例，再驗證不可變報告；每日額度依最新要求改為 **50**、冷卻仍 300 秒，目前 runtime 仍為 20，migration 052／API／Admin 設定尚未部署。正式 dev 切流與四排程 Jobs 驗收仍未完成。

依使用者要求，**本 checkpoint 先回寫文件，再開始下一次真實驗收**。完整證據與待辦見 [Gemini CEO checkpoint](product-ceo-gemini-checkpoint-2026-10-11.md)。
