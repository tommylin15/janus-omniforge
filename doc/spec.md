# Janus — Project Specification

版本：1.9
日期：2026-09-20
狀態：索引；正式契約依下列領域切片為準

## AI 最小讀取規則

先讀本索引，再只讀任務直接相關的切片。只有遇到跨領域契約、安全邊界或引用缺失時才增讀其他切片；測試現況另讀 operations-and-testing。

## 領域路由

| 任務 | 必讀切片 | 條件增讀 |
|---|---|---|
| 產品目標、優先序、AI engine、全域架構決策 | [產品目標與架構決策](spec/overview-and-decisions.md) | 涉及 API 或部署時再讀對應切片 |
| Monorepo、服務責任、GCP 拓撲 | [Monorepo 與 GCP 拓撲](spec/repository-and-gcp.md) | 涉及 IAM／release 時讀品質與發布 |
| Iceberg／PostgreSQL、公開／私人資料、來源、Ingestion | [儲存、資料供應與 Ingestion](spec/storage-data-and-ingestion.md) | 產製 Mart 時讀 Intelligence |
| Mart、Fact Pack、AI analyst、CIO、Aggregator、publication、DuckDB boundary | [Intelligence、Aggregator 與 Runtime](spec/intelligence-and-governance.md) | 對外提供資料時讀 API 與交付 |
| FastAPI、User／Admin、聊天室、GCP 開發與 CI/CD | [API、User、Admin 與交付](spec/api-and-delivery.md) | UI 行為另讀 UI 索引 |
| 非功能需求、驗收與發布 gate | [非功能需求與 Release Gate](spec/quality-and-release.md) | 需要現況證據時讀測試摘要 |
| 最新測試／dev 驗收摘要 | [Operations and Testing](spec/operations-and-testing.md) | 不需預讀其他歷史紀錄 |

執行工作前另依 [TODO](todo.md) 取得當前優先序與驗收條件，依 [WBS](wbs.md) 路由到指定工作切片；UI 工作再讀 [UI](ui.md)。
