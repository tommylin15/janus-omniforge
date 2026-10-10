# Janus 新版 CI/CD — 2026-10-10 最新 active acceptance（PARTIAL）

本節優先於 [歷史 CI/CD TODO](archive/cicd-todo-prior-checkpoints-2026-10-09.md)。目前現役真實 dev 專案仍是 `gen-lang-client-0593591102` 的 GHCR parallel-live，**本次僅完成第二輪 full GHCR 發布、0% 候選、固定 Preview、安全基準與負向 OAuth 驗收；新版 100% 與四 Jobs 新版尚未切流**。舊 AR／GCS 清理不列本次待辦，不動 DB、backups、Iceberg、個人交易或筆記。

- [x] **2026-10-10 不需人工的 CI/CD 補強驗收**：固定 Preview 相同 source SHA 的 no-write live retry [#38009514370](https://github.com/tommylin15/janus-omniforge/actions/runs/38009514370) PASS（receipt `VERIFIED_FIXED_PREVIEW_IDEMPOTENT`，正式流量／tag 未異動且 owner lease 已釋放）；更新後健康失敗必須恢復原 preview SHA、若恢復失敗必須留鎖的**模擬故障回歸** [#38009586797](https://github.com/tommylin15/janus-omniforge/actions/runs/38009586797) PASS。刻意 GCP live 故障演練另列 NOT VERIFIED。
- [x] **可逆 Release 安全閘門**：正常 API 升流量必須有 `reversible_ghcr` Jobs receipt（含舊版基準已驗證、可回復、前版 source identity），服務更新讀回檢查 100%／Ready／RoutesReady／generation／其他 tags／非 traffic config；API 和 Jobs 新來源自動化 request 模板目前皆 `approved=false` 且不觸發任何正式更新，未來請求需匹配完整 SHA 和同源真人 owner 收據。含錯誤狀態測試 [CI #38010078101](https://github.com/tommylin15/janus-omniforge/actions/runs/38010078101) PASS。
- [x] **新版 0% candidate 存在時原 GHCR rollback baseline 複驗**：更正錯把 `latestReadyRevisionName` 當 100% active 的舊檢查；[live #38010139996](https://github.com/tommylin15/janus-omniforge/actions/runs/38010139996) `PASS / gcp_writes=0`，四 Job config/image／正式 API Ready、Scheduler 和 lease 均符合原完整基準。初次誤判 [#38009753176](https://github.com/tommylin15/janus-omniforge/actions/runs/38009753176) FAIL 已保留，不能隱藏。
- [x] **Private Pipeline 歷史差異非敏感分類**：[readonly #38010200797](https://github.com/tommylin15/janus-omniforge/actions/runs/38010200797) 執行了 45 條設定路徑的單欄位刪除比對，未找到與原 hash 一致的單一變更；歷史設定 parity 仍 `NOT_VERIFIED`。此項只代表完成可行的診斷，**不代表 parity 已驗證**。另 Research 舊 AR registry image 不可讀依既有風險項追蹤，不阻擋已通過的四個 GHCR target baseline。
- [x] **上一版現役 GHCR 基準**：`fbcc5f58a2fa31f2f36dc4c82702fb62910c7361` 來源的四 Job pinned digests／八次 live canary、API `janus-api-00451-cuw` 正式 100% 流量，Scheduler `ENABLED`；[forward Jobs #37915584159](https://github.com/tommylin15/janus-omniforge/actions/runs/37915584159)、[API Ready route recovery #37943709614](https://github.com/tommylin15/janus-omniforge/actions/runs/37943709614) PASS。原始 Git-ref lease 已安全釋放，無本次強制解鎖。
- [x] **可用作下一次新版 rollback baseline**：[GHCR read-only real dev #37954237695](https://github.com/tommylin15/janus-omniforge/actions/runs/37954237695) PASS，四個舊版公開 immutable digests、四 Job config fingerprints、正式 API Ready、Scheduler／executions／writer／lease 都由 GCP readback 證實；`ops/ghcr-active-baseline.json` 只保存已觀察非敏感 identity。未來 rollout 要求 `reversible_ghcr`、上一版 digests/fingerprints 與 Registry readback，2026-10-09 舊 AR forward-only waiver 僅適用指定歷史 SHA，不可用於新版。
- [x] **第二輪新來源 full-test GHCR**：source `038498c70e12488f345c3ca0fbe821846ddee4cc` 的 Python／Flutter 完整 gate、四映像 GHCR build/push、匿名 registry/public digests [#37953986962](https://github.com/tommylin15/janus-omniforge/actions/runs/37953986962) 全 PASS。
- [x] **新版 API 0% candidate**：[run #37954588954](https://github.com/tommylin15/janus-omniforge/actions/runs/37954588954) PASS，`janus-api-00457-wed`／`ghcr-038498c70e12` tag、digest／build SHA／health／401、正式舊版 100% 保護與原 lease cleanup PASS。
- [x] **新來源 OAuth/MCP 未登入邊界**：[run #37955226220](https://github.com/tommylin15/janus-omniforge/actions/runs/37955226220) PASS；修正原 workflow 把舊 AR 正式 Revision 名寫死的失效假設。**這僅是 401/403、OAuth metadata、MCP challenge，不是新 SHA 真人 authenticated Owner/PnL PASS**。
- [x] **固定 Preview 正向發布已 live PASS**：[run #37956325838](https://github.com/tommylin15/janus-omniforge/actions/runs/37956325838)、receipt #11628296737，固定 `preview` tag 指向新候選 `janus-api-00457-wed`，固定 <https://preview---janus-api-2oo7qbkd5q-uc.a.run.app/app/> 的新來源完整 SHA／負向探測 PASS；原 preview `janus-api-00451-cuw` 與 SHA 留存，正式流量／其他 tags／service runtime config／Jobs／Scheduler 未改，owner lease `released=true`，獨立 ref readback 404。新流程是 `ghcr-preview-publish-dev.yml` + `ghcr_preview_publish.py`；失敗恢復已有 targeted tests，**尚無刻意引發失敗的 live restore 演練**。
- [x] **GHCR 新映像／Jobs 唯讀盤點**：[run #37955302314](https://github.com/tommylin15/janus-omniforge/actions/runs/37955302314) SUCCESS，四個新 image 的匿名 digest/source label PASS、舊版正式 traffic 維持；[#37955302241](https://github.com/tommylin15/janus-omniforge/actions/runs/37955302241) workflow SUCCESS **不代表所有 preflight PASS**：其 receipt `status=BLOCKED`，因受保護 Research Job `janus-research-big-move-500` 的舊 AR image 不可讀。此 Job 不屬四 Job GHCR 更新目標、尚未異動；應獨立標未知/阻塞而非忽略。
- [x] **新來源真人 A→B→A / PnL 人工確認：USER_ATTESTED PASS**：使用者於 2026-10-10 在本對話明確確認固定 Preview 的 A、B 隔離、拒絕 A 識別碼越權及回 A 的持股／PnL 一致，綁定完整 SHA `038498c70e12488f345c3ca0fbe821846ddee4cc` 和 `janus-api-00457-wed`。`ops/ghcr-owner-acceptance.json` 已更新，證據 [新來源人工驗收](archive/cicd-owner-browser-acceptance-2026-10-10-new-ghcr.md)；這是使用者確認，非 ChatGPT 持雙帳號重演。獨立只讀 MCP 正向 bounded `status=partial`、新候選 MCP 負向邊界 PASS，不能冒充跨兩 owner 新版 MCP E2E。**不因此將尚未執行的 Jobs/API 發布標 PASS**。
- [ ] **新版四 Jobs GHCR→GHCR 實際可逆發布（部署執行阻塞）**：真人 owner acceptance PASS 後，在原有共用 writer mutex／owner lease、Scheduler PAUSED／execution terminal fence 下，使用明確 `reversible_ghcr` request、上一版四 images＋config fingerprint 基準，更新四 Job 到新 digest、兩次獨立 canary／Job，測試失敗回復及真實 rollback 演練後恢復 Scheduler。不得把目前舊版八 canary 當新版八 canary。
- [ ] **新版 API 正式 100% promotion／rollback live（依賴新版 Jobs PASS）**：以新來源 SHA owner acceptance＋GHCR Jobs 終態 PASS＋舊版可回復 digest／source 為必要 gate，明確 100% traffic／rollback rehearsal／Ready／健康／PnL／MCP／其他 tags 和 lease readback；不使用舊 AR 失效映像或一次性 release 修復 workflow 冒充通用 Release。
- [ ] **固定 Preview failure restore live drill**：正常發布和原 preview SHA 保存已成功；測試有 fail-closed／恢復保護，但尚未對實際 Cloud Run 刻意觸發更新後失敗／restore（避免干擾使用者）；保持 `NOT VERIFIED`，不得改勾。
- [ ] **Private Pipeline 歷史完整設定 parity**：前次 AR→GHCR 非 image runtime config 曾遭更新，無可靠舊版完整 snapshot 可重建，故 `NOT_VERIFIED`；本輪的新 GHCR baseline hash 只表示**現役配置**已固定，不能倒推舊 AR 原設定。
- [ ] **受保護 Research Job 的舊 AR registry 引用**：本次 readonly receipt `BLOCKED`，需獨立盤點可靠可重建/恢復證據；Research 不在本次更新範圍，無核准前不得為解決 preflight 而更改其 image 或刪除資料。

- [ ] **安全阻塞記錄（2026-10-10）**：從 `ops/ghcr-jobs-rollout-request.template.json` 提交新 SHA `reversible_ghcr` 的真實四 Jobs request 時，執行環境安全檢查阻擋；GitHub readback 證實正式 `ops/ghcr-jobs-rollout-request.json` 仍為舊 SHA forward-only（未觸發新版部署）。待解除部署執行限制後，沿用已備妥四 GHCR baseline images/config hashes 和共用 lease，絕不以舊 waiver 繼續。

詳細歷史/最新證據：[第二輪 full GHCR／Preview](archive/cicd-ghcr-next-release-preview-2026-10-09.md) · [可回復 GHCR 基準](archive/cicd-ghcr-reversible-baseline-2026-10-09.md) · [舊版路由修復](archive/cicd-ghcr-live-route-finalization-2026-10-09.md)。只在必要真實 E2E gate 完成後才可將整體 CI/CD 設為 CLOSED。
---

# Janus — TODO

版本：3.22（2026-10-08：B7 ACTIVE，待 live acceptance；B8/B9 順序不變）
用途：**只保留確定要做的 active work 與未完成 acceptance**。Deferred、Candidate、Observation、Production-only、已接受缺口與研究構想統一放 [`parking-lot.md`](parking-lot.md)；已完成／被取代內容放 `archive/`。

## 規則

- 在本文件：**做**。必須有 implementation／acceptance，依下列順序執行。
- 不在本文件而在 `parking-lot.md`：目前**不做**，不得自行開工或計入未完成度。
- active work 可因外部核准或 runtime evidence 呈 `partial`／`blocked`；partial 不等於完成。
- 完成證據移至 `archive/` 或 `spec/operations-and-testing.md`，TODO 不保存歷史流水帳。

## 現行架構決策

### Token-first specialists + On-demand CEO

權威文件：

- [`decision-2026-10-03-token-first-specialist-and-on-demand-ceo.md`](decision-2026-10-03-token-first-specialist-and-on-demand-ceo.md)
- [`wbs/wbs-5-specialist-engines.md`](wbs/wbs-5-specialist-engines.md)
- [`spec/specialist-engines.md`](spec/specialist-engines.md)

目前產品契約：

- 五 specialist production 主路徑為 Python／SQL／ML，正常 path 不使用生成式 LLM。
- 約 500 檔在每個交易日 EOD canonical data ready 後做低成本 market screening／cross-sectional discovery；BigQuery 通過 fidelity gate 後優先承接這條全市場計算，不做 500×5 深度 specialist。
- 完整五 specialist 只做 `active watchlist ∪ effective holdings`，依 dirty dependency／input change 更新；無變更 reuse，不固定每日全重算。
- retraining／calibration／OOS evaluation／cache reconciliation 第一版固定 **每月第一個週六 10:30（Asia/Taipei）** 執行；不另設每週六 500×5 全量深算排程。
- plain-language output 由 structured output + SHAP／rules／templates 產生，正常 0 API token。
- Codex CLI／OpenRouter／Gemini 只用於 authorized manual On-demand CEO／approved rare escalation。
- CEO report immutable；重新分析建立新 execution/report，不覆寫舊報告。
- Admin 管 specialist model/evaluation、CEO provider/profile、DB-backed user capability、quota/cooldown、usage/cost/audit。

### Iceberg canonical + BigQuery analytics hybrid

權威文件：

- [`decision-2026-10-06-bigquery-analytics-over-iceberg.md`](decision-2026-10-06-bigquery-analytics-over-iceberg.md)
- [`spec/specialist-engines.md`](spec/specialist-engines.md)
- [`wbs/wbs-5-specialist-engines.md`](wbs/wbs-5-specialist-engines.md)

目前 B 組資料／運算契約：

- Core Iceberg V2／GCS 繼續是 canonical／PIT／provenance/history；BigQuery 不取代 canonical store。
- PostgreSQL serving projection 與 User／Admin request-time hot path 保持不變。
- BigQuery 只作 B 組 analytics compute；通過 cutover gate 後，優先承接 **每日盤後 liquid-500 screening**、cross-sectional features、OOS/evaluation 前處理與 ML training dataset preparation。
- 禁止 BigQuery Storage Read API；小結果走一般 query/result API，大型 training data 走 versioned GCS Parquet export artifact。
- 不預設複製整套 Core 到 BigQuery native storage；temporary/TTL derived data 可用但不可升格 canonical。
- 資料角色固定：Iceberg/GCS 保存 canonical/PIT/history；BigQuery intermediate 是可重建 compute；大型 training/evaluation dataset 以 versioned GCS Parquet 保存；model/evaluation/specialist 成果依 Mart contract 保存。BigQuery 中間結果不要求再回寫一份 Iceberg。
- 先抽出 exact-snapshot analytics reader，再做 BigQuery compatibility/canary；無法證明與固定 Core snapshot 一致時保留 PyIceberg path。
- 本架構方向已核准；若 implementation 需啟用新付費 API／建立 BigLake/Lakehouse/BigQuery 計費資源或擴大 IAM，仍需另有明確授權。

### Admin UI scope

權威文件：

- [`decision-2026-10-03-admin-ui-scope-and-governance.md`](decision-2026-10-03-admin-ui-scope-and-governance.md)
- [`ui/admin.md`](ui/admin.md)

Admin operational convergence **不重做整個 Admin**。保留 `總覽 / 批次 / 個股 / 市場資訊 / AI 分析`，原 placeholder 收斂為 `資料治理`。第一版優先使用 Flutter Material，不導入第二套 metadata／orchestration control plane，也不要求大型 DAG／lineage graph／dashboard。

## 模型確認規則

- 每次只取下列順序中的一個可執行 WBS／工作組。
- 正式執行前依該項標示的【Sol】／【Luna】完成模型 gate；開始後以整體 acceptance scope 結案，不在內部 dataset／adapter／單一畫面反覆停等。
- 新付費 API／model／subscription、新付費 GCP 資源、重大權限擴張、不可逆大量刪除、MFA／OAuth consent／付款仍需使用者明確授權。

# 執行順序：A（CLOSED）→ B → C

依使用者 2026-10-05 指示，先完成上班族操作體驗／效能／Admin，再整合原 specialist 與 CEO 工作。執行細節與可貼給 Codex 的指令見 [Codex 執行指令](codex-execution-plan.md)。以下三組是唯一執行順序；後面的 1～8 是原 WBS acceptance 索引，不再代表先後順序，也不重複計工。

| 工作組 | 範圍與原待辦對應 | 主要模型 | 集中驗收 |
|---|---|---|---|
| A：操作體驗／效能／資料營運 | §6 Admin；§7 非 CEO 功能；§8 非 AI 相依版型；下列新增補強 | Sol | 一組 API／Flutter／資料營運回歸與一輪 dev browser/readback |
| B：specialist／增量快取／BigQuery analytics | §1 specialist + §2 rerun cache；BigQuery analytics hybrid；Admin 對應狀態接線 | Sol | 一組 reader/fidelity／引擎／cache 測試與 bounded dev 執行／reuse／OOS／FinOps readback |
| C：CEO／權限／最終整合 | §3 provider + §4 CEO + §5 Admin profile；§7 AI 整合；§8 剩餘驗收 | Sol | 一組端到端安全／UI 測試與最少已授權 provider live calls |

同組先完成相關程式、migration、UI、tests、文件再集中驗收，不逐檔／逐 API／逐股票獨立部署。失敗僅補跑受影響範圍；原 acceptance、必要安全檢查及真實 dev 證據保留。A 不因尚無 CEO 而延後基本 UI；§8 整體結案仍須所有條件成立。跨組連續執行須使用者明確指定全部組，依 PROJECT_RULES 的本次例外處理。

預警／推播／警訊 outcome 增補已移至 [Parking Lot](parking-lot.md) 與其獨立未來文件，不是本次 active scope；既有 Event specialist 與 OOS 照原契約。

## A 組結案

A 組 implementation／CI／dev runtime 與兩項人工 gate 已於 2026-10-06 全部驗收完成。完成證據已移至：

- [非佇列結案紀錄](archive/group-a-nonqueue-live-closure-2026-10-06.md)
- [latest-price／Ledger UI 驗收紀錄](archive/latest-price-ledger-ui-acceptance-2026-10-06.md)

A 組不再列 active TODO；下一個 active work 為 B 組。
## 2026-10-08 持股頁 UX／首屏加速（獨立於已結案 A 組及進行中的 B7）

- [ ] 「持股／紀錄／報表／筆記」固定頁首、四格只顯示持股、字體放大，台股漲紅跌綠。
- [ ] 官方昨收／當日每股漲跌／幅度與現持股價格變動有缺值、stale／日期與 owner-scoped guard；migration 050 真實驗收。
- [ ] 首屏不等待年度交易歷史、PnL、重算狀態；版本、報價日期與狀態一致；量測 API latency P50／P95。
- [ ] Flutter／Python targeted CI、dev deployment/migration、真實 User UI／Owner 一致性驗收。未通過維持 ACTIVE，不更動原 A 組 CLOSED 判定。

## B 組優先架構調整 acceptance

> **B0～B6 均已 CLOSED / PASS。** B5 [data path](archive/group-b-b5-ml-oos-data-closure-2026-10-08.md) 與 B6 [derived cache](archive/group-b-b6-ml-oos-cache-closure-2026-10-08.md) 各有獨立 live evidence。**恢復原訂 B7 → B8 → B9**：B7 月度 retrain/calibration/OOS/reconciliation 已啟動（未驗收完）；B8 再集中比較 BigQuery/PyIceberg 的效能／成本與 fallback；B9 模型品質及整體驗收。不重做 B4 cache，不因文件回寫把 B7 標為完成。

B 組開始五 specialist／cache 收斂前，先完成 [BigQuery analytics 架構決策](decision-2026-10-06-bigquery-analytics-over-iceberg.md) 的資料讀取邊界；此優先序不代表 BigQuery resource 已建立或啟用。

- [x] 抽出 exact-snapshot analytics reader；既有 PyIceberg path 先包成 reference／fallback，不改 canonical write path。完成證據見 [B1 reader](archive/group-b-b1-reader-acceptance-2026-10-07.md)。
- [x] 建立 BigQuery analytics adapter／compatibility probe，證明固定 Core snapshot 的資料／schema／null／時間／provenance fidelity。B2 CLOSED：沿用 20 contract tests、106 Mart regression、320-row fidelity；本次 shared catalog exact-snapshot mapping、native DECIMAL(20,4)/schema evolution、真實 ohlcv partition pruning 全 PASS，9 jobs 共 60 MiB billed bytes，immutable GCS evidence readback PASS。本輪無 IAM/canonical mutation，PyIceberg 仍為 default；workload canary/cutover 屬後續範圍。見 [B2 結案](archive/group-b-b2-closure-2026-10-07.md)。
- [x] B3 canary 禁止 Storage Read API 與 `bigquery.readsessions.*` 需求；未加入 `google-cloud-bigquery-storage`。大型 ML input 的 versioned GCS Parquet export 仍屬後續 training scope。
- [x] 建立每日盤後 liquid-500 screening：B3 已以真實 controller occurrence `market-screening/2026-10-07/16` 與 Mart execution `janus-intelligence-mart-7f8jl` 驗收；500 檔低成本 screening／cross-sectional ranking 完成，未擴成 500×5 深度 specialist。
- [x] B3 已加入 bounded query／column／partition guards 與 processed bytes／elapsed／peak RSS／artifact growth telemetry；未知 GCS I/O 維持 null，不補 0。
- [x] 同 fixed snapshot 已完成 PyIceberg／BigQuery deterministic canary compare；fidelity／budget PASS。未完成 default cutover gate，因此 **PyIceberg 維持 default**，不把 B3 PASS 誤寫成 BigQuery cutover。
- [x] B5 ML/OOS data path：shared catalog 的 bounded SQL reduction → BigQuery TEMP table → versioned immutable GCS Parquet，Mart live readback。驗收 [#37706568819](https://github.com/tommylin15/janus-omniforge/actions/runs/37706568819) SUCCESS；10,978 rows／499 symbols／533,945 bytes；首次 BigQuery billed 30 MiB，最終 immutable reuse billed 0；storage_read_api=false、CEO=false、LLM tokens=0。詳見 [B5 結案](archive/group-b-b5-ml-oos-data-closure-2026-10-08.md)。
- [x] B6：BigQuery-derived ML/OOS artifact dependency key／pre-query immutable verified reuse／selective invalidation／failure audit 已 CLOSED。CI #37708769385 137 PASS，live #37708769182 0 BigQuery jobs／billed 0、Mart readback PASS，來源異動 scenario 以 targeted tests 證實；見 [B6 結案](archive/group-b-b6-ml-oos-cache-closure-2026-10-08.md)。
- [ ] **B7 月度批次（ACTIVE；已推 main，等待 CI／dev runtime 與 artifact readback）**：將 `specialist-retrain`／calibration／OOS evaluation／cache reconciliation 的 effective schedule 統一為 **每月第一個週六 10:30（Asia/Taipei）**；實作時需修改實際 Scheduler／controller definition、協調依賴與工作流，並以 live runtime readback 驗證；文件本身不算完成。
- [ ] **B8 效能／成本／fallback 集中驗收（B7 後）**：B3 一次真實 canary 已記錄 PyIceberg 30.2256s / BigQuery hybrid 36.0608s（BigQuery 慢約 19.3%，valuation 部分未計入 BigQuery hybrid read）；B5 同 workload PyIceberg ML/OOS baseline 仍欠缺。於 B8 補相同 fixed snapshot、同 symbol/date/feature/output/PIT 的 PyIceberg vs BigQuery real-path，量測 cold/warm elapsed、RSS、BQ processed/billed bytes、GCS bytes（未知 null），並驗證安全 fallback 及 FinOps。不可拿 B5 SQL script 5.84s 與 B0/B1 完整 Mart 725.726/800.966s 直接比較；無證據不切換 BigQuery default。
- [ ] PostgreSQL serving projection 與 A 組既有 read path 不回歸；BigQuery failure 必須可 audit fallback，不影響 canonical ingestion/write。
- [ ] 若需啟用新付費 API、建立 BigLake/Lakehouse/BigQuery 資源或擴大 IAM，依 PROJECT_RULES 取得明確授權；未授權部分標 blocked，不以文件決策冒充 resource approval。

# 原 WBS acceptance（依上方工作組整合執行）

## 1. `WBS-5-MART-SPECIALIST-ENGINES` — 【Sol】

目前進度：`partial`。

先核對 [`spec/operations-and-testing.md`](spec/operations-and-testing.md) 已記錄的公開資料清理 apply/readback 與最新 runtime；依 [`spec/retention-governance.md`](spec/retention-governance.md) 只補尚缺的整合／排程證據，不為舊待辦重跑已完成刪除。其他治理／成本收斂併 A；不以文件過期阻擋 B。

- [x] 約 500 檔**每日盤後**低成本 market screening 已由 B3 CLOSED；Deep Coverage universe／selective execution／no-change reuse 已由 B4 CLOSED。兩者未混成 500×5 全量深算。
- [ ] Fundamental：deterministic financial features + LightGBM baseline。
- [ ] Valuation：deterministic DCF／reverse-DCF／relative valuation + LightGBM／CatBoost benchmark。
- [ ] Quant：LightGBM baseline + Qlib DoubleEnsemble challenger；以 Taiwan PIT walk-forward OOS 決定 champion。
- [ ] Risk／Regime：Riskfolio-Lib + statsmodels／ML。
- [ ] Event／Catalyst：parser／rules + local multilingual Transformers classifier。
- [ ] 五 specialist 產出 structured artifact、SHAP／feature contribution、deterministic plain-language report；正常 path 0 LLM API token。
- [x] Deep Coverage 使用 `active watchlist ∪ effective holdings`；持股離開 500 仍保留，清倉且不在 watchlist 才退出。B4 live acceptance 已驗 5 symbols × 5 roles。
- [ ] 完成 PIT／provenance／missing-data／public-private isolation、tests、dev deployment、live execution、artifact persist/readback 與 OOS benchmark acceptance。

目前 500 檔缺失 ≤10% 為使用者接受範圍；超過先討論，不直接判整體失敗或自行擴張補資料。Mart 資源維持使用者指定 1 CPU／1 GiB；需要提高時先提出 evidence，不自行升級。

使用者最新核准：歷史財報有資料就做 OOS，不再要求原始數值版次／當時公開時間已證明。採最新官方數值版本、優先官方公開／上傳時間，缺少時明示期末後 90 天假設；正式模型作法及結果標示見 specialist SPEC。價格標籤成熟與來源／品質／隔離檢查保留。

## 2. `WBS-5-MART-RERUN-CACHE` — 【Sol】

- [x] 建立 dirty dependency graph：依 accepted/rejected PIT dependency state、feature/engine/model version 只 invalidate 受影響 symbol/specialist；B4 已有 regression + live evidence。
- [x] monthly revenue／financials、EOD price、event 依 specialist dependency mapping 選擇性 invalidation；event-only regression 已驗 1 computed / 4 reused。
- [x] 無 input change 直接 reuse，保留可稽核 cache identity；B4 live 第二輪 0 computed / 25 reused。
- [ ] 每月第一個週六 10:30（Asia/Taipei）執行 retrain／calibration／OOS evaluation／reconciliation，檢查 missed invalidation、orphan artifact、cache identity、model version。
- [ ] specialist change 只標記 CEO report freshness／material delta，**不得自動觸發 CEO LLM**。

## 3. `WBS-5-MART-AI-PROVIDERS` — 【Sol】

有效產品範圍只有 On-demand CEO／approved rare escalation provider runtime。

- [ ] 重用既有 Codex CLI／OpenRouter／Gemini adapter、routing、auth、free/billing gate、fallback/audit 能力。
- [ ] default approved route 為 `Codex CLI → OpenRouter → Gemini`；只有 approved／authorized／free-or-explicitly-approved-paid profile 可執行。
- [ ] 完成 manual CEO request 的 headless dispatch、cold-start auth／續期、timeout／cancel／retry、route snapshot/version/hash、attempt/fallback、usage/cost audit、zero-secret-leakage。
- [ ] 不新增未核准付費 provider／model／resource。

## 4. `WBS-5-MART-CIO-SYNTHESIS`（legacy tracking ID）— CEO Analysis — 【Sol】

產品名稱與語意一律使用 **CEO Analysis**；上述舊 ID 只為既有 WBS／artifact traceability 保留。

- [ ] CEO 只讀最新 validated specialist outputs／Fact Pack／provenance；不得計算或覆寫 canonical numbers，無 publication authority。
- [ ] 只由具 capability 的使用者明確 request；Scheduler、行情或 specialist dirty event 不自動觸發。
- [ ] 產出 thesis、cross-specialist conflict resolution、bull/base/bear、risks、invalidation conditions、unknowns；validator failure 保持 structured partial／blocked。
- [ ] 每次分析／重新分析建立新 immutable execution/report；保存 requester／trigger audit metadata。

## 5. `WBS-6-ADMIN-ANALYSIS-PROFILE` — 【Sol】

- [ ] 管 specialist champion／model／version／evaluation 與 CEO provider／model／profile；保留 immutable version history、rollback、audit、test symbols／compare。
- [ ] 加入 DB-backed Google user capability 管理，例如 `ceo_analysis.request`；backend enforce，Flutter visibility 不可代替 authorization。
- [ ] Admin 顯示 CEO provider approval／auth／health、model list、quota/cooldown、usage/cost；不得接收或顯示 raw token。
- [ ] `Codex CLI → OpenRouter → Gemini` 只適用 On-demand CEO／approved escalation。

## 6. Admin operational convergence — 已完成 A 組範圍

已移入 [A 組結案證據](archive/group-a-nonqueue-live-closure-2026-10-06.md)；B／C 的模型與 CEO 接線保留於其對應待辦。

## 7. User operational convergence — 【Sol／Luna】

- [ ] 【Sol】Stock Detail backend 增加 bounded CEO command/status/history API；驗證 authenticated user、`ceo_analysis.request` capability、symbol/profile、in-flight、quota/cooldown。
- [ ] 【Luna】Stock Detail 顯示五 specialist persisted plain-language outputs、最新 CEO report、analysis/data as-of、dirty/freshness/material-change、immutable history，以及有權限帳號的 `分析／重新分析`。

非 AI Journal／Watchlist／Stock Detail UX、typed formatter 與四頁 390px browser gate 已完成 A 組驗證；交易驗收交接見上文。

## 8. `WBS-6-USER-FINAL-VISUAL-CONVERGENCE` — 【Luna／Sol】

四頁非 AI presentation／PNG references／Flutter regression／authenticated dev browser 已完成 A 組驗證；本 WBS 整體仍保留 B／C 的 AI 整合驗收。

- [ ] Stock Detail persisted-first、manual CEO only、permission-aware、history immutable、freshness/material-change visible。
- [ ] specialist／CEO 接線後再驗四頁 AI-dependent state；不得把 A 組非 AI 結案當作此 WBS 全部完成。

## 完成證據

每個 TODO 至少需有與範圍相稱的 implementation、tests／CI、deployment、migration（如適用）、live runtime／integration acceptance。文件勾選、commit、build、upstream benchmark 或單次 bounded success 本身都不等於完成。

## 歷史／決策入口

- [2026-10-03 Token-first 五 specialist 與 On-demand CEO](decision-2026-10-03-token-first-specialist-and-on-demand-ceo.md)
- [2026-10-03 Admin UI 範圍與資料治理呈現](decision-2026-10-03-admin-ui-scope-and-governance.md)
- [WBS-3 補資料第一版完成（2026-10-03）](archive/wbs-3-data-supplement-v1-completed-2026-10-03.md)
- [2026-10-02 Admin／User／Routing／Provider 歷史決策](archive/decision-2026-10-02-admin-user-routing-and-provider-plan.md)
- [Parking Lot／暫不做](parking-lot.md)

其他已完成／被取代證據保留於 `archive/`；完整 runtime／deployment evidence 見 `spec/operations-and-testing.md`。
