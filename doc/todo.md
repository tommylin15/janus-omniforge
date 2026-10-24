# Janus — 唯一 Active TODO

更新：2026-10-24，研究精簡決策。完整政策見 [PROJECT_RULES §0](PROJECT_RULES.md)／[研究精簡](spec/research-simplification.md)。目前狀態：CODE_DOC_UPDATED／OFFLINE_TESTED_PASS／NOT_DEPLOYED。2026-10-24 Python 259 項、Flutter 5 項測試通過；[CI 40080225057](https://github.com/tommylin15/janus-omniforge/actions/runs/40080225057) 與 [離線測試 40080225060](https://github.com/tommylin15/janus-omniforge/actions/runs/40080225060) 均成功。

| 工作 | 剩餘交付 | 範圍 |
|---|---|---|
| 精簡版本交接 | 離線測試 PASS；後續依 [WI](runbook-research-simplification-wi.md) 完成既有 dev 部署及一次功能確認 | 已完成測試，不冒稱 dev runtime 已更新 |
| OPS-P0-1 備份與清理 | 確認恢復派送後能產生可用備份、清理可安全執行 | 保留真實備份故障修復；取消自然觸發等待與探針，不因 10/17 舊 run 持續追查；36h 刪除保護保留 |
| RV-01…06 | 04 Valuation 估值情境、EPS/BVPS/PE/PB 算式、API/Mart、唯一估值卡與功能確認 | 無第五模型；按資料實際日期、單位處理，不補全歷史 PIT |
| VAL-MIN30 | v25 已完成四因子 NON_PIT Ridge／XGBoost 試訓；補同窗 revenue_yoy、擴展月份與五因子比較 | 已收檔不重抓；[v25 結果](research/valuation-v25-nonpit-direct-training-2026-10-24.md) 保留，非完整 PIT 不阻擋研究 |
| DATA-RELEASE-PREFLIGHT／FACTOR-FACTORY | 讀現有 CURRENT、必要欄位與樣本，產生 X/Y | 不重跑全期 hash／來源／產業歷史稽核；缺實際必要資料才補 |
| D07 共用 X/Y | 日期排序、滾動特徵、X/Y 分離、必要樣本及 train/serving 一致 | 不重建首次公告精確時間、歷史名冊或全公司行動 |
| D07 四模型研究 | Quant、Risk、Fundamental、Valuation 各自使用現有資料與 baseline 比較 | 歷史時間切分足以研究；前瞻新 cohort 非前置；不得把欠佳結果寫成有效 |
| Risk API/UI | 下一次授權啟用時完成模型載入、實際預測與顯示 | 沿已有候選；不因規則精簡自動切 ACTIVE，不強制來回回滾演練 |
| D07-CROSS-JOB-MODEL-CACHE | 三模型具可部署版本後共用 loader/快取 | 保留版本切換與回復，不新增付費常駐服務 |
| D08 | Fact Pack → 既有 Gateway → 報告／Owner history／UI | 事實報告不等全部模型完成；保留權限與數值正確性 |

取消：歷史產業 PIT 資料補證、逐來源稽核、全歷史名冊／公司行動完整重建、強制新20日 cohort 等待、每週／每月例行模型稽核、六個月自然觀察帳本。均為 CANCELLED，不是 PASS，不交下一 AI 續做。

C1-A reader 盤點、P0-2、A-CHANGE、D01～D06、FINOPS-AB 等既有結案保持結案。未授權的 C1-B 真實表／欄位刪除不執行。Risk v2 延後構想不列 active queue。過去驗收數字見 Git 歷史與既有 archive，不在 TODO 重複保存。
