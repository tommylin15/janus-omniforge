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
5. 完成項目移至 archive；新增但未排程工作放入 backlog。
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
- Free Tier 是 billing account／region 條件，Terraform 只能限制資源規格，不能
  保證帳單為 US$0；部署前仍須檢查資格與 billing budget。
