# Janus — 唯一 Active TODO

更新：2026-10-24，研究精簡決策。完整政策見 [PROJECT_RULES §0](PROJECT_RULES.md)／[研究精簡](spec/research-simplification.md)。目前狀態：研究稽核精簡 CODE／RELEASE／DEV DEPLOY／BOUNDED RUNTIME ACCEPTANCE 全部 CLOSED／PASS（2026-10-24；詳見 [收據 WI](runbook-research-simplification-wi.md)）。2026-10-24 Python 259 項、Flutter 5 項測試通過；[CI 40080225057](https://github.com/tommylin15/janus-omniforge/actions/runs/40080225057) 與 [離線測試 40080225060](https://github.com/tommylin15/janus-omniforge/actions/runs/40080225060) 均成功。

| 工作 | 剩餘交付 | 範圍 |
|---|---|---|
| RV-01…06（04 Valuation） | RV-01 已完成靜態 reader 接線清冊，仍缺真實代表股票覆蓋；RV-02 已交純函式與 14 項 CI PASS；接續 RV-01 真實抽樣 → RV-03 實際資料接線 → RV-04 API/Mart → RV-05 唯一估值卡 → RV-06 Dev 驗收 | [RV-01 接線](research/valuation-rv01-serving-readers-2026-10-24.md)／[估值 SPEC](spec/valuation-range.md)；正式仍僅四模型，未部署、不補全歷史 PIT |
| VAL-MIN30 | v25 **重建版**模型封包已從真實 v23/P0P1 資料重新擬合與測試（兩份 UBJ、Ridge、逐筆預測；6/6 targeted PASS），原 v25 位元檔未尋回；v26 五因子／2024–2026 Colab 執行程式已交付，**2024–2026 真實時間切分尚未執行**，下一步以 Colab 真正訓練並讀回報告、UBJ 及測試集成績 | 不重抓資料、不冒稱 original v25；[v25 報告](research/valuation-v25-nonpit-direct-training-2026-10-24.md)／[v26 交付狀態](research/valuation-v26-rebuild-and-five-factor-2026-10-24.md)；RESEARCH_NON_PIT、publication_allowed=false |
| DATA-RELEASE-PREFLIGHT／FACTOR-FACTORY | 讀現有 CURRENT、必要欄位與樣本，產生 X/Y | 不重跑全期 hash／來源／產業歷史稽核；缺實際必要資料才補 |
| D07 共用 X/Y | 日期排序、滾動特徵、X/Y 分離、必要樣本及 train/serving 一致 | 不重建首次公告精確時間、歷史名冊或全公司行動 |
| D07 四模型研究 | Quant、Risk、Fundamental、Valuation 各自使用現有資料與 baseline 比較 | 歷史時間切分足以研究；前瞻新 cohort 非前置；不得把欠佳結果寫成有效 |
| Risk API/UI | 下一次授權啟用時完成模型載入、實際預測與顯示 | 沿已有候選；不因規則精簡自動切 ACTIVE，不強制來回回滾演練 |
| D07-CROSS-JOB-MODEL-CACHE | 三模型具可部署版本後共用 loader/快取 | 保留版本切換與回復，不新增付費常駐服務 |
| D08 | Fact Pack → 既有 Gateway → 報告／Owner history／UI | 事實報告不等全部模型完成；保留權限與數值正確性 |

OPS-P0-1 已於 2026-10-24 有界 CLOSED／PASS：備份派送恢復、當日 Daily 已成功、GCS 36h 保護及 7 Daily／6 Monthly 安全 dry-run 通過；未重做已 PASS 的隔離還原，詳見 [Operations](spec/operations-and-testing.md)。不列 active queue，有新實際故障再立新工項。

取消：歷史產業 PIT 資料補證、逐來源稽核、全歷史名冊／公司行動完整重建、強制新20日 cohort 等待、每週／每月例行模型稽核、六個月自然觀察帳本。均為 CANCELLED，不是 PASS，不交下一 AI 續做。

C1-A reader 盤點、P0-2、A-CHANGE、D01～D06、FINOPS-AB 等既有結案保持結案。未授權的 C1-B 真實表／欄位刪除不執行。Risk v2 延後構想不列 active queue。過去驗收數字見 Git 歷史與既有 archive，不在 TODO 重複保存。
