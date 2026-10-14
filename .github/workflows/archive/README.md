# GitHub Workflows 歷史歸檔清冊

**歸檔日期**：2026-10-14  
**歸檔背景**：依據架構收斂決策，將原本膨脹至 117 份的 GitHub Workflows 進行系統化治理。收斂為四大核心管線（PR/Commit CI、核心 Release/Deployment、備份清理 Cron、統一代碼庫診斷 CLI），並將歷史階段性 Probe、前置診斷、里程碑單次驗收與已廢棄的前 500 母體研究排程封存於此。

> **注意**：依照 GitHub Actions 官方規範，`.github/workflows/` 底下子目錄內的檔案不會被 GitHub 解析為可觸發的 Workflow。此目錄僅作歷史記錄與審計追溯用途。

---

## 歸檔類別與清冊（共 89 份）

### 1. B2 系列：歷史 BigQuery Catalog、GCS 與 IAM 探測（16 份）
- `b2-bigquery-job-permission.yml`
- `b2-catalog-acl-probe.yml`
- `b2-catalog-bootstrap.yml`
- `b2-catalog-existence-diagnostic.yml`
- `b2-catalog-restricted-location.yml`
- `b2-cloudbuild-error-diagnostic.yml`
- `b2-cloudbuild-metadata-preflight.yml`
- `b2-core-fence-readback.yml`
- `b2-gcs-evidence-preflight.yml`
- `b2-iam-capability-preflight.yml`
- `b2-iam-setpolicy-fast-gate.yml`
- `b2-iceberg-metadata-summary.yml`
- `b2-janus-ci-permissions.yml`
- `b2-lakehouse-preflight.yml`
- `b2-nonregister-live-acceptance.yml`
- `b2-permission-preflight.yml`

### 2. B3 / B5 / B7 / B8 / B9 系列：各里程碑階段性驗收與品質讀回（17 份）
- `b3-cloudbuild-metadata-probe.yml`
- `b3-controller-recovery.yml`
- `b3-live-acceptance.yml`
- `b3-metadata-diagnostic.yml`
- `b5-live-acceptance.yml`
- `b7-derived-cache-freshness.yml`
- `b7-monthly-runtime-readback.yml`
- `b8-existing-identity-readback.yml`
- `b8-matched-screening.yml`
- `b8-ml-oos-equal-run.yml`
- `b8-ml-oos-fallback-readback.yml`
- `b8-ml-oos-readback.yml`
- `b9-event-label-protocol.yml`
- `b9-fundamental-data-quality.yml`
- `b9-specialist-oos-quality.yml`
- `b9-valuation-quality.yml`
- `bigquery-compatibility.yml`

### 3. Research 500 系列：舊 500 檔研究母體排程與前瞻留存（15 份，已轉全市場架構）
- `research-cloud-cohort-500-diag.yml`
- `research-cloud-cohort-500-diagnose.yml`
- `research-cloud-cohort-500-emerging-feature-watch.yml`
- `research-cloud-cohort-500-exec-diagnostic.yml`
- `research-cloud-cohort-500-export-matched.yml`
- `research-cloud-cohort-500-export.yml`
- `research-cloud-cohort-500-independent-validation.yml`
- `research-cloud-cohort-500-independent.yml`
- `research-cloud-cohort-500-matched-export.yml`
- `research-cloud-cohort-500-matched.yml`
- `research-cloud-cohort-500-pre-outcome-screen.yml`
- `research-cloud-cohort-500-prospective-extend.yml`
- `research-cloud-cohort-500-prospective.yml`
- `research-cloud-cohort-500-validation.yml`
- `research-cloud-cohort-500.yml`

### 4. CEO P0-V 歷史探測與 502/503 診斷（14 份，現行已收斂至專用 Job 部署）
- `ceo-omniagent-identity-runtime.yml`
- `ceo-omniagent-p0v-preflight.yml`
- `ceo-omniagent-p0v-text-canary.yml`
- `ceo-omniagent-p0v-worker-rollout.yml`
- `ceo-p0v-2048-diagnostic-readonly.yml`
- `ceo-p0v-candidate-readback.yml`
- `ceo-p0v-full-prompt-diagnostic.yml`
- `ceo-p0v-full-prompt-live.yml`
- `ceo-p0v-gateway-httplog-readonly.yml`
- `ceo-p0v-recovery-readback.yml`
- `ceo-p0v-tech-readonly-log-diagnostic.yml`
- `ceo-p0v-technical-acceptance.yml`
- `ceo-readonly-diagnostic.yml`
- `ceo-worker-dev.yml`

### 5. 持股、投資組合與單次維運／除錯腳本（16 份）
- `holdings-p0-mart-fields.yml`
- `holdings-p0-mart-logs.yml`
- `holdings-p0-owner-diagnostic.yml`
- `holdings-p0-owner-live.yml`
- `holdings-p0-runtime-gate.yml`
- `holdings-tpex-acl-migration.yml`
- `holdings-tpex-live-source.yml`
- `portfolio-completeness.yml`
- `portfolio-live-acceptance.yml`
- `portfolio-live-debug.yml`
- `portfolio-revaluation-green.yml`
- `private-ab-note-cleanup-once.yml`
- `private-cleanup-forensics.yml`
- `private-recalc-diagnostic.yml`
- `private-recalc-live-acceptance.yml`
- `private-recalc-queue-state.yml`
- `probe-mops-source.yml`
- `provider-credential-probe.yml`
- `inspect-dev-mart-execution.yml`
- `inspect-dev-runtime.yml`
- `mobile-ledger-drain-once.yml`
- `run-dev-specialist-b0-baseline.yml`
- `run-dev-specialist-b4-acceptance.yml`
- `visual-first-live-baseline.yml`
- `visual-first-preview-readback.yml`

### 6. GHCR 單次演練、Audit 與過期 Preflight（16 份）
- `ghcr-candidate-lease-contract.yml`
- `ghcr-release-lease-drill.yml`
- `ghcr-scheduler-diagnostic.yml`
- `ghcr-scheduler-operator-drill.yml`
- `ghcr-scheduler-recover-dev.yml`
- `ghcr-stale-executions-audit.yml`
- `ghcr-jobs-cutover-gate.yml`
- `ghcr-jobs-forward-resume.yml`
- `ghcr-jobs-preflight.yml`
- `ghcr-jobs-readonly-preflight.yml`
- `ghcr-private-pipeline-iam-grant.yml`
- `ghcr-reversible-baseline-dev.yml`
- `ghcr-revision-retention-preview.yml`
- `cicd-cutover-inventory.yml`
- `postgres-iap-bootstrap.yml`
- `publication-owner-credential-rotation-dev.yml`
