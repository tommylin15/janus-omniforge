# Janus｜目前實作與驗收狀態

更新：2026-10-20（Asia/Taipei）。本頁只保留**最新證據摘要**，不是第二份 TODO。實作及完成狀態以 GitHub `main`、CI／deploy／GCP dev／資料／Owner readback 為準；完整歷史在 [原狀態快照](archive/status-before-consolidation-2026-10-19.md)，近期收據見 [Operations](spec/operations-and-testing.md)。

## 已有範圍的結案

| 項目 | 最新已知證據 | 未覆蓋事項 |
|---|---|---|
| D01～D05 | 2026-10-17 使用者核准 `CLOSED/PASS`；部分嚴格 acceptance 屬 `USER_ACCEPTED/WAIVED`，參見 [結案](archive/d01-d05-relaxed-acceptance-closure-2026-10-17.md) | 豁免不冒稱實測 PASS，不重開 |
| DRL-01 | 2026-10-19 六股 2025Q4 EPS Stage→Core→serving、正式／Preview 6/6 API、兩年 PE/PB 12/12 及相關回滾/畫面在指定 scope PASS；[證據](archive/drl01-completed-2026-10-19.md) | 自然 daily/weekly Ledger `NOT_VERIFIED`；TTM／歷史 strict PIT 未認證 |
| FINOPS-AB（D06 併單） | 2026-10-18 四 Jobs、Core/Mart retention、週維護 env 切換有歷史 Actions PASS；Current-only snapshot 使用者已核准 | 實際清理 objects/bytes 與費用成效仍須原執行收據；兩日 I/O 比對已取消 |
| 持股／關注背景補收 | 2026-10-19 migration 066、8 檔回補、8/8 API readback 在 [舊 TODO 收據](archive/todo-before-consolidation-2026-10-19.md) | 產品8檔 ready 不等於全市場24月研究 PIT/OOS 完備 |
| Admin v2 | 2026-10-19 四頁、使用分析與適用 Flutter/Python tests 按 [原 TODO](archive/todo-before-consolidation-2026-10-19.md) 之 scope PASS | D07 管理模型與 D08 Owner 報告功能另外驗收 |

## 下一個執行範圍

| 工項 | 狀態 | 判定 |
|---|---|---|
| **D07-PRE** | **DESIGN_DECIDED／PARTIAL** | Colab-only 資料整理/訓練目標已定案；24月合格樣本、Colab 實跑/回傳、source training-use、成本、月度人工/自動化尚未整體實證 |
| **D07** | **PLANNED** | B5/B6 fixed source 與 B7 原 Mart 月度歷史能力有 PASS；B9 ML 優勢、Colab 訓練遷移及五角色正式 OOS 未驗收 |
| **D08** | **PLANNED** | P0-V Gateway 先前技術鏈測過，但 Janus 有效 Fact Pack、Owner authenticated 報告／publication 仍未驗收 |

**STAGE-48H 2026-10-20 最新工程狀態：DEPLOY PASS／LIVE FEATURE PARTIAL。** [歷史來源追查 #39344827401](https://github.com/tommylin15/janus-omniforge/actions/runs/39344827401) 證明先前 2,050 objects／650,115,151 bytes 由 `janus-ingestion-core-swsb6` 於 2026-10-19T15:40Z 實刪；[受控 apply #39337954028](https://github.com/tommylin15/janus-omniforge/actions/runs/39337954028) 另刪 453／489,166 bytes，兩次 generation readback 均 PASS，**2,503 件／650,604,317 bytes 有實機歸因**，非 Bucket lifecycle（未設 Delete rule）。新 Stage 原始內容跨 execution 共用與個別 provenance、Admin GCS 六桶一鍵盤點的程式、1,515 Python tests/Flutter、四 GHCR digest [Release #39345633766](https://github.com/tommylin15/janus-omniforge/actions/runs/39345633766) PASS；[四 Jobs rollout #39346705950](https://github.com/tommylin15/janus-omniforge/actions/runs/39346705950) PASS，[Jobs post-rollout #39348777969](https://github.com/tommylin15/janus-omniforge/actions/runs/39348777969) 實機檢查四 Job immutable digest/config、Scheduler ENABLED、0 nonterminal PASS；[API 100% Promotion #39348904538](https://github.com/tommylin15/janus-omniforge/actions/runs/39348904538) PASS 並完成可逆 traffic rollback rehearsal；[獨立 live API #39349499000](https://github.com/tommylin15/janus-omniforge/actions/runs/39349499000) PASS：`janus-api-00566-biq` 100% 流量、同一 SHA `a7e1e7c276e735f629f90525f7f7cf6e7411b07b`、build/image/health 驗證、匿名 POST Admin inventory = 401。**未驗收：**真實登入 Admin 的六桶 metadata 正向讀取與 API IAM、真實新 Stage 去重重用／跨 execution manifest、當日 18:30 自然 Stage-only due + 48h 收據。每週 Iceberg／Core／Mart 維護不變；D07-PRE 在另一對話，不列本工程完成前提。

**10/20 六桶 GCS 獨立 readback：** [FinOps #39349927067](https://github.com/tommylin15/janus-omniforge/actions/runs/39349927067) OBSERVED_COMPLETE（GCP CI WIF 身分、不是 API Admin positive）；六桶 current **1,055,828,835 bytes**、noncurrent **16,877,094 bytes**、soft-deleted 0，Stage **6,265 objects／406,329,684 bytes**，其中 **4,927 objects／96,321,204 bytes** 的 metadata age 已超過 7 天、潛在相同 MD5 額外容量 **165,308,239 bytes**。**新風險：**4,927 個老物件是否確實受到有效 active execution manifest 引用，尚未以 PG 實際狀態逐筆對照；MD5 候選不能直接刪。六桶 CI 成功不代表 API serving IAM 或 Admin OAuth 正向 GCS 一鍵讀取 PASS。

**本對話工作邊界：**STAGE-48H 僅剩 Admin 正向六桶查詢、Stage 真實 payload 重用及自然 18:30 Stage-only 清理三項實機驗收；其餘模型/D07-PRE 已交獨立對話。本工程此時 **PARTIAL**，不得因 rollout/promotion PASS 即宣稱功能完整。其他跨專案治理與非阻擋觀察見 [TODO](todo.md)。
