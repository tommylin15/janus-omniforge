# A 組部署 checkpoint／GCP dev Cloud 驗收交接

時間：2026-10-05（台北）。此 checkpoint 只證明目前變更部署，A 組 acceptance 仍 partial。使用者要求本地暫停剩餘驗收，由 Codex Cloud 針對既有 GCP dev 真實測試驗證；未實作能力如實列缺口，只有驗收發現缺陷才修正。

## 已提交與部署

- 實作 checkpoint：`ba4cf52be580670d9e50629dd569a1185d325426`。
- 離榜保留測試修正：`1765e144e67bd805d1173c87af263d3a350a247f`。
- API migration dependency contract 修正：`0896de8a6352951340140586520b8ef1b7cf39ed`。API／Private Pipeline 部署使用此版本。
- [修正後 CI](https://github.com/tommylin15/janus-omniforge/actions/runs/37276378569)：API 128 tests、Mart 94 tests passed。
- [Flutter CI](https://github.com/tommylin15/janus-omniforge/actions/runs/37275356835)：analyze／tests／web build passed。
- [Ingestion／043 migration](https://github.com/tommylin15/janus-omniforge/actions/runs/37275357242)：兩步 success；該 run 整體 failure 來自後續已修正的舊 API gate，API 當時未部署。
- 043 execution：`janus-ingestion-core-2b57v`；runtime receipt `migration=043_admin_batch_read, status=succeeded, duration_ms=1013`。
- [Private Pipeline 部署](https://github.com/tommylin15/janus-omniforge/actions/runs/37276378889)：success。
- [API 部署](https://github.com/tommylin15/janus-omniforge/actions/runs/37276581861)：success。
- API ready／created revision：`janus-api-g0896de8a6352-config`，100% 流量。
- API image：`us-central1-docker.pkg.dev/gen-lang-client-0593591102/janusai-poc/api@sha256:226c022926c2b61fc93696c058c4bd8b04323b679cb11eb1bd4e45a8c7950ae6`。
- Private Pipeline image：`us-central1-docker.pkg.dev/gen-lang-client-0593591102/janusai-poc/private-pipeline@sha256:881fd666869a8ec87c41607b8db8b54902ebb13a77575437837cd1eb9360fc13`。
- Ingestion image：`us-central1-docker.pkg.dev/gen-lang-client-0593591102/janusai-poc/ingestion-core@sha256:6ae0cdd1bf0ab697fd8ea69e207015d4b51edbc3d5329f88887173bee8c40245`。

## 尚未取得的驗收

- 真實 authenticated User 四頁／Admin 六頁操作與截圖、owner／audience 負向、受控 mutation／projection 驗收。
- 四張正式 PNG 的視覺 regression／GCP 截圖比對與 390×844 overflow。
- 真實冷／暖效能 baseline、p50／p95、導覽恢復／輪詢／query source 證據。
- 資料治理／FinOps／cleanup 剩餘 evidence。既有成功 receipt 可重用，不重複 apply。
- Broker Profile、完整 Quote Router／last-quote persistence、完整四頁收斂與部分治理欄位尚未完成，這次部署不宣稱實作或 acceptance 完成。

正式下一步及權限看 active `doc/status.md`、`doc/todo.md` 與 `doc/codex-execution-plan.md`；本文件為歷史部署證據，不獨立授權下一組。
