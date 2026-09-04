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

- dev → staging → production 同一 digest。
- canary、rollback、backup／restore、runbook。
- 人工 production approval。

### 8.6 驗收條件

- 所有 release gate 通過才可宣稱正式上線。
- 任何 blocked item 都有 owner、deadline、evidence link。
