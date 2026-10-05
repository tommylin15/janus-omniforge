# Janus Current Status

更新：2026-10-05

用途：只回答「現在在哪裡、下一步是什麼、哪些尚未完成」。實作以 GitHub `main` 為準，完成狀態以 tests／CI、deployment、live runtime、trigger／workload、integration evidence 為準。完整 active queue 只看 [`todo.md`](todo.md)。

## 2026-10-05 Cloud 交接狀態

使用者最新指示：先 commit／push 與部署目前版本，剩餘 live／視覺／效能驗收暫停，改由 Codex Cloud 接續。A 組仍為 partial；不得依部署成功勾選整組 acceptance。四張使用者提供的原始 PNG 已恢復並通過 CRC／解壓驗證，視覺來源 blocker 已解除。

目前變更涵蓋個股分區載入／重試、延後 K 線、主頁狀態保留、隱藏持股頁停止輪詢、離榜關注保留與中文搜尋／行情投影、Admin 排程批次／資料治理，以及 migration 043 的既有角色唯讀權限。Broker Profile、完整 Quote Router／last-quote persistence、其餘版型／資料治理欄位、效能 profiling 與 A 組 live acceptance 尚未完成；B／C 尚未由此次變更完成。

部署前本機證據：Flutter 全部 47 tests passed；`flutter analyze --no-fatal-infos lib test` exit 0（35 info）；Python 87 targeted tests passed，另 public-runtime 等前一輪 63 passed；workflow YAML 與 `git diff --check` 通過。這些不是 GCP live acceptance。

Cloud 接續入口：先讀本文件、PROJECT_RULES、README、TODO 的 A 組與 codex-execution-plan。使用者最新澄清：Cloud 任務以**既有 GCP dev 真實測試驗證**為主，並非啟動全部剩餘實作。核對部署／043 migration 與 runtime revision，再做真實 API／auth／owner、authenticated browser、四頁截圖與效能、既有維護 receipt／Job 證據驗收。未實作項目如實記錄；只有驗收發現缺陷才做最小修正及必要重新部署。缺 credentials／登入／瀏覽器能力時列 blocker，mock 不得冒充 live evidence。本地驗收維持暫停，不重做 042 或已成功的 043，不自動擴展至 B／C。

部署與 immutable digest 證據見 [A 組部署 checkpoint](archive/group-a-deployment-checkpoint-2026-10-05.md)：Ingestion／043、Private Pipeline 與 API／Flutter PWA 已成功部署；剩餘 GCP dev 驗收暫停交接。

## 現行產品決策

Janus 採 **Token-first 五 specialist + On-demand CEO**：

- 五 specialist production 主路徑使用 Python／SQL／ML，不是每日五個生成式 LLM workers。
- 約 500 檔只做低成本 market screening／discovery；完整五 specialist 只做 `active watchlist ∪ effective holdings`。
- specialist 依 input change／dirty dependency incremental update；無變化 reuse。
- retrain／calibration／reconciliation 第一版月度。
- specialist 白話文由 structured output + SHAP／rules／templates 產生，正常 0 API token。
- Codex CLI／OpenRouter／Gemini 只保留給 authorized manual On-demand CEO／approved rare escalation。
- CEO report 是 immutable symbol-level research artifact；重新分析建立新 execution/report，不覆寫舊報告。
- Admin 管 DB-backed capability（例如 `ceo_analysis.request`）、specialist model/evaluation、CEO provider/profile、quota/cooldown、usage/cost/audit。

權威文件：

- [`decision-2026-10-03-token-first-specialist-and-on-demand-ceo.md`](decision-2026-10-03-token-first-specialist-and-on-demand-ceo.md)
- [`spec/specialist-engines.md`](spec/specialist-engines.md)
- [`wbs/wbs-5-specialist-engines.md`](wbs/wbs-5-specialist-engines.md)

被取代的每日五 LLM／CIO 規劃只留在 `archive/`／Git history，不再是 active completion gate。

## Admin 現行範圍

唯一 active Admin frontend 是 Flutter／PWA。主導覽目標：

- 總覽
- 批次
- 個股
- 市場資訊
- AI 分析
- 資料治理

Admin operational convergence 不重做整個 shell；`資料治理` 是正式目標名稱。詳細 contract：

- [`decision-2026-10-03-admin-ui-scope-and-governance.md`](decision-2026-10-03-admin-ui-scope-and-governance.md)
- [`ui/admin.md`](ui/admin.md)

## 已存在、可重用的能力

- GCP `dev` 是個人真實 parallel-live environment。
- WBS-3 full-market base coverage／data supplement 已有 500 market coverage、12Q／12M、fixed Core snapshots、Fact Packs、daily incremental、Saturday quality evidence。
- PostgreSQL serving projection migration `042_stock_serving_projection` 已在 dev 完成；`ohlcv`／`valuation`／`events` 共 `78,079 / 78,079` eligible rows 已 materialize，public API 以 `publication.stock_serving_recent` 為 stock-detail hot path、Iceberg 為 fallback，且 live Cloud Logging 已驗證 `source=serving_projection`。完成證據見 [`archive/stock-serving-projection-042-completed-2026-10-04.md`](archive/stock-serving-projection-042-completed-2026-10-04.md)。
- 既有 provider adapters／routing／auth／free-billing gate／validator 的 bounded dev evidence 可重用於 CEO provider path，但**不代表** specialist-engine 或 On-demand CEO 已完成。
- User API 已有 Google OIDC owner boundary；Admin 有獨立 Google admin allowlist。
- Stock Detail 已有 persisted report、positions、notes、Kline/events、analysis feedback 等 read-path basis，可供後續 specialist／CEO integration。
- Flutter Admin shell、Overview／Batch、Stock Workbench 的既有 acceptance 保留；新的 operational convergence 仍在 TODO。
- legacy static Admin 已退役，不再是 parity／release gate。

## Active 執行順序

唯一權威排序見 [`todo.md`](todo.md)：

1. **A：操作體驗／效能／資料營運** — User 非 CEO 功能、Admin operational convergence、四頁非 AI 相依版型、效能／FinOps 與文件對齊。
2. **B：specialist／增量快取** — 合併 `WBS-5-MART-SPECIALIST-ENGINES` 與 `WBS-5-MART-RERUN-CACHE`。
3. **C：CEO／權限／最終整合** — 合併 provider、CEO synthesis（原 CIO tracking ID）、Admin profile、User AI integration 與 Final Visual 剩餘 acceptance。

執行指令見 [`codex-execution-plan.md`](codex-execution-plan.md)。同組先整合程式再集中驗收，原 WBS acceptance 不取消。預警與通知由 Parking Lot 管理，另存 [`future-market-alerts.md`](future-market-alerts.md)，目前不執行。

042 serving projection 重用已有完成證據；公開資料清理依 operations 已有 apply/readback 只補剩餘項，041／compaction／retrain 核對最新證據。此次只是待辦整合，不宣稱任何未完成 capability 已完成。

## 模型／framework 方向

- Fundamental：deterministic financial features + LightGBM。
- Valuation：deterministic valuation + LightGBM／CatBoost benchmark。
- Quant：LightGBM baseline + Microsoft Qlib DoubleEnsemble challenger。
- Risk／Regime：Riskfolio-Lib + statsmodels／ML。
- Event／Catalyst：parser／rules + Hugging Face Transformers multilingual local classifier。
- Explanation：SHAP／feature contribution + deterministic templates。

AutoGluon、FinBERT、FinGPT 只作 benchmark／research challenger；production champion 必須由 Janus Taiwan PIT walk-forward OOS evidence 決定。

## 尚未完成的關鍵 acceptance

- 五 specialist 的完整真實 dev／OOS、完整 ML baseline、dirty dependency、monthly retrain／reconciliation 尚未完成整體驗收。
- On-demand CEO command／capability／immutable report history 尚未完成。
- Admin specialist model/evaluation + CEO capability/profile controls 尚未完成。
- User Stock Detail manual Analyze/Re-analyze + freshness/history 尚未完成。
- Admin `資料治理`、batch operational convergence 尚未完成 live authenticated browser acceptance。

因此目前不得宣稱「Token-first 五 specialist production 已完整完成」、「manual CEO 已可用」或「新版 Admin operational convergence 已完成」。

## Evidence 讀取順序

1. GitHub `main` code／schema／migration／workflow／tests。
2. 最新 CI／deployment／live runtime／trigger／workload／integration evidence。
3. [`todo.md`](todo.md) 看 active acceptance。
4. Active SPEC／WBS／UI contract。
5. [`spec/operations-and-testing.md`](spec/operations-and-testing.md) 與 `archive/` 查歷史 evidence。

文件修改、commit、build、upstream benchmark 或單次 bounded success 都不代表功能完成。
