# Janus 最新驗收證據索引

## 2026-10-26 SEQ-08 已驗證最終部署（歷史 10/25 記錄仍保留、以此較新狀態為準）

| 階段 | Artifact / Workflow | 本次實際狀態 |
|---|---|---|
| 固定新版 source | `462bd1c85708cb5bc4ce1877d35a3645ff9668d4` | Quant/Risk 非交易日最新有效市場交易日(≤7d)與整體 Screening v3同市場≥100 cohort；五 UBJ 不變 |
| 完整 GHCR 同版發布 | [#40215268427](https://github.com/tommylin15/janus-omniforge/actions/runs/40215268427) | full Python/Flutter/4 digests PASS |
| 舊 Job image/config 唯讀基線 | [#40215440753](https://github.com/tommylin15/janus-omniforge/actions/runs/40215440753) | 4/4 來源舊版 `a2881c5c...`；GCP 寫入0 |
| API 0% candidate | [#40215944127](https://github.com/tommylin15/janus-omniforge/actions/runs/40215944127) | PASS |
| Auth negative / OAuth | [#40216220752](https://github.com/tommylin15/janus-omniforge/actions/runs/40216220752) | PASS，不等於 Owner 正向登入 |
| 四 Dev Jobs 固定 digest rollout | [#40216332296](https://github.com/tommylin15/janus-omniforge/actions/runs/40216332296) | `jobs-rollout` completed/success；`{"result":"PASS"}`，receipt artifact #12607933703 |
| Dev API 100% fixed source | [#40247497520](https://github.com/tommylin15/janus-omniforge/actions/runs/40247497520) | `promote-api-only` completed/success；未改Jobs、Storage、Owner或IAM |
| 真實全市場 Screening | [#40247788673](https://github.com/tommylin15/janus-omniforge/actions/runs/40247788673) | 已觸發既有 Mart Job 的有界 `market-screening`，目前仍 `in_progress`，尚無終態 |
| 新真 Core Deep Coverage + PG + 2330/2882 | — | **NOT_YET_VERIFIED**；前輪 10/25 的 Quant0/8、Risk0/8 舊收據不能作新版缺陷修正成果 |
| Owner 正向登入新版 UI | — | **NOT_VERIFIED**；歷史畫面不可證明新版模型結果；MCP read-only 目前 internal error |

本次 user-approved 模型替換不重新徵求發布權；GCS 五頭正式 Registry沿用 [#40193843435](https://github.com/tommylin15/janus-omniforge/actions/runs/40193843435) 已驗證 create-only，沒有重建或換權重。後續唯一入口：Screening 執行結果 → 有界 Deep Coverage → 原子不可變 Mart 產物／PG實際讀回 → 公共股票 2330／2882 → Owner授權 UI；若資料缺值維持 partial，不以 CI／workflow green 替代實際數值。

## 2026-10-25 SEQ-08 真實 Mart 讀回與非交易日根因／離線修復

- **固定前輪線上映像**：`a2881c5c2532beb5570e29a1fda4472c7bb0d448`；五真 UBJ GCS/Registry ACTIVE [#40193843435](https://github.com/tommylin15/janus-omniforge/actions/runs/40193843435) PASS、四既有 Dev Jobs [#40184957380](https://github.com/tommylin15/janus-omniforge/actions/runs/40184957380) PASS、API100 [#40192646498](https://github.com/tommylin15/janus-omniforge/actions/runs/40192646498) PASS。
- **真正 Dev Mart 工作**：[ #40195093746](https://github.com/tommylin15/janus-omniforge/actions/runs/40195093746) `REAL_JOB_PASS_PRODUCT_CONTENT_READBACK_PENDING`、Cloud Run execution `janus-intelligence-mart-fqxjb`、Mart execution `ab806a93-c2d6-46da-ab54-74056bc3cd26`。
- **產物精確唯讀**：[ #40202862020](https://github.com/tommylin15/janus-omniforge/actions/runs/40202862020) = `READBACK_PASS`，Core snapshot `sha256:52256efff0dfef6c26441c47854625306dd4c439389d709c98a1f374c2d7acc7`，`analysis_as_of=2026-10-25`；目標8股（已去識別不輸出Owner組合），Quant 0/8、Risk 0/8、Fundamental 2/8、Valuation PE+PB 4/8。2330、2882均**不在該次私有target union**，不能擅自加入Owner資料；PG `private.specialist_product` 的SQL讀回、Owner本人報告/歷史/UI仍 `NOT_VERIFIED`。
- **日期與原因二次唯讀**：[ #40203590101](https://github.com/tommylin15/janus-omniforge/actions/runs/40203590101) = SUCCESS；八股 `latest_trade_date=2026-10-22`，與週日 `analysis_as_of=2026-10-25` 不同，Risk `no_current_trade_observation` 8/8，Quant 同因且 `full_market_same_day_percent_rank_missing` 8/8。Fundamental 六股缺基期/足月因子，其中二股無有效月營收或market；Valuation四股 `missing_unambiguous_comparable_mops_quarters`。這是已觀察的特徵及來源不足，不是模型重新訓練的證據。
- **CODE 已修正但尚未發布**：`analyst_inputs.latest_eligible_market_session()` 只認至多7天、價格最新日必須等於已觀測市場最新日，不能以分析當日為非交易日而令全角色X空白，也不能將停牌／過期數據視為新值；`market_screening.market_features/rank_features` 依合格市場日計算 Quant15 `ret20_market_rank`，至少100檔完整同市場群組、原百分比tie邏輯與原 `analysis_as_of`、Core snapshot 保持；明示 `source_trade_date`，不使用Owner8檔本身排名。額外 `tests/test_seq08_market_sessions.py`。截至本筆線上仍舊 `a2881c5c...`，修正版 commit `be4c8073af289029cf1a65846b68df8244930eb1`，尚未 Release／Deploy。Selective [#40204115769](https://github.com/tommylin15/janus-omniforge/actions/runs/40204115769) PASS，PostgreSQL/product CI [#40204115801](https://github.com/tommylin15/janus-omniforge/actions/runs/40204115801) PASS。
- **SEQ-08 唯一後續工程**：修正版同SHA Release＋Dev Jobs/API受控部署→新市場日期/新 Core snapshot 真實 Screening 完整 cohort → 有界Mart/PG/報告讀回，不能改寫已存在immutable 10/25 市場排名；2330/2882應走獨立公共資料驗收，Owner正向登入無授權session則列實際缺口。無舊模型相容/回復前置，不問第二次人工發布授權；整體目前為 `LIVE_PARTIAL`，不是 CLOSED。

### 2026-10-25 SEQ-08 首次真 Mart 驗收失敗與安全收斂

- 首次受控 Live Mart run [#40194391101](https://github.com/tommylin15/janus-omniforge/actions/runs/40194391101) = **FAILURE**；僅有 `tests/test_seq08_real_mart_acceptance.py` 2 passed，operator 回報 `RuntimeError`，不可將此 Workflow 判為實際 ML 推論 PASS。
- 受控**唯讀**後驗 [#40194848340](https://github.com/tommylin15/janus-omniforge/actions/runs/40194848340) = SUCCESS：下載前輪失敗 receipt，`prior_phase=PREFLIGHT`、`prior_dispatch_maybe=false`、`operation_exists=false`；既有 Cloud Run Mart 最新十筆 execution 均為以前例行工作（最新 created UTC 12:31:50，早於12:44此次嘗試）；`lease_status=ABSENT`。**可證前輪未派送一筆本次 Mart Job**，現役五頭 GCS ACTIVE／API100不受此預處理失敗影響。
- 修正 `scripts/gcp/seq08_real_mart_acceptance.py`：在取得全域 lease 前即記階段；dispatch POST 前把結果標成可能不明並保留 lease，避免網路中斷時盲目二次派送；失敗只輸出受控代碼與階段。新版重試必須以新的 GitHub main HEAD 觸發、在取得 lease 前不再插入其他 commit；不推論上輪 RuntimeError 根因為已證實的 source drift。
- 正式 2330／2882／Owner、`four-model-serving.json`／PG／登入 UI 的 Live 驗收在取得新執行收據前仍為 **PENDING**。

## 2026-10-25｜SEQ-08 集中發布：已驗證 GCS ACTIVE + Dev Jobs + API 100%／Live 待驗

| Gate | 最新收據 | 判定 |
|---|---|---|
| 真模型 GCS 五頭候選匯入 | [#40182200560](https://github.com/tommylin15/janus-omniforge/actions/runs/40182200560) | create-only + SHA 回讀 PASS；五份XGBoost UBJ |
| 同版 Release | [#40184318031](https://github.com/tommylin15/janus-omniforge/actions/runs/40184318031) | 固定 app SHA `a2881c5c2532beb5570e29a1fda4472c7bb0d448`，完整 Release PASS |
| API candidate / Auth | [#40184723596](https://github.com/tommylin15/janus-omniforge/actions/runs/40184723596)、[#40184856961](https://github.com/tommylin15/janus-omniforge/actions/runs/40184856961) | 0%/OAuth負向邊界 PASS；非 Owner 真人登入證明 |
| 四 Dev Jobs | [#40184957380](https://github.com/tommylin15/janus-omniforge/actions/runs/40184957380) | controlled Jobs rollout `phase=PASS`，四 Job 各2次 canary |
| Dev API 100% | [#40192646498](https://github.com/tommylin15/janus-omniforge/actions/runs/40192646498) | existing API-only bounded workflow `PASS_API_ONLY_100_PERCENT`；基本build SHA、health、未登入拒絕；未改Jobs/Owner/Registry |
| Registry 變更前讀回 | [#40193222840](https://github.com/tommylin15/janus-omniforge/actions/runs/40193222840) | 舊Risk DETERMINISTIC，其餘舊pointer缺失，SEQ08 原子pointer缺失；沒有冒充 ACTIVE |
| 新版五頭正式 Registry | [#40193843435](https://github.com/tommylin15/janus-omniforge/actions/runs/40193843435) | `CREATE_ONLY_ACTIVE_SHA_READBACK_PASS`，five_head_sha_verified=5；單一 `models/registry/seq08-four-models-active.json`，SHA `2d00df0e8f5685db59ba7b3695ca412b440a366a99cd753c15e9b42aa60427b0`；Owner/PG/其他模型候選變更0 |
| 真 Core Mart 一次工作 | [#40194391101](https://github.com/tommylin15/janus-omniforge/actions/runs/40194391101) | 一次既有 Mart `deep-coverage` 受控真資料驗收已啟動；**終態未知／LIVE_PENDING** |
| 2330、2882、Owner 正向／UI | — | **NOT_VERIFIED**；不得用模型ACTIVE或匿名負向401冒充正向產品驗收 |

此表是 2026-10-25 SEQ-08 比本檔較早的 preflight 敘述更新的**實際狀態**。五頭模型直接替換，未保留舊模型預測相容；API 基礎設施故障安全回復仍照既有 runbook。不重訓、不重派補財報、不新增付費GCP／排程。**退出條件尚缺**：非fixture五頭對正式 Mart X 的真實可用率、`four-model-serving.json` 與 PG 產品投影對照、2330／2882與 Owner 本人報告／歷史／UI 正向讀回及缺值理由，必須按一次有界結果如實判定 partial/pass。

### SEQ-06 四模型 user-approved 真 Artifact／GCS 指標核對（2026-10-25；LOCAL_RELOAD_PASS／GCS_NOT_ACTIVE）

- **核准**：使用者在2026-10-25明確核准 Quant、Risk、Fundamental、Valuation 四模型發布，已解除人工 publication approval；並未授權捏造缺值或以未驗收推論宣稱ACTIVE。未新開付費 API、模型或GCP資源。
- **真模型下載／本地重載**：Quant XGB15 SHA `3fb509cb7ca8aa5e4a0ec3ca9139a1d355995478a624e1043853f59500cbffe9`，8 test vectors 誤差0；Risk XGB12研究 refit SHA `e00d302b082fb135991dc4e6f146cf4b9b7dbb56311daae27539564a629e05eb`，12X原生重載（缺訓練 test vector 與終版全歷史模型）；Fundamental RC1 XGB15 SHA `05fa3167f10c650389c4e481c3e3a7de8a2b70f9133ad867f0404c3eb9758b0c`，原生重載、研究5% abstention另需serving；Valuation v26 PE SHA `56060b37fb1c18efa9ba3e5c7352b10eca12c8d13990bc6031cdfad15d3bc610`、PB `c0984c82039307788e2af4c962a5e7376bdd2b29a30cecfcff557a91811ffe7a`，各5個固定向量誤差0。來源均為Drive唯一根`janusChatGPT`，暫存封包未上傳GCS，不是 ACTIVE 指標。
- **real dev Registry readback**：[GCS exact pointer audit #40177858431](https://github.com/tommylin15/janus-omniforge/actions/runs/40177858431) `completed/success`、gcs_writes=0：Risk `DETERMINISTIC`（**目前沒有Risk XGBoost ACTIVE**）；Quant/Fundamental/Valuation均 `POINTER_MISSING`（非PermissionDenied）。前一 #40177726233 將 missing 泛化成 READ_ERROR，已改明確分類並獨立重跑。無上傳、無CAS或PG mutation。
- **Valuation accounting code**：[d15e4d70](https://github.com/tommylin15/janus-omniforge/commit/d15e4d70af9d0238822918698be3f0ea9efaa8f6) 對正式 XBRL Core 指標 `total_assets_snapshot`／`total_liabilities_snapshot`／`total_equity_snapshot`／`net_income_year_to_date`／`revenue_year_to_date` 建立真MOPS consolidated同季+去年相同季度、TWD、日期檢查及衝突拒絕；產出 `roe_proxy`、`debt_ratio`、`log_total_assets`、`revenue_yoy`、`market_code`。研究資料把資產仟元轉元，Core原本已是元，不重乘1000。schema code／target tests [CI #40177556379](https://github.com/tommylin15/janus-omniforge/actions/runs/40177556379) success、[分析產品PG契約 #40177556535](https://github.com/tommylin15/janus-omniforge/actions/runs/40177556535) success；**Mart 真實五欄覆蓋未部署驗收**。
- **服務阻礙，須於SEQ-08排除**：Risk目前8X常數與Registry pin須增量支援12X及四新X，不能直接替換；Quant 目前11X／候選15X，缺新增欄；Fundamental目前9X／候選RC1 15X + 5%拒絕預測gate，沒有條件仍輸出null；Valuation雖映射五因子，現役單頭`valuation-active.json`不能同時發布PE/PB兩頭，且需以真Core資料驗收口徑。GCS候選應以create-only導入與SHA讀回再做必要serving修改、CI、API／Flutter＋rollback及Registry原子切換；不做無界調參重訓或新增自動排程。



### SEQ-04 Owner／Admin 真實登入後 UI 正向驗收（2026-10-25；USER_SCREENSHOT_PASS）

- **證據類型**：使用者於本輪對話提供5張2026-10-25台灣時間16:46–16:48的Dev真實手機瀏覽器截圖；只在對話中檢視、不上傳GitHub/GCS，不記錄Google電子郵件、實際持股代碼／股數／成本／現金／損益或任何Session／Token。
- **Owner UI 正向=PASS**：User App已載入「今日」摘要、本人現金及參考資產、持股與損益列表、個股詳情中的本人持股／成本／損益／公開事實卡；不是匿名API 401、樣板空畫面或fixture，因此可結清本次**使用者實際登入後的Owner UI可讀**。截圖無HTTP／Bearer／API原始回應，因此**不能**由此單獨認定session驗簽、User OAuth token audience、owner workspace snapshot API或跨Owner A/B isolation全面PASS。
- **Admin UI 正向=PASS**：Admin管理後台顯示登入帳號識別、營運自動工作狀態及GCS六桶盤點結果（有實際物件計數與容量）；可證明使用者實際登入環境的Admin畫面及盤點功能載入。截圖不能直接證明Admin token audience驗簽、跨角色API授權邊界或完整後台所有API；這些仍依既有同版自動auth契約與Runtime API收據判斷。
- **獨立功能提示，非auth blocker**：截圖中全市場上市／上櫃顯示部分資料缺漏；Owner持股頁手動更新報價提示「報價暫時無法更新、保留最後資料」。兩項保留為下一次自然ingestion／報價功能檢查資訊，不將其冒充OAuth錯誤，也不把缺值當0。截圖只證明當前已部署版User/Admin界面，**不驗收尚待SEQ-08部署的新版四模型報告、Owner history與UI**。
- **判定與後續**：SEQ-04 `OWNER_UI_AUTH_POSITIVE=PASS_SCREENSHOT`、`ADMIN_UI_AUTH_POSITIVE=PASS_SCREENSHOT`，**Owner/Admin真人UI登入待辦結清，不要求使用者再次登入或創建第二帳號**。嚴格API層的有token正向／wrong audience／server-side Owner A/B isolation，若本次無實際執行收據則維持`NOT_DIRECTLY_VERIFIED`，不捏造；依[OAuth runbook](../runbook-user-oauth-dev.md) 既有policy：2026-10-12已取消將每版真人A→B→A作發版前置，繼續使用自動auth boundary及同來源測試。SEQ-04整體仍需10/26新版自然資料鏈與新週備份收據，不能僅由截圖宣告FULL_PASS。


### SEQ-07 分析報告、Owner history 與 UI 程式／離線驗收（2026-10-25；OFFLINE_PASS／LIVE_DEFERRED）

- **source SHA**：[f9ace32b795e6c1895901e7750f18be2f57da575](https://github.com/tommylin15/janus-omniforge/commit/f9ace32b795e6c1895901e7750f18be2f57da575)。程式包含固定四角色ML serving→既有Mart product JSONB／週期事實報告、Owner token 綁定的不可變歷史讀取 API `/api/v1/me/analysis/{symbol}/reports`、唯一 Valuation 卡及 Flutter Advanced 分析/歷史；CEO按需維持手動；Gateway／CEO history讀取失敗，UI 不阻斷已保存事實卡。
- **離線真實CI收據**：[Python #40175446096](https://github.com/tommylin15/janus-omniforge/actions/runs/40175446096) `completed/success`，275 passed／7 skipped／2 warnings（含 SEQ-07 Owner history 單元測試）；[最新選擇性Python #40175926343](https://github.com/tommylin15/janus-omniforge/actions/runs/40175926343) `completed/success`，272 passed／7 skipped／2 warnings；[Flutter / Web PWA #40175926335](https://github.com/tommylin15/janus-omniforge/actions/runs/40175926335) `completed/success`，widget tests＋Web build＋PWA assets PASS。
- **保留失敗與修復**：Flutter #40175446120 初始測試 fixture 誤放 admin mock，#40175734768／#40175871947 受頁面增加內容後 test button offscreen（800×600）影響；已修正 fixture、測試 scroll-to-visible，以及新增 CEO 不可用但事實報告可用案例，最新CI成功。此為離線測試修復，不代表真實登入或 Gateway 端到端已驗證。
- **部署界限**：依 SEQ-07 卡四階段，集中部署留給 SEQ-08；本次無 GCP rollout、migration、新表、新排程、新服務、registry ACTIVE 切換、模型訓練、Owner 真實資料寫入及付費 LLM 呼叫。下個入口固定 SHA／artifact／digest 受控部署及 2330、2882、Owner 持股／觀察、分析／估值卡／報告歷史／Gateway（既有授權）實際讀回；Quant/Fundamental/Valuation 正式 artifact／Valuation accounting mapping 欠缺驗收，不得因UI能顯示狀態而稱四模型完成。



### SEQ-04 本週 weekly 補建及舊備份 occurrence 修復（2026-10-25 16:08 Asia/Taipei；PASS）

- **本週不可變 weekly=PASS**：[GitHub #40175398373](https://github.com/tommylin15/janus-omniforge/actions/runs/40175398373) `completed/success`；12項相關測試通過，透過既有WIF、固定GCS source generation與目的 `ifGenerationMatch=0`，將已成功的 `2026-10-19` daily 備份建立為 `weekly/2026-10-19.dump`。**新建1份、30,872,328 bytes**；新週副本逐位元SHA-256與PG `control.ledger_backup_requests` 原daily大小／checksum完全一致，目的generation `1792915700206005`。未新建daily或執行pg_dump、不覆寫或刪除任何備份。此為**2026-10-19週的真實副本**，不是預先製造下一週 `2026-10-26` 的備份；下週自然首次成功仍獨立待驗。
- **舊00:30 occurrence=PASS**：同run只對 `ledger-backup/2026-10-25/00` 作一次CAS，預先核對原 `running`、本日 `control.ledger_backup_requests` status `succeeded`、retention `succeeded`、有效size/SHA/completed；`cas_updates=1`，同交易補寫 `control.batch_event_outbox` **1筆事件**，實際PG回讀 `status=succeeded`。不是靠另一筆02:30的成功冒充00:30，也沒有重跑備份。**獨立後驗**：[現有backup audit #40175661818](https://github.com/tommylin15/janus-omniforge/actions/runs/40175661818) `completed/success`，台灣00:30原紀錄 UTC `2026-10-24 16:30:00` 已回讀 `ledger-backup|succeeded`，與02:30另一筆 `succeeded` 分開可見；不再列為running。
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


## 2026-10-25｜SEQ-08 直接替換模型：GCS import preflight 工程收據（尚未部署）

- **使用者核准：** Quant／Risk／Fundamental／Valuation 四角色直接使用新版，無須再次人工發布授權。舊 Risk8、舊 deterministic 推論、既有不存在的模型不再作相容／模型回復前置；本決策與資料／Auth／API 安全防護分離，見 [PROJECT_RULES §0.3](../PROJECT_RULES.md)。
- **版本與代碼：** 原始整合 commit [810b0fb6](https://github.com/tommylin15/janus-omniforge/commit/810b0fb6a7b49e99f8d12813093855e37ac81ca7)，修測試後同版 HEAD [e415048c](https://github.com/tommylin15/janus-omniforge/commit/e415048cf97d5a89aaacde40ebcf7759451887da)。新增 `scripts/gcp/seq08_candidate_import.py` 對五份新 UBJ 固定 SHA256、12／15／15／5／5 維度、已知 Risk／Val 特徵順序、來源位置、preprocessing與型態做預檢；`--apply` 只上傳既有 Dev Mart GCS `models/candidates/` 的 create-only 物件並下載讀回，**不觸碰任何 ACTIVE pointer、Risk PG、API 流量或 Owner 資料**。新增四組單元測試、接入既有分析CI，不增加 workflow、Job、Scheduler 或付費服務。
- **CI 結果：** [Selective #40179984749](https://github.com/tommylin15/janus-omniforge/actions/runs/40179984749) completed/success；[Analysis/Postgres #40179984775](https://github.com/tommylin15/janus-omniforge/actions/runs/40179984775) completed/success，均為 SHA `e415048cf97d5a89aaacde40ebcf7759451887da`。前兩輪 [#40179732146](https://github.com/tommylin15/janus-omniforge/actions/runs/40179732146)／[#40179899825](https://github.com/tommylin15/janus-omniforge/actions/runs/40179899825) 新fixture錯誤已修；歷史失敗未偽裝PASS。
- **刻意未宣稱：** 本次執行環境尚無五份可讀的真實 UBJ 檔案／相應本地 manifest 可用於上述 CLI，未執行 `--apply`、無任何GCS candidate create-only readback；Risk仍由最近 [#40177858431](https://github.com/tommylin15/janus-omniforge/actions/runs/40177858431) 實測為 DETERMINISTIC，Quant／Fundamental／Valuation ACTIVE pointer 不存在。Risk12／Quant15／Fund15 abstention／Valuation v26 PE+PB 的新正式 serving reader、PG/Registry與一次產品鏈完整 live 尚未完成；不能把 CI PASS 說成四模型上線。
- **繼續同一 SEQ-08，不新增序號：** 補足五權重之有界可讀輸入及原研究 schema→候選import真hash讀回→新版特徵與五頭推論→固定SHA Release／Dev Job/API/Flutter→2330／2882／既有Owner有界正向驗收。Dev既有業務兩小時排程不重建。

## 歷史收據

- [截至 2026-10-25 整理前的完整收據](../archive/document-cleanup-2026-10-25/operations-and-testing.md)：保留歷次失敗、恢復、來源 SHA 與範圍，不改判歷史結果。
- [更早的 2026-10-15 基線](../archive/documentation-baseline-2026-10-15-operations-and-testing.md)。

維護方式：同一事件的新結果取代本頁摘要時，把完整舊收據移到 archive 並留下連結；不要每次重新追加全部結案歷史。
