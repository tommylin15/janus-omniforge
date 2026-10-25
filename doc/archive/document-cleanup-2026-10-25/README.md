# 文件整理紀錄與接續指示｜2026-10-25

基準：GitHub main `17e30f15eec3a89a721399102af9ca948309c7c6`。本次僅文件整理；不改程式、不執行軟體測試或部署，也不改判歷史 PASS／FAIL／UNKNOWN。

## 範圍與判準

盤點 repository 全部 303 份 Markdown 路徑、現行文件標題／狀態及引用，逐項處理明確被取代的執行卡、已結案交接與歷史收據；完整處置清冊見 [inventory.csv](inventory.csv)。此清冊不是宣稱逐字重新驗證每份歷史研究的數據。保留有效 SPEC、UI、WBS、可重用 runbook、模型研究成果與仍有缺口的當前任務；不單按日期判斷過時。

GitHub 移動 18 份舊文件；Operations 與 status 另外保存整理前快照。Ops 從 114,496 bytes 精簡為約 6 KB，僅留最新 SEQ-04 有界證據及歷史入口。TODO 的現行任務與收據不重寫，status 改成導航，SEQ AI 卡移除過期的「下一步 SEQ-02」。

## 歷史搬移清冊

| 原位置（doc/ 下） | 歷史檔 | 理由／現行來源 |
|---|---|---|
| `execution-cards/d05-integrated-release-dev.md` | [d05-integrated-release-dev.md](execution-cards/d05-integrated-release-dev.md) | 舊分線執行卡；現行改用 SEQ-01～08，研究調校由 Parking Lot 管理 |
| `execution-cards/d06-iceberg-retention-io.md` | [d06-iceberg-retention-io.md](execution-cards/d06-iceberg-retention-io.md) | 舊分線執行卡；現行改用 SEQ-01～08，研究調校由 Parking Lot 管理 |
| `execution-cards/finops-ingestion-iceberg-ab-and-c-gate.md` | [finops-ingestion-iceberg-ab-and-c-gate.md](execution-cards/finops-ingestion-iceberg-ab-and-c-gate.md) | 舊分線執行卡；現行改用 SEQ-01～08，研究調校由 Parking Lot 管理 |
| `execution-cards/d02-full-market-snapshot-performance.md` | [d02-full-market-snapshot-performance.md](execution-cards/d02-full-market-snapshot-performance.md) | 舊分線執行卡；現行改用 SEQ-01～08，研究調校由 Parking Lot 管理 |
| `execution-cards/d08-ceo-admin-owner-report.md` | [d08-ceo-admin-owner-report.md](execution-cards/d08-ceo-admin-owner-report.md) | 舊分線執行卡；現行改用 SEQ-01～08，研究調校由 Parking Lot 管理 |
| `execution-cards/d03-four-page-charts-visual.md` | [d03-four-page-charts-visual.md](execution-cards/d03-four-page-charts-visual.md) | 舊分線執行卡；現行改用 SEQ-01～08，研究調校由 Parking Lot 管理 |
| `execution-cards/d01-holdings-trading-valuation.md` | [d01-holdings-trading-valuation.md](execution-cards/d01-holdings-trading-valuation.md) | 舊分線執行卡；現行改用 SEQ-01～08，研究調校由 Parking Lot 管理 |
| `execution-cards/d07-model-lifecycle.md` | [d07-model-lifecycle.md](execution-cards/d07-model-lifecycle.md) | 舊分線執行卡；現行改用 SEQ-01～08，研究調校由 Parking Lot 管理 |
| `execution-cards/a-change-analysis.md` | [a-change-analysis.md](execution-cards/a-change-analysis.md) | 舊分線執行卡；現行改用 SEQ-01～08，研究調校由 Parking Lot 管理 |
| `execution-cards/d07-specialist-b9-oos.md` | [d07-specialist-b9-oos.md](execution-cards/d07-specialist-b9-oos.md) | 舊分線執行卡；現行改用 SEQ-01～08，研究調校由 Parking Lot 管理 |
| `execution-cards/d04-controller-backup-handoff.md` | [d04-controller-backup-handoff.md](execution-cards/d04-controller-backup-handoff.md) | 舊分線執行卡；現行改用 SEQ-01～08，研究調校由 Parking Lot 管理 |
| `runbook-bigquery-compatibility.md` | [runbook-bigquery-compatibility.md](runbook-bigquery-compatibility.md) | 舊 BQ 路線已退役 |
| `runbook-research-simplification-wi.md` | [runbook-research-simplification-wi.md](runbook-research-simplification-wi.md) | 研究精簡已依既有邊界結案；政策見 research-simplification |
| `research-simplification-inventory.md` | [research-simplification-inventory.md](research-simplification-inventory.md) | 研究精簡已依既有邊界結案；政策見 research-simplification |
| `decision-2026-10-06-bigquery-analytics-over-iceberg.md` | [decision-2026-10-06-bigquery-analytics-over-iceberg.md](decision-2026-10-06-bigquery-analytics-over-iceberg.md) | 舊 BQ 路線已退役 |
| `research/data-governance-c0-2026-10-23.md` | [data-governance-c0-2026-10-23.md](research/data-governance-c0-2026-10-23.md) | C0/C1-A 歷史盤點；當前政策見 data-governance 與 TODO |
| `research/data-governance-c1a-2026-10-23.md` | [data-governance-c1a-2026-10-23.md](research/data-governance-c1a-2026-10-23.md) | C0/C1-A 歷史盤點；當前政策見 data-governance 與 TODO |
| `pilot-operational-evidence.md` | [pilot-operational-evidence.md](pilot-operational-evidence.md) | 早期 Pilot 觀察快照；不恢復已取消的等待門檻 |

## Drive 整理

[歷史文件資料夾](https://drive.google.com/drive/folders/14G6rs4eN8sv9cjJbkwSDHu0NvN6z4jnS)：將根目錄 10 份已確認過時文件原地移動，保留 ID 與既有分享連結：五份 GAS v0.2 模型規格（含已取消 Event）、撤案第五模型估值指示、研究精簡舊交接與 patch、已吸收的交易 UX 參考、空白重建控制草稿。新版研究入口為 [四模型總索引](../../research/00-四模型最新版本索引.md)，估值契約見 [Valuation](../../spec/valuation-range.md)。

Drive 操作表、研究成果、資料源與程式資料夾未整批搬移；沒有足夠取代證據的文件保留，不宣稱所有子資料夾內容已逐字審核。未來分期文件保留；工程狀態以 GitHub main 為準。

## AI 接續維護指示

1. 先讀 [PROJECT_RULES](../../PROJECT_RULES.md)、[TODO](../../todo.md)、[SEQ 卡](../../execution-cards/sequential-delivery.md)。歷史文件不是新工作授權；不可依舊卡重啟已取消稽核、第五模型或舊 BQ/GAS 路線。
2. 現行狀態只寫 TODO；README/status 僅導航；SPEC 保存穩定契約；runbook 保存可重用程序。不要把同一批收據複製到多份入口。
3. 新收據取代舊收據時，將完整歷史移入 archive，以日期／來源 SHA／適用範圍命名；目前 Operations 保留最新摘要與必要歷史連結。舊失敗保留原判，不因後續成功抹除。
4. 新需求先比對現行契約，直接更新同一份正式文件。未啟動需求留 Parking Lot；不要另造「最新版」「final-v2」並行權威。
5. 歸檔前確認替代來源、引用與仍有作用的操作程序；修復入站／出站相對連結。Drive 使用原 ID 移動，不刪原件或複製整套版本。
6. 未證實過時的研究成果、現役 Notebook、資料檔與操作表保留。需要內容級判斷時逐份確認，不以檔名日期自動刪除。
7. 提交前重新取得 main，保留其他工作階段的最新 TODO／SPEC 更新。本輪文件差異與本地連結檢查不是軟體驗測，不能寫成 runtime PASS。

## 文件檢查

本輪以實際 diff、搬移清冊、相對連結目的地與 Drive 目的資料夾讀回檢查；環境未提供 `/ponytail-review`，不冒稱已執行。無程式／測試／workflow 變更。既存歷史斷鏈不視為本輪新增，必要連結依搬移結果修正。
