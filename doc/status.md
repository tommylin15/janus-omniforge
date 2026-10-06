# Janus Current Status

更新：2026-10-06

用途：只回答「現在在哪裡、下一步是什麼、哪些尚未完成」。實作以 GitHub `main` 為準，完成狀態以 tests／CI、deployment、live runtime、trigger／workload、integration evidence 為準。完整 active queue 只看 [`todo.md`](todo.md)。

## 2026-10-06 A 組：非佇列工作完成，交易驗收交由使用者

A 組非佇列範圍已完成實作、測試、GitHub 同步、既有 dev 部署與真實 authenticated 四頁／Admin 六頁讀回。最終 runtime `7a5a1f9`、Deploy `37426621108` success、Ready／100% traffic／build-id 一致；治理頁已取得公開清理 receipts。完整 [結案證據](archive/group-a-nonqueue-live-closure-2026-10-06.md)。

手機入口／效能依使用者明確指示結案，未提供 p95／樣本／裝置資訊不補造。使用者仍在調整交易佇列，要求本對話先不驗、由本人另行驗收；mutation／duplicate／刷新 gate 保留於 TODO，不宣稱該筆交易成功。A 整體尚有此人工驗收交接，B／C 未啟動。

## 2026-10-06 B 組優先架構決策（尚未實作完成）

使用者已核准 [Iceberg canonical + BigQuery analytics hybrid](decision-2026-10-06-bigquery-analytics-over-iceberg.md) 作為 B 組 specialist／cache 的優先資料運算架構：

- Core Iceberg V2／GCS 繼續是 canonical／PIT／provenance/history；不改成 BigQuery native canonical warehouse。
- PostgreSQL serving projection 與 User／Admin request-time read 保持現行架構。
- BigQuery 只作 analytics compute，優先承接 liquid-500 screening、cross-sectional feature／ranking、OOS/evaluation preprocessing 與 ML training dataset preparation。
- 禁止 BigQuery Storage Read API；大量 training input 採 SQL 縮減後 export versioned GCS Parquet。
- B 組第一優先是抽出 exact-snapshot analytics reader、保留 PyIceberg reference/fallback，再做 BigQuery fidelity/cost/performance canary；未證明固定 Core snapshot 一致前不得切 default。
- **目前只有架構與執行順序核准，沒有 evidence 顯示 BigQuery／BigLake resource 已建立或 API/IAM 已核准。** 需要新增付費 API/resource、catalog/dataset/connection 或 IAM 時仍依 PROJECT_RULES 取得明確授權。

B 組架構決策不代表 specialist 已完成；A 組目前僅保留上述使用者交易驗收交接。

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

- A 組僅保留由使用者另行驗收的交易佇列／真實 mutation／duplicate／交易後刷新；非佇列四頁、Ledger read consistency、YTD 與 Admin live 驗證已完成。
- 五 specialist 的完整真實 dev／OOS、完整 ML baseline、dirty dependency、monthly retrain／reconciliation 尚未完成整體驗收。
- On-demand CEO command／capability／immutable report history 尚未完成。
- Admin specialist model/evaluation + CEO capability/profile controls 尚未完成。
- User Stock Detail manual Analyze/Re-analyze + freshness/history 尚未完成。

因此不得宣稱交易 gate 已通過、A 組所有 acceptance 全部完成、Token-first 五 specialist production 已完整完成或 manual CEO 已可用；Admin operational convergence 與 A 組非佇列範圍已完成。

> **A 組不是「部署完成後做驗收」，而是「在真實 GCP dev 驗收中持續發現並關閉 implementation gap」；Today、Watchlist、Ledger、Stock Detail 的非 AI 主體 UI 必須在真實登入與真實資料下明顯收斂至 Final Visual Contract，且 Holdings／Records／Reports 必須共用一致、可追溯且可刷新之 canonical position state，否則 A 組維持 partial。**

## Evidence 讀取順序

1. GitHub `main` code／schema／migration／workflow／tests。
2. 最新 CI／deployment／live runtime／trigger／workload／integration evidence。
3. [`todo.md`](todo.md) 看 active acceptance。
4. Active SPEC／WBS／UI contract。
5. [`spec/operations-and-testing.md`](spec/operations-and-testing.md) 與 `archive/` 查歷史 evidence。

文件修改、commit、build、upstream benchmark 或單次 bounded success 都不代表功能完成。
