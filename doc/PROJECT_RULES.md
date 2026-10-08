# Janus — AI 基礎作業規則

所有 Janus／OmniForge 工作遵守本文件。文件角色先看 [`README.md`](README.md)。

## 1. 權威與事實判定

### 1.1 目前實作／完成狀態

涉及目前程式碼、API、schema、migration、tests、CI/CD、deployment、infra、trigger、workload 或實際完成狀態時，依下列證據判定：

1. GitHub `main` 的實作與版本化設定。
2. tests／CI、deployment、live runtime、trigger／workload 與 integration evidence。
3. `spec/operations-and-testing.md` 的最新證據摘要。
4. 其他 active 文件。
5. `archive/` 與歷史 checkpoint。

程式已寫完、文件已更新、build 成功或 partial success 都不能單獨宣稱整體完成。資料不足時寧可維持 unknown／partial／blocked，不造假補齊。

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
- 使用者指定一個 WBS 後，預設以該 WBS 的整體 acceptance scope 結案；按驗收條件組織一段連續工作，不按 dataset、adapter、文件或程式改動切成多輪。合併同來源、共用整合路徑或可一起驗收的工作；dataset／adapter 等內部步驟只作進度 checkpoint，不是停等、重新授權或另開對話的邊界。
- 同一 WBS 中不得在每個 dataset／內部步驟完成後自行停止或要求使用者再次確認。只有使用者明確要求暫停、既定模型切換／驗收閘門，或 §1.3 外部核准及真實成本／安全／範圍 blocker 才暫停受影響部分；其餘安全且獨立的工作繼續推進。閘門解除後接續同一 WBS，直到整體 acceptance 完成，或只剩無法自行解除的 blocker；未滿足 acceptance 時維持 partial／blocked，不宣稱 WBS 完成。
- 一個 WBS 的授權不延伸到其他 WBS；完成當前 WBS，或完成所有可繼續部分且剩餘條件確實受阻後停止，下一個 WBS 重新走模型與授權閘門。
- **2026-10-05 合併執行例外**：使用者要求本次非預警改善整合既有 TODO、先集中完成程式再合併驗收。TODO 明列的 A／B／C 工作組可各自合併所列 WBS 範圍，以整组為模型 gate／主要驗收單位，原 WBS acceptance 不取消。只有使用者明確下達「全部剩餘工作組」指令時，才可跨組連續執行；單組授權不自動延伸。流程見 `codex-execution-plan.md`。安全、migration、付費／production 與外部授權邊界不變。
- `ready` 可執行；`blocked` 只做安全盤點，不假設外部授權、付費決策或依賴已滿足。
- ID 不在 active TODO 時不得自行從 `parking-lot.md`、archive 或研究規劃開工。
- 採最小合理變更；不得因此省略必要 tests、migration、deployment 或 live acceptance。

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

- 查 API、GCP 或 logs 時只取回答／驗收需要的欄位、時間範圍與 limit；先窄查再擴大。
- 跨多模組的大型工作拆成可獨立驗收的切片；checkpoint 要記錄已改內容、實際測試、未完成依賴與下一入口。
- 不得以節省 token 為理由跳過驗證、遺漏失敗或宣稱未完成項目已完成。

## 11. 中文優先

- Active SPEC／WBS／TODO／UI 與使用者可見文案以繁體中文為主。
- API path、schema 欄位、程式識別字、WBS ID、provider／model／product 名稱保留原文。
- 歷史紀錄與測試證據可保留原始語言，只要不被誤認為目前使用者契約。

## 12. CI／Release 分離（2026-10-08 正式目標政策；實作遷移中）

### 12.1 正式路徑與邊界

- 正式目標流程固定：**ChatGPT → GitHub → GitHub Actions → GCP API → GitHub Actions Logs → ChatGPT**。本節是使用者已核准的**目標契約**，不是已完成部署聲明；目前實作、驗收與未完成項見 [CI/CD 規格](spec/cicd-v2.md) 及 [status](status.md)。
- GitHub `main` Push 可以保留輕量／selective CI 作快速回饋，但**任何 Release 必須在 GitHub Actions 對目標完整 Git SHA 執行所需全部測試、安全／schema／migration／建置檢查，全部 PASS 後才能建置並發布 GHCR 映像**。文件-only 變更可略過無關測試，但不得把選擇性 CI 冒充完整 Release gate。
- GitHub Actions 建立 container image、推送至 **GHCR（`ghcr.io`）**、記錄不可變 `sha256` digest；以完整 Git SHA／工作包 ID／workflow run ID 連結測試、build 與 release evidence。不得以 mutable tag 作 Cloud Run deployment identity。
- **新 CI/CD 流程不觸發 Cloud Build／Trigger，不主動寫入 GCS、Artifact Registry，不把這兩者當新的 image、receipt、mutex 或 release state store；不新增常駐 Compute Engine 作 Docker host。** 此限制不取消既有 Janus 業務資料流對已授權 GCS／Iceberg 的合法讀寫，亦不代表既有 Cloud Build／Artifact Registry／GCS 資產已停用或刪除。

### 12.2 Cloud Run 候選、驗收、正式切換與回滾

- **使用公開 GHCR package** 才可走 Cloud Run 直接部署；發布後必須驗證匿名可拉取與 digest 可解析。私人 GHCR package 需要 Artifact Registry remote repository 等額外路徑，**不符合目前「新流程不使用 Artifact Registry」目標，必須 fail closed**。GHCR visibility、外部 registry availability、rate／size 等限制與現有 Cloud Run 服務實際相容性須在 dev 驗證。
- GitHub Actions 使用固定 `ghcr.io/...@sha256:...` 呼叫 GCP API，對**既有 Cloud Run Service** 建立 `--no-traffic`、帶專屬 tag 的 0% 正式流量候選 revision；候選 tag URL 可供受控測試，並非完全無請求。記錄先前 traffic、revision、digest 與設定，再做 health／authenticated owner／OAuth／PnL／MCP 等適用的真實 dev acceptance。所有必需 gate PASS 才明確移轉流量；失敗時將流量恢復至先前已驗證 revision，並 readback。
- Cloud Run **Job 無 Service 的 0% traffic revision 語意**。Job image 更新必須另有 mutex、active execution／Scheduler fence、固定 digest／設定 snapshot、必要的隔離 canary 與可回復步驟；不得把 API 候選 PASS 直接當成 Jobs 發布成功，也不得未經 gate 更新排程使用的 Job image。
- Release 使用完整 Git SHA、上一次成功發布 SHA、相同 SHA 冪等與舊 SHA 防覆蓋規則；保留上一可用 image／revision／Job 設定與回滾證據，直到新版本 live PASS。正常 Push 不得自動切換 Cloud Run traffic 或 Job。部分成功、timeout、未知執行均不視為 PASS，也不盲目重送任何 Job。
- Release receipts／diagnostics 以 GitHub Actions logs、job summary 與必要的保護性 workflow artifacts 保留；只輸出非敏感欄位（SHA、digest、revision、workflow/run、gate 結果、baseline、rollback 與 UTC）。不在 log／artifact／argv 印出 Secret、token、owner 個資或敏感 payload。部署互斥、state 持久性及可回復路徑必須在正式啟用前實際驗證，不能假定 Actions concurrency 就等於跨 run／跨 runtime 的完整鎖。

### 12.3 GCP 身分及既有 Cloud Build 唯讀診斷

- GitHub Actions 使用 GCP Workload Identity Federation（WIF）與最小 IAM；GHCR publish 的 GitHub token 僅給需要的 `packages: write`。部署身分只擁有受限既有 dev Cloud Run 的必要更新／readback 權限，不能以「診斷」名義授予 Cloud Build 建置權；不得把 credentials 寫入 repo 或 logs。任何重大權限擴張與新付費資源仍依 §1.3 取得明確授權。
- 既有 Cloud Build 只允許**可選的唯讀查詢**，不得成為新發布依賴：在 WIF 具必要查詢權限時，讀指定 build 的 `SUCCESS`／`FAILURE`／其他真實狀態、失敗 step ID／status／exit code（存在時）與經 allowlist 篩選／遮罩的簡短錯誤摘要，寫到 GitHub Actions Logs／summary，再由 ChatGPT 讀取 workflow run。建議將 `cloudbuild.builds.get`、必要時 `cloudbuild.builds.list` 與 `logging.logEntries.list` 限縮於唯讀診斷身分／範圍；取得這些欄位並非需要啟動 Build。
- 若 WIF、IAM、Logging 查詢或 redaction 無法驗證，診斷顯示 `unknown / blocked`，不把未觀測到的 log 當成功，也不公開原始無遮罩的 Cloud Build logs。舊 `cloudbuild*.yaml`／Trigger 在核對其餘依賴與停用方案前不得自稱已移除。

### 12.4 實作與證據分離

- 舊 regional Cloud Build Release、Artifact Registry image、GCS receipts／mutex、`ci-v2.yml` selective CI 與部分 `deploy-dev.yml` 操作仍可能存在於 `main`／dev；**目前狀態以 workflow／runtime readback 為準**。文件更新不代表新 Actions full test + GHCR + Cloud Run release 已上線。
- 對本次或後續工作要求的 evidence，至少涵蓋完整 SHA、完整測試 gate、GHCR public pull／digest、WIF 權限、0% candidate、authenticated acceptance、traffic／Job readback、rollback；確認切換新路徑後才有條件停止舊發布入口，不進行無法復原的清理。
- `AGENTS.md` 只引用本權威文件；實際命令與轉換時序記在 [runbook](runbook-dev-deploy.md)，不另建立互相矛盾的政策。任何 commit／push 前必須先執行 `/ponytail-review`；完成工作前檢查規則、適用 tests／lint／驗證，說明修改、真實證據與未決事項。
