# Janus 共用 GAS Loader｜Drive 程式 → Apps Script 受控同步

更新：2026-10-20。工程元件：`research/gas/janus_gas_loader.gs`，本文件是其唯一操作說明。**本元件不執行所同步的程式、不建立定時器、不部署 Cloud Run，也不能把 Drive `.gs` 直接當作可執行專案。**

## 目標與安全界線

- 程式來源：私人 `janusChatGPT/GAS 程式/<檔名>.gs`。首次範例 `risk_monthly_pilot.gs`（Drive 檔案 ID：`1DTybrJBjYGwLmjXpAwBJH3ZiFeZwVzZq`）。
- 建議 GitHub `main` 是程式審查/版本控制來源；Drive 的 `.gs` 是待同步副本。只允許明列的 Drive 檔案 ID、指定 Apps Script `scriptId` 及目標程式檔名。**修改 Drive 程式須重新審核並更新 `approvedSha256`。**
- 人工執行 `janusGasLoaderPreviewFromEditor()`，檢查差異並取得10分鐘確認碼 → 設定 `JANUS_LOADER_CONFIRM_CODE` → 執行 `janusGasLoaderApplyFromEditor()`。不使用 `eval`。沒有確認碼絕不修改遠端 HEAD。
- 同步保留目標專案其他 `.gs`/HTML/`appsscript.json` 的原始 `source`/`type`；`updateContent` 是整個專案內容覆寫 API，因此新增/替換檔案之前必須取得並攜回**完整**專案檔案清單。首次變更前建立 `projects.versions.create` 不可變版本，讀回備份一致才 PUT，PUT 後讀回全部檔案雜湊。失敗嘗試用備份版本復原、重新驗證，失敗標示 `rollback NOT VERIFIED`。
- 只同步 HEAD 原始碼；不建立/執行觸發器、不更新 deployments、不修改來源、Owner 私有資料或 canonical。目標專案已有的觸發器在 HEAD 更新後可能使用新程式碼，因此**只挑選已核准的測試/專用目標**；不要對正在執行的正式 GAS 專案直接測試。
- 不自行擴權、啟用付費服務，也不將 OAuth token、Secret、原始程式全文寫進 log。

## 一次性的人工 Google 操作

1. 登入與 Drive 同一個 Google 帳戶，開啟 https://script.google.com/home/projects/create，建立獨立專案 `Janus GAS Loader`（請勿放進 Risk 目標專案，避免 Loader 自己覆寫自己）。
2. 從 [Drive GAS 程式](https://drive.google.com/drive/folders/1p6fDn9DPSKisT2iFkahb9P8T_y9g73vS) 的 `janus_gas_loader.gs` 複製程式內容到 Loader 專案的 `Code.gs`。在 **專案設定** 勾選「在編輯器中顯示 appsscript.json」，用 GitHub `research/gas/appsscript.loader.json` 的內容取代 Loader 自身的 manifest，儲存。
3. 前往 [Apps Script 設定](https://script.google.com/home/usersettings)，開啟允許 Apps Script API 存取專案的選項。所使用的 Google Cloud Project 也須啟用 Apps Script API；如果需要新增付費資源或擴大 IAM，先停止，這不屬於本 Loader 的自動操作範圍。確認 Google 所需 OAuth 授權（Drive 唯讀、Apps Script 專案修改、外部 HTTP 請求）。
4. 另外建立專用測試目標 `Janus Risk Pilot` Apps Script 專案。從其「專案設定」複製 **Script ID**；此 ID 是允許同步的 `scriptId`，**不要誤填 Drive `.gs` 檔案 ID**。
5. 在 Loader 專案的「專案設定 → 指令碼屬性」設定：

| 指令碼屬性 | 填入內容 |
|---|---|
| `JANUS_LOADER_FOLDER_ID` | `1p6fDn9DPSKisT2iFkahb9P8T_y9g73vS` |
| `JANUS_LOADER_SELECTED_KEY` | `risk_pilot` |
| `JANUS_LOADER_TARGETS_JSON` | 下方單行 JSON（填入你新建的 Script ID） |

```json
[{"key":"risk_pilot","sourceFileId":"1DTybrJBjYGwLmjXpAwBJH3ZiFeZwVzZq","scriptId":"填入你自己的目標ScriptID","destinationName":"risk_monthly_pilot","approvedSha256":"0000000000000000000000000000000000000000000000000000000000000000"}]
```

6. 第一次執行 `janusGasLoaderPreviewFromEditor()` 將回報 `SOURCE_HASH_NOT_APPROVED` 及 `observedSha256`。請比對 Drive 程式和經審核的 GitHub 內容，**只有核對正確後**，把 JSON 的 `approvedSha256` 改成 `observedSha256`，再執行 Preview（查看「執行紀錄」輸出）。Drive 複製/匯出可能帶 BOM 或 CRLF；Loader 統一為 LF 並保留一道尾行換行，SHA 依**正規化後的程式碼**計算。不可只因提示哈希就不看內容直接批准。
7. Preview 若顯示 `REVIEW_REQUIRED`，核對 `targetScriptId`、`destination`、`existingFileCount`、`unchangedFileCount` 和 `sourceSha256`。於10分鐘內新增指令碼屬性 `JANUS_LOADER_CONFIRM_CODE`（填回 Preview 的12位碼），再執行 `janusGasLoaderApplyFromEditor()`。
8. 成功應回傳 `SYNCED_VERIFIED`、`backupVersion`、檔案數與 `collectorExecuted=false`。開啟**目標** Apps Script 專案確認 `risk_monthly_pilot.gs` 已出現、其他檔案還在。之後 Risk 採集器本身需依 `research/colab/README.md` 設定 `JANUS_RESEARCH_FOLDER_ID`、來源授權等腳本屬性，並**另外手動**執行 `janusRiskPilotCollect()`；同步不會代跑。

## 日後更新 / 多專案

- 修改 GitHub 程式 → 同步/審核 Drive 版本 → 更新 pinned SHA → Preview → Apply。若顯示 `NO_CHANGE`，不需要 Apply。
- 新增第二個角色的 GAS 時，將新的 `{key,sourceFileId,scriptId,destinationName,approvedSha256}` 放進同一 `JANUS_LOADER_TARGETS_JSON` 陣列，透過 `JANUS_LOADER_SELECTED_KEY` 切換；最多20個白名單目標，不需第二套 Loader。
- `SOURCE_HASH_NOT_APPROVED`：來源未核准；`target changed since preview`：目標 HEAD 被其他操作改動，請重新 Preview；`rollback NOT VERIFIED`：停止修改該目標，依 `backupVersion`/專案實際內容人工處理；`HTTP 403`：查 Google API 啟用、OAuth、Script ID 權限，切勿繞過。

## 測試、證據與範圍

- 本地 `node --test tests/gas_loader/test_janus_gas_loader.cjs`，涵蓋來源 SHA、隱私/來源 ID、manifest 完整、原專案其他檔保留、preview/apply 確認、版本、衝突、一次性碼、rollback。
- 測試皆為 mock API 契約回歸；**Google Apps Script API live 授權、實際同步、Risk 採集及 Colab OOS 必須獨立讀回**，不得以本地測試或 CI planner SUCCESS 說成 live PASS。
- 沒有 Google API 權限時不自行建立外部 OAuth App 或新 GCP project。正式 Janus ingestion、Core/Mart、Owner、Stage48h 與既有 Scheduler 不受影響。

Google 官方參考：
- https://developers.google.com/apps-script/api/how-tos/enable
- https://developers.google.com/apps-script/api/reference/rest/v1/projects/getContent
- https://developers.google.com/apps-script/api/reference/rest/v1/projects/updateContent
- https://developers.google.com/apps-script/api/reference/rest/v1/projects.versions/create