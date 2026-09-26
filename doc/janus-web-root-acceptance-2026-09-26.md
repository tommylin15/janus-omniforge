# Janus Web Root Routing Acceptance — 2026-09-26

用途：記錄 `janus-api`／Flutter User App 直接開啟 Cloud Run service root 時的 404 修復與 dev live acceptance。這是單一 routing incident 的 evidence，不代表 User product completeness、Admin completeness 或 `WBS-8-DEV-PILOT-RUN` 整體完成。

## 問題

- 當時 Cloud Run `janus-api` service 與 `/app` Flutter entrypoint 都已 Ready，但 FastAPI 沒有 `/` route。
- 因此直接開啟 Cloud Run service URL root 會得到 404；`/app` 本身仍是既有 Flutter web entrypoint。
- 這個問題屬於 web entry routing，不是 Cloud Run service failed，也不是資料完整度問題。

## TDD evidence

1. RED commit：`77328dfb5f590cca8afb99dd815d42953e8ee0f4`（`test: reproduce janus web root 404`）。
2. GitHub Actions run `36224928757` 的 `test-api` 明確失敗：`test_service_root_redirects_to_flutter_app` 得到 `404 != 307`；同次 targeted API suite 為 `1 failed, 22 passed`，`deploy-api` 因測試失敗而跳過。
3. GREEN commit：`27c8a0b7d091bcc0e86147688b5907762b32a2ba`（`fix: redirect Janus web root to app`），在 FastAPI 增加 `/` → `/app` 的 `RedirectResponse`。
4. GitHub Actions run `36225249002`：targeted API suite `23 passed`；Cloud Build `1b4a2ea6-9c9b-4d4f-847a-a7deff82feb8` 成功，`deploy-api` 與既有 `verify-dev.sh api` 都成功。

## Runtime evidence

- Cloud Run revision：`janus-api-g27c8a0b7d091-config`
- 100% canonical traffic 指向該 latest revision。
- Immutable image digest：`sha256:002e52dbebb21dfeb231a556e3c049728e54c9aad2246f3ba834bd1eb2e73991`
- 為避免只靠 unit test 判斷，`Inspect dev runtime` 的 `janus-api` case 增加 live root probe；harness commit：`fa816e11d4aa714b109f64583590e9b97d055dc3`。
- Acceptance request commit：`ebd61062bbb6e8392f7f7bd759f20516758bb4bd`；GitHub Actions run：`36226506571`。
- 該 run 在 GitHub runner 上實際讀取目前 Cloud Run service URL，驗證：
  - `/` HTTP status = `307`
  - `Location` = `/app`
  - `/app/` entrypoint 包含 `Janus · OmniForge`
  - job conclusion = `success`
  - log summary：`janus-api root redirects to /app and live entrypoint is reachable`

## 判定

- **Janus web root routing incident：complete。** 直接開啟 canonical Cloud Run service root 不再落到 404，而會導向 Flutter `/app` entrypoint。
- 本次只跑 API targeted suite（23 tests）與 dev live routing acceptance；沒有宣稱本次因此完成整個 repository test suite、User product completeness、portfolio completeness、market-home completeness 或 Admin workspace。
- Product Completeness foreground queue 不因本修復改序；下一個 foreground 原子項目仍由 `doc/todo.md` 定義，目前為 `WBS-6-PORTFOLIO-COMPLETENESS`，需重新做模型確認後才能開始。
