# Janus 文件入口

> 排程、備份與資料快照依 [統一批次契約](spec/unified-batch-flow.md)；部署狀態與未完成驗收以 [唯一 TODO](todo.md) 為準。

> **2026-10-24 研究精簡決策優先**：本文涉及獨立資料稽核、逐來源補證、全歷史 PIT／精確時間校準、例行週月稽核及自然驗收等待的要求已取消，不再是待辦或發布前置。依 [研究精簡政策](spec/research-simplification.md)，保留必要日期／單位、基本防洩漏與操作安全；歷史證據不改判 PASS。


更新：2026-10-25。本頁只導航，不保存暫停、部署版本或重複待辦。

先讀 [PROJECT_RULES](PROJECT_RULES.md) → [status](status.md) → [唯一TODO](todo.md) → [SEQ逐項AI指示](execution-cards/sequential-delivery.md)。現行只有 **SEQ-01→08一條順序線**；每項分文件設計、程式開發、測試驗收、部署。四模型本版正式上線；研究調校留2027年第一季，已結案項不重開。

文件權責、唯一待辦與**需要使用者決策的重大風險**統一見 [專案管理](project-management.md)；舊 [文件盤點](archive/documentation-review-2026-10-15.md) 轉歷史證據，不當現在的工作佇列。

## 1. 先判斷你要回答哪一種問題

| 問題 | 主要來源 | 不應拿來取代 |
|---|---|---|
| 現在程式到底怎麼做 | GitHub `main` 的 code／schema／migration／workflow／tests | Drive 設計稿、歷史文件 |
| 現在在哪裡、下一步是什麼 | `status.md` | 大型 evidence ledger、archive |
| 現在是否真的完成／可用 | tests、CI、deployment、live runtime、trigger／workload／integration evidence；最新證據索引見 `spec/operations-and-testing.md`，Dev Pilot evidence window 新 checkpoint 見 `archive/document-cleanup-2026-10-25/pilot-operational-evidence.md` | 「文件已寫完」、舊 checkpoint |
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
- `project-management.md`：單一執行順序、文件責任、驗收與風險決策選項。
- `spec/valuation-range.md`：2026-10-24 最新決策改為 **04 Valuation 估值區間子契約**，第五模型已撤銷；工程進度依唯一 TODO；舊 Drive AI 交接屬歷史參考；[Drive AI 交接](https://drive.google.com/file/d/1M7pxgkeyzK_Joi4C9Z2aTSRCgdV-u5YO/view)。
- `wbs.md`：單一路線責任、必要前置與集中部署；不另建第二份 TODO。
- `spec/data-governance.md`：正式 Canonical 保存、Scheduler 與補收政策；模型研究採集另以 `spec/research-collection-gas-drive-colab.md` 為唯一規格。
- `status.md`：目前狀態與下一個執行序列的短入口；不是新的 source of truth。
- `todo.md`：只保存確定要做的 active queue 與未完成 acceptance；暫不做與已接受缺口見 `parking-lot.md`。
- `codex-execution-plan.md`：**按SEQ-01→08順序分派**的現行 AI 操作；舊 DRL／D01–D06 工程指令已封存。
- `execution-cards/README.md`：現行SEQ四階段操作路由；D01～D08 舊卡已移歷史區，不形成工作義務。
- `spec/research-collection-gas-drive-colab.md`：**D07-PRE 唯一新版（保留既有路徑，GAS已退役）**；官方 TWSE／TPEx→Colab→Drive 月資料夾→Colab；研究普通股（ETF 排除）、各市場70%、先盤點欄位。
- `future-market-alerts.md`：使用者指定獨立保存的未來預警增補；狀態由 `parking-lot.md` 管理，不是 active scope。
- `spec.md`：SPEC 索引；正式契約在 `spec/*.md`。
- `wbs.md`：WBS 索引；工作切片在 `wbs/*.md`。
- `ui.md`：UI 索引；頁面／元件契約在 `ui/*.md`。
- `ui/reference/user-app-final/README.md`：既有四張 PNG 的視覺基礎契約；sample 值不能作 canonical。
- `ui/visual-first-four-pages.md`：2026-10-11 [四頁視覺優先正式 UI 規格（A）](ui/visual-first-four-pages.md)。
- `ui/visual-first-delivery.md`：[已結案 D02/D03 原工程對照 B](ui/visual-first-delivery.md)，繼續作產品/資料/UI 契約參考，但不是新的 active TODO。
- `spec/operations-and-testing.md`：最新證據索引；完整舊ledger已移至archive，日常定位先看status。
- `runbook-data-supplement.md`：每日增量、按需資料處理、Admin 結果與排程修復程序。
- `spec/cicd-v2.md`：GHCR → Cloud Run Release／回滾契約；2026-10-10 dev 發布範圍曾 PASS；後續版本仍須獨立驗收，歷史收據在 [archive](archive/cicd-ghcr-api-promotion-2026-10-10.md)，不重複寫在索引。
- `runbook-dev-deploy.md`：dev API／Jobs 發布、共用鎖／lease、固定 Preview、回滾及 migration 的可重跑程序。
- `github-workflows.md`：GitHub Actions workflow 架構、composite action 與統一 workflow 開發規範。
- `runbook-pilot-calendar-repair.md`：Dev Pilot TWSE 交易日曆修復、operator IAP migration 與 bounded ingestion 驗收程序。
- `runbook-user-oauth-dev.md`：User／MCP OAuth 的專用操作與 A/B owner isolation 驗收程序。
- `runbook-parallel-live-dev.md`：dev 作為個人真實平行上線環境的操作語意。
- `secret_list.md`：Secret inventory 與相關 evidence；不得包含 secret payload。
- [Janus／omniAgent split 歷史入口](archive/omniagent-split-status.md)：非現行 Janus active gate。
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

Operations只保存當前適用摘要／歷史連結，不無限追加。原2296行ledger完整保存於 [歷史快照](archive/documentation-baseline-2026-10-15-operations-and-testing.md)，相對連結已校正；新增證據以完整SHA／run／scope／觀察時間記錄，舊FAIL不改判。Pilot舊觀察已封存；依現行政策，不重啟自然等待窗口。

## 方案 A 與模型資料入口（2026-10-21）
[變化判讀SPEC](spec/change-analysis.md) → [A-CHANGE 歷史卡](archive/document-cleanup-2026-10-25/execution-cards/a-change-analysis.md)；[四模型角色/X/Y](spec/specialist-engines.md) → [時間窗口與前處理](spec/model-feature-time-contract.md) → [D07 歷史卡](archive/document-cleanup-2026-10-25/execution-cards/d07-specialist-b9-oos.md)。唯一工作順序與驗收仍見[TODO](todo.md)。


模型生命週期細節見 [模型契約](spec/model-lifecycle.md)；舊日週分析／月評估研究指令不作本次待辦，第二版另行啟動。


## 四模型收檔／貼標／訓練目前唯一版本入口

[四模型與資料工程最新版本總索引](research/00-四模型最新版本索引.md)：兩本 v3.8.4 獨立 Colab 收檔、ChatGPT v3.8.2 貼標及產業 PIT 檢查、ChatGPT 四模型訓練介面、各角色 OOS/發布證據及 _archive 位置。舊版 Colab Notebook 與歷史研究文件保留歸檔，不再當現行工作入口。此研究流程與目前已發布的 Risk v1 模型分開。

## 四角色獨立 Colab 建模文件與 AI 指令

- [Quant 趨勢｜XGBoost 操作與開發指令](colab-models/01-quant-xgboost.md)
- [Risk 風險｜XGBoost 操作與開發指令](colab-models/02-risk-xgboost.md)
- [Fundamental 營運｜XGBoost 操作與開發指令](colab-models/03-fundamental-xgboost.md)
- [Valuation 估值｜XGBoost 操作與開發指令](colab-models/04-valuation-xgboost.md)

2026-10-25：四模型全部以本版正式上線為目標，採現有可發布artifact；必要serving／快取／報告／UI接線依SEQ-06…08。上述研究Notebook保留，調校與全面研究資料改善移至 [2027 Q1第二版](parking-lot.md#v2-2027-q1)，不是本次發布前置。模型檔存在不等於已上線，實際狀態依runtime證據。

## SEQ 外未來分期規劃

[Parking Lot 分期入口](parking-lot.md#future-stages) → [適度性／工具比較／五期規劃與 WBS](future-development-stages.md) → [逐期四階段 AI 指示](future-development-stages.md#ai-handoff)。僅為規劃文件，未啟動項目不列 Active TODO；現行 SEQ 順序與狀態仍以 [TODO](todo.md) 為準。

## 文件封存與後續維護

[2026-10-25 整理清冊與 AI 維護指示](archive/document-cleanup-2026-10-25/README.md)。歷史區不產生工作義務；無明確取代依據的有效契約、研究成果與操作程序保留。
