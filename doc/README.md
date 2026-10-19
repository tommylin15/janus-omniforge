# Janus 文件入口

更新：2026-10-19。本頁只導航，不保存暫停、部署版本或重複待辦。

先讀 [PROJECT_RULES](PROJECT_RULES.md) → [status](status.md) → [TODO](todo.md) → [AI開發指示](codex-execution-plan.md)。產品方向：持股／交易與效能 → 通用圖表／四頁 → 五角色品質 → 有效後報告；獨立FinOps依TODO判定。

本次 [文件盤點及風險](documentation-review-2026-10-15.md) 與 [系統建置補強](spec/system-development-contract.md) 已整理UI、研究、資料及可執行驗收；文件完成不代表產品完成。

## 1. 先判斷你要回答哪一種問題

| 問題 | 主要來源 | 不應拿來取代 |
|---|---|---|
| 現在程式到底怎麼做 | GitHub `main` 的 code／schema／migration／workflow／tests | Drive 設計稿、歷史文件 |
| 現在在哪裡、下一步是什麼 | `status.md` | 大型 evidence ledger、archive |
| 現在是否真的完成／可用 | tests、CI、deployment、live runtime、trigger／workload／integration evidence；最新證據索引見 `spec/operations-and-testing.md`，Dev Pilot evidence window 新 checkpoint 見 `pilot-operational-evidence.md` | 「文件已寫完」、舊 checkpoint |
| 完整未完成工作與 acceptance | `todo.md` | archive、舊 roadmap |
| 某 WBS 的責任與驗收邊界 | `wbs.md` → `wbs/*.md` | runtime snapshot |
| 產品／資料／API／治理契約 | `spec.md` → `spec/*.md` | TODO 中的暫時執行筆記 |
| UI 契約 | `ui.md` → `ui/*.md`；User App 最終 presentation 另見 `ui/reference/user-app-final/README.md` | mock screenshot／過期 implementation note／圖片中的 sample value |
| 怎麼安全操作 | `runbook-*.md` | 歷史 build ID／revision |
| 已完成／已取代的歷史 | `archive/` | active execution queue |
| 原始設計、研究規劃、模型研究產物 | Google Drive 白名單根目錄 `janusChatGPT` | GitHub／runtime 的實作現況 |

GitHub 與 Drive 不一致時：**目前實作與完成狀態以 GitHub／runtime evidence 為準；原始設計與核准規格可參考 Drive。差異要明確指出，不自行把其中一方覆蓋成另一方。**

資料治理、週維護 Scheduler／Jobs、兩種補資料機制與 D07 研究資料窗口，請先讀 **[統一資料治理入口](spec/data-governance.md)**，再按需要查 [因子矩陣](spec/factor-coverage-retention-ledger.md)、[Retention](spec/retention-governance.md)、[總控](runbook-batch-controller-dev.md)／[補資料](runbook-data-supplement.md)。文件不等同實際資料筆數、清理成功或自然排程驗收。

## 2. Active 文件地圖

- `PROJECT_RULES.md`：治理、權限、驗證與文件維護規則。
- `spec/data-governance.md`：現行保存、唯一業務排程與週維護、補資料兩路徑、D07 研究窗口的單一導覽；不新增工作包。
- `status.md`：目前狀態與下一個執行序列的短入口；不是新的 source of truth。
- `todo.md`：只保存確定要做的 active queue 與未完成 acceptance；暫不做與已接受缺口見 `parking-lot.md`。
- `codex-execution-plan.md`：持股 → 通用圖表 → 模型研究與有效後報告的作業指示；先整合再驗收，不另維護待辦狀態。
- `execution-cards/README.md`：八張 D01～D08 獨立 AI 任務執行卡與驗收／恢復指示；只作執行路由，不建立另一份待辦。
- `decision-2026-10-06-bigquery-analytics-over-iceberg.md`：B 組 Iceberg canonical + BigQuery analytics hybrid 決策；禁止 Storage Read API，BigQuery 不取代 PostgreSQL serving 或 canonical Iceberg。
- `future-market-alerts.md`：使用者指定獨立保存的未來預警增補；狀態由 `parking-lot.md` 管理，不是 active scope。
- `spec.md`：SPEC 索引；正式契約在 `spec/*.md`。
- `wbs.md`：WBS 索引；工作切片在 `wbs/*.md`。
- `ui.md`：UI 索引；頁面／元件契約在 `ui/*.md`。
- `ui/reference/user-app-final/README.md`：既有四張 PNG 的視覺基礎契約；sample 值不能作 canonical。
- `ui/visual-first-four-pages.md`：2026-10-11 [四頁視覺優先正式 UI 規格（A）](ui/visual-first-four-pages.md)。
- `ui/visual-first-delivery.md`： [工程工作單（B）](ui/visual-first-delivery.md)，涵蓋資料缺口、Flutter／API／Mart、P0/P1/P2 與真實 acceptance。
- `spec/operations-and-testing.md`：最新證據索引；完整舊ledger已移至archive，日常定位先看status。
- `pilot-operational-evidence.md`：`WBS-8-DEV-PILOT-RUN` 六個 calendar months evidence window 的新增 bounded checkpoint；保存 observed failure／recovery／manual intervention 與尚未觀察到的 evidence category，不把 checkpoint 當成 WBS 完成。
- `runbook-data-supplement.md`：每日增量、週六品質檢查、Admin 結果與排程修復程序。
- `spec/cicd-v2.md`：GHCR → Cloud Run Release／回滾契約；2026-10-10 dev 發布範圍曾 PASS；後續版本仍須獨立驗收，歷史收據在 [archive](archive/cicd-ghcr-api-promotion-2026-10-10.md)，不重複寫在索引。
- `runbook-dev-deploy.md`：dev API／Jobs 發布、共用鎖／lease、固定 Preview、回滾及 migration 的可重跑程序。
- `github-workflows.md`：GitHub Actions workflow 架構、composite action 與統一 workflow 開發規範。
- `runbook-pilot-calendar-repair.md`：Dev Pilot TWSE 交易日曆修復、operator IAP migration 與 bounded ingestion 驗收程序。
- `runbook-user-oauth-dev.md`：User／MCP OAuth 的專用操作與 A/B owner isolation 驗收程序。
- `runbook-parallel-live-dev.md`：dev 作為個人真實平行上線環境的操作語意。
- `secret_list.md`：Secret inventory 與相關 evidence；不得包含 secret payload。
- `omniagent-split-status.md`：Janus／omniAgent 分離的歷史入口，不是 active gate。
- `decision-2026-10-07-owner-scoped-parallel-private-recalculation.md`：Private Mart owner-scoped 重新計算的契約，不是 B 組排程入口。

## 3. 文件維護原則

1. README 與索引只保存穩定導航與責任，不固定容易過期的 revision、digest、build ID。
2. `status.md` 只回答「現在在哪、下一步是什麼」；SPEC 保存契約；TODO 保存所有尚未完成工作；Operations／Pilot evidence ledger 保存 observed evidence。不要互相複製全文。
3. Runbook 保存可重複執行的程序，不混入已失效的部署 checkpoint。實際 resource name／flag 若可能漂移，執行前以目前程式與 runtime 查證。
4. 完成項目與被取代規劃移至 `archive/`，active 文件只留下必要連結。
5. 未排程構想、Deferred、Production 才需要的工作及已接受缺口統一放在 `parking-lot.md`；Drive 研究資料不自動成為 active TODO。
6. 文件 commit 只能改變文件本身。是否「完成」仍要用 implementation、tests、CI、deployment 與 live integration evidence 判定。
7. Final Visual Contract 的圖片屬 presentation acceptance target，不是 canonical data source；sample value 不得反向污染 API／schema／Mart／Private Mart contract。

## 4. 證據維護

Operations只保存當前適用摘要／歷史連結，不無限追加。原2296行ledger完整保存於 [歷史快照](archive/documentation-baseline-2026-10-15-operations-and-testing.md)，相對連結已校正；新增證據以完整SHA／run／scope／觀察時間記錄，舊FAIL不改判。Pilot自然觀察仍在原檔，不重啟六個月窗口。
