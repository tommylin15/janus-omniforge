# Project Instructions

本專案的正式開發規則、架構決策與工作限制，統一記錄於：

- `doc/PROJECT_RULES.md`

每次開始任何工作前，必須先完整閱讀並遵守
`doc/PROJECT_RULES.md`。

若本文件與其他文件衝突，以 `doc/PROJECT_RULES.md` 為準。

若使用者的新指示與既有規則衝突，必須先指出衝突，再依使用者最新明確指示執行。

完成工作前必須：

1. 檢查是否違反 `doc/PROJECT_RULES.md`
2. 執行適用的測試、lint 或驗證
3. 說明修改內容、驗證結果與尚待決定事項
4. 未經明確授權，不得部署 production 或建立付費 GCP 資源

Windows PowerShell 環境執行 `bash -n` 時，`bash.exe` 會透過 WSL 啟動，
workspace sandbox 內固定因 `Bash/Service/CreateInstance/E_ACCESSDENIED` 失敗。
Shell 語法檢查應直接使用已核准的 sandbox 外 `bash -n` 執行路徑，不要先重試
已知會失敗的 sandbox 內呼叫。

在執行任何 commit 或 push 前，必須先執行 `/ponytail-review`。