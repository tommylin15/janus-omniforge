# Janus TODO — Dev 平行上線執行補充

日期：2026-09-20
狀態：目前有效；與 `todo.md` 一起解讀，僅調整環境與驗收語意，不改寫既有完成證據。

## 1. 全域執行政策

- 目前 GCP `dev` 是 Janus 個人使用階段的主要真實運行環境（parallel-live environment）。後續 TODO 若寫 `dev`、`GCP dev`、`Dev Pilot`、`live acceptance`，預設都在這個真實環境執行，不解讀成必須用假資料、mock、staging 或模擬操作。
- 已核准且使用者實際需要的功能，優先完成真實閉環：真實資料／持久化 → 真實 backend／Job／Scheduler → 真實 auth → 真實 API／MCP／provider → 真實 Flutter／Admin UI。能以 bounded scope 安全驗證時，不額外建立一套假資料流程作前置。
- `Production`、`productionization`、`Prod Go／No-Go` 只約束未來對外、多使用者、HA／SLA、更高可靠性、較大權限或成本的正式營運強化，不阻擋目前 dev 個人真實使用已通過 real-path acceptance 的能力。
- 六個月 Dev Pilot 改解讀為持續收集 reliability／cost／data／analysis usefulness evidence 的觀察期；它不是「六個月內只能測試、不能真的使用」。
- 未完成項目仍維持未完成；本政策不能把 local test、程式已寫完、fixture success 或 partial runtime success 包裝成 full live success。

## 2. 驗收優先順序

1. 現有 GCP dev 的真實 runtime／URL／revision／immutable image。
2. 真實 OAuth／owner、真實持久化資料與現有 PostgreSQL／Iceberg。
3. 真實 API、Cloud Run Job／Service、Scheduler、Agent Gateway、核准 provider 與核准 MCP。
4. 真實 Flutter User／Admin 操作流程。
5. targeted automated tests／contract tests。
6. mock／fixture／localhost 僅作快速回歸或故障注入補充。

任何步驟若因外部權限、成本、provider quota 或真實服務無法安全製造故障而不能執行，應明確標記 blocked／partial，而不是改用模擬結果宣稱 real path 完成。

## 3. WBS-4C／MCP 特別調整

- WBS-4C 的主要價值是讓 Agent Gateway 實際連接並使用核准的真實 MCP／provider；正常驗收應優先確認真實 server 的 initialize／tool discovery／tool call／auth／result path。
- `janus-mcp-fixture` 只保留作 deterministic fault injection：timeout、cancel、disconnect、`tools/list` changed、schema/error handling、secret-redaction／leakage negative tests 等。
- Fixture 不是正式業務資料來源、不應出現在正常 User UI 的 MCP 選單，也不是 Flutter Admin 或主要 API 的依賴。
- 不要求 fixture 長期部署才能讓真 MCP 功能被個人使用。若故障注入 coverage 已足夠，可 scale-to-zero、按需部署或只保留測試程式碼；是否刪除 GCP service 以當時尚未完成的 WBS-4C acceptance evidence 判定。
- 真人 device-code、durable continuation、owner-scoped auth 等目前仍未完成的條件保持未完成；「dev 是真實環境」不等於把這些風險自動視為已解決。

## 4. UI／資料行為

- UI 只顯示真實 backend 已知狀態；缺資料、stale、partial、provider unavailable、MCP unavailable 必須直接顯示，不用 sample data 或 placeholder 補成功。
- 正常使用流程不得把 fixture secret、fixture tool 或測試 owner 當作正式資料顯示。
- 研究暫存、scenario input、validation sample、experimental artifact 即使在 dev 真實執行，也仍依 research／canonical／provenance／PIT／source authorization 規格分類；環境真實不代表研究結果自動成為 canonical。

## 5. 仍保留的最低安全底線

- Secret／credential 不進 log、UI state、URL、一般資料表或 image。
- 大量／不可逆刪除需要防誤觸、狀態可追蹤，以及可恢復／可重建判斷。
- Schema 變更使用 migration／version，不能直接手改真實資料庫而不留 lineage。
- 重要個人資料至少有已核准 bounded backup／export／restore 或可重建來源。
- Owner／auth 邊界、資料外送範圍、PIT／provenance／canonical 與 source authorization 不因個人使用而取消。

## 6. 對既有 TODO 的解讀

若 `todo.md` 的舊文字同時出現「dev POC」「Pilot Entry」「production blocked」「productionization」等詞，先依 `PROJECT_RULES.md`、`spec.md`、`wbs.md` 與本文件判斷：

- 對目前單一使用者 real dev path 已可安全驗收的能力：允許在 dev 真實使用並累積 evidence。
- 對多人 owner provisioning、HA／PITR、distributed lock、multi-instance、正式 SLA、外部公開服務或新增付費基礎設施：仍屬未來 Production／擴張條件，不因本政策自動放行。
- 對既有 checklist 的完成狀態：只依 GitHub tests、CI、deployment、live data、trigger、workload 與 integration evidence 更新，不能僅因政策改變就勾選完成。
