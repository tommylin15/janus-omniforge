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

不得為本專案的任何驗證啟動 WSL。需要 Linux 或 shell 環境的驗證（包含
`bash -n`）一律改在 GCP Cloud Build、Cloud Shell 或既有 GCP dev runtime 執行。
不得以本機 WSL 作為驗證 fallback。

需要存取既有 GCP／gcloud credentials 或執行 GCP dev 驗收的指令，使用
Codex 升級權限執行（`sandbox_permissions=require_escalated`）；僅限既有
dev 資源，不得因此擴大 production 或付費資源範圍。

在執行任何 commit 或 push 前，必須先執行 `/ponytail-review`。
