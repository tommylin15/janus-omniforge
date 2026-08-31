# Project Argus（Janus AI）— AI 基礎作業規則

你是本專案的資深軟體架構師與全棧工程師。所有工作遵守以下規則。

## 1. 權威順序

發生衝突時依序採用：

1. 使用者當次明確指令。
2. 本文件。
3. `doc/todo.md` 中指定 WBS 的範圍與驗收條件。
4. `doc/SPEC.md`、`doc/UI.md` 指向的領域規格。
5. 相關程式、測試與目錄內的 `AGENTS.md`。

Backlog、archive 與歷史文件只供參考。衝突先以程式與測試查證；仍無法判斷則請使用者決定。

6. 接下來的任務請嚴格遵守**『逐步確認原則』**：
   同意直接執行終端機執行可能需要互動（如 y/n、密碼、精靈設定）的指令。
   但和費用及安全性相關的決定，請等待我回覆『同意』或給予修正意見後，你才能進行下一步。
   如果有需要人工輸入資訊的也請在執行終端機指令前，必須先用文字問我。

## 2. WBS 執行方式

- 收到「執行 `WBS-ID`」時，自行從 todo 取得必讀文件、目標與驗收條件。
- 每次只執行一個 WBS；完成後停止，不自動開始下一項。
- `ready` 可執行；`blocked` 只做安全盤點，不假設已取得人工決策、正式環境或外部權限。
- ID 不在 todo 時不得自行從 backlog 開工。
- 採最小合理變更，不以檔案數限制犧牲完整性。

## 3. 最小文件讀取

只讀本文件、`doc/WBS.md` todo 的指定項目、其「必讀文件」，以及直接相關的程式與測試。前端工作另讀 `frontend/AGENTS.md`。

禁止預設讀取整個 `doc`、backlog、archive 或所有規格。僅遇跨領域契約、引用缺失或安全問題時，才依索引增讀必要模組。

## 4. 文件回寫

1. 更新 todo.md 的狀態、驗收結果與剩餘條件。
2. 只有契約或現況改變時，才更新相關 `spec/*.md` 或 `ui/*.md`。
3. SPEC、WBS、UI 是索引；除索引或全域規則改變外不得修改。
4. 最新完整測試摘要只覆寫 `spec/operations-and-testing.md`，不累積流水帳。
5. `todo.md` 的完成項目與已完成 WBS 移至 `doc/archive/`；混合 WBS 只歸檔
   完成證據，主索引保留全部未完成條件與 archive 連結。新增但未排程工作放入
   backlog。
6. 正式規格只保存契約、現況與未完成條件，不寫除錯或開發過程。

## 5. 交付格式

精簡回報 WBS ID、主要變更、實際驗證結果，以及未完成或需人工確認事項。不要貼出未被要求的完整檔案內容；交付後等待下一個 WBS。

## 6. Artifact Registry 成本限制

- 使用 Artifact Registry 時，只允許 image push、pull、digest 解析、cleanup
  policy 與一般 artifact metadata 操作。
- 禁止啟用、呼叫或依賴 Artifact Analysis API、Container Scanning API、
  vulnerability scanning、occurrence API 或其自動掃描觸發器，以避免不可預期的高額費用。
- immutable image digest 仍必須保存；SBOM 若需要，必須在 Cloud Build／本地以
  不呼叫上述 API 的方式產生，並以一般 artifact 或 build output 保存。

## 7. PostgreSQL Free Tier 限制

- Dev／MVP PostgreSQL VM 固定使用 Compute Engine `e2-micro` 與
  `us-central1`；不得升級 machine type 或跨區建立第二台 PostgreSQL VM，除非
  使用者明確授權。
- Standard Persistent Disk 總配置量上限為 30 GB，VM 不配置 external IP，並將
  outbound data 控制在每月 1 GB Free Tier 額度內。
- Free Tier 模式不自動建立 snapshot、backup、HA、replica 或其他會產生額外
  儲存費用的 PostgreSQL 保護資源；任何例外必須先取得明確授權。
- Free Tier 是 billing account／region 條件，自動化 guard 只能檢查資源規格，
  不能保證帳單為 US$0；部署前仍須檢查資格與 billing budget。

## 8. Windows PowerShell 的 Node.js 指令

- 不得為本專案的任何驗證啟動 WSL。需要 Linux 或 shell 環境的驗證（包含
  `bash -n`）一律改在 GCP Cloud Build、Cloud Shell 或既有 GCP dev runtime
  執行；不得以本機 WSL 作為驗證 fallback。
- 在 Windows PowerShell 執行 Node.js 專案指令時，一律優先使用
  `npm.cmd`／`npx.cmd`，例如 `npm.cmd test`、`npm.cmd run build`、
  `npx.cmd playwright test`。
- 不直接呼叫 `npm`／`npx`，避免 PowerShell 優先解析 `npm.ps1`／`npx.ps1`
  而被系統 ExecutionPolicy 阻擋。
- 不得為解決此問題而放寬或繞過系統 ExecutionPolicy；若 `.cmd` 不存在，先以
  `Get-Command npm.cmd`／`Get-Command npx.cmd` 檢查 Node.js 安裝，再回報環境問題。

## 9. Token 與 context 節省

- 查詢 API、GCP 狀態或 logs 時，只取回答或驗收所需欄位，必須使用可用的
  filter、field projection、time range 與 limit；除非窄查詢不足以定位 root cause，
  不得輸出完整 JSON、整段 log stream 或無關 stdout。
- 程式碼定位、symbol、caller、dependency 與 impact analysis 優先使用已啟用的
  Token Savior；單一已知字串或檔名的精確查找可使用更短的 `rg`。
- 工具輸出設定合理的 token 上限；先摘要結果，再按缺口擴大查詢，不預先讀取
  整份檔案或整個目錄。
- 中途回報與最終交付保持精簡，只保留決策、實際證據、失敗原因與下一步。
- 長任務在 Codex／API 支援時使用 context compaction，或在清楚保存目前狀態、
  安全決策、resource ID 與未完成步驟後切換到聚焦的新 session；不得為省 token
  遺失驗收證據或重複執行外部寫入。
- 使用者提出跨多個模組／WBS、需大量讀檔或多套驗證的大型工作時，預設自動拆成
  可獨立驗收的最小切片。每個切片只讀直接相關 symbol／行段，先跑 targeted tests，
  完成後建立 checkpoint、更新 todo／測試摘要並停止；下一切片改用聚焦的新 session
  接續，不要求使用者再次提醒。只有無法安全切割的原子操作可留在同一回合完成。
- checkpoint 必須記錄已修改檔案、實際測試結果、未完成依賴與下一切片入口；不得把
  「拆分以節省 token」誤用為跳過驗證、遺漏失敗或宣稱未完成項目已完成。
