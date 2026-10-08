# CI/CD V2 盤點 — 2026-10-08

狀態：PARTIAL。這是盤點／實作 checkpoint，非 closure。

- 工作 baseline：GitHub main `6ab59bf0e24b52bcf557172348e59271db5d1414`。原本工作目錄未提交 B3 變更保留；使用 detached main checkout，不建立 branch／PR。
- Connection：`tommy-github`，`us-central1`，installation stage `COMPLETE`；repository `tommylin15-janus-omniforge` 已連結。GitHub 授權由使用者完成。
- 新 Trigger：`janus-dev-v2`／`15f3d1cb-fbb2-447b-8f1a-cfd3173e321d`，`^main$`，`disabled=true`。沿用既有 Cloud Build default compute SA，不擴 IAM；`janus-ci` 未見 project-level build 角色，不自行授予新角色。
- 初始 inventory 的 regional／global Cloud Build Trigger 都空；本次只新增上述停用 Trigger。
- `gs://gen-lang-client-0593591102_cloudbuild` 實際存在，location `US`，約 3,208,164 bytes。2026-10-07T04:37:59Z 與 2026-10-06T22:55:13Z bucket-create audit principal 都是 `life-assistant-github-deployer@gen-lang-client-0593591102.iam.gserviceaccount.com`。
- Build `0970f14e-7376-4708-8f1c-b8d6a3bcf53a`（2026-10-08T01:29:51Z）使用該 legacy source bucket。其他系統仍可能重建它；Janus 只做防回歸，不刪除其他系統 source evidence。
- Approved regional bucket `gen-lang-client-0593591102-cloudbuild-regional` 為 `US-CENTRAL1`；Core／Stage／Mart／Private／research buckets 保留。
- 既有 Job digest：ingestion／batch controller `sha256:c6896b3fe9a9ca7d6c618365d87855524410862030808e0d84232f41e54041a3`；Mart `sha256:782d79873adfde248f70362d84597ea3ad59d683932b5681838b915803a1bc95`；Private `sha256:4b94971d1418093185828e40bd4661219186f850adfb65946ade3f014f5ad772`。
- API：`janus-api-g53d655ccb108-config`、100% traffic；digest `sha256:7528bdf24045169f45bcd976f44f969360939a4b100ab90441bbecef610b93a5`。MCP tagged revisions 與 canonical traffic 不同，未自行更動。
- 舊 deploy run `37714565908`：ingestion deploy／tests success；050 migration execution `janus-ingestion-core-6vvmc` 為 `INSUFFICIENTPRIVILEGE / 42501`，API skipped。DB marker 到 049，未見 050。
- DB 查證 publication schema／stock_serving_recent view 均由 `janus_publication` 擁有，private 由 `janus_control` 擁有。050 授權已存在，失敗來自 control 階段跨 publication namespace 驗 ACL；最小修復將該檢查留在 publication owner，不擴角色。
- Local targeted tests：修復前 CI/CD/container/migration 40 PASS；050 owner-phase 修復後 CI/CD/migration 31 PASS。Linux `bash -n` 在修正 heredoc／CRLF 後 PASS。新版本 CI、Build、deployment／runtime acceptance 尚未執行，不以 local tests 冒充 live。
- 資源／費用：新增停用 Trigger；使用者完成 GitHub connection 授權；沒有新增 VM／Job／bucket、提高 CPU/memory、IAM grant、production、掃描 API 或資料刪除。Cloud Build 實際 usage／帳單尚待實際 build 後讀回，未知不填零。
