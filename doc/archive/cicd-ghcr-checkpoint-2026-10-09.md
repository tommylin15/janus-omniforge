# 新版 CI/CD 接續 checkpoint — 2026-10-09

本次只驗收 GitHub Actions → 公開 GHCR → Cloud Run；依使用者最新指示，舊 Revision／映像／GCS／AR 清理移出 active queue，不作為結案條件。

## 真實 dev 唯讀證據

- 既有 `us-central1` Janus Cloud Build Trigger `janus-dev-v2`（`15f3d1cb-fbb2-447b-8f1a-cfd3173e321d`）讀回 `disabled=true`；同輪 regional ongoing builds 為空。未修改 Trigger，也未呼叫 Build。這是時間點快照，不能代替發布鎖內重新驗證。
- Cloud Run `janus-api` Ready；GHCR source `8f6e7891e280cd021e25e1f036acedc28e3dbcec` 對應 candidate `janus-api-00448-vir`、tag `ghcr-8f6e7891e280` 為 0%，原 `janus-api-g53d655ccb108-config` 100%。未切流、改 Job image 或暫停 Scheduler。
- [候選負向邊界驗收 #37868708360](https://github.com/tommylin15/janus-omniforge/actions/runs/37868708360) SUCCESS，完成於 `2026-10-09T01:13:51Z`；workflow SHA `794acfc0b500bc22e2e39f75b8e24b7db1b29505`。驗證候選 tag／原 100% 流量、build identity、OAuth metadata、未登入 Private／Admin 拒絕與 MCP Bearer challenge；不宣稱真實 owner／callback／PnL parity／MCP authorized tool acceptance。

## 本輪發布防護修改

- `run-dev-ingestion.yml` 的現役 Job config writer 與候選部署、legacy recovery、Scheduler operator 共用 `janus-dev-runtime-writers`，不取消進行中的 run。
- legacy recovery 與 ingestion request 在任何 GCP 寫入前檢查既有 global Git-ref lease；lease 存在或查詢失敗均停止，不自行釋放其他 owner 的 lease。
- candidate lease contract CI 擴充受影響 workflow paths 與 Scheduler contract tests。
- 本機 targeted tests **52 PASS**；首次未設定 PYTHONPATH 的 collection error 已以正確 project import paths 重跑通過。`git diff --check`、修改文件的 local-link 檢查與四個 workflow YAML parse PASS。WSL bash -n 遇到啟動／stdin timeout，改用既有 Git Bash 驗證四個 workflow 共 28 段 shell，bash -n PASS。
- `/ponytail-review` 未發現須修正項；整體 Jobs mutex／rollback／rollout 尚未完成 live acceptance，不因此標 CLOSED。

## 尚待事項

1. 本機修改的 commit／push 被自動審核拒絕，要求使用者明確確認直接變更 main；目前保留 working tree，未提交。
2. 外部 Chrome 的真實 A → B → A 登入與私人讀取已觀察：A 的 portfolio snapshot／quotes、journal history／pnl、recalculation-status 均 HTTP 200，持股 4 筆、交易歷史 89 筆、年度 PnL 存在；B 相同五個 API HTTP 200，持股與歷史皆 0，PnL missing，重算 IDLE。畫面未把 A 的資料顯示給 B；只保存計數與結果，不保存 token、owner identifiers 或金額。此為 observed UI/read isolation，尚未完成已知 A identifier 的 B negative probe、MCP authorized tool 或 candidate-vs-current PnL parity。
3. 既有 Private MCP connector 回 Authentication required；Read-only v2 annual-pnl bounded selector 回 unavailable。兩者都不能當成 candidate MCP live acceptance。
4. Jobs 發布鎖內 writer／Scheduler／execution fence、完整 snapshot／rollback／canary／GHCR rollout，以及 API 100% promotion／rollback 和 release baseline 尚未驗收。

原 B3 stash、`.cicd-v2-work/` 與 `token-savior/` 均保留，沒有套回或納入本輪改動。

## 現役版 A 登入與 parity 補充

- 使用者回報現役網址 Google OAuth `origin_mismatch`，依頁面實際 Client ID 提供精確 Authorized JavaScript origin 後，使用者確認登入正常；外部 Chrome 已觀察登入後頁面。未由 agent 修改 OAuth 設定。
- 同 A 現役 API 的 journal history、pnl、recalculation-status、portfolio quotes、summary、journal positions 均 HTTP 200。與先前候選回應遞迴排序 object keys 後比對：89 筆交易歷史、年度 PnL 與重算狀態完全一致；現役持股 4 筆。
- Quotes 的 positions／items 與其他共有資料欄位一致；完整回應差異僅 checked_at 與候選額外 ledger_version／snapshot_kind，不能宣稱整份 quotes response 完全相等。此次完成 User API 年度 PnL parity，MCP authorized acceptance 與已知 A identifier 的 B negative probe 仍未完成。

## Codex MCP 登入阻塞與本機修正

- 使用者提供錯誤 `OAuth client or redirect URI is not allowed`，client 為 `https://chatgpt.com/oauth/codex/client.json`，redirect 為本機 IPv4 loopback `/callback`。既有 client check 接受該 client，redirect check 只支援 ChatGPT HTTPS callbacks，拒絕了 Codex 本機回呼；這是 Janus 授權入口拒絕，發生於 Google login 之前。
- 本機修正限定上述精確 Codex client，允許 `http://127.0.0.1:<合法明確 port>/callback`；token exchange 同步檢查、原始 callback／client／resource／S256 綁定保留。Consent CSP 僅加入該次精確 loopback origin。沒有將 loopback 加入 Google callback，也沒有改既有 scope／owner allowlist。
- OAuth targeted tests 11 PASS（含兩個不同 port 的授權／交換、其他 client 與非精確 URL 拒絕、錯誤 port／PKCE 拒絕）。擴大含 User API 的測試在 OAuth 11 項後停滯且無新輸出，已中止，不能認作 PASS。
- 重跑 OAuth 與本輪發布防護直接相關範圍合計 63 tests PASS。重新執行 `/ponytail-review`，檢查所有 redirect helper callers、授權／Google callback／consent／token exchange、原始 code binding、workflow guard 與文件差異，未發現須修正項；此為本機 review，不代替完整 release CI 或 live OAuth 驗收。
- 仍是未發布的 working tree；此 callback allowlist 擴充須依 PROJECT_RULES §1.3 明確核准，commit／push 亦仍待先前自動審核要求的明確確認。未宣稱 live MCP 登入恢復。

## 授權後發布進度（優先於上述本機快照）

- 使用者已明確授權 commit／push、既有 dev 發布與 Codex callback allowlist 修正，並要求修正兩個既有 MCP tag 的 revision。OAuth／writer 修正已 commit／push `92349c509181590b8977b0ade355d7497bb62a8b`。
- [完整 GHCR Release #37872497498](https://github.com/tommylin15/janus-omniforge/actions/runs/37872497498) SUCCESS：Python 759 passed、2 deselected（workflow 明列已移除 legacy modules），Flutter gate SUCCESS、四個映像 publish SUCCESS、匿名 pull／digest gate SUCCESS。尚未因此宣稱 MCP live 登入成功。
- 新增人工執行的 bounded MCP tag repair workflow／helper：僅既有兩個 tag、0% candidate、canonical 100% 不變；shared concurrency／lease、鎖內 Trigger／Build fence、pre-login gate、fail-closed rollback/readback，routing snapshot artifact 留 1 日供操作失敗 recovery，不新增舊路由入口。
- Route＋lease 23 tests PASS；首次 pytest tmp_path 遇 sandbox temp 權限錯誤，改 fresh workspace `.tmp` test directory 重跑通過。workflow YAML parse、Git Bash `bash -n` PASS。`/ponytail-review` 核對 helper calls、gate、switch／recovery、測試與文件，未发现須修正項。仍待 candidate deploy／MCP route repair 的真實 Actions evidence。
