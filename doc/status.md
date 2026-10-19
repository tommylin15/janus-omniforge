# Janus｜目前實作與驗收狀態

更新：2026-10-19（Asia/Taipei）。本頁只保留**最新證據摘要**，不是第二份 TODO。實作及完成狀態以 GitHub `main`、CI／deploy／GCP dev／資料／Owner readback 為準；完整歷史在 [原狀態快照](archive/status-before-consolidation-2026-10-19.md)，近期收據見 [Operations](spec/operations-and-testing.md)。

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

**Stage 最新發布阻塞（2026-10-19）：** [自動 Release #39269705984](https://github.com/tommylin15/janus-omniforge/actions/runs/39269705984) full Python / Flutter tests 與四元件 GHCR publish/verify PASS；`api-candidate` 因缺 `/workspace/v2-state/build-receipt.json` 失敗，`auth-boundary`、`preview`、`jobs-rollout` 均 skipped。**沒有 48h Stage dev Job 新映像、自然排程或實刪驗收**；目前僅 code/targeted/CI 層 PASS，live rollout 為 BLOCKED。原 [首次失敗 #39269117162](https://github.com/tommylin15/janus-omniforge/actions/runs/39269117162) 為兩個既有 retired Pilot 測試差異；新 run 已依現有正式 GHCR release 排除並通過完整適用測試。修復必須沿既有獲核准的 GHCR candidate/Jobs release、不可跳過 auth/rollback gates。

**唯一順序：[STAGE-48H → D07-PRE → D07 → D08](todo.md)**。Stage 48h TTL、Stage-only worker 與每日 Controller due 已有 GitHub 變更／targeted tests；尚未有新 GHCR digest、Cloud Run Job rollout、自然 due、實刪 generation 收據，維持 `CODE_PARTIAL / LIVE_NOT_VERIFIED`。自然 Ledger、FINOPS 真實刪除數與 Pilot 是非阻擋觀察，不在此頁重建工作清單。重大風險／選項集中 [管理文件](project-management.md)。本次文件整理**未**重新驗收 GCP、Colab、資料樣本或現有部署。
