# Janus SPEC — 產品目標與架構決策

更新：2026-10-03

本文件只保存目前有效的產品與架構決策。被取代的規劃與 checkpoint 應放 `archive/`，不得在本文件保留第二套 active 說法。現在實作／完成狀態仍以 GitHub `main`、tests／CI、deployment、live runtime、trigger／workload 與 integration evidence 為準。

## 1. 產品定位

Janus／OmniForge 是以台股為主的個人投資研究與資料系統，涵蓋市場資料、湖倉、研究 Mart、個人交易記帳、持股／損益、關注股、研究成果與治理。它不是自動下單系統、券商帳戶同步產品、持牌投顧或保證獲利服務。

通用對話／Agent runtime 由 omniAgent 負責；Janus 提供投資 domain API、User／Admin UI 與 authenticated read-only MCP context。Janus 不恢復 generic Chat／Agent UI、thread lifecycle、Skills／approval runtime 或通用 provider dispatch。

## 2. Dev 與完成判定

- GCP `dev` 是目前個人使用階段的真實 parallel-live environment，可使用已核准的真實資料、OAuth、MCP、Cloud Run、PostgreSQL、Iceberg 與實際 workflow。
- `prod` 是未來多人／對外／HA／SLA 等營運強化，不是目前 dev 功能可使用的前置條件。
- mock／fixture／localhost 只補故障注入與快速回歸，不得取代主要 real-path acceptance。
- 程式、文件、build 或單次 partial success 都不能單獨宣稱完成；完成需依 implementation、tests／CI、deployment、migration、live runtime、trigger／workload、integration／data 與 acceptance evidence 綜合判定。

Dev Pilot／長期 evidence window 若仍在執行，只負責累積可靠性、成本與使用證據；它不覆蓋 active TODO，也不把與 Pilot 無關的已驗收 dev capability 強制降格為 POC。

## 3. User／Admin frontend

User 與 Admin 共用 `apps/user_app` Flutter／PWA codebase，但維持不同 navigation、workspace state、token audience、CORS、backend authorization 與 audit boundary。

2026-10-02 已退役 legacy static HTML／JS Admin；它不再是 fallback、parity gate 或 active runtime。歷史座標只保留於 archive。

Admin 目前產品範圍依 `../ui/admin.md`：

- `總覽`
- `批次`
- `個股`
- `市場資訊`
- `AI 分析`
- `資料治理`

其中 `資料治理` 是原 `進階管理` placeholder 的正式目標名稱；這是既有 Admin 的精簡收斂，不是另建 metadata／orchestration 平台。`個股`、`市場資訊`、`AI 分析` 保留。

User／Admin 只經 FastAPI 契約讀寫已持久化資料；一般 page load 不直接讀 Stage，不觸發 scraper，也不因畫面載入自動觸發 CEO LLM。

## 4. 資料與湖倉

- 公開資料採 Source → Stage → Core → Mart → API／UI。
- PostgreSQL 保存 Iceberg catalog、control、execution、publication、audit、服務索引與私人 append-only ledger；raw market payload 與完整 Mart payload 不放 PostgreSQL。
- GCS + Iceberg／Parquet 是公開與 Private Core／Mart 的主要持久層；DuckDB／PyIceberg 是 bounded runtime，不作獨立持久資料庫。
- Public／Private namespace、IAM、bucket prefix、table、service index、retention 必須隔離；Flutter filter 不是 security boundary。
- canonical number、fixed decimal、PIT／future leakage、provenance、source authorization、missing／stale／partial honesty 與 immutable lineage 必須維持。

公開 retention 依 `retention-governance.md`，目前至少包括 Stage 7 天、一般 Core 365 天、Deep Coverage 價量／benchmark 1096 天、財報 12 季、Mart 分析列 90 天及有引用保護的 snapshot／manifest 規則。Private retention 未有另外核准契約時不得套用 Public 規則推測。

## 5. 市場覆蓋與 Deep Coverage

目前 research market coverage 以約 500 檔低成本 market screening／discovery 為主；不再以約 1,700–2,000 檔全市場深度分析作 active product contract。

完整五 specialist 只對 `active watchlist ∪ effective holdings` 執行。Watchlist 的 50 active distinct-symbol quota 保留作成本／來源護欄；持股離開 500 仍留在 Deep Coverage，清倉且不在 watchlist 才退出後續深度更新。

高頻／tick／文本／alternative data 不因資料存在就自動擴張覆蓋；source authorization、license、quota／cost、retention、PII／redistribution 與 citation policy 需先通過。

## 6. Token-first 五 specialist

2026-10-03 起，五 specialist production 主路徑為 Python／SQL／ML，不再是每日五個生成式 LLM workers：

1. Fundamental — deterministic financial features + LightGBM baseline。
2. Valuation — deterministic valuation + LightGBM／CatBoost benchmark。
3. Quant — LightGBM baseline + Qlib DoubleEnsemble challenger。
4. Risk／Regime — Riskfolio-Lib + statsmodels／ML。
5. Event／Catalyst — parser／rules + local multilingual classifier。

約 500 檔只做便宜 screening／必要 cross-sectional inference；完整五 specialist 只做 Deep Coverage。Specialist 依 input change／dirty dependency 更新，沒有 input change 就 reuse；第一版 ML retrain／calibration／reconciliation 以月度為主。

Specialist plain-language output 以 structured output + SHAP／feature contribution／rules／templates 產生，正常 path 0 API token。LLM 不擁有 canonical number、score 計算或 publication authority。

詳細契約見 `specialist-engines.md` 與 `../wbs/wbs-5-specialist-engines.md`。

## 7. On-demand CEO

Codex CLI／OpenRouter／Gemini 既有 provider adapter、routing、auth、free／billing gate 成果保留，但有效產品用途只屬 authorized manual On-demand CEO／rare escalation，不再代表五 specialist 的日常 route。

CEO：

- 只讀最新 validated specialist outputs、Fact Pack 與 provenance；
- 只由具有 backend capability（例如 `ceo_analysis.request`）的使用者明確觸發；
- 不由 Scheduler、EOD price、event 或 specialist dirty update 自動觸發；
- 每次分析／重新分析建立新的 immutable execution／report，不覆寫舊報告；
- 不計算或覆寫 canonical numbers，也沒有 publication authority。

User Stock Detail 預設讀 persisted report；有權限帳號才顯示「分析／重新分析」。Admin 管 specialist model／evaluation 與 CEO provider／model／profile、capability、quota／cooldown、usage／cost／audit。

## 8. FastAPI／Auth／MCP

FastAPI 分離 `/api/v1/public/*`、`/api/v1/me/*`、`/api/v1/admin/*` 的 response model、auth、rate limit、CORS 與 audit。User 身分以驗證後的 issuer／subject 綁定內部 UUID；email 只供顯示，不作 owner key；User token 不得存取 Admin endpoint。

Janus ChatGPT MCP 是 authenticated read-only external consumer，沿用 existing `janus-api` 與 bounded query boundary；不接受 SQL、table、GCS URI、object path、client-selected owner 或 mutation。第一版工具為 `janus_sources`、`janus_market_context`、`janus_private_context`；私人內容仍依 owner scope 與 opt-in／disclosure contract。

## 9. Batch／operations

目前 dev batch controller 以 GitHub `main` 為真相，固定管理：

- `ingestion`
- `data-supplement`
- `mart`
- `data-quality`
- `private`
- `core-cleanup`
- `mart-cleanup`

未來 500 screening、dirty specialist update、monthly retrain／reconciliation、On-demand CEO execution 只有在 implementation／runtime 真正存在後才進 Admin Job Control Center，不由文件或 placeholder 提前宣稱。

Manual rerun／retry 必須經 backend allowlist、idempotency／duplicate guard、dependency／exclusive guard 與 audit；UI 不直接操作任意 Cloud Run job name、checkpoint 或 storage object。

## 10. Supply-chain Intelligence

Supply-chain Intelligence 仍是研究方向，但目前不是自動展開的 production ingestion。可保留 ontology、source matrix、leading indicator、company exposure、expectation signal／gap 與 evaluation 的研究／規格；任何新 crawler、paid source、Graph DB、BigQuery、新 Cloud Run service 或其他付費資源仍需依 active TODO／人工授權另案啟動。

研究鏈維持：`External／Official Data → Stage → Core → relationship／indicator model → Mart → Janus／ChatGPT analysis`，所有 inferred／hypothesis relationship 必須與 confirmed evidence 分開。

## 11. 非目標與安全底線

- 不新增第二套 scheduler／control plane／canonical metadata store 只為改善 UI。
- 不讓 LLM 計算、補值、覆寫 canonical numbers 或決定 publication。
- 不把 research／temporary data 升格成 canonical。
- 不在 log、前端、Git 或公開輸出暴露 secret、token、password、private key、raw private payload 或 storage credential。
- 新付費 API／model／subscription、付費 GCP 資源、重大權限擴張、不可逆大量真實資料刪除及 MFA／OAuth consent／付款仍需使用者明確授權。