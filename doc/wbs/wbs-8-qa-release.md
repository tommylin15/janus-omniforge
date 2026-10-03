# Janus WBS 8 — PIT、QA 與發布

更新：2026-10-03
狀態：責任／驗收契約；active 執行順序只看 `../todo.md`

## 8.0 環境與完成判定

- GCP `dev` 是目前個人真實 parallel-live environment；能力通過自身 real-path acceptance 後可直接使用，不需要等待 staging／production 或六個月 observation window。
- Production 只代表未來多人／對外／HA／SLA／正式營運隔離，不是目前 dev 功能的資格 gate。
- 完成依 GitHub implementation、tests／CI、deployment、live data、trigger／workload、auth／owner、API／MCP、Flutter／Admin、integration evidence 綜合判定。
- mock／fixture／sample 只作快速回歸／故障注入，不能代替 live acceptance。
- canonical data、PIT／future leakage、provenance、source authorization、publication、owner/auth、public/private isolation、LLM/CEO 不得修改 canonical numbers 等治理要求維持。

## 8.1 Outcome／PIT evaluation

對需要 predictive／ranking evidence 的 analysis／specialist，至少保存可追溯 identity：

- symbol／scope；
- `analysis_as_of`；
- Core／Mart snapshot；
- feature／engine／model／evaluation revision；
- code／image revision；
- execution identity；
- 5／20／60 trading-day outcome；
- relative benchmark；
- MFE／MAE；
- valid／excluded status、exclusion reason、provenance。

membership／source authorization 以 effective time 進 PIT；不得用今天的 watchlist／coverage 回填歷史樣本。

walk-forward tuning、threshold／weight optimization、champion promotion 只能用 PIT OOS evidence；不得用 upstream benchmark、training success 或 future data 替代。

## 8.2 Token-first specialist evaluation

五 specialist 的 QA／evaluation 依 current engine contract，而不是舊每日五 LLM role contract。

至少驗證：

- 500 screening 不產生 LLM calls；
- Deep Coverage admission／exit／held-off-market／overlap；
- deterministic replay；
- input hash／engine／model version lineage；
- dirty dependency 只更新受影響 specialist；
- no-change reuse 可稽核；
- monthly retrain／calibration／reconciliation 可重跑；
- OOS promotion evidence；
- one-specialist failure／missing 不冒充 full success；
- public/private isolation、PIT、provenance、missing-data negative cases。

## 8.3 On-demand CEO evaluation

On-demand CEO capability 完成後，QA 至少驗證：

- backend capability／auth；
- manual-only trigger；
- in-flight duplicate guard；
- provider／model／profile approval；
- route snapshot/version/hash；
- auth lifecycle／cold start；
- timeout／cancel／bounded retry；
- fallback class；
- usage／cost／quota/cooldown；
- secret redaction；
- validated specialist inputs only；
- immutable report history；
- validator failure = partial／blocked，不是 success；
- upstream specialist update 只標記 freshness/material delta，不自動觸發 CEO。

`Codex CLI → OpenRouter → Gemini` 只在 CEO／approved escalation evaluation 出現，不作五 specialist daily route 驗收。

## 8.4 自動化 QA

依受影響範圍執行：

- Python／pytest；
- FastAPI contract／auth tests；
- schema／migration／Iceberg evolution；
- retry／idempotency／rollback；
- Flutter analyze／widget／golden／screenshot；
- browser／integration；
- build／deployment smoke。

跨模組契約、安全／權限、migration、release boundary 變更時再擴大完整驗證；小改不機械式重跑所有 suite。

## 8.5 UI／A11y／browser acceptance

- User／Admin 依各自 active UI contract 驗收。
- 目前個人 live scope 以實際使用 device／browser 主流程取得 real-path evidence；完整跨裝置/A11y matrix 依 active WBS 分階段完成。
- loading／empty／error／partial／stale／missing／blocked 不使用 sample／placeholder 補成成功。
- User Final Visual Convergence 另依 `../ui/reference/user-app-final/README.md`；PNG、golden 或 build 單獨不能構成完成。
- Admin operational convergence 需 authenticated Flutter/PWA browser + 真實 batch／retention／storage telemetry；legacy static Admin 不再是 acceptance target。

## 8.6 Data quality／retention QA

資料安全最低驗證：

- required keys／types；
- duplicate；
- future leakage；
- freshness；
- source authorization；
- schema drift；
- quarantine／retry；
- obvious outlier／corporate-action sanity（適用時）。

公開資料清理由 `../spec/retention-governance.md` 定義。驗收至少涵蓋 Stage/Core/Mart retention、reference protection、fresh Core fence、orphan cleanup、安全 generation/delete condition、maintenance report/readback 與 failure semantics。

Private retention 若未有獨立核准 contract，不得用 Public cleanup test 推導其 retention 已定義。

## 8.7 Admin QA

Admin 至少驗證：

- `/api/v1/admin/*` backend auth／audience negative cases；
- actionable overview drill-down；
- effective batch/occurrence，不由 Flutter hard-code scheduler truth；
- execution detail／retryability／lineage；
- manual action allowlist／idempotency／dependency／exclusive guard／audit；
- `資料治理` 的 retention／DQ／live bytes／maintenance／protected refs／unknown semantics；
- AI Analysis Profile 的 specialist model/evaluation 與 CEO provider/profile/capability 分離；
- 一般 Admin 不取得 user trade／position 正文。

## 8.8 ChatGPT MCP acceptance

MCP live acceptance 只約束 MCP capability，不阻擋無關 Janus 功能。

至少驗證：

- OAuth login／reconnect／expiry／refresh；
- unauthenticated deny；
- server-side owner binding；
- owner isolation（無第二 owner 可測時明確 blocked）；
- `janus_sources`、`janus_market_context`、`janus_private_context` discovery／call；
- allowlisted selectors；
- arbitrary SQL／URI／owner injection／mutation rejection；
- source／as-of／provenance；
- secret／storage locator absence；
- record／byte／date bounds；
- no unnecessary conversation/context persistence；
- Cloud Run scale-to-zero／bounded cost evidence。

外部 ChatGPT plan／UI capability 若阻擋 integration，只將 MCP 標 blocked，不擴大成整體 Janus blocker。

## 8.9 Evidence window

已通過 real-path acceptance 的 capability 在 dev 持續真實使用並累積 evidence。建議 bounded periodic summary，但 summary 不是使用批准證。

Evidence 分類：

- Data：coverage／freshness／failure／quarantine／source stability；
- Specialist：PIT/OOS、model/evaluation、reuse、outcome；
- CEO：manual availability、provider/fallback、latency、usage/cost、usefulness（完成後）；
- Operations：controller/jobs/API、maintenance、storage growth、manual intervention；
- Cost：Cloud Billing、provider/resource growth；
- Security/Privacy：auth、owner isolation、secret、delete/cleanup。

material change 必須能追溯 baseline／revision；不要求每個 commit 都形成正式 release。

## 8.10 Future Production review

只有實際需要多人／對外／HA／SLA 時才評估獨立 Production topology。Evidence review 可產生：

- `KEEP_DEV_PARALLEL_LIVE`
- `GO_PRODUCTION_PLANNING`
- `EXTEND_EVIDENCE_WINDOW`
- `NO_GO`

任何結果都不自動建立 production／paid resource。Production IAM、HA、backup、RTO/RPO、staging／promotion 需另案設計與人工核准。

## 8.11 ResearchContext／Supply-chain（Planned）

只有 active TODO 啟動後才執行。

ResearchContext acceptance 至少驗證 same-`analysis_as_of`、PIT、provenance、deterministic replay、stale/missing/partial、owner isolation、bounded output、secret/storage-locator absence 與 no LLM-generated canonical numeric result。

Supply-chain signal 共用既有 PIT／evaluation infrastructure；relationship 必須區分 confirmed／inferred／hypothesis，保存 effective time／revision／provenance。未經 source authorization／成本核准不得啟動 paid source、crawler 或新 runtime。