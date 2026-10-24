# Janus / OmniForge｜Valuation v25 重跑封包與 v26 五因子長期樣本外研究

- 執行日期：2026-10-24，使用目前 Janus 研究資料；模型狀態：`RESEARCH_NON_PIT_DIAGNOSTIC`，**publication_allowed=false**。
- 禁止將本 ZIP 匯入 canonical、Registry、Risk ACTIVE 或 UI publication。未改動任何雲端訓練排程、付費 GCP 服務、正式 serving。

## 關於 v25 封包的誠實說明

歷史 v25 GitHub 報告存在，但原二進位模型與訓練原始碼沒有完整可核實的封存檔。因此 `v25_replay` 是**直接使用 v23 已保存的真實 4,000 個歷史估值月快照，及 P0/P1 真財報重訓所得的新模型**；不是原始 v25 二進位檔案的 SHA 級恢復。

真資料量和日期切分已重現：PE train/val/test 765/200/370，PB 1141/311/622；市場中位數和 Ridge 的測試誤差與 v25 記錄高度吻合；新 XGBoost 測試 MAE PE 0.8034（原 v25 報告 0.7920）、PB 0.4399（原記錄 0.4326），差異已保留不掩飾。各 branch 都有完整 `.ubj`、Ridge 係數、`test_predictions.csv`、`test_vectors.json` 與實際報告及檔案 hash。

## v26 的真實五因子

五個 X 是 `roe_proxy`、`debt_ratio`、`log_total_assets`、`revenue_yoy`、`market_code`。其中：
- `roe_proxy = MOPS 本期淨利（累計來源數字） / 權益總計`，不是年度化 ROE。
- `debt_ratio = 負債總計 / 資產總計`。
- `log_total_assets = log(資產總計 × 1000)`，MOPS 原始財報數字以仟元研究假設換算為元。
- `revenue_yoy = 本年同季 MOPS 累計營業收入 / 去年同季累計營業收入 - 1`，不是單季營收 YoY；條件需兩季皆實有來源數字、去年累計營業收入 > 0。
- `market_code = 0/1`（TWSE/TPEx）。

財報截至日 + 90 天只是可重跑的研究時點假設，不是查證後的公告日。X 禁止加入當月 PE、PB、價格、市值與當期 target-derived 欄位；只納入當時選定的先前財報研究窗口。沒有原始值時不補造。使用 2024-01 至 2026-09 **33 個原研究 release Parquet 月檔**（來源 SHA 與 manifest 比對）；依月保留市場最後觀測日期。2024 初期由於財報 YoY 尚未具備可用的 prior-year window，部分月份不進入五因子訓練。

## 固定樣本外測試（低 MAE 較佳，皆為 log 倍數）

| 測試 | PE Baseline | PE Ridge | PE XGB5 | PB Baseline | PB Ridge | PB XGB5 |
|---|---:|---:|---:|---:|---:|---:|
| 2025-10~12 | 0.6378 | 0.6340 | **0.5469** | 0.5363 | 0.5315 | **0.4492** |
| 2026-01~09 | 0.7062 | 0.6901 | **0.6259** | 0.5931 | 0.6105 | **0.5182** |

四因子 ablation 與五因子使用**完全相同有效 X/Y 列、時間分割與訓練配置**。五因子 XGB 在 2025 測試 PE/PB MAE 分別降低 0.00641 / 0.00852，在 2026 測試降低 0.00696 / 0.01581。注意 2025 H2 PE 驗證 MAE=0.6482 **比基準0.6191差**；這不是穩健全面勝出的證據。

### 資料/特徵深度

- 財報 1,181,442 原始列（使用同來源 MOPS 的選定 5 個科目），28,553 組已觀測股票/季度。
- `revenue_yoy` 在原財務季度表可算 20,542 組，整體 v26 五因子完整的估值月截面 54,764 列；7,133 列因一項或多項特徵缺漏被排除，沒有填值。
- v26 Fold-2025Q4 PE test 3,981/PB test 5,562；Fold-2026 PE test 12,636/PB test 16,977。
- 月份全股共用同一 split。模型儲存為 XGBoost 原生 `.ubj`，在離線環境重載，五個定向驗收測試 5/5 通過。沒有未來收益標籤，也不聲稱預測下一期價格。

## 檔案清單

- `code/valuation_research_train.py`：真正從既有財報/估值載入、建 X/Y、分月切分、訓練 Ridge/XGB 的 Python 程式。
- `code/valuation_v26_ablation.py`：同一批真資料 4-vs-5 因子直接比較。
- `code/test_valuation_training.py`：完整 X/Y、split、重載、hash 測試。
- `code/janus_parquet_min.py`、`code/parquet_meta_inspect.py`：本地環境沒有 pyarrow 時的只讀限定 Parquet decode。一般有 pyarrow 的環境直接 `pd.read_parquet`。
- `results/v25_replay`：兩個歷史四因子 UBJ、預測、試訓報告與完整 SHA256。
- `results/v26`：2025 與 2026 兩個 fold × PE/PB 共四份五因子 UBJ、predictions、模型報告與 SHA256。
- `results/v26_four_feature_same_sample`：同樣本四因子對照；四份 `.ubj`、預測與公平比較。

## 再執行

備妥受控既有檔案：`manifest.json`、`Janus_Valuation_04_v23_歷史月末整併與模型准入_20261024.zip`、`Valuation_P0_P1_實測資料與程式_20261024.zip`，以及 33 份原 release 估值月檔 `2024-01.parquet.bin` 至 `2026-09.parquet.bin`。上述真資料**不重複封裝進模型 ZIP**；來自 `janusChatGPT/資料源/JanusDataset_v3_202610/canonical/` 與 `janusChatGPT/模型研究/valuation`，每次程式驗 SHA。不要將其他 2024Q1 財報 Parquet 混作同月估值檔。

```bash
python code/valuation_research_train.py --root <既有來源資料目錄> --output results/v25_replay --mode v25_replay
python code/valuation_research_train.py --root <既有來源資料目錄> --output results/v26 --mode v26
python code/valuation_v26_ablation.py --v26 results/v26 --out results/v26_four_feature_same_sample
PYTHONPATH=code python -m unittest discover -s code -p 'test_valuation_training.py' -v
```

**已知限制**：五因子財務值由研究用固定延後假設產生；沒有真歷史第一公告、產業有效 cohort；目前沒有成熟跨市場調整或前瞻封存；因此禁止將相對倍數研究 MAE 解釋為投資報酬、估值合理價或正式上線通過。
