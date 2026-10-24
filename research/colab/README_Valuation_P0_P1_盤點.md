> **2026-10-24 政策更新**：研究數字與歷史結論保留；本文舊有逐來源／全歷史 PIT 補證、精確時間校準及新前瞻成熟等待不再是工作或發布前置。取消例行稽核，依 [研究精簡政策](../../doc/spec/research-simplification.md) 按需評估；不把取消視為 PASS。

# Valuation P0＋P1 真實資料盤點與財務 Mapping（研究限定）

版本：`valuation-financial-label-v2.0.0`。單純完成研究資料檢查與候選科目名稱映射。**無網路補收、無訓練、無模型發布，不更新 canonical/CURRENT.json，`publication_allowed=false`**。

## 真實資料基準（2026-10-24 此輪靜態讀回）

- Drive 根：`/content/drive/MyDrive/給ai專用/janusChatGPT`（啟動時檢查存在，不可換成 `個人用`，也不可默默建立替代根目錄）。
- `資料源/JanusDataset_v3_202610/canonical/CURRENT.json` 固定指向 `release-0bbae8d9c1ca7d8d`，manifest `3.1.0`、`publication_allowed=false`。
- 本輪已**逐檔實際下載並核對** 15 個 `financials/YYYY-MM.parquet` SHA256 與列數（2022Q4～2026Q2），1,181,442 筆、1,977 個不同代號，對應 318 個全域不同原始科目（321 組 dataset×原始科目）。
- `income` 493,867、`balance` 489,410、`cashflow` 198,165；`mops` 1,168,822、`finmind` 12,620。全部 `published_at=null`、`historical_pit=NOT_VERIFIED`，單位及 period_basis 均屬未認證狀態。
- 候選科目名稱映射涵蓋 456,599 列，**不是可直接衍生或可發布的 456,599 列**。缺 scope、單位、期間及修訂證據，故財務科目品質分類為 `MAPPING_REQUIRED`；不可直接作財務因子。
- 上述實測僅限財報 15 個檔案；其餘 revenue、valuation、ohlcv、corporate_actions、industry historical membership 尚未完成同等逐列驗證。本輪沒有宣稱全 155 檔案 SHA 已驗證。

## 如何執行

建議執行 Google Drive `CoLab程式/13_Valuation_P0_P1_盤點與Mapping.ipynb`，它會檢查模組檔 SHA256 與 ROOT 存在後，從 `CURRENT` 開始讀實際 manifest 和全部引用檔，再只讀財報 Parquet。**不要先跑 12 的 fetch cell**。

命令列入口（從 GitHub `main` 同版程式）：

```bash
python research/colab/valuation_backfill.py audit-p0p1 \
  --root '/content/drive/MyDrive/給ai專用/janusChatGPT' \
  --run-id P0P1_20261024
```

資料輸出位置：`模型研究/valuation/backfill_candidates/P0P1_20261024/p0p1/`。Run 可以自訂，但不可使用已發現版本漂移的舊 Run；不會碰其他模型與既有資料。

輸出檔案：
- `inventory.csv.gz`：逐列完整 inventory（壓縮 CSV，可由 pandas.read_csv 讀取；大檔不需在 GitHub 放逐列原始值）。
- `financial_mapping_audit.csv`：dataset×原始科目×來源×口徑與分類的聚合；`valuation_mapping_catalog_v2.json` 為程式版本化名稱契約。
- `gap_plan.csv`：每市場／股票／季度／報表／指定科目的 P1／P2 候選缺口；`FETCH_REQUIRED` 尚待二次比對 raw 未映射科目與來源期別後才允許真正 fetch。本輪估計與實際 HTTP 都為 0。
- `field_coverage.csv`：按 market、quarter、dataset、item 的原始可匹配覆蓋率（分母僅為 release 當季在該 dataset 出現的股票，不等於歷史全市場）。另保留已驗證可計算率 0，避免以 raw 覆蓋冒充可用率。
- `source_conflicts.csv`：同一標準科目多原始名稱或多來源並存的證據，不覆蓋、不取平均。不同金額標為待人工核對。
- `quality_issues.csv`：原始科目重複來源鍵；`pit_status_summary.json`、`factor_readiness.csv`、`audit_summary.json` 與 `執行摘要.md`。

## Mapping 規則

僅對 dataset+原始科目**精確名稱**做可回查 mapping，禁用模糊比對、名稱子字串與 `_per` 金額欄。`營業毛利（毛損）` (調整前) 和 `營業毛利（毛損）淨額` 為不同目標，不能強行合併。`basic_eps` 單位是元／股，不能乘上財報千元倍率或做 YTD EPS 差分。銀行與保險科目保留原始值；產業時點未驗證前不得假定某公司全年屬同一 cohort。含修訂／公告未知時保留 `PIT_UNVERIFIED`。

## 尚未完成／下一道 gate

P1 的科目**名稱對應**與候選分類已完成；真正的 `unit_multiplier`、單季/YTD、合併/個體、公告時點、歷史修訂、金融業獨立 mapping 仍需補來源證據。本輪不據此重抓財報或執行財務比率／TTM；待品質 gate 可讀回通過才進下一階段。不得把研究輸出資料升格 canonical。
