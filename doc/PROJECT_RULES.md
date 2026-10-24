# Janus — AI 基礎作業規則

所有 Janus／OmniForge 工作遵守本文件。文件角色先看 [`README.md`](README.md)。

## 0. 研究系統精簡（2026-10-24 最新決策）

依 [研究精簡政策](spec/research-simplification.md) 執行：取消獨立資料稽核、逐來源補證、全歷史 PIT／時間校準、例行品質重抓與前瞻成熟等待門檻。既有日期／單位／來源欄位可沿用，不做額外追溯工程。只保留直接影響功能、模型答案正確性與資料安全的檢查。本條覆蓋本文件其他章節及所有舊 SPEC／WBS／TODO／Drive 相反指示；取消不等於驗證通過。

本次只改文件與程式，不執行測試、CI、部署、批次或 runtime 驗收；後續依 [WI](runbook-research-simplification-wi.md) 交接。

## 1. 權威與事實判定

### 1.1 目前實作／完成狀態

涉及目前程式碼、API、schema、migration、tests、CI/CD、deployment、infra、trigger、workload 或實際完成狀態時，依下列證據判定：

1. GitHub `main` 的實作與版本化設定。
2. tests／CI、deployment、live runtime、trigger／workload 與 integration evidence。
3. `spec/operations-and-testing.md` 的最新證據摘要。
4. 其他 active 文件。
5. `archive/` 與歷史 checkpoint。

程式已寫完、文件已更新、build 成功或 partial success 都不能單獨宣稱整體完成。資料不足時寧可維持 unknown／partial／blocked，不造假補齊。

### 1.1.1 有界驗收與結案原則（2026-10-20 使用者決策）

- **不得把「在已定義範圍內查無問題」和「尚未窮盡所有理論上可能的問題」混為一談。** 工作開始即依使用者要求與現有 SPEC／TODO 確認合理、可執行的盤點／驗收邊界；該範圍的實作、測試、必要 runtime 讀回成功且**未發現具體異常**時，該工項直接標記 `CLOSED／PASS`。查無待刪資源也屬清理完成，實刪數如實記錄 0，不再延伸假設性盤點。
- **禁止無證據的無限追查。** 不得僅因「可能還有未知排程／資源／情境」、「不能排除任何可能性」或「尚未逐一窮舉」而把已完成工項維持 `PARTIAL`、持續追加測試、另立 TODO、反覆提醒或擴大查核。只有**明確的失敗收據、現役依賴、實際異常、未執行的原定驗收條件，或已知安全／資料完整性風險**，才構成需處理的剩餘工作，且須具體指出證據與影響。
- **文件最小化。** 已結案的盤點／退役只在 archive 或 Operations 保留簡短可追溯收據，從 active `todo.md` 移除完成項與無根據觀察，不為同一工項增加多份待辦、暫存報告或一次性程式／Workflow。日後若有新的真實異常，再依具體證據建立新工項，不重開舊案。
- 此原則不容許將實際 `FAILED`、IAM `DENIED`、查詢無法執行、未進行的**原定**驗收、尚有正式引用的資源或高風險不可逆刪除謊稱為 PASS；權限、費用、Owner／canonical 資料與 rollback 安全邊界仍依本文件治理。

### 1.2 需求、治理與設計意圖

發生需求或契約衝突時，依序採用：

1. 使用者當次明確指令。
2. 本文件。
3. `todo.md` 中指定 WBS 的範圍、狀態與驗收條件。
4. `wbs.md` 及其工作切片。
5. `spec.md`、`ui.md` 指向的領域契約。
6. Google Drive 白名單根目錄 `janusChatGPT` 內的正式規格、研究與規劃資料。
7. archive／歷史文件。

Drive 與 GitHub 不同時，目前實作狀態以 GitHub／runtime evidence 為準；Drive 保留原始設計／核准規格的參考價值。必須指出差異，不自行把任一方改寫成另一方。

Janus User App 的 presentation target 另由 `ui/user-app.md` 與 `ui/reference/user-app-final/README.md` 定義。該 visual contract 對資訊架構、section order、component hierarchy 與 presentation convergence 具規範性；但 canonical number、auth／owner isolation、PIT／provenance、source authorization、missing／stale／partial／blocked 語意與 publication／LLM boundary 仍以 active SPEC／runtime contract 為準。圖片中的 sample price、PnL、日期、AI prose、logo 或其他示意值永遠不得當成 canonical fact。

### 1.3 人工決策

費用、安全性、不可逆大量刪除、擴大權限、production／新付費資源等決定必須取得使用者明確授權。需要人工輸入帳密、MFA、OAuth consent 或其他資訊時，不得自行猜測。

**免費額度內的操作不視為費用變更。** 在已授權任務範圍內，若可確認帳戶符合免費額度資格、剩餘額度足夠且本次用量受限，可直接執行 query、dev 資源操作與雲端資料變更，不因服務本身可計費而重複要求費用授權。不得只因服務提供 Free Tier 就假定本次免費；超出或無法確認免費額度且未有既有費用授權時，仍需取得授權。此例外不解除安全性、權限擴張、production、不可逆資料操作或其他明列禁令。

### 1.4 專案 Skill 使用邊界

- **Janus／OmniForge 專案不使用 Superpowers plugin／skill。** 處理本專案的分析、規劃、實作、debug、testing、review、verification 或 completion 判定時，不得主動 invoke `using-superpowers`、`brainstorming`、`writing-plans`、`systematic-debugging`、`test-driven-development`、`verification-before-completion` 或其他 Superpowers skills。
- Superpowers 即使安裝在 ChatGPT／Codex 執行環境，也不是 Janus 的權威來源、工作方法、WBS prerequisite、acceptance gate 或完成判定依據；不得因其存在而改變本文件、active `todo.md`、WBS／SPEC、GitHub `main` 或 runtime evidence 所定義的流程。
- 本專案的工程工作直接依本文件、active TODO／WBS／SPEC、repository implementation、tests／CI 與真實 runtime evidence 執行。除非使用者日後在 Janus 專案內明確修改本規則，否則不得以通用 workflow skill 覆蓋或包裝 Janus 專案流程。
- **ChatGPT 對話模式不得因非系統強制的 skill 不可用、未安裝或無法呼叫而停等。** 若 repository 規則、runbook、tests／CI 與 runtime evidence 足以安全執行，直接完成修改、測試、commit、push、deployment 與 acceptance 閉環；僅系統硬性限制、§1.3 所列人工授權事項或真實 blocker 可中止受影響工作。

### 1.5 MCP 唯讀限制（2026-10-09）

- Janus Dev Private 與 Janus Dev Read-only v2 都只作讀取；不得使用 `janus_private_ledger_append` 或 ledger-recording skill 補登個人交易／股息，即使當前外掛快取仍宣告該工具。
- MCP server 不得提供 ledger write；User App 記帳與其他既有非 MCP 路徑不受此限制影響。

### 1.6 FINOPS-AB snapshot 清理決策（2026-10-18 最新）

- 使用者明確取消歷史研究／模型／報告／publication 引用對舊 snapshot 與舊檔案的保留限制，並選擇「只保留目前 snapshot；其餘可清理」。每張 Core／Mart Iceberg 表只保留 current snapshot；取消最近24小時及舊 named branch／tag 的保留，未來研究／模型／snapshot 政策另訂。
- 本次 FINOPS-AB 可移除指向非 current snapshot 的 named refs、過期所有非 current snapshot，再清理 current snapshot 不使用且超過7天的舊檔；不再要求 `CORE_RETENTION_FENCE_URI`、外部研究清冊或 publication `core_snapshot_id` 讀權作歷史保留 gate。舊研究／報告／PIT snapshot 重播不再保證，不偽稱歷史仍可讀。
- 此決策不授權刪除 current snapshot 使用的檔案、Owner 私有交易／現金／持股，或繞過現役 writer／mutation lock、固定 digest、catalog pointer、7日檔齡、generation 與讀回驗證。先完成 compaction 與 current 資料讀回，再作有界清理，保留實刪 objects／bytes 與失敗收據。
- 本節覆蓋 active SPEC／WBS／TODO／runbook 中與此相反的歷史引用保護及24小時／named snapshot 保留條款；既有 row TTL、Stage政策及其他安全邊界未由本次決策變更。

### 1.7 資料補收可使用第三方來源（2026-10-18 使用者核准）

- 補資料以取得可用真實資料為目標，**不要求一定來自官方，也不要求先窮盡官方來源**。可直接採用 Yahoo 股市等第三方網站／供應者已整理的歷史數值；不得再因缺官方報表或官方股數分母而停止能由第三方完成的補收。官方既有資料仍可重用，不必重抓。
- 本決策是已授權補收工作使用第三方來源的專案核准；一般公開可讀、無新增費用的來源，不需逐次請使用者重複核准或另開 WBS。來源登錄／adapter／schema 必須如實支援第三方，不得假冒 `mops`／官方；新增付費訂閱、權限或 production 變更仍依 §1.3。
- 保留來源網站／URL、取得時間、原始內容或 hash、股票、期別、單位與口徑。EPS 可直接採用供應者標示的「單季每股盈餘」，不必自行重建其官方分母；不得混用累季／年度／預估 EPS，不自行用累計 EPS 差分或猜股數。分割／減資等每股基準不明時保留來源口徑，不冒稱跨期可比。
- 第三方實測值可沿既有 Stage→Core→serving→API／UI 發布；來源、修訂與差異需可追溯，不覆蓋成官方認證，不倒填歷史首次公告／PIT。僅更新文件不代表補收、部署或發布已完成。
- 此節覆蓋 active TODO／WBS／SPEC／runbook 中「只限官方」「不得新增第三方來源」「須先找官方／另行逐源人工核准」等相反的補收限制；不擴大當前股票、期間、排程或付費範圍。本次 EPS 仍只補六股2025Q4，不自動擴成全市場。工具不限定 Firecrawl，優先直接 HTTP 或既有工具完成。

### 1.8 Stage 48 小時保留期（2026-10-19 使用者最終定版）

- 此決策只針對既有 dev Stage Bucket：`gen-lang-client-0593591102-dev-stage`，將原始 payload、sidecar、manifest、quarantine 與 Stage commit marker 的保留期固定為 **48 小時（2 天）**；覆蓋較早「維持7天／只執行一次2天特例」的討論。以物件 metadata `updated` 的 UTC 時間計算到期。與 Core/Mart Iceberg orphan 的 7 日檔齡及私有資料保存期限**不同**，不可連動修改。
- 透過既有 Controller／`janus-ingestion-core` 執行每日一次 Stage-only cleanup，不把日清理拖進每週的 Iceberg compaction；既有週六 Core/Mart 維護不變。清理成功以實際 generation 刪除、物件數與 bytes 前後讀回為準，未部署、未觸發、未驗收的狀態不得稱 PASS。
- **有效租約**而非單純 `status` 決定 Stage active 引用保護：僅 `queued/running/retrying` 且 PostgreSQL `claimed_until > UTC now` 的執行與其共用原始資料受保護；`running/retrying/queued` 過期或無租約，不得讓 **48 小時已到期** Stage 永久保留。未滿 48 小時的物件仍由 TTL 保護；apply 前需重新讀取有效租約，若執行集合改變即 fail closed。此處只調整 dev Stage 的 active 判定，不修改 Core manifest／row 的有效引用政策。刪除限現役 dev Stage、既有 worker fencing／固定 GCS generation／allowlist／有界資源與失敗讀回。Hash/MD5 相同只代表疑似內容相同：有有效租約仍在引用時不得直接刪去全部副本；去重需保留代表物件與 provenance，實際可刪容量需 generation 讀回。
- 本節是使用者明確核准的 2 天 Stage TTL 與現有 dev 範圍受控清理，**不**授權刪除 Core 現用檔、Mart、Research frozen training input 或 Private Owner 資料。

### 1.8.1 Controller 工作紀錄 5 天追查與派送上限（2026-10-24 新決策）

- 使用者決定：**工作 `requested_at` 距目前 UTC 超過 5×24 小時**的 `analysis`／`collection` 佇列 execution，一律**排除 P0-2 追查、人工恢復與 Controller 自動重派**；恰好 5 天內（含邊界）才可依原安全 gate 考慮派送。不再逐筆追查原凍結 57 筆中的超齡工作，也不把消失於查詢窗口當作成功／失敗。
- 選擇可逆**邏輯排除**，不是對 `control.executions`、`execution_items`、Core/Mart／GCS 做物理刪除、批量 status UPDATE，或捏造終態。稽核歷史可保留；系統的其他資料保留／Stage 48h／Iceberg 7d 政策不受影響。
- 一般 queue SELECT 上限收斂為 5 天；既有 `pending` queue occurrence 在真正派送前再核對 execution age/trigger/未完成狀態，超齡或無法核對就 `skipped`，不送 Worker。舊 `JANUS_P02_ANALYSIS_RECOVERY` / `JANUS_P02_ANALYSIS_EXECUTION_REF` 歷史恢復入口停用，不能繞過 5 天上限。
- 新程式只有完成測試、實際 dev Controller rollout 和 Scheduler/current image 讀回後才可宣稱生效。已在執行中的 Cloud Run Job 不因工作年齡被直接取消；安全的在途終態由正常機制處理，不能再啟動超齡工作的恢復流程。
- 本條覆蓋 active TODO／WBS／SPEC／P0-2 舊研究記錄的「逐筆收斂原 57 UUID」「歷史恢復最多 30 天」及「一般隊列 7 天」相反指示；歷史原始審計收據保留供稽核，不再作 active 工項。

### 1.9 D07-PRE 研究路線、資料門檻與立即退役（2026-10-20）

[新研究採集與模型契約](spec/research-collection-gas-drive-colab.md) 定義官方 TWSE／TPEx→Colab→Drive 月資料夾→Colab 模型路線；GAS、Core→BQ／PyIceberg→Colab 必經出口及 Cloud Run 月度 retrain 已退役。採集不以24月歷史PIT先驗完整或GCP Core/Mart為前置。研究母體是上市／上櫃普通股（排除 ETF）；D07-PRE 每市場×資料集×月研究准入以 **TWSE 上市 ≥90%、TPEx 上櫃 ≥70%** 分別判定。第一輪月 OHLCV 先依現行普通股名冊的實際有行情股票數／名冊數，作可稽核的 PROBE 研究准入；不以歷史下市名冊尚未補全阻擋 Risk OOS。歷史 PIT／公司行動及來源授權仍標真實狀態；正式 model promotion 另依其契約判定。

已確定新架構不使用、也不被正式服務引用的舊研究 Job、Scheduler、Workflow、BQ 資源**立即移除，不等待新 Colab 開發或驗收**。移除 GCP 實際資源仍需依引用、安全、資源 ID 與讀回證據判定，不可把 GitHub 修改當作 live deletion；共享 Mart/Controller 不能連同市場 screening、Owner、API、週 Iceberg 維護與備份一併刪除。正式 Core 上市 90%／上櫃 70% 品質規範與上述研究准入**門檻數字一致但驗收／母體／認證責任分開**，ETF 正式持股行情仍保留。

個人非商業研究不代表可以忽略第三方 API 的自動存取、訓練使用與資料保留條款。研究/canonical 分離、來源 provenance、不得補造缺值、模型品質與 LLM 非出版權力依然有效。

### 1.10 方案 A（2026-10-21）
使用者選擇先交付有證據的事實解讀、站內盤前/盤後與變化追蹤，再接經驗證模型。契約見 [變化判讀](spec/change-analysis.md)、[四模型角色](spec/specialist-engines.md)、[因子時間](spec/model-feature-time-contract.md)。事實模板不依賴四模型validated；未驗證ML不得顯示機率或買賣分數。公開個股判斷不以Owner現金/成本作X，私人曝險另隔離。本輪授權文件整理，不因列入TODO而自動開發/部署；後續依使用者指定工作包執行。舊結案不重開，無新推播/付費/日常LLM。


### 1.10.1 四模型與 Valuation 整合（2026-10-24 最新決策，覆蓋同日較早第五模型提案）

- **正式模型角色僅四個**：Quant、Risk、Fundamental、Valuation。**取消獨立第五模型**，`valuation_range` 不得成為 model／Registry／promotion role、第五訓練工作線、第二組 canonical 價帶或額外發布排程；Event／Catalyst 亦不設第五個模型。
- 原「估值參考區間」**功能併入 04 Valuation**：保留原 PE／PB 相對估值 baseline、XGBoost 倍數研究；共用 EPS/BVPS、歷史 PE/PB、來源、會計期別、PIT、公司行動及同一 publication/rollback 管理。以可重算、可獨立驗收的確定性情境引擎輸出**唯一估值卡**；不要求 XGBoost 已通過 promotion 才能研究或啟用情境，但情境輸入／算式／顯示仍需自身品質 gate。不得將分位區間稱為 ML 報酬預測或信賴區間。
- 保留 Event 公告原文、修訂去重、公司行動與 A-CHANGE 事實提醒。**現役 runtime 仍有五筆 deterministic specialist baseline 及 `event` schema/API/快取/讀取器**，此為舊相容資料現況，非新第五模型。後續須在 04/RV 工作線完成 reader/Owner/API/rollback 相容、真實 dev 測試後才可解除舊五筆假設；不得因決策直接刪除既有 artifact、資料表、API 或共享排程。
- 第三方研究補證可沿既有範圍進行；本決策不授權新增付費服務、變更 Risk ACTIVE、擴大全市場採集或直接修改 canonical。舊 Drive 第五模型指示只作已撤案歷史參考，權威執行範圍以本規則、[四模型 SPEC](spec/specialist-engines.md)、[04 子契約](spec/valuation-range.md)、[WBS](wbs.md) 及[唯一 TODO](todo.md) 為準。

### 1.11 Risk 研究與發布

取消逐來源授權補證、全歷史 PIT／公司行動重建、訓練後新增前瞻 cohort 與自然日批證明作發布前置。現有歷史回測可作研究評估，已看過的樣本不冒稱獨立新 OOS。保留實際模型載入、八因子順序與計算一致、必要欄位／數值、基本 cutoff 防洩漏、Owner 目標範圍與可回復切換。

### 1.12 Risk 目前狀態與交接

2026-10-23 的 DETERMINISTIC 回滾是歷史已執行事實；本次只取消過度門檻，沒有改 Registry，也不把未測試的新程式稱為 ACTIVE。下一執行者依精簡 WI 完成有界技術測試與功能驗收，無須補做本次取消的稽核。

## 2. Dev 平行上線環境政策

- 目前 `dev` 是 Janus 個人使用階段的主要真實運行環境（parallel-live environment），不是只供假資料、mock、demo 或 pre-production 演練的 staging。
- Dev 預設使用已核准的真實資料、API、MCP、Google OAuth、Cloud Run／Job／Scheduler、PostgreSQL／Iceberg 與實際 workflow；完成條件優先用這條真實鏈路驗證。
- `prod` 代表未來對外、多使用者或 HA／SLA 等營運強化，不是目前個人真實使用的前置條件。
- Mock／fixture／localhost simulation 只補足 timeout、cancel、disconnect、error、secret-redaction 等真實服務不適合刻意製造的異常情境，不得取代主要 real-path acceptance。
- 保留既有 dev 資源命名與 topology，除非有實際需求，不為「環境看起來像 production」做無價值重構。
- 平行上線不取消最低安全底線：secret 不進 log／前端／一般資料表；owner／auth boundary 保留；schema 變更走 migration／version；重要資料需有可重建、匯出或已核准 bounded backup／restore 路徑；partial 不包裝成 full success。
- research-only、canonical、PIT、future leakage、provenance、source authorization、publication gate 等資料治理邊界仍有效；研究暫存不因位於 dev 自動升格為 canonical data。

## 3. ChatGPT GitHub 與工程執行權

- repository 目前只維持 `main`；ChatGPT 預設直接 commit 到 `main`，不主動建立 branch／PR，除非使用者特別要求。
- ChatGPT 可直接修改、建立、刪除並 commit 文件、Python、TypeScript／JavaScript、Dart、SQL migration、shell／PowerShell、Dockerfile、Cloud Build、GitHub Actions、Terraform／IaC、runtime／deployment config、tests、application source 與其他專案內容。
- ChatGPT 可對既有 dev 環境執行或觸發 tests、CI、build、migration、Cloud Run deployment／Job／Scheduler 與既有 workload，並完成「分析 → 修改 → 測試 → commit → deploy → runtime 驗收 → 修正」閉環；直接驗收失敗時可在既有授權範圍內繼續修正與重新部署。
- 新增或提高付費 GCP／第三方資源、啟用新的付費 API／模型／subscription、production 首次建立或重大權限擴張、大量且不可逆的真實資料刪除、沒有可靠 rollback／backup／rebuild 路徑的破壞性操作，以及 MFA／OAuth consent／付款／帳號管理，仍需使用者明確授權或本人操作；費用認定適用 §1.3 的免費額度例外。
- 任何回寫都不得偽造 implementation status。未實作、未測試、未部署、未觸發或未連上真實依賴的項目不得因文件或程式已更新而標成完成。

## 4. WBS 執行方式

- 收到「執行 `WBS-ID`」時，先從 `todo.md` 找 active item，再依 `wbs.md` 讀對應切片與直接引用的 SPEC／UI。
- 收到「執行 `D01`～`D08`」時，先在 `todo.md` 確認授權、範圍和 active acceptance，再從 `execution-cards/README.md` 讀對應單張標準化執行卡及其引用的 WBS／SPEC／UI。卡片不構成新的待辦、授權或完成狀態。
- 使用者指定一個 WBS 後，預設以該 WBS 的整體 acceptance scope 結案；按驗收條件組織一段連續工作，不按 dataset、adapter、文件或程式改動切成多輪。合併同來源、共用整合路徑或可一起驗收的工作；dataset／adapter 等內部步驟只作進度 checkpoint，不是停等、重新授權或另開對話的邊界。
- 同一 WBS 中不得在每個 dataset／內部步驟完成後自行停止或要求使用者再次確認。只有使用者明確要求暫停、既定模型切換／驗收閘門，或 §1.3 外部核准及真實成本／安全／範圍 blocker 才暫停受影響部分；其餘安全且獨立的工作繼續推進。閘門解除後接續同一 WBS，直到整體 acceptance 完成，或只剩無法自行解除的 blocker；未滿足 acceptance 時維持 partial／blocked，不宣稱 WBS 完成。
- 一個 WBS 的授權不延伸到其他 WBS；完成當前 WBS，或完成所有可繼續部分且剩餘條件確實受阻後停止，下一個 WBS 重新走模型與授權閘門。
- **2026-10-05 合併執行例外**：使用者要求本次非預警改善整合既有 TODO、先集中完成程式再合併驗收。TODO 明列的 A／B／C 工作組可各自合併所列 WBS 範圍，以整组為模型 gate／主要驗收單位，原 WBS acceptance 不取消。只有使用者明確下達「全部剩餘工作組」指令時，才可跨組連續執行；單組授權不自動延伸。流程見 `codex-execution-plan.md`。安全、migration、付費／production 與外部授權邊界不變。
- `ready` 可執行；`blocked` 只做安全盤點，不假設外部授權、付費決策或依賴已滿足。
- ID 不在 active TODO 時不得自行從 `parking-lot.md`、archive 或研究規劃開工。
- 採最小合理變更；不得因此省略必要 tests、migration、deployment 或 live acceptance。

### 4.1 全市場及批次總控（2026-10-13 最新決策）

**全市場與總控契約（2026-10-14 coverage 更新）：**市場資料、screening、研究母體、搜尋／新增關注資格全部改為上市／上櫃全部個股，必要資料缺失率 TWSE 上市 ≤10%、TPEx 上櫃 ≤30%（均含邊界）分市場通過；不再維持前 500 母體。所有業務批次由 Cloud Scheduler 總控，GitHub Actions 只保留備份清理定時排程。實作／切換依最新 status 與 runtime evidence 分項判定；授權及暫停範圍只由當次使用者指令與 active TODO 決定。 [全市場／總控契約](spec/full-market-batch-policy.md) 定義分母、快照、即時操作與遷移驗收；[2026-10-13 歷史批次盤點](archive/batch-inventory-2026-10-13.md) 只供追溯，**現況**以 [治理總入口](spec/data-governance.md) 與 Controller/runtime 認定。交易入帳／試算及報價按需刷新不等定時批次，背景工作共用 request／fence。此決策取代舊 Liquid 500 admission，保留 50 筆關注 quota、來源與金額／模型品質約束。

## 5. 最小文件讀取

先讀本文件與 `doc/README.md`，再依任務只讀：

- `todo.md` 的目標項目；
- `wbs.md` 對應切片；
- 直接相關的 `spec/*.md`、`ui/*.md`；
- 直接相關的程式、測試、workflow 或 infra；
- 目錄內若存在額外 `AGENTS.md`，再遵守該局部規則。

**凡 ChatGPT／Codex／其他工程 agent 的任務涉及 Janus User App presentation、layout、visual regression、Product Completeness，或「今日／關注／記帳／筆記／個股詳情」任一畫面，必須額外讀 `ui/user-app.md` 與 `ui/reference/user-app-final/README.md`。對應 PNG binary 已存在時也必須實際檢視；binary 尚未 commit 時不得假裝已做 screenshot comparison 或 final visual acceptance。**

禁止預設把整個 `doc/`、archive、所有 SPEC 或所有 WBS 全部載入。只有跨領域契約、安全邊界、引用缺失或盤點任務才擴大範圍。

## 6. 文件角色與回寫

1. `todo.md`：**只保存使用者／專案已確定「要做」的 active queue 與未完成 acceptance**；不保存 Deferred、Candidate、Observation、Production 才可能需要或已接受缺口。完成證據移入 archive。
2. `wbs.md`／`wbs/*.md`：責任與驗收邊界，不保存短期 runtime snapshot。
3. `spec.md`／`spec/*.md`：目前契約；除 operations 外，不寫除錯流水帳。
4. `ui.md`／`ui/*.md`：目前 UI 契約與狀態語意；`ui/reference/user-app-final/README.md` 是 User App 的 active Final Visual Contract，對應 PNG 是 presentation acceptance target，不是可丟棄的 mock screenshot。
5. `spec/operations-and-testing.md`：只保存最新完整 evidence summary；舊 checkpoint 應定期移入 `archive/`，不得無限 append。
6. `runbook-*.md`：可重跑的操作程序；容易漂移的 revision、digest、build ID 只放 operations／archive，不固定在 README 或一般 runbook。
7. `archive/`：已完成、已取代、歷史 checkpoint；不得當 active 指令來源。
8. `parking-lot.md`：**目前「不做」的單一收納處**。未排程構想、可能需求、自然 observation、未來 Production 工作、已接受資料缺口與研究 roadmap 可保留於此供日後翻找，但不計入專案未完成度，也不得自行開工；只有使用者明確決定「做」後才移回 `todo.md`。
   - 2026-10-05 使用者指定預警另存 `future-market-alerts.md`；Parking Lot 仍是其唯一狀態入口，獨立文件只保存內容，不形成另一份 active queue。
9. 白名單 Drive `janusChatGPT` 可保存正式規格、研究與規劃資料；Drive 研究內容不因存在就自動成為 TODO。

## 7. 驗證與完成判定

- 預設跑覆蓋本次 diff 的最小驗證；不因慣例每次都重跑完整 test／lint／build。
- TODO 合併工作組先完成相依程式／測試／文件再集中驗收；同一份有效 evidence 可覆蓋多個 WBS。必要安全／migration 前置檢查保留，失敗或實質修改才重跑受影響範圍；不得為減少次數停用必要 CI 或以舊證據代替新版本驗收。
- 文件小改至少檢查路徑、連結、內部一致性與 diff；程式修改由執行環境跑直接相關 targeted tests。
- 跨模組契約、migration、安全／權限、依賴、建置鏈或里程碑結案時，再評估完整測試。
- GCP dev／live／E2E 驗收必須由真實 GCP dev runtime 或其受控 acceptance path 證明；localhost／fixture 不得冒充 live evidence。
- 完成狀態依 implementation、tests、CI、deployment、runtime、trigger／workload、integration evidence 綜合判斷。
- `WBS-6-USER-FINAL-VISUAL-CONVERGENCE` 額外要求四張 final PNG binary、Flutter targeted／golden／screenshot regression，以及 GCP dev 真實 authenticated screenshot／browser acceptance；只完成文件、圖片、widget、golden 或 build 任一單項都不得宣稱整體完成。

## 8. 成本與安全限制

### Artifact Registry

- 允許 image push／pull、digest 解析、cleanup policy 與一般 artifact metadata。
- 禁止啟用或依賴 Artifact Analysis／Container Scanning／vulnerability occurrence API，以避免不可預期費用。
- immutable image digest 仍需保存；SBOM 若需要，使用不依賴上述掃描 API 的方式產生。

### PostgreSQL dev Free Tier

- Dev／MVP PostgreSQL 固定 `e2-micro`、`us-central1`；不得自行升級 machine type、跨區建立第二台或新增 HA／replica／付費保護資源。
- Standard Persistent Disk 總配置上限 30 GB，VM 不配置 external IP，outbound data 維持 Free Tier 約束。
- 重要資料優先使用既有 bounded logical backup／export／可重建來源；新增付費保護資源需明確授權。
- 自動化 guard 只能檢查資源規格，不能保證帳單為零；部署前仍需核對 billing eligibility／budget。

## 9. Windows／WSL 操作

- Windows PowerShell 執行 Node.js 指令優先使用 `npm.cmd`／`npx.cmd`，不為此放寬 ExecutionPolicy。
- 可使用 WSL 執行 dev migration、Linux／shell 驗證與 GCP dev 驗收，但不得藉此擴大 production 或付費資源。
- Secret 不得出現在 argv、shell trace、process listing、Cloud Build substitution、deployment metadata 或 log。

## 10. Context 與大型工作

- **長時間任務等待交接（2026-10-21 使用者決策）**：GitHub Actions workflow、遠端建置、部署或其他非同步長時間任務已啟動，且下一步只剩等待完成時，提供任務／run 連結、目前已知狀態與完成後的接續步驟，隨即停止本輪工作，交由使用者觀察並回報後再接續。不得為長時間等待持續輪詢、阻塞等待或另設自動監看；使用者當次明確要求代為等待／監看時才例外。一般立即回應的指令、查詢、檔案修改、commit／push、單次狀態讀取與短時間驗證直接執行並接續，不因此停下或要求使用者回報；推送觸發背景 CI 也不阻止完成這些短操作。本規則不豁免必要 CI、發布或驗收 gate，尚未取得結果不得宣稱 PASS。
- 查 API、GCP 或 logs 時只取回答／驗收需要的欄位、時間範圍與 limit；先窄查再擴大。
- 跨多模組的大型工作拆成可獨立驗收的切片；checkpoint 要記錄已改內容、實際測試、未完成依賴與下一入口。
- 不得以節省 token 為理由跳過驗證、遺漏失敗或宣稱未完成項目已完成。

## 11. 中文優先

- Active SPEC／WBS／TODO／UI 與使用者可見文案以繁體中文為主。
- API path、schema 欄位、程式識別字、WBS ID、provider／model／product 名稱保留原文。
- 歷史紀錄與測試證據可保留原始語言，只要不被誤認為目前使用者契約。

## 12. CI／Release 分離（2026-10-08 核准；2026-10-10 dev 範圍已驗收）

### 12.1 正式路徑與邊界

- 正式流程固定：**ChatGPT → GitHub → GitHub Actions → GCP API → GitHub Actions Logs → ChatGPT**。目前核准的 dev 發布範圍已於 2026-10-10 實測結案，執行證據與使用者豁免記錄見 [CI/CD 規格](spec/cicd-v2.md)、[status](status.md)；**本節仍是後續每次發版的治理契約**，不得將一次 PASS 視為未來版本自動通過。
- GitHub `main` Push 可以保留輕量／selective CI 作快速回饋，但**任何 Release 必須在 GitHub Actions 對目標完整 Git SHA 執行所需全部測試、安全／schema／migration／建置檢查，全部 PASS 後才能建置並發布 GHCR 映像**。文件-only 變更可略過無關測試，但不得把選擇性 CI 冒充完整 Release gate。
- GitHub Actions 建立 container image、推送至 **GHCR（`ghcr.io`）**、記錄不可變 `sha256` digest；以完整 Git SHA／工作包 ID／workflow run ID 連結測試、build 與 release evidence。不得以 mutable tag 作 Cloud Run deployment identity。
- **新 CI/CD 流程不觸發 Cloud Build／Trigger，不主動寫入 GCS、Artifact Registry，不把這兩者當新的 image、receipt、mutex 或 release state store；不新增常駐 Compute Engine 作 Docker host。** 此限制不取消既有 Janus 業務資料流對已授權 GCS／Iceberg 的合法讀寫，亦不代表既有 Cloud Build／Artifact Registry／GCS 資產已停用或刪除。

### 12.2 Cloud Run 候選、驗收、正式切換與回滾

- **使用公開 GHCR package** 才可走 Cloud Run 直接部署；發布後必須驗證匿名可拉取與 digest 可解析。私人 GHCR package 需要 Artifact Registry remote repository 等額外路徑，**不符合目前「新流程不使用 Artifact Registry」目標，必須 fail closed**。GHCR visibility、外部 registry availability、rate／size 等限制與現有 Cloud Run 服務實際相容性須在 dev 驗證。
- GitHub Actions 使用固定 `ghcr.io/...@sha256:...` 呼叫 GCP API，對**既有 Cloud Run Service** 建立 `--no-traffic`、帶專屬 tag 的 0% 正式流量候選 revision；候選 tag URL 可供受控測試，並非完全無請求。記錄先前 traffic、revision、digest 與設定，再做 health／可自動執行的 OAuth／auth 邊界、適用且有可驗證方式的 authenticated owner／PnL／MCP 等 dev acceptance（不以人工 OAuth 登入為必經）。所有必需 gate PASS 才明確移轉流量；失敗時將流量恢復至先前已驗證 revision，並 readback。
**2026-10-23 dev API 簡化驗收（使用者最新決策）**：既有 dev API 發版不必刻意做「新版 100% → 舊版 100% → 新版 100%」往返演練。正式請求可明確指定 `traffic_validation_mode=direct`，先核對固定 GHCR SHA/digest、已通過的 release/candidate/auth、所需 Jobs 收據與上一個真實可用 revision，然後只切換一次到新版 100%；讀回單一 100%、Ready、build SHA、health 與基本未登入權限拒絕，符合即可交付使用。若真正部署/檢查失敗，仍保留上一版並按失敗恢復流程處置；此模式 `rollback_rehearsal=NOT_REQUESTED`，不得說成完成回滾演練。此簡化**不涉及 prod、不開新付費資源、不放寬 secret/owner 及資料隔離**。
- Cloud Run **Job 無 Service 的 0% traffic revision 語意**。Job image 更新必須另有 mutex、active execution／Scheduler fence、固定 digest／設定 snapshot、必要的隔離 canary 與可回復步驟；不得把 API 候選 PASS 直接當成 Jobs 發布成功，也不得未經 gate 更新排程使用的 Job image。
- Release 使用完整 Git SHA、上一次成功發布 SHA、相同 SHA 冪等與舊 SHA 防覆蓋規則；保留上一可用 image／revision／Job 設定與回滾證據，直到新版本 live PASS。正常 Push 不得自動切換 Cloud Run traffic 或 Job。部分成功、timeout、未知執行均不視為 PASS，也不盲目重送任何 Job。
- 2026-10-09 使用者最新指示：本次只驗收 GitHub Actions → GHCR → Cloud Run 新流程。舊 Revision／映像／GCS／AR 資產清理不列 active TODO，也不作為 Release 結案條件；保留回滾所需版本與證據。
- Release receipts／diagnostics 以 GitHub Actions logs、job summary 與必要的保護性 workflow artifacts 保留；只輸出非敏感欄位（SHA、digest、revision、workflow/run、gate 結果、baseline、rollback 與 UTC）。不在 log／artifact／argv 印出 Secret、token、owner 個資或敏感 payload。部署互斥、state 持久性及可回復路徑必須在正式啟用前實際驗證，不能假定 Actions concurrency 就等於跨 run／跨 runtime 的完整鎖。

**2026-10-12 使用者新決策：取消每次 GitHub Actions 發版的人工 OAuth 登入 gate。** Dev Jobs／API promotion／固定 Preview **不得**要求 Owner 每個來源 SHA 重新開瀏覽器登入 Google、重做 OAuth consent 或人工 A→B→A；歷史 `ops/ghcr-owner-acceptance.json` 保留稽核，但不再作為新版本強制發版證明。

- **保留可自動執行的 OAuth 驗證**：同 SHA 0% candidate 的 OAuth discovery、issuer／redirect、PKCE S256／refresh grant metadata、未登入 User／Admin 401／403、MCP Bearer challenge／private tool 拒絕；既有的 token、refresh rotation／revoke、wrong audience、owner-scope 程式回歸及可安全自動完成的正向 authenticated readback 照常執行。Jobs／API promotion 需可追溯的同來源 `ghcr-candidate-auth-boundary.yml` 成功 run ID（`auth_boundary_run`），腳本驗證 run、workflow、source identity；缺失或失敗不得越過。
- **不能混淆驗收結果**：metadata／負向 401 PASS 不等於真人 Google 登入、A/B owner isolation、正向 refresh 交換或 PnL PASS；無法自動測的功能按原獨立驗收標 `NOT_VERIFIED`／`PARTIAL`，不要造假或要求使用者每版登入。其餘 SHA、完整 CI、Jobs canary、source/privacy、lease、rollback、正式 traffic readback gate 均不豁免。
- 例行發版免人工 OAuth 驗證不等於代理人可以自行完成 MFA／Google consent，也不自動授權新 scope／OAuth client／redirect 權限擴張；真的改動時仍依 §1.3 取得使用者本人操作及核准。

### 12.3 GCP 身分及既有 Cloud Build 唯讀診斷

- GitHub Actions 使用 GCP Workload Identity Federation（WIF）與最小 IAM；GHCR publish 的 GitHub token 僅給需要的 `packages: write`。部署身分只擁有受限既有 dev Cloud Run 的必要更新／readback 權限，不能以「診斷」名義授予 Cloud Build 建置權；不得把 credentials 寫入 repo 或 logs。任何重大權限擴張與新付費資源仍依 §1.3 取得明確授權。
- 既有 Cloud Build 只允許**可選的唯讀查詢**，不得成為新發布依賴：在 WIF 具必要查詢權限時，讀指定 build 的 `SUCCESS`／`FAILURE`／其他真實狀態、失敗 step ID／status／exit code（存在時）與經 allowlist 篩選／遮罩的簡短錯誤摘要，寫到 GitHub Actions Logs／summary，再由 ChatGPT 讀取 workflow run。建議將 `cloudbuild.builds.get`、必要時 `cloudbuild.builds.list` 與 `logging.logEntries.list` 限縮於唯讀診斷身分／範圍；取得這些欄位並非需要啟動 Build。
- 若 WIF、IAM、Logging 查詢或 redaction 無法驗證，診斷顯示 `unknown / blocked`，不把未觀測到的 log 當成功，也不公開原始無遮罩的 Cloud Build logs。舊 `cloudbuild*.yaml`／Trigger 在核對其餘依賴與停用方案前不得自稱已移除。

### 12.4 實作與證據分離

- 舊 regional Cloud Build Release、Artifact Registry image、GCS receipts／mutex、`ci-v2.yml` selective CI 與部分 `deploy-dev.yml` 操作仍可能存在於 `main`／dev；**目前狀態以 workflow／runtime readback 為準**。文件更新不代表新 Actions full test + GHCR + Cloud Run release 已上線。
- 對本次或後續工作要求的 evidence，至少涵蓋完整 SHA、完整測試 gate、GHCR public pull／digest、WIF 權限、0% candidate、authenticated acceptance、traffic／Job readback、rollback；確認切換新路徑後才有條件停止舊發布入口，不進行無法復原的清理。
- `AGENTS.md` 只引用本權威文件；實際命令與轉換時序記在 [runbook](runbook-dev-deploy.md)，不另建立互相矛盾的政策。任何 commit／push 前先執行 `/ponytail-review`；若環境無此非系統命令，依 §1.4 以實際 diff／契約／連結／適用測試 review 替代並明示，不偽稱已執行；完成工作前檢查規則、適用 tests／lint／驗證，說明修改、真實證據與未決事項。
