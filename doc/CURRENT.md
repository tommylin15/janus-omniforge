# Project Argus（Janus AI）— Current Work

更新日期：2026-08-25

目前 WBS：WBS 0 — 專案啟動與決策封版

狀態：`ready`

## 目標

建立可審查、可重現且不直接建立雲端資源的專案啟動基線，完成 WBS 0
所需的 repository、GCP IaC、共用契約與治理設計。所有可能產生費用的 GCP
資源僅建立程式碼與設定；實際建立資源須由使用者另行明確授權。

## 必讀文件

- `doc/PROJECT_RULES.md`
- `doc/wbs.md` 的「WBS 0 — 專案啟動與決策封版」
- 與當次變更直接相關的程式、測試及目錄內 `AGENTS.md`

## 已確認的專案決策

| 項目 | 決策 |
|---|---|
| GCP Project ID | `gen-lang-client-0593591102` |
| Billing account | `tommyGCP`（`014EF3-8C5D8C-A73A2B`） |
| Region | `us-central1` |
| PostgreSQL | GCE PostgreSQL |
| 第一批股票 | `2330` |
| 第一版 LLM | Gemini |
| Dev 資源前綴 | `janus-dev` |
| AI 權限 | 可修改程式與 Terraform，並建立 commit 與 PR |
| Production deployment | 必須人工批准 |
| 費用控制 | 未經使用者另行明確授權，只建立 IaC 與設定，不實際建立任何可能計費的 GCP 資源 |

## 執行範圍

1. 建立 monorepo 基礎結構、repository 治理檔案與開發期必要設定。
2. 建立 GCP dev 環境的 Terraform/IaC 定義，但不執行會建立、修改或刪除
   遠端資源的命令。
3. 建立 GitHub 與 GCP Workload Identity Federation、Cloud Build service
   account 及必要 API 的宣告式設定，但不套用至 GCP。
4. 建立共用 contracts package、schema version 與 compatibility policy。
5. 固定 development completeness gate 為 30%，並定義 provenance、quality
   flag、publication status 與 execution status。
6. 盤點 deterministic constants，標示為 approved、development-default 或
   pending。

## 限制與人工關卡

- 不執行 `terraform apply` 或其他會建立、修改、刪除 GCP 資源的命令。
- 不部署 dev、staging 或 production；production 永遠需要人工批准。
- 不建立 GCE VM、GCS bucket、Cloud SQL 或其他可能計費的 GCP 資源。
- 不建立或提交長效 service-account JSON key、資料庫密碼或其他 secret。
- Billing account 僅供 IaC 參數化；未取得額外授權不得進行 billing 綁定或資源建立。

## 驗收條件

- PR 設定可供 Cloud Build trigger 使用，且失敗建置不會進行部署。
- GitHub 與 repository 不保存 service-account JSON key 或 secret。
- Terraform 格式及靜態驗證通過，並可產生可審查的 dev 基礎資源 plan；若
  plan 需要遠端認證，須保留為人工驗證項目，不得為此建立資源。
- 共用契約及治理常數具有自動化測試，並固定 development completeness
  gate 為 30%。
- 所有尚未套用的雲端設定與需要人工執行的驗證，均明確列為剩餘條件。

## 目前驗證

- 已登錄並核對使用者確認的專案決策。
- Repository baseline 已建立 monorepo 目錄、CODEOWNERS、PR template、
  EditorConfig 與 Git attributes。
- Repository baseline 已通過結構、格式及敏感檔名靜態檢查。
- 尚未建立或修改任何 GCP 資源。

## 剩餘條件

- 確認 `@tommyGCP` 是預期的 GitHub code owner，並由 repository 管理員設定
  branch protection。
- 完成 GCP IaC、Workload Identity Federation 與 Cloud Build 宣告式設定。
- 完成共用 contracts、治理常數及其自動化測試。
- 由人工在具備適當 GCP 權限的環境審查 Terraform plan。
- 使用者另行明確授權後，才可進行任何會產生費用的 GCP 操作。
