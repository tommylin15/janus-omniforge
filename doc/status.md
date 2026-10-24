# Janus｜目前實作與驗收狀態

更新：2026-10-24（多線文件整理；OPS-P0-2 已有真實 Controller-only dev rollout 收據）。**此頁是現況摘要，不是第二份 TODO。** 現行工作順序與未完成驗收以 [唯一 Active TODO](todo.md) 為準；完整收據集中 [Operations](spec/operations-and-testing.md)，既往狀態見 [archive](archive/status-before-consolidation-2026-10-19.md)。

## 2026-10-24 多工作線狀態覆蓋（較下方 10/22 歷史表更新）

此頁較下方 A-CHANGE／D07-PRE／Risk 研究敘述是 **2026-10-22 當時截面**，不得作目前完結狀態或下一任務順序。**唯一 active 順序/狀態是 [TODO §1](todo.md)**；跨線依賴見 [WBS](wbs.md)；本次只改文件，不宣稱新 runtime PASS。

- **OPS-P0-2｜5 天工作排除／Controller live（CLOSED／PASS，2026-10-24）**：使用者核准超過 5×24h 的 analysis／collection 只排除追查與恢復，不實體刪除。一般 queue SQL 5 天上限、persisted pending 派送前重新核對、舊 30 天 one-shot override 停用均已實作；[targeted CI #40048549032](https://github.com/tommylin15/janus-omniforge/actions/runs/40048549032) 37 PASS；首輪完整 Release 舊測試 2 FAIL 已修正，[正式 GHCR #40049195127](https://github.com/tommylin15/janus-omniforge/actions/runs/40049195127) 完整 PASS；[Controller-only dev #40049724410](https://github.com/tommylin15/janus-omniforge/actions/runs/40049724410) `completed/success`：5 個 rollout 測試 PASS、read-only canary PASS、Scheduler ENABLED、目前 image digest `sha256:ccc4decc6f38b12e0b0ed62c2f22ab3b9e82a3fad336f10912671b1a028dd0f2`、`data_mutations=0`、`queue_recovery_dispatches=0`、Global Lease 已釋放。**不宣稱原 57 筆執行終態已補正**；原 57 超齡歷史按 §1.8.1 撤出追查，PG／GCS 紀錄保持。
- **P0-1**：備份分離清理已經歷有界 dry-run/apply PASS，但首個自然排程未取得證據；僅待其真實 occurrence readback，不重跑全部。
- **C1-A／資料治理（PARTIAL）**：[13張 Core/Mart live metadata #40052513368](https://github.com/tommylin15/janus-omniforge/actions/runs/40052513368) PASS、[11/11 Mart 現役 retention 已完成 table-scan 收據 #40052878512](https://github.com/tommylin15/janus-omniforge/actions/runs/40052878512) PASS；**非維護業務 reader 仍 UNKNOWN、每張表獨立 backup/rebuild/rollback NOT_VERIFIED**。Core market_volume 與 ohlcv 共同14欄、前者獨有 stock_name、後者獨有 change_percent，雙表均 KEEP、不做資料等價推論。九張 Mart 退役候選維持 BLOCKED_FOR_RETIREMENT，**C1-B 刪表／欄許可為 0**；逐表見 [C1-A §23](research/data-governance-c1a-2026-10-23.md)。
- **Janus 2.0／A-CHANGE**：已有部分程式與 UI，但原定整包 dev/Owner 驗收未結案；2.0 建議為設計方向，**非已發布新 UI**。
- **第五角色**：2026-10-24 已核准以 `valuation_range` 取代 Event 模型，[SPEC](spec/valuation-range.md) 已寫，**NOT_IMPLEMENTED**；公告/事實提醒保留。
- **四模型研究**：Quant 研究 r1 凍結且不可發布；Risk 依 [PROJECT_RULES §1.12](PROJECT_RULES.md) 最新受控回滾 **DETERMINISTIC + SHADOW_UNVALIDATED**（本輪未重新查 live）；Fundamental XGB 5% RC1 僅研究；Valuation 財務 mapping、單位及 PIT 尚未具完整資料驗證；四模型各自 OOS/promotion gate 未通過。
- **D08**：可平行準備事實 Fact Pack／Owner 受控報告，模型數值只有相應模型正式發布後才可納入。

## 已完成／結案

- **Life 風格股市 UI 漸層色卡：USER_ACCEPTED／CLOSED（2026-10-22）**。Flutter 顯示改版 `1fc29ea` 涵蓋首頁大盤、關注、持股摘要與緊湊列、個股標頭，保留台股紅漲綠跌、實際行情及缺值語意。完整 [GHCR Release #39757237689](https://github.com/tommylin15/janus-omniforge/actions/runs/39757237689)、[0% candidate #39760791053](https://github.com/tommylin15/janus-omniforge/actions/runs/39760791053)、[OAuth／Owner 負向邊界 #39761510405](https://github.com/tommylin15/janus-omniforge/actions/runs/39761510405)、[dev API-only 100% 切流／回滾 #39763193647](https://github.com/tommylin15/janus-omniforge/actions/runs/39763193647) 均 `completed/success`；使用者於本對話明確回覆「驗收完畢」。此項僅 UI presentation，不代表 A-CHANGE 其他工作包或 D07 Risk 模型 gate 結案。


- **當日損益／ETF 盤中刷新與 YTD 同行 UI 修正：USER_ACCEPTED／CLOSED（2026-10-22）**。本人於本次對話明確回覆「驗收完成」，確認此次手機介面與 ETF／上櫃盤中損益修正的既定驗收範圍。正式 dev API-only 100% source `a3a3b30648e7`、full GHCR、OAuth 負向驗證、0% candidate、實際新→舊→新回滾與 lease 釋放均 PASS，詳見 [Operations](spec/operations-and-testing.md)。真人接受是使用者回報，不取代未提供的逐檔原始報價、金額或自動量測收據；不額外重開已通過的發版 gate。


- **持股摘要（萬元）、最新持股當日損益、ETF／TPEx MIS 與非普通股資訊入口：2026-10-22 dev API-only 100% 發布 PASS。** 正式 GHCR source `566522998769`，schema migration 067、Python／Flutter 完整 Release、0% candidate、OAuth／private 負向驗證、API 新→舊→新流量回滾均有 [Operations 統一收據](spec/operations-and-testing.md#2026-10-22持股-uietf上櫃盤中行情與當日損益正式-dev-api-only-發版-pass)；未另外冒稱已登入逐檔盤中正向畫面驗收。


- **D01～D05、DRL-01、FINOPS-AB（含 D06）、背景持股／關注股補收與 Admin v2**：按各自已核准的實際驗收範圍 `CLOSED／PASS` 或 `USER_ACCEPTED`，不重開已接受的歷史 gate。
- **D07 舊 GCP／BQ 研究路線退役：CLOSED。** Controller 舊 `specialist-retrain` 與 Mart 研究 fit 入口已移除；[完整 GHCR Release #39355867356](https://github.com/tommylin15/janus-omniforge/actions/runs/39355867356)、[四 Jobs rollout #39356643823](https://github.com/tommylin15/janus-omniforge/actions/runs/39356643823)、[四 Jobs/Scheduler readback #39358461946](https://github.com/tommylin15/janus-omniforge/actions/runs/39358461946) PASS。
- **GCP/BQ 專屬研究清理：CLOSED。** [實機清理 #39359490206](https://github.com/tommylin15/janus-omniforge/actions/runs/39359490206)、[資源清單 #39359661801](https://github.com/tommylin15/janus-omniforge/actions/runs/39359661801)：8 Cloud Run Jobs、1 個現役正式 Scheduler、BigQuery 1 個空 dataset／0 table／0 view，**沒有舊研究專屬殘留；實刪 0**。沒有具體異常證據，不為假設性可能性新增待辦。

## 當前工作包

2026-10-21文件決策：方案A事實解讀/站內盤前盤後優先；模型與X/Y/窗口已定版，**A-CHANGE 已啟動實作及集中驗收；D07 Risk 已在研究環境實際訓練並完成 OOS，尚未部署正式模型**。執行順序只看TODO。下列既有runtime狀態不因文件更新改判。

| 工作包 | 目前狀態與可操作的剩餘驗收 |
|---|---|
| **STAGE-48H CLOSED** | 2026-10-23 已授權六桶唯讀 IAM 修復並逐桶讀回；正式 Admin 六桶全 OBSERVED，合計 902.71 MB／7,638 件。既有清理與發布未重做。證據見 [Operations](spec/operations-and-testing.md)。 |
| **P1 A-CHANGE** | **IN_PROGRESS**：使用者已啟動 A1～A4 整包；事實／跨日狀態／盤前盤後與首頁／個股接線已實作，集中 targeted／CI／dev／真實 API/UI 驗收進行中，尚未結案。 |
| **P1 D07-PRE** | **21 個月 Drive r1 實際封存、SHA 與普通股研究品質 PASS（TWSE ≥90%、TPEx ≥70%）；Risk 研究 OOS 已實跑完成。** 已確認 799,468 行／1,979 有行情股票；Rolling20 vs Ridge：181,557 OOS 行 MAE 改善8.49%，但2026 Q1 walk-forward 退步7.09%，仍是 `RESEARCH_OOS_ONLY_NOT_PROMOTABLE`。來源授權、歷史PIT與公司行動留在D07正式promotion gate；研究收據見 [Risk OOS](archive/d07-risk-oos-real-2026-10-21.md)。Colab本人執行／新版CI尚無收據。 |
| **P2 D07** | **Risk v0 五因子及 v1 八因子研究 OOS 已完成，均未發布。** v1 在21月現行普通股名冊真實資料上，同樣本 MAE 為0.127537，較 v0 0.133647 改善4.57%；四段回溯診斷改善但非 untouched holdout；[v1研究收據](archive/d07-risk-v1-ohlcv-oos-2026-10-22.md)。Colab本人重跑、CI與正式promotion gate未通過；其他角色仍待開發。 現行 Risk 維持baseline，Quant等其他角色之 Colab OOS、Janus Mart Registry／推論／rollback／Admin 品質未完成；Event 缺真人標籤仍採rules。 |
| **P3 D08** | **待開發。** 有效五角色 Fact Pack 後之 CEO／Admin／Owner 受控報告與真人登入歷史驗收；沿用已驗證 Gateway 技術鏈。 |

## 文件與執行約束

採用 [有界驗收結案原則](PROJECT_RULES.md#111-有界驗收與結案原則2026-10-20-使用者決策)：**原定範圍查核成功且沒有具體異常即結案**，不要求排除一切未知情境；實際失敗或原定未驗收條件仍依證據處理。新版研究唯一來源為 [Colab → Drive 月資料夾契約](spec/research-collection-gas-drive-colab.md)，正式 Core／Owner／Stage／週 Iceberg 不受舊研究退役影響。
