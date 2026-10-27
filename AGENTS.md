# Janus / OmniForge — Agent 核心作業守則 (`AGENTS.md`)

> **權威文件宣告**：本文件為 Agent 進入專案時的基礎定位與核心守則摘要。完整工程規範、最新政策覆蓋（如研究精簡、第三方補收、單一順序線 `SEQ` 等）、部署程序、安全邊界與 WBS 驗收標準，一律以 [`doc/PROJECT_RULES.md`](doc/PROJECT_RULES.md) 為唯一最高權威來源。每次開始工作前，必須先閱讀並遵守 [`doc/PROJECT_RULES.md`](doc/PROJECT_RULES.md) 與 [`doc/README.md`](doc/README.md)。

---

## 1. 專案定位

- 本專案負責 **Janus / OmniForge 投資研究系統** 的產品設計、資料工程、軟體工程、模型研究、測試驗證、部署維運與資料治理。
- 本專案性質為 **研究系統開發專案**，而非個人持股操作或代客交易專案。

## 2. 權威來源與事實判定

- **實作與現況判定**：涉及目前程式碼、API、schema、migration、tests、CI/CD、deployment、infra、runtime、bug 或完成狀態時，一律以 GitHub `tommylin15/janus-omniforge` 的 `main` 分支內容以及實際 **runtime evidence** 為準。
- **跨來源差異處理**（GitHub / Runtime vs. Google Drive）：
  - **目前實作與完成狀態**：以 GitHub 與實際 runtime 證據為準。
  - **原始設計、研究推演與核准規格**：參考 Google Drive。
  - **禁止隱瞞差異**：若兩者不一致，必須明確指出差異，不得自行假裝一致或擅自將任一方改寫覆蓋成另一方。

## 3. Google Drive 使用邊界

- 唯一允許主動搜尋與讀寫的 Google Drive 白名單根資料夾為：**`janusChatGPT`**。
- 該資料夾用於存放正式規格、研究資料、模型推演、evaluation、benchmark、暫存分析與未排程的架構構想。
- **嚴格區隔**：Drive 內的暫存或研究資料不自動成為待辦事項（TODO），亦不得直接視為 production 或 canonical source of truth。

## 4. GitHub 與工程執行權限

- **單一分支策略**：本專案目前僅維護 `main` 單一 branch。除非使用者特別要求，不主動建立額外 branch 或 PR。
- **直接工程閉環授權**：在使用者當次指令與現行工作範圍內，AI 可直接執行：
  - 建立、修改、刪除並 commit 文件、應用程式原始碼、tests、schema、migration、scripts、Dockerfile、GitHub Actions、Cloud Build、IaC 與 runtime / deployment 設定。
  - 執行或觸發 tests、CI、build、migration、Cloud Run deployment、Job、Scheduler 與既有 `dev` 環境 workload。
  - 對既有 `dev` 環境完成 **「分析 → 修改 → 測試 → commit → deploy → runtime 驗收 → 修正」** 的完整工程閉環；若直接驗收未通過，可在既有授權範圍內繼續修正與重新部署，無須每一步重複請求授權。
- **規範依循**：詳細工程規則、部署程序、安全 guard、WBS / SEQ 執行方式與 acceptance criteria，依 GitHub 內的 [`doc/PROJECT_RULES.md`](doc/PROJECT_RULES.md)、[`doc/README.md`](doc/README.md)、runbook、SPEC、WBS 與 [`doc/todo.md`](doc/todo.md) 執行。

## 5. 需要人工授權的事項

一般既有 `dev` 環境的部署、版本化 migration、Job 執行、rollback 與常規修復不需逐次確認；但**以下事項必須先取得使用者明確授權或由使用者本人操作**：

1. **費用變更**：新增或調高付費 GCP / 第三方資源、啟用新的付費 API、模型或 subscription（已確認符合且在免費額度內之既有操作除外，依 [`doc/PROJECT_RULES.md`](doc/PROJECT_RULES.md) §1.3 辦理）。
2. **環境與權限擴張**：首次建立 `prod` 環境，或進行重大 IAM / OAuth / 系統權限擴張。
3. **高風險資料操作**：大量且不可逆的真實資料刪除，或缺乏可靠 rollback / backup / rebuild 路徑的破壞性操作。
4. **本人專屬操作**：MFA 驗證、OAuth consent 授權、付款設定或帳號管理等必須由使用者親自完成的步驟。

## 6. Dev 環境定位

- **真實平行上線環境（Parallel-Live）**：目前的 `dev` 是 Janus 個人使用階段的主要真實運行環境，並非僅供 mock、fixture 或 staging 演練的測試場。
- **真實鏈路運行**：在 `dev` 環境中可使用已核准的真實資料、API、OAuth、MCP、Cloud Run、PostgreSQL、Iceberg 與各項既有服務。
- **Prod 的定義**：`prod` 代表未來多人使用、高可用（HA）、SLA 或正式外部營運需求，不是目前個人真實使用的前置條件。

## 7. 核心治理原則（採精簡與務實治理）

所有開發、資料處理與模型整合遵守以下務實底線（已放寬過度繁瑣之歷史稽核限制，細部依 [`doc/PROJECT_RULES.md`](doc/PROJECT_RULES.md) §0 與 §1.7 執行）：

- **資料來源彈性與可追溯**：除了官方來源外，**已核准之第三方來源（如 Yahoo 股市等公開可讀來源）可直接使用，不限定只能使用官方資料，亦不要求先窮盡官方來源**；惟須如實標註來源（不得將第三方冒充為官方），並確保資料與操作具備基本可追溯性與可重跑性。
- **研究與治理精簡**：取消獨立資料稽核、逐來源授權補證與全歷史 PIT 重建等過度限制；僅保留直接影響系統功能、模型答案正確性、基本 cutoff 防洩漏（避免 future leakage）與資料安全的必要檢查。
- **真實性底線**：缺值不造假、不臆測補齊；資料不足時寧可標示 `missing` / `partial` / `unknown` 或不下結論。
- **資料層級隔離**：分離 canonical data 與 research data；研究暫存不因位於 `dev` 而自動升格為 canonical。
- **LLM 權責邊界**：LLM 不擁有 canonical 數值的決定權，亦不具備最終 publication 的決策權。
- **誠實狀態揭露**：`partial success` 必須如實呈現，不得包裝或宣稱為 `full success`。
- **機密保護**：Secret、token、password、private key 等敏感資訊，絕對不得進入 Git、一般 log、argv、前端程式碼或公開輸出。

## 8. 完成判定標準

- **禁止過早宣稱完成**：不得僅因程式碼已寫完、已 commit、build 成功或 deployment 完成，就單方面宣稱任務「已完成（PASS）」。
- **綜合證據驗收**：必須依任務性質綜合確認 GitHub implementation、tests、CI、deployment、migration、live runtime、trigger / workload、integration、live data 與 acceptance evidence。
- **證據不足之處理**：凡缺乏實際驗證證據的項目，狀態必須維持 `unknown`、`partial` 或 `blocked`，據實回報。

## 9. 工作方式與溝通原則

- **最小必要讀取**：先讀 [`doc/PROJECT_RULES.md`](doc/PROJECT_RULES.md)、[`doc/README.md`](doc/README.md) 與任務直接相關之最小必要文件與目前實作，不預設將整個 repository、`archive/` 或 Google Drive 全部載入。
- **最小合理變更**：實作以最小合理變更為原則，但不得以此為由省略必要的 tests、migration、deployment 或 live acceptance。
- **語言規範**：Active SPEC、WBS、TODO、UI 與使用者可見說明以**繁體中文**為主；API 路徑、schema 欄位、程式識別字與產品／模型名稱保留原文。
- **直率提出異議**：發現設計、指令、假設或現況有不妥、矛盾或風險時，**必須直接提出並說明原因，不要盲目順從或一味回答「可以」**。
