# Janus／OmniForge Valuation｜P1 金額單位與會計期間口徑交叉驗證

日期：2026-10-24，研究限定，`publication_allowed=false`。

## 範圍與結果

- GitHub 基準：`main` commit `54dc6148655f8d14aa65c3afb452087bcc62eccc`（此版本是盤點前的 baseline，P1 新 commit 以實際 GitHub 讀回為準）。
- 現行資料：`release-0bbae8d9c1ca7d8d`；CURRENT SHA256 `0b64ac6927805fb98260121da94624d7e08ac423f0aa13b8349d4c304f0135cd`。
- 來源輸入：前輪 P0 的 1,181,442 筆 `inventory.csv.gz`（SHA256 `f85fd1c16c286628e02d067088b0f9f473932596d83a098561537cc172bc376c`），可在 `janusChatGPT/模型研究/Valuation_P0_P1_實測資料與程式_20261024.zip` 找到。
- **504 組候選交叉來源**：391 `CONSISTENT_1000X_COHORT_ONLY`、4 `VALUE_MISMATCH_REVIEW`、109 `AMBIGUOUS_SOURCE_OR_PREVIOUS_QUARTER`。另外 `duplicate_source_keys_excluded=105` 為配對候選範圍內的來源重複鍵，與 109 組不能直接加總。
- 資產負債表 `total_assets`：113 組，111 組符合千倍；`total_liabilities`：113 組，111 符合；`total_equity`：113 組，113 符合。
- MOPS 累季營收 vs FinMind 單季營收：Q1 16/16 同一季度直接千倍；Q2～Q4 40/44 在減去前季 MOPS 累計後符合千倍，餘 4 組列為 `VALUE_MISMATCH_REVIEW`。
- 原始檔其他財務科目的單位、期間及 statement scope **未做全覆蓋驗證**；對同一股票的來源差異不自動選高優先級替代或回填。

## 來源證據與決策

1. MOPS 財務比較 E 點通，三大報表分類明示「綜合損益表（累計）」、「現金流量表（累計）」，「資產負債表」為時點值：<https://mopsfin.twse.com.tw/>。這是一般報表的*提供者說明*，不是現行 canonical 各個 raw row 的會計期間欄位認證。
2. FinMind 基本面資料：`date` 是財報期末，不能冒充實際公告時間；`TaiwanStockFinancialStatements`、`TaiwanStockBalanceSheet`、`TaiwanStockCashFlowsStatement` 原始說明：<https://finmind.github.io/tutor/TaiwanMarket/Fundamental/>。其財報模組的 EPS 是單季值（現行資料未有原始發布時點）：<https://github.com/FinMind/FinMind-Doc/blob/master/docs/tutor/TaiwanMarket/Fundamental.md>。
3. 目前 canonical 財報 `unit_basis`：MOPS `RETAIN_SOURCE_HEADER_VERIFY_BEFORE_TRAINING`，FinMind `PROVIDER_REPORTED_UNVERIFIED`；`period_basis`：MOPS `QUERY_PERIOD_UNVERIFIED`，FinMind `PROVIDER_QUARTER_END_INFERRED`；`statement_scope` 均空值；`published_at` 在全部 1,181,442 筆皆為空。
4. **數值配對通過不是來源認證**。需要把 MOPS 原始 response header／報表期別／單位與 FinMind API 元資料逐 source request、symbol、quarter hash 關聯到既有列，檢查合併與個體表、重編修訂、金融業模板，再決定可用單位或期間。過程不能憑 1,000 倍推回所有股票與科目。
5. `EPS` 不可套用 YTD 差分；完整單季值轉換只對在同一來源／合併別／財報年度／單位且四季可核對的**流量**候選生效，2022Q4 若缺同年 Q3，不准以跨年 Q4 差分。
6. 無已查證來源的歷史公告時間，`historical_pit_verified_rows=0`。`observed_at` 是本次抓取時間，不能視為歷史 first-published-as-of；`source_unit_verified_rows=0`、`source_period_verified_rows=0` 不是說 1,181,442 筆資料全錯，而是目前來源證據不足。

## 操作與產物

Colab 打開 `14_Valuation_P1_單位與期間交叉驗證.ipynb`，從 `ROOT/模型研究/Valuation_P0_P1_實測資料與程式_20261024.zip` 讀 P0 凍結輸入，以 SHA 校驗，然後執行 `valuation_unit_period_audit.run`，只寫至 `ROOT/模型研究/valuation/backfill_candidates/P1_20261024/unit_period/`。

或在本機使用：

```bash
python -m pytest -q tests/test_valuation_unit_period_audit.py
python research/colab/valuation_unit_period_audit.py \
  --inventory-gz /path/to/inventory.csv.gz \
  --expected-sha256 f85fd1c16c286628e02d067088b0f9f473932596d83a098561537cc172bc376c \
  --out /path/to/research-only-output
```

產物：`unit_period_pairs.csv`、`unit_period_cohorts.csv`、`audit_summary.json`、`P1_單位期間驗證收據.md`，均不寫 canonical。**P1 研究對照工作在已定義的 504 組範圍內完成；P1「全體來源單位／會計期間正式認證」仍 PARTIAL。**
