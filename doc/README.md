# Janus 文件入口

更新：2026-10-08

本頁定義 repository 內文件的角色，避免同一件事同時在 README、SPEC、WBS、TODO、runbook 與測試紀錄各自形成不同版本。

## 1. 先判斷你要回答哪一種問題

| 問題 | 主要來源 | 不應拿來取代 |
|---|---|---|
| 現在程式到底怎麼做 | GitHub `main` 的 code／schema／migration／workflow／tests | Drive 設計稿、歷史文件 |
| 現在在哪裡、下一步是什麼 | `status.md` | 大型 evidence ledger、archive |
| 現在是否真的完成／可用 | tests、CI、deployment、live runtime、trigger／workload／integration evidence；完整歷史 ledger 見 `spec/operations-and-testing.md`，Dev Pilot evidence window 新 checkpoint 見 `pilot-operational-evidence.md` | 「文件已寫完」、舊 checkpoint |
| 完整未完成工作與 acceptance | `todo.md` | archive、舊 roadmap |
| 某 WBS 的責任與驗收邊界 | `wbs.md` → `wbs/*.md` | runtime snapshot |
| 產品／資料／API／治理契約 | `spec.md` → `spec/*.md` | TODO 中的暫時執行筆記 |
| UI 契約 | `ui.md` → `ui/*.md`；User App 最終 presentation 另見 `ui/reference/user-app-final/README.md` | mock screenshot／過期 implementation note／圖片中的 sample value |
| 怎麼安全操作 | `runbook-*.md` | 歷史 build ID／revision |
| 已完成／已取代的歷史 | `archive/` | active execution queue |
| 原始設計、研究規劃、模型研究產物 | Google Drive 白名單根目錄 `janusChatGPT` | GitHub／runtime 的實作現況 |

GitHub 與 Drive 不一致時：**目前實作與完成狀態以 GitHub／runtime evidence 為準；原始設計與核准規格可參考 Drive。差異要明確指出，不自行把其中一方覆蓋成另一方。**

## 2. Active 文件地圖

- `PROJECT_RULES.md`：治理、權限、驗證與文件維護規則。
- `status.md`：目前狀態與下一個執行序列的短入口；不是新的 source of truth。
- `todo.md`：只保存確定要做的 active queue 與未完成 acceptance；暫不做與已接受缺口見 `parking-lot.md`。
- `codex-execution-plan.md`：TODO 的 A／B／C 合併工作組執行指令；先整合修改再集中驗收，不另維護待辦狀態。
- `decision-2026-10-06-bigquery-analytics-over-iceberg.md`：B 組 Iceberg canonical + BigQuery analytics hybrid 決策；禁止 Storage Read API，BigQuery 不取代 PostgreSQL serving 或 canonical Iceberg。
- `future-market-alerts.md`：使用者指定獨立保存的未來預警增補；狀態由 `parking-lot.md` 管理，不是 active scope。
- `spec.md`：SPEC 索引；正式契約在 `spec/*.md`。
- `wbs.md`：WBS 索引；工作切片在 `wbs/*.md`。
- `ui.md`：UI 索引；頁面／元件契約在 `ui/*.md`。
- `ui/reference/user-app-final/README.md`：Janus User App 的 active Final Visual Contract；固定 `today.png`、`watchlist.png`、`ledger.png`、`stock-detail.png` 四個 presentation target 路徑。PNG binary 未實際 commit 前，不得宣稱 final screenshot reference 已到位。
- `spec/operations-and-testing.md`：最新完整 evidence summary 與尚待整理的歷史 checkpoint；日常定位優先看 `status.md`，舊證據逐步移至 `archive/`。
- `pilot-operational-evidence.md`：`WBS-8-DEV-PILOT-RUN` 六個 calendar months evidence window 的新增 bounded checkpoint；保存 observed failure／recovery／manual intervention 與尚未觀察到的 evidence category，不把 checkpoint 當成 WBS 完成。
- `runbook-data-supplement.md`：每日增量、週六品質檢查、Admin 結果與排程修復程序。
- `spec/cicd-v2.md`：2026-10-08 核准的 Actions + 公開 GHCR + Cloud Run 發布／回滾契約；現行階段性驗收見 `status.md` 與 [第二輪 GHCR／固定 Preview live evidence](archive/cicd-ghcr-next-release-preview-2026-10-09.md)。完整 GHCR Release、固定 Preview、同 SHA Owner 人工驗收、四 Jobs 新版 8/8 canary 與 API 正式 100% 切流／真實 traffic rollback 均 PASS；使用者 2026-10-10 豁免四項額外演練／舊 AR 歷史問題，**目前 dev CI/CD scope 已結案 PASS**，未實測項保留原始標記於 [Parking Lot](parking-lot.md)，不列 TODO。
- `runbook-dev-deploy.md`：dev 部署、migration、Job 與 Secret 的操作程序；CI/CD 節記錄已上線 GHCR/固定 Preview、共用 lease 和新人員 OAuth gate 後的可逆 rollout／promotion 步驟。最新切流結果見 [2026-10-10 API live rollback evidence](archive/cicd-ghcr-api-promotion-2026-10-10.md)；其他 Research/Private 歷史差異見 [先前盤點](archive/cicd-ghcr-unattended-hardening-2026-10-10.md)，不可混淆 API traffic 與 Jobs image rollback。
- `runbook-pilot-calendar-repair.md`：Dev Pilot TWSE 交易日曆修復、operator IAP migration 與 bounded ingestion 驗收程序。
- `runbook-user-oauth-dev.md`：User／MCP OAuth 的專用操作與 A/B owner isolation 驗收程序。
- `runbook-parallel-live-dev.md`：dev 作為個人真實平行上線環境的操作語意。
- `secret_list.md`：Secret inventory 與相關 evidence；不得包含 secret payload。
- `omniagent-split-status.md`：只保留 Janus／omniAgent 拆分的歷史入口，不再是 Janus active gate。

## 3. 文件維護原則

1. README 與索引只保存穩定導航與責任，不固定容易過期的 revision、digest、build ID。
2. `status.md` 只回答「現在在哪、下一步是什麼」；SPEC 保存契約；TODO 保存所有尚未完成工作；Operations／Pilot evidence ledger 保存 observed evidence。不要互相複製全文。
3. Runbook 保存可重複執行的程序，不混入已失效的部署 checkpoint。實際 resource name／flag 若可能漂移，執行前以目前程式與 runtime 查證。
4. 完成項目與被取代規劃移至 `archive/`，active 文件只留下必要連結。
5. 未排程構想、Deferred、Production 才需要的工作及已接受缺口統一放在 `parking-lot.md`；Drive 研究資料不自動成為 active TODO。
6. 文件 commit 只能改變文件本身。是否「完成」仍要用 implementation、tests、CI、deployment 與 live integration evidence 判定。
7. Final Visual Contract 的圖片屬 presentation acceptance target，不是 canonical data source；sample value 不得反向污染 API／schema／Mart／Private Mart contract。

## 4. Operations ledger 的處理方式

`spec/operations-and-testing.md` 已累積大量歷史 checkpoint。GitHub connector 在不遺失原文的前提下無法安全做 server-side blob 搬移或小範圍 patch，因此目前**保留原檔完整 evidence，不做高風險整檔重寫**。六個月 `WBS-8-DEV-PILOT-RUN` 的新增 bounded checkpoint 先追加至 `pilot-operational-evidence.md`，並由 `status.md` 連結目前判定；等有可驗證的完整搬移／patch 流程時，再考慮整併至 operations ledger 或將舊 checkpoint 分期移入 `archive/`。


## Owner-scoped Private Mart recalculation

- [設計與驗收契約](decision-2026-10-07-owner-scoped-parallel-private-recalculation.md)
