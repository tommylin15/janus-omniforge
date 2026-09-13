# TODO 完成紀錄（2026-09-13：WBS-6／WBS-7）

本紀錄收納 WBS-6／WBS-7 已完成的實作與驗收項目；未完成條件仍保留在
[`doc/todo.md`](../todo.md)。

## PostgreSQL／FastAPI／Flutter

- Governance typed editing、group validation、diff preview、immutable history 與
  optimistic lock；Admin UI 顯示 approved／development-default／pending，分析流程只讀
  已提交版本。
- PostgreSQL migration、role isolation、queue claim、connection exhaustion、VM
  restart/reconnect、retention/pruning tests；相關 GCP dev 與自動測試驗收完成。
- Model／evaluation artifact 與大型 governance diff 寫入 GCS，並以 manifest 保存
  object URI、snapshot ID 與 hash。
- Publication index 可解析 immutable GCS／Iceberg artifact；blocked／insufficient-data
  成品 fail-closed，不進公開 API／Web。
- Governance／audit metadata 使用 migration、optimistic lock、retention 與專用 role；
  大 payload／diff artifact 放 GCS。
- Report block／unblock 實際 mutation、理由保存與 audit API；migration 022、SQLite／
  FastAPI contract 與既有 dev PostgreSQL SQL acceptance 完成。
- 舊 WSGI routes 遷移至 FastAPI，`janus-web` workflow／dev service 移除，`janus-api`
  成為唯一 dev HTTP boundary。
- Public／private／admin router、response model、auth、CORS、rate limit、IAM 與 audit
  boundary 完成；public GCP acceptance 與 final revision 驗收通過。
- Public API health、daily brief、sector rotation、topics、candidates、stock health、
  history、Kline、events，以及 Private journal／notes／watchlist／chats contract 完成。
- 未知／停用股票 404、無資料 waiting、no scraper／Agent／LLM、safe redaction、public
  read-only pool／statement timeout 與 private ownership 驗收完成。
- Flutter Material 3 User App 導覽、Today、StockHealthCard、個股進階資料、個人工
  作台、screening 與 responsive surface 完成；Flutter Cloud Build 驗收通過。

## 自動化驗收

- Backend pytest、FastAPI contract、Flutter analyze／widget、Admin Vitest、Playwright、
  TypeScript／ESLint／production build 驗收完成。
- Iceberg schema evolution、failure／retry／idempotency tests 完成。
- PostgreSQL role isolation、pool exhaustion、restart/reconnect、migration rollback、
  publication index、safe output 與 log redaction tests 完成。

## WBS-7 安全／監控／FinOps

- WBS-7.1 IAM／Secret：runtime service-account 分離、最小 consumer、dev／production
  guard、無 user-managed key、PostgreSQL private IP／IAP boundary 完成。
- WBS-7.2 Observability：execution／trace lineage、source／dataset health、Job duration／
  retry／publication、API SLI 與 safe error taxonomy 完成。
- WBS-7.3 FinOps：Cloud Run bounds、GCS lifecycle、Artifact cleanup、無 snapshot guard
  與 budget thresholds 完成；已建立 320 TWD（US$10 等值）budget guard。
- WBS-7.4 安全驗收：secret／raw payload／敏感 URI redaction、lineage、IAM 與 network
  guard 的本機及 GCP dev 證據完成。
