# Janus — 唯一 Active TODO

更新：2026-10-24，研究精簡決策。完整政策見 [PROJECT_RULES §0](PROJECT_RULES.md)／[研究精簡](spec/research-simplification.md)。目前狀態：研究稽核精簡 CODE／RELEASE／DEV DEPLOY／BOUNDED RUNTIME ACCEPTANCE 全部 CLOSED／PASS（2026-10-24；詳見 [收據 WI](runbook-research-simplification-wi.md)）。2026-10-24 Python 259 項、Flutter 5 項測試通過；[CI 40080225057](https://github.com/tommylin15/janus-omniforge/actions/runs/40080225057) 與 [離線測試 40080225060](https://github.com/tommylin15/janus-omniforge/actions/runs/40080225060) 均成功。

| 工作 | 剩餘交付 | 範圍 |
|---|---|---|
| RV-01…06（04 Valuation） | RV-01 reader 靜態對應已完成、真實逐股覆蓋待確認；RV-02 16 項 PASS；RV-03 已新增直接讀既有 Core/Serving 的唯讀 adapter，13 項 CI PASS，但尚未有 Dev 真實資料讀回，維持 PARTIAL；下一步在既有 Dev 有界讀回 2330／金融股資料，若缺 24 個有效月份或同口徑四季 EPS/BVPS，明列缺口不硬造 → RV-04 API/Mart → RV-05 單一估值卡 → RV-06 Dev 驗收 | [RV-01 接線](research/valuation-rv01-serving-readers-2026-10-24.md)／[估值 SPEC](spec/valuation-range.md)；正式仍僅四模型，未部署、不補全歷史 PIT |
| VAL-MIN30 | **v25 新重跑封包與 v26 真資料五因子擴展已完成本輪研究驗收**：原 v25 位元檔未尋回，另從 v23/P0P1 真資料重訓兩個 `.ubj`、Ridge 與測試預測（不得稱原 SHA 復原）；v26 已直接讀回既有 release 2024-01～2026-09 33 個 valuation Parquet、比對來源 manifest SHA，組出 54,764 列真實五因子 X/Y，完成 2025Q4 與 2026Q1–Q3 兩組 PE/PB Ridge／XGBoost 時序 OOS；2026 PE/PB XGB log MAE **0.6259/0.5182**（同窗基準 **0.7062/0.5931**）；同樣本四因子 vs 五因子 PE/PB 均有小幅改善。5/5 targeted tests 與全部 `.ubj` 重新載入 PASS。**限制：2025 PE 驗證未勝基準、財報 quarter_end+90d 是 NON_PIT 研究假設；不等於可發布或預測報酬**。兩份模型 ZIP／測試／預測已上傳 Drive 並讀回；參閱 [v26 真資料試訓](research/valuation-v26-fivefactor-time-oos-2026-10-24.md)。後續只在需要時做更獨立的 OOS／模型效用檢查，不再重跑補收或溯源稽核。 | `publication_allowed=false`；Research NON_PIT，原 canonical／Registry／Risk ACTIVE 皆未改；沒有新付費資源 |
| DATA-RELEASE-PREFLIGHT／FACTOR-FACTORY | 讀現有 CURRENT、必要欄位與樣本，產生 X/Y | 不重跑全期 hash／來源／產業歷史稽核；缺實際必要資料才補 |
| D07 共用 X/Y | 日期排序、滾動特徵、X/Y 分離、必要樣本及 train/serving 一致 | 不重建首次公告精確時間、歷史名冊或全公司行動 |
| D07 四模型研究 | Quant、Risk、Fundamental、Valuation 各自使用現有資料與 baseline 比較 | 歷史時間切分足以研究；前瞻新 cohort 非前置；不得把欠佳結果寫成有效 |
| Risk API/UI | 下一次授權啟用時完成模型載入、實際預測與顯示 | 沿已有候選；不因規則精簡自動切 ACTIVE，不強制來回回滾演練 |
| D07-CROSS-JOB-MODEL-CACHE | 三模型具可部署版本後共用 loader/快取 | 保留版本切換與回復，不新增付費常駐服務 |
| D08 | Fact Pack → 既有 Gateway → 報告／Owner history／UI | 事實報告不等全部模型完成；保留權限與數值正確性 |

OPS-P0-1 已於 2026-10-24 有界 CLOSED／PASS：備份派送恢復、當日 Daily 已成功、GCS 36h 保護及 7 Daily／6 Monthly 安全 dry-run 通過；未重做已 PASS 的隔離還原，詳見 [Operations](spec/operations-and-testing.md)。不列 active queue，有新實際故障再立新工項。

取消：歷史產業 PIT 資料補證、逐來源稽核、全歷史名冊／公司行動完整重建、強制新20日 cohort 等待、每週／每月例行模型稽核、六個月自然觀察帳本。均為 CANCELLED，不是 PASS，不交下一 AI 續做。

C1-A reader 盤點、P0-2、A-CHANGE、D01～D06、FINOPS-AB 等既有結案保持結案。未授權的 C1-B 真實表／欄位刪除不執行。Risk v2 延後構想不列 active queue。過去驗收數字見 Git 歷史與既有 archive，不在 TODO 重複保存。
