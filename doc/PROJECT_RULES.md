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

### 1.3 人工決策

費用、安全性、不可逆大量刪除、擴大權限、production／新付費資源等決定必須取得使用者明確授權。需要人工輸入帳密、MFA、OAuth consent 或其他資訊時，不得自行猜測。

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
- 新增或提高付費 GCP／第三方資源、啟用新的付費 API／模型／subscription、production 首次建立或重大權限擴張、大量且不可逆的真實資料刪除、沒有可靠 rollback／backup／rebuild 路徑的破壞性操作，以及 MFA／OAuth consent／付款／帳號管理，仍需使用者明確授權或本人操作。
- 任何回寫都不得偽造 implementation status。未實作、未測試、未部署、未觸發或未連上真實依賴的項目不得因文件或程式已更新而標成完成。

## 4. WBS 執行方式

- 收到「執行 `WBS-ID`」時，先從 `todo.md` 找 active item，再依 `wbs.md` 讀對應切片與直接引用的 SPEC／UI。
- 每次只執行一個可獨立驗收的原子任務；完成後停止，不自動把下一項當成已授權。
- `ready` 可執行；`blocked` 只做安全盤點，不假設外部授權、付費決策或依賴已滿足。
- ID 不在 active TODO 時不得自行從 archive 或研究規劃開工。
- 採最小合理變更；不得因此省略必要 tests、migration、deployment 或 live acceptance。

## 5. 最小文件讀取

先讀本文件與 `doc/README.md`，再依任務只讀：

- `todo.md` 的目標項目；
- `wbs.md` 對應切片；
- 直接相關的 `spec/*.md`、`ui/*.md`；
- 直接相關的程式、測試、workflow 或 infra；
- 目錄內若存在額外 `AGENTS.md`，再遵守該局部規則。

禁止預設把整個 `doc/`、archive、所有 SPEC 或所有 WBS 全部載入。只有跨領域契約、安全邊界、引用缺失或盤點任務才擴大範圍。

## 6. 文件角色與回寫

1. `todo.md`：active queue、未完成 acceptance、blocked／deferred；完成證據移入 archive。
2. `wbs.md`／`wbs/*.md`：責任與驗收邊界，不保存短期 runtime snapshot。
3. `spec.md`／`spec/*.md`：目前契約；除 operations 外，不寫除錯流水帳。
4. `ui.md`／`ui/*.md`：目前 UI 契約與狀態語意。
5. `spec/operations-and-testing.md`：只保存最新完整 evidence summary；舊 checkpoint 應定期移入 `archive/`，不得無限 append。
6. `runbook-*.md`：可重跑的操作程序；容易漂移的 revision、digest、build ID 只放 operations／archive，不固定在 README 或一般 runbook。
7. `archive/`：已完成、已取代、歷史 checkpoint；不得當 active 指令來源。
8. 新增但未排程的構想放 `todo.md` 明確標示的 Deferred／Backlog 區，或白名單 Drive 的研究／規劃文件；不要假設存在獨立 `doc/backlog/`。

## 7. 驗證與完成判定

- 預設跑覆蓋本次 diff 的最小驗證；不因慣例每次都重跑完整 test／lint／build。
- 文件小改至少檢查路徑、連結、內部一致性與 diff；程式修改由執行環境跑直接相關 targeted tests。
- 跨模組契約、migration、安全／權限、依賴、建置鏈或里程碑結案時，再評估完整測試。
- GCP dev／live／E2E 驗收必須由真實 GCP dev runtime 或其受控 acceptance path 證明；localhost／fixture 不得冒充 live evidence。
- 完成狀態依 implementation、tests、CI、deployment、runtime、trigger／workload、integration evidence 綜合判斷。

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
