# Janus｜目前實作與驗收狀態

更新：2026-10-20（Asia/Taipei）。**此頁是現況摘要，不是第二份 TODO。** 現行工作順序與未完成驗收以 [唯一 Active TODO](todo.md) 為準；完整收據集中 [Operations](spec/operations-and-testing.md)，既往狀態見 [archive](archive/status-before-consolidation-2026-10-19.md)。

## 已完成／結案

- **D01～D05、DRL-01、FINOPS-AB（含 D06）、背景持股／關注股補收與 Admin v2**：按各自已核准的實際驗收範圍 `CLOSED／PASS` 或 `USER_ACCEPTED`，不重開已接受的歷史 gate。
- **D07 舊 GCP／BQ 研究路線退役：CLOSED。** Controller 舊 `specialist-retrain` 與 Mart 研究 fit 入口已移除；[完整 GHCR Release #39355867356](https://github.com/tommylin15/janus-omniforge/actions/runs/39355867356)、[四 Jobs rollout #39356643823](https://github.com/tommylin15/janus-omniforge/actions/runs/39356643823)、[四 Jobs/Scheduler readback #39358461946](https://github.com/tommylin15/janus-omniforge/actions/runs/39358461946) PASS。
- **GCP/BQ 專屬研究清理：CLOSED。** [實機清理 #39359490206](https://github.com/tommylin15/janus-omniforge/actions/runs/39359490206)、[資源清單 #39359661801](https://github.com/tommylin15/janus-omniforge/actions/runs/39359661801)：8 Cloud Run Jobs、1 個現役正式 Scheduler、BigQuery 1 個空 dataset／0 table／0 view，**沒有舊研究專屬殘留；實刪 0**。沒有具體異常證據，不為假設性可能性新增待辦。

## 當前四個工作包

| 工作包 | 目前狀態與可操作的剩餘驗收 |
|---|---|
| **P0 STAGE-48H** | **部署與既有清理／跨 execution 去重 PASS；功能收尾中。** [4,927 件／96,321,204 bytes 實刪 #39355428497](https://github.com/tommylin15/janus-omniforge/actions/runs/39355428497)、[shared raw/provenance #39358645373](https://github.com/tommylin15/janus-omniforge/actions/runs/39358645373)、[48h dry-run #39359037869](https://github.com/tommylin15/janus-omniforge/actions/runs/39359037869) PASS。只餘 2026-10-20 18:30 自然 Stage-only 執行收據、Admin OAuth 登入後六桶一鍵正向驗收；已通過的刪除／部署不再重做。 |
| **P1 D07-PRE** | **資料鏈建置中。** `research/gas/field_probe.gs` 是小範圍欄位探測程式，尚非實測全市場月檔；接續實抓合法公開欄位、GAS 分批→Drive `YYYY-MM.zip`／quality／SHA、Colab 讀取 smoke。研究分市場×dataset ≥70%，不拿完整 24 月 PIT 作採集前置。 |
| **P2 D07** | **待開發。** 五角色 Colab 訓練／OOS、Janus Mart Registry／推論／rollback／Admin 品質；Quant／Risk 優先，Event 缺真人標籤保留 rules。 |
| **P3 D08** | **待開發。** 有效五角色 Fact Pack 後之 CEO／Admin／Owner 受控報告與真人登入歷史驗收；沿用已驗證 Gateway 技術鏈。 |

## 文件與執行約束

採用 [有界驗收結案原則](PROJECT_RULES.md#111-有界驗收與結案原則2026-10-20-使用者決策)：**原定範圍查核成功且沒有具體異常即結案**，不要求排除一切未知情境；實際失敗或原定未驗收條件仍依證據處理。新版研究唯一來源為 [GAS → Drive → Colab 契約](spec/research-collection-gas-drive-colab.md)，正式 Core／Owner／Stage／週 Iceberg 不受舊研究退役影響。
