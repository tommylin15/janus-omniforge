# Janus WBS 8 — PIT、QA 與發布

## WBS 8 — PIT、QA 與發布

### 8.0 目前環境與完成判定

- 目前 GCP `dev` 是 Janus 個人使用階段的真實平行上線環境；已通過對應 real-path acceptance 的能力可以直接在此真實使用，不需要先建立 staging／production，也不需要等六個月 Pilot 結束。
- `Production` 只代表未來若需要多人／對外、HA／SLA、正式營運隔離、較高可靠性或更大成本與權限時，另行評估的營運層級；它不是今天 Janus 能否真的跑、能否接真資料／真服務或能否供使用者使用的資格證。
- 完成狀態仍依 GitHub implementation、tests、CI／build、deployment、live data、trigger、workload、OAuth／owner、API／MCP／provider、Flutter／Admin 與 integration evidence 判定。文件已寫、local test 綠燈、fixture success 或 partial runtime success 不得包裝為 full live success。
- mock／fixture／sample 僅能做快速回歸、deterministic contract 或真實服務不適合故意製造的 fault injection；標示為 live／GCP dev／user-facing acceptance 的驗收必須以真實 runtime 與真實 backend 狀態為主。
- canonical data、PIT／future leakage、provenance、source authorization、publication gate、owner／auth boundary、LLM 不得修改 canonical numbers 等資料可信度與治理要求完全保留，不因 dev 是真實使用環境而放寬。

### 8.1 `WBS-8-PILOT-OUTCOME-COLLECTION` — Pilot Day-1 outcome collection

- 每個適用 analysis 至少可追溯 analysis identity、`analysis_as_of`、symbol／scope、
  relevant Core／Mart snapshot、governance revision、prompt／analysis revision、
  code／image revision，以及適用時的 provider／model。
- 從 Pilot Day 1 開始收集 5／20／60 trading-day outcome、relative benchmark、MFE、
  MAE、valid／excluded status、exclusion reason 與 provenance；優先重用既有 PIT／
  evaluation artifact model。
- 不合格樣本排除原因與 provenance ID。
- membership 與來源授權均以 effective time 納入 PIT；不得用今日關注股深度追蹤名單回填歷史樣本。

### 8.1.1 Calibration／optimization（後置）

- walk-forward tuning、role weight optimization、40／60 threshold revision 與 governance tuning 留在後續；它們不是目前 parallel-live dev 真實使用既有能力的共同前置 blocker。

### 8.2 自動化 QA

- pytest、FastAPI contract tests、Flutter analyze／widget tests、Vitest、Playwright、TypeScript、build。
- schema／migration／Iceberg evolution 測試。
- failure、retry、idempotency、rollback 測試。

### 8.3 實機與 A11y

- Flutter Android／iOS／Web、iOS Safari、Android Chrome、iPad Safari。
- VoiceOver、TalkBack、keyboard、touch、safe area。
- WCAG AA 實際對比。
- 目前個人 live scope 先以實際使用中的 device／browser 主流程取得 real-path evidence；完整 cross-device／A11y matrix 可分階段補齊，不得用 mock UI 或 sample data 取代已宣稱完成的實際裝置流程。

### 8.4 UI 驗收後的資料品質強化

- 本節的順序是 quality-improvement 工作排序，不是整個 Janus 能否真實使用的環境閘門。Admin 資料營運流程、Flutter 關注／記帳／筆記／AI／健康檢查與實機 A11y 的相關能力應各自依 live acceptance 判定。
- 完成跨源一致性、null profile、freshness、coverage、schema drift、outlier／corporate-action 校準與 quality-score 版本化。
- 校準 market regime、sector rotation、topic uncertainty、candidate health 與 private PnL 的品質折減，不得改寫歷史 Mart。
- Admin DQ dashboard 顯示結構化摘要、quarantine drill-down、門檻 revision 與 evidence；不提供 raw payload 旁路。
- 以已驗收 UI 的真實閱讀問題調整 DQ 門檻；完整 production-grade data-quality claim 仍需對應 evidence，但未完成高階 DQ tuning 不得被解讀為已通過 real-path acceptance 的既有個人功能只能 POC／模擬使用。

### 8.5 Release／Parallel-Live Dev Evidence

#### 8.5.1 Parallel-Live Dev Capability Acceptance

- 目前沒有「Pilot Entry 前不得真實使用」的全域資格閘門。每個能力只要其必要的安全、資料、runtime 與 integration gate 通過，就可以在既有 GCP dev 真實使用並持續累積 evidence。
- WBS-3 canary／full-market safety、ledger durability、outcome collection、usefulness feedback、release baseline 與 security／privacy／cost evidence，依各自影響範圍判定能力是否 accepted；未完成項目維持 blocked／partial，不得把不相關能力一併降格成 POC。
- Supply-chain Intelligence 的 `WBS-5-SUPPLY-FOUNDATION`、`WBS-5-SUPPLY-SOURCE-MATRIX`、
  `WBS-5-SUPPLY-SEED-GRAPH`、`WBS-5-SUPPLY-SIGNAL-MART` planning evidence 與本節的
  `WBS-8-SUPPLY-PILOT-EVALUATION` contract 是 Supply-chain 後續 implementation 的 planning／trust prerequisite；不是整個 Janus dev 能否真實使用的 prerequisite，也不代表六個 domain 必須全部 ingestion-ready。
- data-safety DQ 的 required key／type、duplicate、future leakage、freshness、basic coverage、schema drift，以及適用時的 obvious outlier／corporate-action sanity，仍是相關 canonical ingestion／analysis path 的必要安全條件；完整 DQ dashboard、quality-score tuning 與大型 drill-down 可後續強化。
- ChatGPT MCP acceptance 決定的是 ChatGPT MCP capability 能否宣稱 live accepted。若被外部 ChatGPT plan／UI capability 阻擋，MCP 標記 blocked；它不阻擋與 MCP 無關的 Janus 個人使用流程。
- 相關 WBS 可以平行準備；不存在為了取得「Pilot Entry 資格」而強制序列化所有真實服務的規則。
- `pilot_started_at` 若保留，表示六個月 evidence window 的基準起點，不是第一次允許真實使用的日期。
- Evidence scope 使用既有 Dev environment；不因開始 evidence window 自動新增 staging／production infrastructure。

#### 8.5.2 Six-Month Dev Evidence Window

- Scheduler／ingestion／analysis 在目前 parallel-live dev 持續真實執行，累積 Data／Analysis／Operations／Cost／Security evidence；這段期間同時就是使用者實際使用 Janus 的期間，不是只能測試的等待期。
- 建議產生 bounded monthly summary；summary 是 evidence checkpoint，不是目前 dev 功能的使用批准證。
- application 可以正常迭代，但重要分析結果必須保留足夠 lineage，避免之後無法解釋版本差異。
- 未來獨立 Production topology 不在本階段自動建立；這只表示多人／HA／SLA 等營運升級尚未進行，不影響已通過 real-path acceptance 的 dev 能力可用性。

#### Mart AI evaluation slice — `WBS-8-PILOT-MART-AI-EVALUATION` (Planned)

依賴 `WBS-5-MART-AI-VALIDATION`、`WBS-5-MART-CIO-SYNTHESIS`、
`WBS-5-MART-RERUN-CACHE` 與 `WBS-6-ADMIN-ANALYSIS-PROFILE`。Evidence window 期間收集
role validation pass rate、provider failure／retry／availability、latency、token
usage、actual API cost、cache reuse、single-role rerun success、manual intervention、
rollback events、usefulness feedback、deterministic／AI divergence 與 outcome evidence
lineage。驗收要求每項 evidence 都綁 immutable execution／profile／provider／model／
prompt lineage，且可區分 partial success、failure 與 full success。

這不是 predictive model tuning；不提前做 role weight、threshold、leading-indicator
或 major-wave forecast optimization。

#### 8.5.3 Future Production Topology Review

- 六個 calendar months 的 evidence window 完成後可 review 實際 evidence，但 review 的目的，是判斷是否值得維持現有 parallel-live dev、延長 evidence window，或是否真的需要另一套 Production 營運層級；不是補發目前 dev 的「正式可用資格」。
- 建議 outcome = `KEEP_DEV_PARALLEL_LIVE`／`GO_PRODUCTION_PLANNING`／`EXTEND_EVIDENCE_WINDOW`／`NO_GO`。
- `GO_PRODUCTION_PLANNING` 只代表允許開始未來多人／對外／HA／SLA／正式營運的 architecture／migration planning，不等於自動部署 Production。
- production resource、IAM、HA、backup、RTO／RPO 等仍需獨立設計與人工授權。
- 保留 same digest promotion principle、canary、rollback、backup／restore、runbook 與 human approval；是否建立 staging 依未來實際營運需求決定。
- Release flow 改為：`capability real-path acceptance in parallel-live dev → continuous real use + evidence collection → optional future Production topology review`。

### 8.6 驗收條件

- 每個宣稱可在目前 dev 真實使用的能力，都必須通過自己的 real-path release／integration gate；不得用文件完成、mock/sample、fixture success 或 partial success 代替。
- 未來若建立獨立 Production，才另外套用該 Production topology 的 release／HA／SLA／promotion gate；沒有 Production 不代表目前 Janus 不可用。
- 任何 blocked item 都有 owner、下一步與 evidence link；資料不足或外部能力不足時維持 blocked／partial。

### 8.7 `WBS-8-CHATGPT-MCP-ACCEPTANCE`

模型：【Sol】。此能力在 MCP adapter complete、使用者確認支援所需 custom
read-only MCP integration 的 ChatGPT plan／UI，並對需要的 GCP dev deployment／test
給予明確授權後才能宣稱 MCP live accepted。

驗收 ChatGPT Developer Mode／custom app 是否能 discover Janus tools，並覆蓋 OAuth
login／reconnect／expiry／refresh、unauthenticated deny、server-side owner binding、
owner A／B isolation、market context、approved private positions／performance／trades、
investment-profile opt-in、v1 notes unavailable、arbitrary SQL／URI／owner injection
rejection、source／as-of／provenance、secret／storage locator absence、range／output
limits、no mutation、no unnecessary context snapshot growth、Cloud Run scale-to-zero
compatibility 與 bounded cost evidence。若第二個 owner／account 不可用，owner-isolation
live test 必須標為 blocked，不得捏造成功。

此 connector acceptance 不新增整個 Janus 的 Production Release prerequisite；未通過時只代表 MCP capability 尚未 full accepted。

### 8.8 `WBS-8-PILOT-RELEASE-BASELINE`

目前 parallel-live dev 的重要 analysis 必須能歸入可識別的 Pilot／evidence
baseline／epoch。至少保存或可追溯 git SHA、immutable image digest、governance
revision、prompt version／hash、relevant schema revision、model／provider 與
source／config revision。可採 monthly baseline、materially changed analysis
baseline 或 named Pilot epoch 其中一種簡單制度；不建立 staging，也不要求每次
commit 成為正式 release。Artifact Registry retention 本次不變；若未來需要 exact
old binary rerun，另案評估 image retention 成本。

Supply-chain 的 epoch lineage 另外要求 feature／signal revision 與 relevant Core／Mart
snapshot；不得用新資料或新模型改寫舊 epoch 的歷史 analysis artifact。這些欄位沿用本節
baseline mechanism，不建立新的 release system。

### 8.9 `WBS-8-SUPPLY-PILOT-EVALUATION` — Supply-chain Pilot measurement

Supply-chain signal 共用既有 Pilot outcome／PIT artifact，不另建 evaluation infrastructure。
規劃 5／20／60 trading-day outcome、benchmark-relative outcome、MFE、MAE、valid／excluded
與 exclusion provenance，並比較 signal lead time、incremental predictive value 及不同
epoch／revision。沒有 evidence value 的 indicator 可標記淘汰；evidence window 的目的不是證明六個
domain 全部有效。開始個人 live 使用不要求六個 domain 全部 ingestion-ready，且所有 materially
affecting change 必須可追溯至 baseline／epoch lineage。

### 8.10 `WBS-8-RESEARCH-CONTEXT-ACCEPTANCE`（Pilot Evolution／Planned）

- 驗證 ResearchContext same-`analysis_as_of`、PIT／future-leakage、provenance、stale／missing／partial、bounded output 與 deterministic signal reproducibility。
- 驗證 owner A／B isolation、private-data leakage negative cases、secret／storage locator absence，以及 ChatGPT MCP 對 SQL／URI／owner injection／mutation 的拒絕。
- 驗證 LLM 關閉不改變 canonical numeric result，UI 不將 null／missing 顯示為 0。
- 本 acceptance 不新增整個 Janus 的 live-use blocker；Supply-chain 依既有 Gate A–E 與 `WBS-8-SUPPLY-PILOT-EVALUATION`，相關能力未通過時維持 blocked／partial。