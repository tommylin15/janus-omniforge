# Janus｜目前實作與驗收狀態

更新：2026-10-21（Asia/Taipei）。**此頁是現況摘要，不是第二份 TODO。** 現行工作順序與未完成驗收以 [唯一 Active TODO](todo.md) 為準；完整收據集中 [Operations](spec/operations-and-testing.md)，既往狀態見 [archive](archive/status-before-consolidation-2026-10-19.md)。

## 已完成／結案

- **D01～D05、DRL-01、FINOPS-AB（含 D06）、背景持股／關注股補收與 Admin v2**：按各自已核准的實際驗收範圍 `CLOSED／PASS` 或 `USER_ACCEPTED`，不重開已接受的歷史 gate。
- **D07 舊 GCP／BQ 研究路線退役：CLOSED。** Controller 舊 `specialist-retrain` 與 Mart 研究 fit 入口已移除；[完整 GHCR Release #39355867356](https://github.com/tommylin15/janus-omniforge/actions/runs/39355867356)、[四 Jobs rollout #39356643823](https://github.com/tommylin15/janus-omniforge/actions/runs/39356643823)、[四 Jobs/Scheduler readback #39358461946](https://github.com/tommylin15/janus-omniforge/actions/runs/39358461946) PASS。
- **GCP/BQ 專屬研究清理：CLOSED。** [實機清理 #39359490206](https://github.com/tommylin15/janus-omniforge/actions/runs/39359490206)、[資源清單 #39359661801](https://github.com/tommylin15/janus-omniforge/actions/runs/39359661801)：8 Cloud Run Jobs、1 個現役正式 Scheduler、BigQuery 1 個空 dataset／0 table／0 view，**沒有舊研究專屬殘留；實刪 0**。沒有具體異常證據，不為假設性可能性新增待辦。

## 當前工作包

2026-10-21文件決策：方案A事實解讀/站內盤前盤後優先；模型與X/Y/窗口已定版，**DOC_UPDATED，尚未新增實作/訓練/部署**。執行順序只看TODO。下列既有runtime狀態不因文件更新改判。

| 工作包 | 目前狀態與可操作的剩餘驗收 |
|---|---|
| **P0 STAGE-48H** | **原部署／清理／去重及 10/20 自然 Stage-only 執行 PASS；僅餘 Admin OAuth 六桶正向驗收。** [原 4,927 件實刪 #39355428497](https://github.com/tommylin15/janus-omniforge/actions/runs/39355428497)、[shared raw #39358645373](https://github.com/tommylin15/janus-omniforge/actions/runs/39358645373)、[自然執行讀回 #39523200448](https://github.com/tommylin15/janus-omniforge/actions/runs/39523200448)：Controller 18:31 tick，worker 18:33 terminal／generation PASS，該輪實刪 1,025 件／265,691,880 bytes，週維護 true；直接 PG occurrence row 未另查。既有刪除／部署不重做。 |
| **P1 A-CHANGE** | 規格與AI卡已定版；事實解讀/變化狀態/盤前盤後/UI待後續工程。 |
| **P1 D07-PRE** | **Colab-first 程式已建／待真實採集。** 官方 TWSE/TPEx 整市場逐日抓取、普通股名冊白名單、`YYYY-MM/` 資料夾、續跑 SHA 與 Risk reader 已建立；GAS 路線退役。缺 Colab 實抓月資料讀回、歷史已下市股票母體及正式70%證據，研究資料仍 PROBE。 |
| **P2 D07** | **待開發。** 五角色 Colab 訓練／OOS、Janus Mart Registry／推論／rollback／Admin 品質；Quant／Risk 優先，Event 缺真人標籤保留 rules。 |
| **P3 D08** | **待開發。** 有效五角色 Fact Pack 後之 CEO／Admin／Owner 受控報告與真人登入歷史驗收；沿用已驗證 Gateway 技術鏈。 |

## 文件與執行約束

採用 [有界驗收結案原則](PROJECT_RULES.md#111-有界驗收與結案原則2026-10-20-使用者決策)：**原定範圍查核成功且沒有具體異常即結案**，不要求排除一切未知情境；實際失敗或原定未驗收條件仍依證據處理。新版研究唯一來源為 [Colab → Drive 月資料夾契約](spec/research-collection-gas-drive-colab.md)，正式 Core／Owner／Stage／週 Iceberg 不受舊研究退役影響。
