# Janus 文件入口

更新：2026-09-26

本頁定義 repository 內文件的角色，避免同一件事同時在 README、SPEC、WBS、TODO、runbook 與測試紀錄各自形成不同版本。

## 1. 先判斷你要回答哪一種問題

| 問題 | 主要來源 | 不應拿來取代 |
|---|---|---|
| 現在程式到底怎麼做 | GitHub `main` 的 code／schema／migration／workflow／tests | Drive 設計稿、歷史文件 |
| 現在在哪裡、下一步是什麼 | `status.md` | 大型 evidence ledger、archive |
| 現在是否真的完成／可用 | tests、CI、deployment、live runtime、trigger／workload／integration evidence；完整 ledger 見 `spec/operations-and-testing.md` | 「文件已寫完」、舊 checkpoint |
| 完整未完成工作與 acceptance | `todo.md` | archive、舊 roadmap |
| 某 WBS 的責任與驗收邊界 | `wbs.md` → `wbs/*.md` | runtime snapshot |
| 產品／資料／API／治理契約 | `spec.md` → `spec/*.md` | TODO 中的暫時執行筆記 |
| UI 契約 | `ui.md` → `ui/*.md` | mock screenshot／過期 implementation note |
| 怎麼安全操作 | `runbook-*.md` | 歷史 build ID／revision |
| 已完成／已取代的歷史 | `archive/` | active execution queue |
| 原始設計、研究規劃、模型研究產物 | Google Drive 白名單根目錄 `janusChatGPT` | GitHub／runtime 的實作現況 |

GitHub 與 Drive 不一致時：**目前實作與完成狀態以 GitHub／runtime evidence 為準；原始設計與核准規格可參考 Drive。差異要明確指出，不自行把其中一方覆蓋成另一方。**

## 2. Active 文件地圖

- `PROJECT_RULES.md`：治理、權限、驗證與文件維護規則。
- `status.md`：目前狀態與下一個執行序列的短入口；不是新的 source of truth。
- `todo.md`：完整未完成工作、planned／blocked／deferred 與現行 acceptance registry。
- `spec.md`：SPEC 索引；正式契約在 `spec/*.md`。
- `wbs.md`：WBS 索引；工作切片在 `wbs/*.md`。
- `ui.md`：UI 索引；頁面／元件契約在 `ui/*.md`。
- `spec/operations-and-testing.md`：完整 implementation／test／deployment／runtime evidence ledger，包含歷史 checkpoint；日常定位優先看 `status.md`，需要稽核才進本檔。
- `runbook-dev-deploy.md`：目前 dev 部署、migration、Job 與 Secret 的操作程序。
- `runbook-pilot-calendar-repair.md`：Dev Pilot TWSE 交易日曆修復、operator IAP migration 與 bounded ingestion 驗收程序。
- `runbook-user-oauth-dev.md`：User／MCP OAuth 的專用操作與 A/B owner isolation 驗收程序。
- `runbook-parallel-live-dev.md`：dev 作為個人真實平行上線環境的操作語意。
- `secret_list.md`：Secret inventory 與相關 evidence；不得包含 secret payload。
- `omniagent-split-status.md`：只保留 Janus／omniAgent 拆分的歷史入口，不再是 Janus active gate。

## 3. 文件維護原則

1. README 與索引只保存穩定導航與責任，不固定容易過期的 revision、digest、build ID。
2. `status.md` 只回答「現在在哪、下一步是什麼」；SPEC 保存契約；TODO 保存所有尚未完成工作；Operations 保存完整 observed evidence。不要互相複製全文。
3. Runbook 保存可重複執行的程序，不混入已失效的部署 checkpoint。實際 resource name／flag 若可能漂移，執行前以目前程式與 runtime 查證。
4. 完成項目與被取代規劃移至 `archive/`，active 文件只留下必要連結。
5. 未排程構想放在 `todo.md` 明確標示 Planned／Blocked／Deferred，或白名單 Drive 的研究／規劃文件；不得假裝已進 active queue。
6. 文件 commit 只能改變文件本身。是否「完成」仍要用 implementation、tests、CI、deployment 與 live integration evidence 判定。

## 4. Operations ledger 的處理方式

`spec/operations-and-testing.md` 已累積大量歷史 checkpoint。GitHub connector 在不遺失原文的前提下無法安全做 server-side blob 搬移，因此目前**保留原檔完整 evidence，不做高風險整檔重寫**。日常工作以 `status.md` 作短入口；等有可驗證的完整搬移流程時，再把舊 checkpoint 分期移入 `archive/`。
