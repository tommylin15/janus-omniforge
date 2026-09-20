# Janus — Parallel-Live Dev 操作 Runbook

日期：2026-09-20

本文件補充 `runbook-dev-deploy.md`。現有 GCP dev 資源、名稱、project、region、URL、部署腳本與 Secret reference 不因政策調整而改名；改的是操作與驗收語意。

## 1. 環境定位

目前 `dev` 是 Janus 個人使用階段的真實平行上線環境。部署到 dev 會影響實際個人資料與使用流程，因此不得把它當成可隨意清空的 disposable sandbox；同時也不需要另外建立 staging／production 才能開始真實使用。

正常開發目標是讓 main branch 的核准變更經既有 Cloud Build／deploy path 到達 GCP dev，並在真實 runtime 上用 bounded scope 驗證。`localhost`、mock、fixture 可以先做快速檢查，但不能代替標示為 live／GCP dev 的最終證據。

## 2. 真實資料與服務

Dev 預設使用：

- 真實 Google OAuth／allowlisted owner。
- 真實 PostgreSQL private ledger／control data 與 Private／Public Iceberg。
- 真實 Cloud Run API、Agent Gateway、Jobs 與 Scheduler。
- 經核准的真實 OpenRouter／Gemini／Codex 路徑與 MCP server。
- 真實 Flutter User／Admin surface。

資料不足時 fail explicit：顯示 missing／stale／partial／unavailable，不產生 placeholder 或假資料補成功。

## 3. 部署與 migration

沿用 `runbook-dev-deploy.md` 的既有腳本與 guard。因 dev 保存真實資料：

- schema 變更必須走 migration／version，保留可追溯紀錄；
- destructive migration 或大量刪除先確認影響範圍與恢復／重建路徑；
- secret rotation 不得把 secret 放入 argv、log、UI、build substitution 或一般資料表；
- 部署後以 revision／immutable image digest／runtime probe 判定，不只看 build 成功；
- partial success 必須保留 partial 狀態，不可因 Cloud Build 綠燈就宣稱 end-to-end 完成。

## 4. Backup／recovery 最低要求

目前不為個人使用強制建立 HA、replica、multi-region 或付費 production-only backup infrastructure。重要資料至少符合一項：

- 有既有 bounded logical backup／export 並有 restore evidence；或
- 能從具 provenance 的上游來源與 migration／event ledger 可重建。

私人 ledger 已核准的 `pg_dump → restricted Private GCS` 路徑繼續作為低成本 durability 手段。任何新增付費 persistent protection resource 仍需人工批准。

## 5. MCP fixture

`janus-mcp-fixture` 不是正常 runtime 的業務依賴。真實 MCP 是正常功能驗收主體；fixture 只用於故障注入，例如：

- timeout／cancel；
- disconnect／transport failure；
- tools list changed／invalid schema；
- secret-redaction／leakage negative test。

Fixture 可 scale-to-zero、按需部署或保留程式碼而不長期運行。移除 fixture 的 GCP service 不應影響 Flutter Admin、主要 API 或正常 Agent Gateway → real MCP 路徑；真正刪除前仍須用當時的 dependency／integration evidence 確認沒有 runtime 綁定。

## 6. 未來 Production

只有當使用模式變成對外、多使用者、需要 HA／SLA、更強 owner provisioning、multi-instance consistency 或正式營運隔離時，才啟動獨立 Production topology review。是否建立 staging、production project、replica、PITR、multi-region 等依實際 evidence 與成本決定，不預先複製一整套環境。

如果個人使用持續適合現有 GCP dev，維持 parallel-live dev 是有效的長期選項，而不是暫時失敗狀態。
