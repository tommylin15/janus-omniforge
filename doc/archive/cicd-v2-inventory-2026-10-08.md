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
- 首輪 Repository Trigger 手動 SHA build `c9a8ab87-d1f7-46a9-813e-a2e194a344f9`，sourceProvenance 為 Git SHA `1e5b6ba52a6ce9db5c233c70f6153ab7e0e8b12a`，無 GCS source staging。Tests 485 PASS／3 FAIL，原因為 test image 缺 `libgomp.so.1`；Docker build/push/deploy 未執行，證明 tests failure gate 生效。後續修復僅安裝 test container 的 libgomp1。
- 清理前 Artifact Registry 盤點：15 versions、4,290,979,269 image bytes，missing-size=0。這是 registry metadata aggregate，不是帳單容量；尚未執行刪除。

## CI／Release追加政策checkpoint

- GitHub Connection：`tommy-github` COMPLETE；Janus repository source已連接。
- Trigger同一ID `15f3d1cb-fbb2-447b-8f1a-cfd3173e321d`原地轉manual `sourceToBuild`，移除`repositoryEventConfig`，沒有新增trigger。
- V2 shadow Build `29f80814-c0f2-471c-ab0c-aa2b17426a2c` SUCCESS；SHA `dfec48479e1641a7f7429023b07e9df9cd98cd72`。
- 四元件digest：ingestion `a7a1352a3612bbc966acdfa3f5160b9ae70aed13f028c052294fab85b659f8a3`；Mart `53be0a226c4823d790f73f5a4a1af9d0b4ef733b6dac4555c9aafd1ccbd96477`；private `3c500bb683132e78ab2ed4e4b0c1dcfcf93e5c4acaea0b91faba2ea0cdb3425a`；API `251cbc9a6864214fe7b16a308d01cae9e14bb9f4016aff7202383e4142c535ed`，均為`sha256:`。
- `v2/evidence/29f80814-c0f2-471c-ab0c-aa2b17426a2c/build-receipt.json`保存完整registry URI、tests PASS、runtime NOT_RUN。
- 050版本化SQL经IAP在existing dev PostgreSQL執行：BEGIN／GRANT／publication schema+view ACL true／control private isolation true／INSERT marker／COMMIT；沒有新增resource或擴大IAM。
- 原Push policy已被使用者追加政策取代；新的main Push只測試，正常runtime發布只能明確Release。四元件仍同一輪acceptance，不逐元件重新核准。

- API no-traffic候選 `janus-api-v2-dfec48479e1641a7f742`：health、public health、未登入User／Admin 401、Flutter完整SHA／User+Admin bootstrap PASS；原positive traffic未變，Job images沒有更新。
- 第一次候選在API mutation前因既有active Job停止；修正為candidate只讀Job，第二次有限嘗試完成。兩次receipt分別保存`candidate-receipt.json`及`candidate-2-receipt.json`，沒有覆寫失敗證據。
- 真實browser候選登入顯示GSI origin不允許；已請使用者為既有User／Admin OAuth client加入固定`v2-candidate` origin。authenticated gates仍NOT_RUN，不偽造PASS、不升流量。

- CI／Release分離版本 `a8596ca233c77f595771624ecad1bc840b99ef52` main Push：selective CI [37730258698](https://github.com/tommylin15/janus-omniforge/actions/runs/37730258698) SUCCESS，只跑controller／ingestion；migration validation及Portfolio contract皆SUCCESS。沒有舊Deploy workflow。
- 明確manual候選Build `6e20016d-5309-4984-91a1-42e8dde15872` Repository Source／resolvedGitSource完整SHA一致；prepare、tests/security與四元件Docker SUCCESS（完成狀態見下列receipt）。
- Job idle fence修正：九月private image-not-found execution的Completed=False已是terminal，不能只以缺completionTime判active。新版helper真實讀回四Job均IDLE，沒有cancel／redispatch。

- Build `6e20016d-5309-4984-91a1-42e8dde15872` SUCCESS；API revision `janus-api-v2-a8596ca233c77f595771`公開／negative／Flutter gate PASS，Job images及positive API traffic未變，receipt仍PARTIAL。
- 真實read-only migration preflight execution `janus-ingestion-core-jkm9f` PASS；existing image來源為`dev-1e5b6ba52a6ce9db5c233c70f6153ab7e0e8b12a`，沒有apply已完成migration。
- 發現existing AR native `delete-all` ANY + KEEP1，與本次rollback保留政策衝突；原政策原地切dry-run，`cleanupPolicyDryRun=true`讀回。沒有image deletion／資源擴張。現役API舊digest `7528bdf24045169f45bcd976f44f969360939a4b100ab90441bbecef610b93a5`仍可describe。
- 本機兩個既有DuckDB金融timestamp測試因缺lock內`pytz==2025.2`失敗；補齊至workspace暫存dependency target，不改business code或global Python，必要驗證重跑79 PASS。
