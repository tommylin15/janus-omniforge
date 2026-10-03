# Janus — Project Specification

版本：2.1
日期：2026-10-03
狀態：索引；正式契約依下列領域切片為準

## 全域環境定位

目前 `dev` 是 Janus 個人使用階段的主要真實運行環境（parallel-live environment），可直接使用已核准的真實資料、API、MCP、OAuth、Cloud Run／Job／Scheduler、PostgreSQL／Iceberg 與實際使用流程。`prod` 是未來對外、多使用者或高可靠性營運的強化階段，不是目前功能可真實使用的前置條件。

Fixture／mock／localhost simulation 只補足真實服務難以安全重現的 timeout、cancel、disconnect、error、secret-redaction 等異常測試，不得取代主要 real-path acceptance，也不得單獨成為 WBS blocker。research-only、canonical、PIT／future leakage、provenance、source authorization、publication 與 public/private isolation 邊界仍依 active SPEC 執行。

## AI 最小讀取規則

先讀本索引，再只讀任務直接相關的切片。只有遇到跨領域契約、安全邊界或引用缺失時才增讀其他切片；目前實作與完成證據另讀 GitHub `main`、runtime 及 `spec/operations-and-testing.md`。

## 領域路由

| 任務 | 必讀切片 | 條件增讀 |
|---|---|---|
| 產品目標、優先序、Token-first specialist、On-demand CEO、全域架構決策 | [產品目標與架構決策](spec/overview-and-decisions.md) | 涉及 API 或部署時再讀對應切片 |
| Monorepo、服務責任、GCP 拓撲 | [Monorepo 與 GCP 拓撲](spec/repository-and-gcp.md) | 涉及 IAM／release 時讀品質與發布 |
| Iceberg／PostgreSQL、公開／私人資料、來源、Ingestion | [儲存、資料供應與 Ingestion](spec/storage-data-and-ingestion.md) | 產製 Mart 時讀 Intelligence |
| Mart、Fact Pack、五 specialist、evaluation、On-demand CEO boundary、publication、DuckDB boundary | [Intelligence、Aggregator 與 Runtime](spec/intelligence-and-governance.md) | specialist 細節再讀 [Specialist Engines](spec/specialist-engines.md) |
| 公開資料 retention／Stage-Core-Mart 清理與 reference fence | [公開資料刪除治理](spec/retention-governance.md) | 需要 runtime evidence 時讀 Operations |
| FastAPI、User／Admin、MCP／OAuth、GCP 開發與 CI/CD | [API、User、Admin 與交付](spec/api-and-delivery.md) | UI 行為另讀 UI 索引 |
| 非功能需求、驗收與發布 gate | [非功能需求與 Release Gate](spec/quality-and-release.md) | 需要現況證據時讀測試摘要 |
| 最新測試／dev 驗收摘要 | [Operations and Testing](spec/operations-and-testing.md) | 不需預讀其他歷史紀錄 |

執行工作前另依 [TODO](todo.md) 取得當前優先序與驗收條件，依 [WBS](wbs.md) 路由到指定工作切片；UI 工作再讀 [UI](ui.md)。