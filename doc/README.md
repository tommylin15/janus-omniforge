# Janus 文件入口

更新：2026-09-24

本頁定義 repository 內文件的角色，避免同一件事同時在 README、SPEC、WBS、TODO、runbook 與測試紀錄各自形成不同版本。

## 1. 先判斷你要回答哪一種問題

| 問題 | 主要來源 | 不應拿來取代 |
|---|---|---|
| 現在程式到底怎麼做 | GitHub `main` 的 code／schema／migration／workflow／tests | Drive 設計稿、歷史文件 |
| 現在是否真的完成／可用 | tests、CI、deployment、live runtime、trigger／workload／integration evidence；摘要見 `spec/operations-and-testing.md` | 「文件已寫完」、舊 checkpoint |
| 現在要做什麼 | `todo.md` | archive、舊 roadmap |
| 某 WBS 的責任與驗收邊界 | `wbs.md` → `wbs/*.md` | runtime snapshot |
| 產品／資料／API／治理契約 | `spec.md` → `spec/*.md` | TODO 中的暫時執行筆記 |
| UI 契約 | `ui.md` → `ui/*.md` | mock screenshot／過期 implementation note |
| 怎麼安全操作 | `runbook-*.md` | 歷史 build ID／revision |
| 已完成／已取代的歷史 | `archive/` | active execution queue |
| 原始設計、研究規劃、模型研究產物 | Google Drive 白名單根目錄 `janusChatGPT` | GitHub／runtime 的實作現況 |

GitHub 與 Drive 不一致時：**目前實作與完成狀態以 GitHub／runtime evidence 為準；原始設計與核准規格可參考 Drive。差異要明確指出，不自行把其中一方覆蓋成另一方。**

## 2. Active 文件地圖

- `PROJECT_RULES.md`：治理、權限、驗證與文件維護規則。
- `todo.md`：只放目前未完成工作、active queue、blocked／deferred 與現行 acceptance。
- `spec.md`：SPEC 索引；正式契約在 `spec/*.md`。
- `wbs.md`：WBS 索引；工作切片在 `wbs/*.md`。
- `ui.md`：UI 索引；頁面／元件契約在 `ui/*.md`。
- `spec/operations-and-testing.md`：最新實作／測試／部署／runtime 驗收摘要。它是 evidence summary，不是永久 append-only 日誌；舊 checkpoint 應定期移至 `archive/`。
- `runbook-dev-deploy.md`：目前 dev 部署、migration、Job 與 Secret 的操作程序。
- `runbook-user-oauth-dev.md`：User／MCP OAuth 的專用操作與 A/B owner isolation 驗收程序。
- `runbook-parallel-live-dev.md`：dev 作為個人真實平行上線環境的操作語意。
- `secret_list.md`：Secret inventory 與相關 evidence；不得包含 secret payload。
- `omniagent-split-status.md`：只保留 Janus／omniAgent 拆分的歷史入口，不再是 Janus active gate。

## 3. 文件維護原則

1. README 與索引只保存穩定導航與責任，不固定容易過期的 revision、digest、build ID。
2. SPEC 保存「契約」；TODO 保存「尚未完成的工作」；Operations 保存「已觀測到的現況證據」。三者不要互相複製全文。
3. Runbook 保存可重複執行的程序，不混入已失效的部署 checkpoint。實際 resource name／flag 若可能漂移，執行前以目前程式與 runtime 查證。
4. 完成項目與被取代規劃移至 `archive/`，active 文件只留下必要連結。
5. 未排程構想放在 `todo.md` 明確標示的 Deferred／Backlog 區，或白名單 Drive 的研究／規劃文件；不得假裝已進 active queue。
6. 文件 commit 只能改變文件本身。是否「完成」仍要用 implementation、tests、CI、deployment 與 live integration evidence 判定。

## 4. 已知文件技術債

`spec/operations-and-testing.md` 目前仍偏大，包含多個歷史 checkpoint。由於它同時承載最新 2026-09-24 runtime evidence，本次不做高風險整檔重寫；後續應在保全最新 evidence 後，把過期段落按日期移入 `archive/`，讓 active 摘要只保留目前狀態與近期驗收。
