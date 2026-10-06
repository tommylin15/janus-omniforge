# A 組 non-live closure checkpoint — 2026-10-06

狀態：**non-live implementation closure = complete；A 組整體 = partial。**

本文件只證明可由 repository／tests／migration／CI/CD／Cloud Run verify 完成的 A 組工程閉環。它**不**取代 authenticated browser、手機 PWA、真實 owner mutation、效能、Scheduler/GCS 的 live acceptance。

## 本輪已關閉

### 1. Final Visual production path 與資料視覺化

- production build target：`lib/final_visual.dart`。
- Today／Watchlist／Ledger／Stock Detail 使用新版 presentation layer；Today 移除「櫃買指數」。
- 新增 `final_charts.dart`：Stock Detail OHLCV candlestick＋有 `volume_shares` 時成交量、五面向健康度 bars、Ledger Reports 月度已實現損益。
- 視覺化不建立新的 canonical number；沒有 backend 欄位即 bounded unavailable。

主要 commits：`16063d52`、`88033b2b`、`b1209c10`、`ed240b1d`、`3e29701f`。

### 2. User／Admin PWA 安裝 identity

- User 保持 `id/start_url=/app/`。
- Admin 使用 `admin-manifest.json`，`id/start_url=/app/admin`。
- 同一個 Flutter build 產生 `index.html` 與 `admin-index.html`；沒有建立第二套 User App。
- API 對 `/app/admin` 與其 fallback 回 Admin shell；app shell／manifest 使用 no-store 更新政策。

主要 commits：`3ea8d2c5`、`55e8b2d2`。

### 3. Ledger YTD／correction／refresh semantics

- YTD 區分 authoritative annual P&L、confirmed zero、pending、unavailable。
- Records 恢復 append-only「建立更正」；呼叫既有 correction endpoint，不原地修改 ledger。
- 新增／更正成功後顯示 pending，並以同一 `load()` 重新讀取 summary／annual P&L／positions／history／monthly summary／performance／notes。

主要 commits：`4c169996`、`4ff11ae1`、`6f62d607`。

### 4. Admin Private Pipeline operations

- migration `045_private_pipeline_operations` 建立去識別化 operational status，只含 pipeline checkpoint/change backlog、latest ledger version、valuation date/lag、result/execution/update time。
- `janus_web_control` 只有 aggregate SELECT；不暴露 owner、symbol、trade 或 holdings body。
- Private Pipeline 完成／失敗會更新 aggregate；Admin 資料治理讀取並顯示 unknown/available，不以缺值補零。
- migration 045 成功；Private Pipeline seed execution `janus-private-pipeline-hv8sq` 成功。

主要 commits：`39bef1af`、`3ea8d2c5`、`55e8b2d2`。

## CI/CD 與 runtime evidence

- Flutter User App run `37405203811`：SUCCESS；analyze、58 tests、PWA metadata、production web build 全部成功。
- Deploy dev run `37405204175`：SUCCESS。
- Cloud Run latest Ready revision：`janus-api-g3e29701ffae1-config`；traffic 100%。
- image digest：`sha256:801e157899e99c38f2ca3d059a6b246d8391d9299a84b6018c26612465296f68`。
- verify：Flutter User/Admin workspace、distinct User/Admin PWA manifests、Admin auth boundary、retired Admin redirect、web build、branding/PWA metadata 全部 match `3e29701ffae1dfe3aa9d32deb50ded03f8145c18`。
- migration 045／Private Pipeline rollout run `37398213942`：retry attempt 2 SUCCESS。attempt 1 的 HTTP 429 發生在 post-deploy verify；既有 migration/deploy success 未重做。

## 尚未完成：live-only acceptance

1. 真實 Android 安裝 User 與 Admin 後各自重開，確認兩個 icon 的 PWA identity/route。
2. Google authenticated User／Admin、owner isolation、未登入拒絕。
3. Today／Watchlist／Ledger／Stock Detail 約 390px 實機視覺對照；包含 loading／empty／error／partial／stale／missing。
4. 真實 owner 新增與建立更正交易後，驗證 operational position、Private Mart pending→refreshed、Holdings／Records／Reports／YTD 一致性。
5. 暖機核心 p95 ≤2 秒、visited restore ≤300ms 的真機量測。
6. Scheduler/Private Pipeline 真實時序、retry/failure receipt。
7. GCS lifecycle/cleanup、live/noncurrent/soft-deleted/billable bytes 與 reclaimed-cost evidence。
8. Admin 真實資料治理／effective jobs／Private Pipeline aggregate readback。

因此 **A 組不得標 done**；完成判定仍是 `partial`，直到上述 live gate 有足夠 evidence。
