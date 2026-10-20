# Janus｜目前實作與驗收狀態

更新：2026-10-20（Asia/Taipei）。本頁只保留**最新證據摘要**，不是第二份 TODO。實作及完成狀態以 GitHub `main`、CI／deploy／GCP dev／資料／Owner readback 為準；完整歷史在 [原狀態快照](archive/status-before-consolidation-2026-10-19.md)，近期收據見 [Operations](spec/operations-and-testing.md)。

**2026-10-20 D07 新架構與退役狀態：**新版研究採集採 GAS→私有 Drive 每月 ZIP→Colab，普通股／ETF排除、研究70%門檻；舊 Controller 月度 retrain 與 workflow 已自 GitHub main 移除，Mart retrain/OOS 入口已自原始程式拆除。**舊月度 retrain 入口已隨 [四 Job rollout #39356643823](https://github.com/tommylin15/janus-omniforge/actions/runs/39356643823) 部署，且 [readback #39358461946](https://github.com/tommylin15/janus-omniforge/actions/runs/39358461946) 已確認四 Job digest/config；但歷史 pending 與其他 GCP／BigQuery 獨立研究資源實際退役仍須 D07 對話驗收**，不可聲稱 live 清理完成。詳見 [新研究契約](spec/research-collection-gas-drive-colab.md)、[唯一 TODO](todo.md)。

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

**10/20 最新六桶獨立 GCS metadata readback：**[FinOps #39356190151](https://github.com/tommylin15/janus-omniforge/actions/runs/39356190151) OBSERVED_COMPLETE：六桶 current **968,619,706 bytes**、noncurrent **16,877,094 bytes**、soft-deleted 0。Stage current **1,457 objects／318,859,190 bytes**，**超過7天 0 件**；同 hash 潛在重複 **126,687,768 bytes** 僅供調查，不是已確認可刪容量。CI 身分的六桶讀回不等於 API serving IAM 或 Admin OAuth 正向按鈕驗收。

**2026-10-20 Stage 過期保護調查與刪除狀態：** [dry-run #39351045998](https://github.com/tommylin15/janus-omniforge/actions/runs/39351045998) 發現 61 個 active PostgreSQL control records、其中 4,927 件舊 Stage 物件被 24 筆 `running` 狀態保護；[read-only audit #39352303651](https://github.com/tommylin15/janus-omniforge/actions/runs/39352303651) 證明 `claimed_until` 尚有效者為零，24 筆均超過 7 天（96,321,204 bytes），不是已驗證的模型引用。使用者明確同意清除該批舊 Stage 及真正實體重複原始檔。**已實刪僅 37 個／38,396 bytes**（[GCP apply #39351609294](https://github.com/tommylin15/janus-omniforge/actions/runs/39351609294)，generation PASS），4,927 件**已由受控 #39355428497 實刪 PASS**：Cloud Run execution `janus-ingestion-core-8zr4h`、generation readback PASS，96,321,204 bytes（Stage 6,384／415,180,394 → 1,457／318,859,190）；Core/Mart/Private 刪除 0。此項 PASS 不等於新常態 48h 自然排程、Admin 正向或跨 execution 去重已驗收。原有 MD5 疑似額外容量 165,308,239 bytes 未實體驗證，可能和這批 4,927 件重疊，不能直接加總或冒稱節省。Stage 範圍之外不更動。

**本對話工作邊界：**STAGE-48H 僅剩 Admin 正向六桶查詢、Stage 真實 payload 重用及自然 18:30 Stage-only 清理三項實機驗收；其餘模型/D07-PRE 已交獨立對話。本工程此時 **PARTIAL**，不得因 rollout/promotion PASS 即宣稱功能完整。其他跨專案治理與非阻擋觀察見 [TODO](todo.md)。
