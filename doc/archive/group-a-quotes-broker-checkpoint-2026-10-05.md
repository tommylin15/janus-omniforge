# A 組 Quote Router／Broker Profile runtime checkpoint（2026-10-05）

A 組維持 **partial**。本 checkpoint 只記錄實作／部署及 bounded runtime evidence，
不取代真實 authenticated browser／四頁 Final Visual Contract acceptance。

## 實作與 tests

- Main feature commit：`2d8a7bf6c916f8901bb29779d48dfbe753a52420`。
- Quote／Broker contract：[`quotes-and-broker-profile.md`](../spec/quotes-and-broker-profile.md)。
- Python targeted tests 146 passed；Flutter tests 48 passed；analyze 無 errors／warnings。
- Remote Flutter run `37305142465`、Portfolio Contract `37305142466`、schema CI `37305142451` 全成功。
- Runtime readback 發現的共用 context freshness 補強：main `5d37e5fb6c8bd05562e110a5538f673ed8ef2150`；相關 Python tests 47 passed。

## 第一輪 GCP deployment（實際 verification logs）

- GitHub Actions [37305142870](https://github.com/tommylin15/janus-omniforge/actions/runs/37305142870)：success。
- 正式 migration `044_quotes_broker_profile`；execution `janus-ingestion-core-8j8t5`。
- GCP evidence UTC `2026-10-05T11:55:41Z`：operation `serving_schema_migration`、status `succeeded`、duration 746ms。
- 未重跑 041／042／043；未部署 Intelligence Mart。
- Ingestion／Private Pipeline／API deployment success。
- API latestCreated＝latestReady＝`janus-api-g2d8a7bf6c916-config`，100% traffic。
- API image digest：`sha256:aab6616ee1d47af7fb427b8e9bacebcb58db99964134334da37916a4f8270ffe`。
- GCP verification UTC `2026-10-05T12:05:43Z`：live Flutter build-id 與 feature commit 相符；user/Admin workspace、Admin auth boundary、retired redirect、PNG／PWA metadata checks passed。

## 第二輪 freshness deployment

Main `5d37e5fb6c8bd05562e110a5538f673ed8ef2150`；run `37306165330`。
Run 已於 UTC 2026-10-05T12:16:22Z completed／success；remote API tests 147 passed。
Ingestion／Mart／migration 全 skipped，沒有重跑已成功 migration；Private Pipeline／API success。
API latestCreated＝latestReady＝`janus-api-g5d37e5fb6c8b-config`，100% traffic。
Image digest：`sha256:ea4198ec208f049f8b314b285a3634e5d2106fe788ca7002bfab4ea410fb698b`。
UTC 2026-10-05T12:16:18Z 的 live verification：Flutter build-id＝此 code commit，
user/Admin workspace、Admin auth boundary、retired redirect、branding／PWA passed。
此部署 readback 不包含 authenticated owner Broker／Ledger API 或四頁 browser acceptance。

## Authenticated owner readback 與驗收邊界

Janus Dev Read-only v2 的真實 owner `trades` 返回 ledger version 24；
`positions`／2026 `annual-pnl` 返回 version 10、as_of 2026-09-24 並標為 available。
沒有把私人明細、owner ID 或 credential 寫入 repo。

第一輪 Cloud Run traffic logs 確認既有 `mcp-adapter`／`mcp-oauth` tags
仍指向 `janus-api-mcpownerbfix20260924`，所以 connector readback **不是目前
canonical API／Ledger UI 的驗收證據**。Main 的共用 context Mart 路徑也未做 ledger freshness
比對，已補齊：過期結果 pending／private_mart_stale、空 records、current ledger version。
本切片未變更 MCP OAuth tags／issuer／allowlist／scope。

Dev browser 停在 Google 登入頁；登入 popup 控制回報 locale override protocol error，
不能自動完成 authenticated browser acceptance。不得把此 tooling error 宣稱為 site bot block。

以下保持未驗收：Broker Profile 真實 CRUD／quote persisted cold read／source fallback、
export/delete privacy runtime lifecycle；Ledger Holdings／Records／Reports consistency、YTD realized P&L、
交易 refresh/invalidation；Today／Watchlist／Ledger／Stock Detail 四頁 Final Visual、390px／狀態布局；
warm p95 ≤2s、visited restore ≤300ms；Admin Data Governance／effective jobs。
Declared cash 尚非 canonical cash ledger；自動計費／per-trade fee-rule snapshots 尚未交付。
