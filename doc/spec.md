# Janus — Project Specification

版本：2.1
更新：2026-10-19
狀態：索引；正式契約依下列領域切片為準

## 全域環境定位

目前 `dev` 是 Janus 個人使用階段的主要真實運行環境（parallel-live environment），可直接使用已核准的真實資料、API、MCP、OAuth、Cloud Run／Job／Scheduler、PostgreSQL／Iceberg 與實際使用流程。`prod` 是未來對外、多使用者或高可靠性營運的強化階段，不是目前功能可真實使用的前置條件。

Fixture／mock／localhost simulation 只補足真實服務難以安全重現的 timeout、cancel、disconnect、error、secret-redaction 等異常測試，不得取代主要 real-path acceptance，也不得單獨成為 WBS blocker。research-only、canonical、PIT／future leakage、provenance、source authorization、publication 與 public/private isolation 邊界仍依 active SPEC 執行。

## AI 最小讀取規則

先讀本索引，再只讀任務直接相關的切片。只有遇到跨領域契約、安全邊界或引用缺失時才增讀其他切片；目前實作與完成證據另讀 GitHub `main`、runtime 及 `spec/operations-and-testing.md`。

已結案 D01～D05／DRL／Admin 的有效業務契約仍見 [持股優先](spec/holdings-first.md) 與相應 domain SPEC，不代表當前仍需重做；**目前全部 active 執行依 [唯一 TODO](todo.md) 的 P0 作業安全、A-CHANGE／2.0、04 Valuation 估值區間子功能、D07-PRE／治理、四模型研究與 D08 分線；責任與跨線合流依 [WBS](wbs.md)**。

全上市櫃母體、TWSE缺失率≤10%／TPEx≤30% coverage、批次總控與即時快照見 [新契約](spec/full-market-batch-policy.md)。

資料保存、批次、補資料及模型研究先經 [統一資料治理入口](spec/data-governance.md) 路由；已改 current-only Snapshot、週維護以現役 Controller/env/occurrence 驗收。新增跨領域 [因子收錄、容量與保存矩陣](spec/factor-coverage-retention-ledger.md)：串接全市場／Deep Coverage／私人資料收錄範圍、估算筆數與 Stage/Core/Mart 到期處置。期限治理權威仍是 [公開資料刪除治理](spec/retention-governance.md)，非獨立歷史搬移授權。

## 領域路由

| 任務 | 必讀切片 | 條件增讀 |
|---|---|---|
| 產品目標、優先序、Token-first specialist、On-demand CEO、全域架構決策 | [產品目標與架構決策](spec/overview-and-decisions.md) | 涉及 API 或部署時再讀對應切片 |
| Monorepo、服務責任、GCP 拓撲 | [Monorepo 與 GCP 拓撲](spec/repository-and-gcp.md) | 涉及 IAM／release 時讀品質與發布 |
| Iceberg／PostgreSQL、公開／私人資料、來源、Ingestion | [儲存、資料供應與 Ingestion](spec/storage-data-and-ingestion.md) | 產製 Mart 時讀 Intelligence |
| Mart、Fact Pack、四模型及舊 event 事實 specialist 相容、evaluation、On-demand CEO boundary、publication、DuckDB boundary | [Intelligence、Aggregator 與 Runtime](spec/intelligence-and-governance.md) | specialist 細節再讀 [Specialist Engines](spec/specialist-engines.md) |
| 公開資料 retention／Stage-Core-Mart 清理與 current-only snapshot | [公開資料保存治理](spec/retention-governance.md) | 排程、補收先讀 [統一治理入口](spec/data-governance.md)；真實執行查 Operations |
| FastAPI、User／Admin、MCP／OAuth、GCP 開發與 CI/CD | [API、User、Admin 與交付](spec/api-and-delivery.md) | UI 行為另讀 UI 索引 |
| 非功能需求、驗收與發布 gate | [非功能需求與 Release Gate](spec/quality-and-release.md) | 需要現況證據時讀測試摘要 |
| 最新測試／dev 驗收摘要 | [Operations and Testing](spec/operations-and-testing.md) | 不需預讀其他歷史紀錄 |

執行工作前另依 [TODO](todo.md) 取得當前優先序與驗收條件，依 [WBS](wbs.md) 路由到指定工作切片；UI 工作再讀 [UI](ui.md)。

2026-10-15 補強契約：[系統建置與驗收補強](spec/system-development-contract.md)；狀態與執行順序只看TODO。

## 2026-10-24 最新 SPEC ↔ WBS ↔ TODO 串接

- **正式文件追溯順序**：[PROJECT_RULES](PROJECT_RULES.md) → 指定領域 SPEC → [WBS 依賴矩陣](wbs.md) → [唯一 Active TODO](todo.md) → [Operations 驗收證據](spec/operations-and-testing.md)。
- **04 Valuation 估值參考區間子功能**：[04 情境子契約](spec/valuation-range.md) 正式取消第五模型，保留 PE/PB 研究並將唯一價格區間卡、EPS/BVPS/歷史倍數、來源及 publication 整合於 04；公告／變化提醒仍由 [A-CHANGE](spec/change-analysis.md) 提供。RV-01…06 在 TODO 是 04 功能工作，現役舊五筆 event baseline 相容遷移需實際驗收。
- **治理 C0/C1、57 leases**：[資料治理](spec/data-governance.md)／[C1-A Live](research/data-governance-c1a-2026-10-23.md)。現況不等於 C1-B 清掃許可，P0-2 作業收斂不自動阻塞研究。
- **研究資料與四模型**：[最新研究索引](research/00-四模型最新版本索引.md) 管理實際 Notebook／資料版本；[模型時間](spec/model-feature-time-contract.md)、[模型生命週期](spec/model-lifecycle.md) 管理獨立 OOS／promotion；四角色可獨立研究，不能修改現役 Risk。
- **Janus 2.0**：[Drive 核准設計](https://drive.google.com/file/d/15sT38MsE96RAwD-aZnAHvOvEINtythPO/view) 是研究／產品目標，不代表已部署；最新 UI 仍讀 [UI 契約](ui.md) 與 runtime。

## 方案 A 與模型資料入口（2026-10-21）
[變化判讀SPEC](spec/change-analysis.md) → [A-CHANGE AI卡](execution-cards/a-change-analysis.md)；[四模型角色/X/Y](spec/specialist-engines.md) → [時間窗口與前處理](spec/model-feature-time-contract.md) → [D07 AI卡](execution-cards/d07-specialist-b9-oos.md)。唯一工作順序與驗收仍見[TODO](todo.md)。


模型開發/運作/回收唯一契約：[模型生命週期](spec/model-lifecycle.md)，涵蓋四模型建議資料量及舊 event 事實相容、GCS候選與受控發布、批次推論、結果成熟、36月回饋保存與每月評估；實作狀態依TODO。

