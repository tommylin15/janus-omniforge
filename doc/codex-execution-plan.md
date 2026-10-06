# Codex 執行指令：操作體驗、效能與低成本營運收斂

更新：2026-10-06

本文件是 [TODO](todo.md) 工作組的執行方式，不是第二份待辦或完成紀錄。需求／安全依 [PROJECT_RULES](PROJECT_RULES.md)，各原 WBS 的 acceptance 保留；checkbox 與剩餘工作只在 TODO 維護。2026-10-05 使用者要求預警暫緩，其餘盤點改善整合既有工作，相關程式盡量一次寫完再集中驗收。本次建立文件不代表已執行下列工作。

## 可直接貼給 Codex 的指令

```text
請先讀 doc/PROJECT_RULES.md、doc/README.md，再安全同步 GitHub main；不得覆蓋本機未提交修改。
依 doc/todo.md 的工作組順序與 doc/codex-execution-plan.md 執行全部剩餘工作組，保留原 WBS 的驗收追蹤。
先核對最新程式、CI、runtime evidence，重用已完成成果，不重做 migration 042、已完成回補或憑證輪替。
本次目標是完成非預警的 UI、讀取效能、Admin、資料治理、成本控制與既有 specialist／CEO 待辦。
B 組優先採 doc/decision-2026-10-06-bigquery-analytics-over-iceberg.md：Iceberg 保持 canonical，BigQuery 只作 analytics compute，禁止 Storage Read API，PostgreSQL serving 不動。
同一工作組先完成所有相依程式、migration、UI、測試與文件修改，再集中跑適用測試與一次整合 dev 驗收。
不要每個檔案、API、畫面、股票各自 commit、build、deploy、驗收或要求確認；失敗只重跑受影響範圍。
完成一組後接續下一組；外部授權或資料不足只阻擋相依部分，其他已授權工作繼續。
遵守既有模型 gate；同組以 Sol 為主要執行模型，UI 不必逐頁切換模型。不自行啟用平行 agent。
預警、推播、通知送達與額外 outcome 產品不執行；見 Parking Lot 連結的未來文件。
不新增／提高付費資源、不部署 production、不擴大 IAM、不自動呼叫 CEO、不擴大資料刪除。
任何 commit 或 push 前先執行 /ponytail-review。依現有 main／dev 流程交付，記錄真實結果，不把 partial 寫成完成。
```

使用者只指定單一工作組時，就只執行該組；上方「全部剩餘工作組」指令被明確下達後才跨組連續執行。不是因本文件存在就啟動實作。

## 1. 開始前只做一次必要核對

1. 檢查工作樹／分支，fetch GitHub；能 fast-forward 才同步，遇到 divergence 或使用者改動先保留，不 reset／clean。同步造成的未追蹤殘留也不得自行刪除。
2. 讀目標 TODO 與直接相關 SPEC／WBS／UI；涉及四頁時讀 Final Visual Contract 並實際檢視可解碼 PNG。
3. 建立簡短差異表：已完成可重用、仍缺實作、只缺 live evidence、外部 blocker。保留原 WBS ID，不複製已完成工作。
4. 效能工作先取一輪 bounded baseline：實際裝置／網路、冷／暖啟動、各頁核心內容可见時間、API 次數、auth／DB／Core query source／scan／lock 等待；不為盤點製造長時間壓測或付費工作。

同步後已知基礎：migration 042 的 serving projection 與 hot-path 已有 [完成證據](archive/stock-serving-projection-042-completed-2026-10-04.md)。因此全表掃描改善限尚未覆蓋的摘要／fallback 等路徑，不把所有個股讀取一律視為全表掃描。041 operational position projection、Iceberg compaction、共用 runtime image 與 specialist idle-transaction 修正已有程式；是否滿足目標 acceptance 仍核對最新證據。不要重新做已完成的 migration、全量 backfill、憑證 rotation 或複製 runtime image。

## 2. 工作組 A：User／Admin、讀取效能與資料營運

來源：TODO「User operational convergence」的非 CEO 項目、「Admin operational convergence」、「Final Visual Convergence」不依賴新 AI 能力的部分，以及本次效能／FinOps 補強。主要模型【Sol】。

### User 與 read path 一起修改

- 修正 Stock Detail 在 build 內建立 request future、所有 section 等待最慢 dependency、無效 retry；request 隨 symbol／session 明確更新，主要內容先顯示，K 線／進階內容延後或按需載入。
- 保留已訪問主頁的資料與捲動狀態，不預抓全部昂貴頁面；隱藏頁／背景／logout 停止行情輪詢，owner 切換清除私人狀態，回到前景再依 freshness 更新。
- 關注支援股票代號／中文名稱搜尋、名稱、行情日期、持股與待追蹤事項。新加入仍守現行 universe／quota；已關注離榜者保留並標示，不在 GET 停用或隱藏。同步核對 DB function／trigger、Deep Coverage union、quota 與所有呼叫者，不能只改 Flutter。
- 重用 042 projection；檢查 freshness、分頁／歷史範圍、空集合與 fallback 行為，不把過期 projection 當新資料、不靜默漏歷史。尚需 Iceberg 的 symbol/date 查詢下推 filter／selected fields，保留正確排序與 limit 語意。市場摘要只在 profiling 證明需要時以既有可重建讀取模型改善，不建立第二套 canonical store。
- 量測後改善 DB connection reuse／小型有界 pool、Google 公開驗證憑證 cache、重複 user upsert 與 serialized reader；不取消 token expiry／issuer／audience／allowlist／owner 驗證。pool 總連線需符合 e2-micro 能力，不用提高 concurrency 掩蓋排隊。
- 完成既定 Quote Router／persisted last quote：來源由 backend versioned contract 管理，先回最後成功值再有界更新；保留 quote_at、received_at、session、freshness，冷啟動及上游失敗仍可顯示有日期的舊值。共用行情與私人持股分離；不覆寫 EOD canonical valuation。
- 重用 041 與交易同步投影，核對買賣／更正後 shares、cost、cash 及 projection lag；Private Mart 的估值／PnL 仍為原契約，不能因即時操作成功就宣稱正式估值更新。補齊 Broker Profile 既定範圍，不新增成本法或券商同步。
- 四頁依既有資訊階層收斂，共用 typed formatter、分區 loading／empty／error／stale／missing。健康度與白話摘要優先，工程欄位與 CEO 留進階。不得趁此次加入預警卡、通知中心或推薦頁。
- 驗證四張 reference PNG。損壞時優先從可追溯 Git／原始資產恢復，不能用目前 UI 截圖冒充原 target；無有效來源時記錄 visual blocker，其他程式工作繼續。不得靜默重新設計 target。

### Admin／資料治理／成本一起修改

- 維持六個主頁與現有 shell。總覽只突出需要處理事項，partial 以白話說明受影響資料／數量；Admin 不展示私人 user-to-symbol mapping 或交易內容。
- 批次由 backend effective definition／occurrence 產生；包含實際存在的月度 specialist-retrain，區分已定義、已部署與已觀察成功。預設近 3 天，history bounded；安全 retry／manual run 沿用 allowlist、冪等與 dependency／exclusive guards。
- 以單一資料治理表取代 placeholder：資料層、最新成功時間、coverage、DQ、live／noncurrent／soft-deleted bytes、有效 retention、最後 maintenance、protected references。取不到顯示 unknown，不將 live bytes 當 billable bytes。
- 私人缺資料摘要只給本人；Admin 只給去識別化 aggregate。500 檔缺失 ≤10% 的已核准容忍度保留，同時顯示本人持股／關注可用率；缺值不等於零風險。TWSE-listed-only、非嚴格 PIT 財報研究與資料時間明示。
- 保留股號、日期、幣別、單位、必要價格／交易算術、provenance 與來源授權檢查；不為消除 partial 做全面歷史補齊或新增來源。涉及現有報酬／漲跌顯示時核對 corporate action；缺乏調整依據時標示不可比，不自行產生調整價。預警的 corporate-action 抑制規則留未來文件。
- 使用既有 telemetry／可讀帳單記錄 API p50/p95、request 數、query source／fallback、scan bytes（可得時）、Job duration／peak RSS／retry、cache reuse 與 storage growth。月成本以可取得的實際 billing 為準；歸因估算另標示，未知不補 0。不新增付費 BigQuery export 或監控平台。
- 比較 cleanup 耗時／操作量／回收量及有效版本政策，優先避免空轉與重複工作；改頻率若會違反 retention 時限先提出具體 contract diff／成本證據，不自行延長或加強刪除。既有成功清理 receipt 可重用，不為驗收反覆 apply。
- 保持既有區域、API min=0/max limits、PostgreSQL e2-micro／30 GB／無 external IP、Mart 1 CPU／1 GiB。未達效能時先定位原因，涉及常駐實例／資源升級僅提出待核准選項。
- 文件對齊：舊 coverage inventory 標明日期及最新證據入口；status／TODO 區分已驗收與 remaining；批次清單及 041／042／compaction 現況依證據更新。保留歷史，不大改 operations ledger。

### A 的集中驗收

一次合併 Python API／query／auth／owner／watchlist／quotes／ledger／Admin targeted tests，Flutter analyze 與受影響 widget／golden tests；採 repository 鎖定依賴與適合的 Linux／WSL 環境。先前 Windows 缺 pytz 是環境線索，不可跳過測試或認定 GCP 壞掉。

相關程式全部就緒後，一次部署受影響既有 dev 服務／Job（若有 migration 先按相依順序安全套用），同一輪 authenticated browser 驗收涵蓋 User 四頁、Admin 六頁、owner／audience 負向與資料讀回。mutation 使用受控 acceptance 資料及可稽核更正，不污染既有真實帳本。

效能目標：已訪問頁主要內容恢復 ≤300ms；暖機核心資訊可見 p95 ≤2 秒。記錄裝置／網路、樣本數與測量方法，建議同條件前後各 20 次 bounded 主流程；冷啟動／登入／外部行情另列，不把 20 次當生產 SLO 證明。未達需記錄瓶頸及剩餘 acceptance，不任意提高資源或宣稱通過。同一輪確認 projection source telemetry、fallback、390×844 無 overflow、分區錯誤不拖垮首屏、離頁停止輪詢。新 AI 未完成區塊可 bounded unavailable；不得因此宣稱整個 specialist／CEO 或 Final Visual WBS 完成。

## 3. 工作組 B：specialist／cache／BigQuery analytics 合併完成

來源：`WBS-5-MART-SPECIALIST-ENGINES` + `WBS-5-MART-RERUN-CACHE` + [BigQuery analytics 架構決策](decision-2026-10-06-bigquery-analytics-over-iceberg.md)；主要模型【Sol】。

### B 組 AI 作業指示

以下步驟按順序執行。除非遇到 PROJECT_RULES 的付費／IAM／不可逆／OAuth 人工 gate，不在每個內部步驟停下要求確認；可自行完成的 code/tests/dry-run 繼續做。任何未取得 live evidence 的項目保持 partial/blocked。

1. **建立 baseline，不先改 runtime。**
   - 讀 `specialist_runtime.py`、`storage.py`、`packages/duckdb_query/iceberg.py`、Core manifest／snapshot contract 與直接相關 tests。
   - 固定一份既有真實 dev Core snapshot／cohort，記錄 current PyIceberg row count、output hash、screening/evaluation result、elapsed、peak RSS、可取得的 GCS/scan evidence。
   - 不重做 A 組 migration、backfill、serving projection 或 UI。

2. **抽出 exact-snapshot analytics reader。**
   - 先把目前 PyIceberg path 包成 `IcebergSnapshotReader`（名稱可依 repository convention 調整），reference 行為不可改變。
   - 建立最小 `AnalyticsSnapshotReader` contract，只暴露 specialist 所需的 bounded dataset/features + snapshot identity/provenance，不把 BigQuery client object 傳進 engine。
   - 原 targeted tests 必須先在 abstraction 後維持 green，再加新 adapter tests。

3. **加入 BigQuery adapter，但先不切 default。**
   - 使用一般 BigQuery query/jobs client；可新增並 pin `google-cloud-bigquery`，**不得加入 `google-cloud-bigquery-storage`**。
   - 不使用 `.to_dataframe()` 的 Storage Read 加速路徑；小結果用 row iterator／一般 query result API。
   - adapter 必須接受 immutable Core execution/snapshot fence，沒有可證明的 exact-snapshot mapping 就 fail closed，不偷偷改讀 latest。

4. **做 BigQuery／Iceberg compatibility probe。**
   - 只用 bounded 真實 dev table/snapshot；核對 region、GCS location、schema evolution、decimal、timestamp/date、null、partition pruning、source/provenance。
   - Google legacy metadata-URI Iceberg external table 不作預設 final architecture；優先評估可共享 Iceberg metadata 的 Google-supported Lakehouse／Iceberg REST path或其他 exact-snapshot 方案。
   - **若下一步需要啟用 BigQuery/BigLake API、建立 dataset/catalog/connection/cache、增加 IAM 或產生新付費資源，而沒有本次以外的明確授權證據：不要 mutation。** 將該步標 blocked，保留 code/test/dry-run 成果並繼續不相依工作。

5. **先搬最適合 BigQuery 的 workload。**
   - 第一個候選：liquid-500 screening。
   - 第二個：cross-sectional rank/window/join 與 feature aggregation。
   - 第三個：OOS/evaluation preprocessing。
   - 不搬 User/Admin request-time read、Ledger/private owner path；不建立 full-Core BigQuery duplicate warehouse。
   - Query 強制 selected columns、date/symbol/partition predicate、bounded cohort；可用時先 dry-run/bytes estimate，設定合理 maximum-bytes fail-closed guard。

6. **建立 ML 大資料出口，不用 Storage Read API。**
   - 流程固定為 `Iceberg → BigQuery SQL reduction → bounded destination result（必要時）→ EXPORT DATA/versioned GCS Parquet → ML Job`。
   - Export artifact 保存 Core snapshot identity、analysis_as_of、schema/feature version、content hash/provenance、retention。
   - Temporary destination table 預設 TTL／可重建；不要把 intermediate 當 canonical。

7. **再整合 dirty dependency／rerun cache。**
   - input／feature／engine／model identity 與 BigQuery-derived artifact identity 一起納入 invalidation。
   - no-change 在昂貴 query 前判定 reuse；不是 BigQuery 算完後才比較 output hash。
   - monthly reconciliation 能檢查 snapshot mapping、artifact identity、fallback 與 orphan temporary output。

8. **做 deterministic canary 與 fallback。**
   - 同一固定 Core snapshot 對 PyIceberg／BigQuery 跑代表性 screening／feature／evaluation。
   - 比對 row set、null/missing、排序、aggregate、output hash/允許誤差與 provenance。
   - BigQuery timeout/quota/config/fidelity failure 必須安全 fallback PyIceberg 並可 audit；不能破壞 canonical write／PostgreSQL serving。
   - 只有通過的 workload 才切 BigQuery default，其他維持 reference path。

9. **FinOps／效能驗收後才決定擴大。**
   - before/after 記錄 BigQuery processed/billed bytes、query elapsed、Cloud Run elapsed/peak RSS、GCS I/O evidence（可得時）、export bytes、artifact growth、fallback/reuse rate。
   - 不宣稱 BigQuery 會讓 Core GCS storage bytes 自動下降；驗證重點是 Cloud Run data movement、Python/Arrow memory、重複 intermediate artifact 與 scan control。
   - 如果成本／效能沒有實質收益，保留 hybrid adapter 但不擴大 workload。

10. **完成既有五 specialist／cache acceptance。**
    - 依最新 specialist SPEC 完成 Fundamental／Valuation／Quant／Risk／Event、資料優先 OOS、dirty dependency、monthly retrain/reconciliation。
    - 500 檔只做低成本 screening；Deep Coverage 承接 A 的 watchlist／holdings 語意。
    - CEO freshness 可更新但不自動執行 CEO；Admin 只讀真實 evaluation/reuse/runtime 狀態。

### B 組集中驗收

先合併 reader abstraction、BigQuery adapter、query guards、export path、dirty cache、controller、artifact/retention 與 tests，再集中跑 targeted tests。若既有 GCP dev 已有相應已授權 BigQuery/Lakehouse 資源，可做 bounded real-data compatibility/canary；否則把 resource-dependent acceptance 標 blocked，不自行啟用或建立。

完成可執行的程式後，用同一固定 snapshot 做 PyIceberg vs BigQuery compare、no-change replay、必要的 selective invalidation、OOS readback與 failure fallback。保留既有 1 CPU／1 GiB specialist runtime限制；資料、模型、BigQuery fidelity、成本或授權不足都不得包裝成 full success。

## 4. 工作組 C：CEO、權限、Admin profile 與 User 整合

來源：`WBS-5-MART-AI-PROVIDERS`、`WBS-5-MART-CIO-SYNTHESIS`、`WBS-6-ADMIN-ANALYSIS-PROFILE`、User 的 specialist／CEO integration，以及 Final Visual WBS 的剩餘 acceptance；主要模型【Sol】。

後端 capability／quota／cooldown／in-flight、provider lifecycle／route、validator、immutable report/history、Admin profile／audit、User command/status/history 與 permission-aware UI 一次接好。沿用原 TODO acceptance；手動 Analyze 才呼叫、page load／dirty／Scheduler 不呼叫，重分析建立新報告，不覆寫 canonical numbers。

可先寫完不依賴 live specialist 的接口與錯誤處理；主要真實成功路徑需 B 的有效 persisted outputs。provider 額度與授權重新核對，歷史一次性驗收額度不能重用為新授權。缺 OAuth/MFA、合法 route 或資料只阻擋相依 live acceptance，不製造 mock 成功。

集中一次 backend／Flutter／安全／故障注入測試、一次相關 dev release。以最少已授權 live provider 呼叫完成 request → execution → report → history／readback → Admin audit，重分析能力仍需原契約所要求的證據；timeout／cancel／retry 等以合適測試補足，不刻意反覆消耗模型。共用 A 的未受影響頁面證據，只重驗 AI 區塊与受改動主流程；四頁最終 visual acceptance 仍需全部條件到位。

## 5. 集中驗收規則

- 「一次寫完」指同組有相依的完整 vertical slice，含 tests／migration／文件，不是最後才發現 schema 或安全設計不通。必要的 migration dry-run、資料保護、auth／owner 檢查可提前；不為節省次數省掉不可逆操作防護。
- 預設每組一個主要整合測試批次與一輪 dev release／acceptance，不為每個檔案或 checkbox 獨立驗收。這不是硬性次數上限；失敗、實質修改或證據缺漏才重跑受影響部分。
- 重用同 commit／等價未變更依賴的 CI、build、screenshot、readback，寫清涵蓋範圍；不得以舊證據驗收新變更。CI 已覆蓋的相同測試不無理由在本機再跑整套。
- commit 前完成適用本機／CI 前置檢查及 /ponytail-review；push 前亦須 review 覆蓋待推 diff。推送若觸發 canonical CI/deploy，沿用該流程，不另外重複建立／部署相同 image。
- 不停用既有必要 CI gates；先整合程式再一次送入現有流程。多服務可共用一輪驗收，migration 與部署仍遵守相依順序。
- 每組結尾只記一次 evidence summary：code/image、tests、deployment、runtime/readback、效能／成本、剩餘 blocker。TODO 只保留剩餘工作，原 WBS 逐項引用共用證據。
- 完成要求維持真實 dev／authenticated browser／persisted data；文件、build 或 partial 本身不算完成。沒有帳單權限不新增 IAM，成本數字維持 unknown 並列明限制。


## 2026-10-05 最新指示：Cloud 只接續 GCP dev 真實驗收

使用者在本地要求先 commit／push、完成目前版本部署，暫停剩餘驗收；Cloud 的重點為既有 GCP dev 真實測試驗證。這項指示覆蓋上方完整實作執行範本的本次使用範圍，不啟動剩餘功能或 B／C。最新部署結果由 status 連結 checkpoint。

可直接貼給 Cloud：

```text
請先讀 AGENTS.md、doc/PROJECT_RULES.md、doc/README.md、doc/status.md，
再讀 TODO 的 A 組與直接相關 SPEC／UI／Final Visual Contract。
此次只做既有 GCP dev 真實測試驗證，依最新部署 checkpoint 接續。

1. 確認 GitHub／gcloud 既有授權、User／Admin 真實登入及瀏覽器能力；
   缺 credentials／OAuth／MFA／browser 時列 blocker，mock 不取代 live。
2. 核對 main、GitHub Actions、API ready revision／流量與 Job digest；
   不重跑已成功的部署或 042／043 migration。
3. 對真實 dev API 驗證 auth／audience／owner、watchlist 搜尋／離榜保留、
   資料日期／缺值、projection／fallback、Admin 批次／治理讀取。
4. 用真實 authenticated browser 驗證 User 四頁／Admin 六頁、分區重試、
   導覽保留與隱藏／背景停輪詢；保存實際截圖、比對四張正式 PNG，
   檢查 390×844 overflow。未實作能力如實記錄，不臨時擴大功能。
5. 需要 mutation 時只用核准的受控 acceptance 資料與可稽核更正，
   不污染真實帳本；沒有安全資料就先完成讀取驗證。
6. 在 GCP dev 真實鏈路量測冷／暖 API 與頁面，記錄裝置、網路、
   樣本數、p50／p95、API 次數與可得 query／DB／Job telemetry；
   檢核導覽恢復 ≤300ms、暖機核心資訊 p95 ≤2 秒，不能量測就標未知。
7. 讀既有 maintenance receipt、Scheduler／Job、retention 與容量證據；
   不重複 cleanup apply，不觸發回補／retrain／CEO 作為一般驗收。
8. 產出通過／失敗／未實作／無法驗證清單，附 SHA、revision、時間、
   方法與安全 evidence，回寫 status／TODO；partial 不宣稱整組完成。

只有驗收發現缺陷才做最小修正、相關測試及受影響 dev 重新部署；
commit／push 前先 /ponytail-review。不開 B／C，不用 Superpowers／平行 agents，
不部署 production、不新增或提高付費資源、不擴大 IAM、
不自動呼叫 CEO、不做預警／通知。
```
