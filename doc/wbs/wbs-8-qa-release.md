# Janus WBS 8 — PIT、QA 與發布

## WBS 8 — PIT、QA 與發布

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

- walk-forward tuning、role weight optimization、40／60 threshold revision 與 governance tuning 留在後續，不提前成為 Pilot Entry blocker。

### 8.2 自動化 QA

- pytest、FastAPI contract tests、Flutter analyze／widget tests、Vitest、Playwright、TypeScript、build。
- schema／migration／Iceberg evolution 測試。
- failure、retry、idempotency、rollback 測試。

### 8.3 實機與 A11y

- Flutter Android／iOS／Web、iOS Safari、Android Chrome、iPad Safari。
- VoiceOver、TalkBack、keyboard、touch、safe area。
- WCAG AA 實際對比。

### 8.4 UI 驗收後的資料品質強化

- 本節有順序 gate：Admin 資料營運流程、Flutter 關注／記帳／筆記／AI／健康檢查與實機 A11y 尚未通過前不得開工。
- 完成跨源一致性、null profile、freshness、coverage、schema drift、outlier／corporate-action 校準與 quality-score 版本化。
- 校準 market regime、sector rotation、topic uncertainty、candidate health 與 private PnL 的品質折減，不得改寫歷史 Mart。
- Admin DQ dashboard 顯示結構化摘要、quarantine drill-down、門檻 revision 與 evidence；不提供 raw payload 旁路。
- 以已驗收 UI 的真實閱讀問題調整 DQ 門檻；完成前保留 30% development gate，不宣稱 production-grade 品質。

### 8.5 Release

#### 8.5.1 Dev Pilot Entry

- 核心 MVP／acceptance 與必要的安全、資料、runtime gate 足以安全長期運作後才能開始。
- WBS-3 canary／full-market safety gate、Pilot ledger durability（至少一次 successful restore evidence）、outcome collection、usefulness feedback、release baseline 與 security／privacy／cost evidence 必須 ready。
- Supply-chain Intelligence 的 `WBS-5-SUPPLY-FOUNDATION`、`WBS-5-SUPPLY-SOURCE-MATRIX`、
  `WBS-5-SUPPLY-SEED-GRAPH`、`WBS-5-SUPPLY-SIGNAL-MART` planning evidence 與本節的
  `WBS-8-SUPPLY-PILOT-EVALUATION` contract 必須 ready；這是 planning prerequisite，不是
  六個 domain 全部 ingestion-ready，也不解鎖 implementation。
- Pilot Entry 前至少確認 data-safety DQ 已存在：required key／type、duplicate、future leakage、freshness、basic coverage、schema drift，以及適用時的 obvious outlier／corporate-action sanity；完整 DQ dashboard、quality-score tuning 與大型 drill-down 留在後續。
- ChatGPT MCP acceptance 必須完成；若被外部 ChatGPT plan／UI capability 阻擋，須由使用者明確決定是否允許在 connector blocked 狀態啟動 Pilot。
- 上述 WBS-3 gate、四個 Pilot readiness gap 與 ChatGPT MCP CONTRACT／ADAPTER／ACCEPTANCE 可在 Entry 前平行準備；WBS-3 不構成任何 Track B task 的前置 dependency。
- 記錄正式 `pilot_started_at`；Pilot duration = 6 calendar months。
- 定義本次 Pilot evidence scope，確認使用既有 Dev environment。
- 確認不因 Pilot 自動新增 staging／production infrastructure。

#### 8.5.2 Six-Month Dev Pilot

- Scheduler／ingestion／analysis 持續執行，累積 Data／Analysis／Operations／Cost／Security evidence。
- 建議產生 bounded monthly summary；summary 是 evidence checkpoint，不是 production approval。
- application 可以正常迭代，但重要分析結果必須保留足夠 lineage，避免 Pilot 後無法解釋版本差異。
- production promotion 保持 blocked；這是 calendar-duration operational phase，不要求單一 Codex session 執行六個月。

#### Mart AI evaluation slice — `WBS-8-PILOT-MART-AI-EVALUATION` (Planned)

依賴 `WBS-5-MART-AI-VALIDATION`、`WBS-5-MART-CIO-SYNTHESIS`、
`WBS-5-MART-RERUN-CACHE` 與 `WBS-6-ADMIN-ANALYSIS-PROFILE`。Pilot 期間只收集
role validation pass rate、provider failure／retry／availability、latency、token
usage、actual API cost、cache reuse、single-role rerun success、manual intervention、
rollback events、usefulness feedback、deterministic／AI divergence 與 outcome evidence
lineage。驗收要求每項 evidence 都綁 immutable execution／profile／provider／model／
prompt lineage，且可區分 partial success、failure 與 full success。

這不是 predictive model tuning；不提前做 role weight、threshold、leading-indicator
或 major-wave forecast optimization。

#### 8.5.3 Production Go／Extend／No-Go Review

- 六個 calendar months 完成後 review Pilot evidence，outcome = `GO`／`EXTEND_PILOT`／`NO_GO`。
- `GO` 只代表允許開始 production architecture／migration planning，不等於自動部署 production。
- production resource、IAM、HA、backup、RTO／RPO 等仍需獨立設計與人工授權。
- `EXTEND_PILOT` 繼續 Dev Pilot；`NO_GO` 不建立 production。
- 保留 same digest promotion principle、canary、rollback、backup／restore、runbook 與 human production approval。
- Release flow：`dev acceptance → six-month Dev Pilot → human Go/Extend/No-Go → conditional staging/production planning`；Pilot 後再決定是否需要 staging。

### 8.6 驗收條件

- 所有 release gate 通過才可宣稱正式上線。
- 任何 blocked item 都有 owner、deadline、evidence link。

### 8.7 `WBS-8-CHATGPT-MCP-ACCEPTANCE`

模型：【Sol】。Blocked until MCP adapter complete、使用者確認支援所需 custom
read-only MCP integration 的 ChatGPT plan／UI，並對任何 GCP dev deployment／test
給予明確授權。

驗收 ChatGPT Developer Mode／custom app 是否能 discover Janus tools，並覆蓋 OAuth
login／reconnect／expiry／refresh、unauthenticated deny、server-side owner binding、
owner A／B isolation、market context、approved private positions／performance／trades、
investment-profile opt-in、v1 notes unavailable、arbitrary SQL／URI／owner injection
rejection、source／as-of／provenance、secret／storage locator absence、range／output
limits、no mutation、no unnecessary context snapshot growth、Cloud Run scale-to-zero
compatibility 與 bounded cost evidence。若第二個 owner／account 不可用，owner-isolation
live test 必須標為 blocked，不得捏造成功。

此 connector acceptance 不新增 Janus Production Release prerequisite。

### 8.8 `WBS-8-PILOT-RELEASE-BASELINE`

Pilot 期間仍可開發與部署 Dev，但重要 analysis 必須能歸入可識別的 Pilot
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
epoch／revision。沒有 evidence value 的 indicator 可標記淘汰；Pilot 目的不是證明六個
domain 全部有效。Pilot Day 1 不要求六個 domain 全部 ingestion-ready，且所有 materially
affecting change 必須可追溯至 baseline／epoch lineage。

### 8.10 `WBS-8-RESEARCH-CONTEXT-ACCEPTANCE`（Pilot Evolution／Planned）

- 驗證 ResearchContext same-`analysis_as_of`、PIT／future-leakage、provenance、stale／missing／partial、bounded output 與 deterministic signal reproducibility。
- 驗證 owner A／B isolation、private-data leakage negative cases、secret／storage locator absence，以及 ChatGPT MCP 對 SQL／URI／owner injection／mutation 的拒絕。
- 驗證 LLM 關閉不改變 canonical numeric result，UI 不將 null／missing 顯示為 0。
- 本 acceptance 不新增 Dev Pilot Entry blocker；Supply-chain 依現有 Gate A–E 與 `WBS-8-SUPPLY-PILOT-EVALUATION`。
