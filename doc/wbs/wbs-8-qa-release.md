# Janus WBS 8 — PIT、QA 與發布

## WBS 8 — PIT、QA 與發布

### 8.1 PIT

- 5／20／60 交易日 outcome。
- relative benchmark、MFE／MAE、coverage、calibration。
- 不合格樣本排除原因與 provenance ID。
- membership 與來源授權均以 effective time 納入 PIT；不得用今日關注股深度追蹤名單回填歷史樣本。

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
- 記錄正式 `pilot_started_at`；Pilot duration = 6 calendar months。
- 定義本次 Pilot evidence scope，確認使用既有 Dev environment。
- 確認不因 Pilot 自動新增 staging／production infrastructure。

#### 8.5.2 Six-Month Dev Pilot

- Scheduler／ingestion／analysis 持續執行，累積 Data／Analysis／Operations／Cost／Security evidence。
- 建議產生 bounded monthly summary；summary 是 evidence checkpoint，不是 production approval。
- application 可以正常迭代，但重要分析結果必須保留足夠 lineage，避免 Pilot 後無法解釋版本差異。
- production promotion 保持 blocked；這是 calendar-duration operational phase，不要求單一 Codex session 執行六個月。

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
