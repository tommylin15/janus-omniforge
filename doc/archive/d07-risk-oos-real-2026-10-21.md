# D07 Risk｜真實普通股 r1 研究 OOS 收據（2026-10-21）

狀態：**RESEARCH_OOS_EVALUATED / NOT_PROMOTABLE**。本次為 ChatGPT 執行環境對已封存 Google Drive 原始月檔的實際訓練及回測，**不是 Colab console 實跑收據、不是 GitHub CI PASS，也不是正式 Janus Registry 發布**。資料未寫入正式 Core／Mart。

## 資料與稽核
- 唯一資料路徑：`MyDrive/給ai專用/janusChatGPT/資料源/2025-01` 至 `2026-09`，共 21 個月 `r1` 不可變月檔。
- 逐月讀回並驗證 manifest 宣告的 `ohlcv-r1.csv.gz`、`quality-r1.json`、`universe-r1.csv` SHA256；同一普通股名冊 1,982 檔（TWSE 1,089／TPEx 893），至少有行情股票 1,979 檔；行情總計 **799,468 列**。
- 21／21 個月符合上市普通股 ≥90%、上櫃普通股 ≥70% 的**現行名冊月度股票**與**股票×交易日**兩層研究准入。最低分月股票涵蓋：TWSE **94.58%**、TPEx **92.61%**；最低股票交易日有效率：TWSE **94.20%**、TPEx **90.79%**。兩市場各 **422** 個由 manifest 來源日期確認的已收交易日。
- 沒有自行補出缺日、無法對齊的停牌日不補價格／報酬；移動窗口只有完整交易日連續性才納入。未來 20 個市場交易日的 label 在成熟後才進訓練／OOS。

## 單一 cutoff：Rolling20 vs Ridge(alpha=10)
- `train_cutoff=2026-03-31`，train 只用 `label_matures_on <= cutoff` 的歷史標籤，先 fit StandardScaler，再 fit pooled Ridge；不拆成逐檔獨立模型。
- OOS 信號為 2026-04 至 2026-08，最後未來20交易日結果成熟到 2026-09-30；**354,483 train rows，181,557 OOS rows，104 OOS unique market dates**。
- baseline 與 challenger 使用完全相同有效樣本、時間分割及未來 20 日實際波動標籤。

| 測量 | Rolling20 baseline | Ridge challenger | 改善 |
|---|---:|---:|---:|
| OOS MAE（年化波動率單位） | 0.146827 | 0.134357 | **8.49%** |
| OOS RMSE | 0.200651 | 0.183205 | **8.70%** |
| TWSE OOS MAE | 0.139681 | 0.128268 | **8.17%** |
| TPEx OOS MAE | 0.157064 | 0.143080 | **8.90%** |

每月 MAE 相對改善：2026-04 **+1.80%**、05 **+3.68%**、06 **+5.22%**、07 **−1.69%**、08 **+28.24%**。不得只報平均，不提 7 月失敗。

## 四個分段 walk-forward 診斷（事後已檢視，非 untouched holdout）

| 訓練成熟 cutoff | OOS period | OOS rows | OOS days | MAE 改善 |
|---|---|---:|---:|---:|
| 2025-09-30 | 2025 Q4 | 100,631 | 62 | +7.34% |
| 2025-12-31 | 2026 Q1 | 92,529 | 55 | **−7.09%** |
| 2026-03-31 | 2026 Q2 | 107,027 | 61 | +3.61% |
| 2026-06-30 | 2026 07–08 | 74,530 | 43 | +15.10% |

未調整價格的「單日絕對 log return > ln(1.35)」作**排除窗口敏感度檢查**，不能當公司行動正式事實。敏感度情境：train 354,242、OOS 181,471；baseline MAE 0.145996、Ridge 0.133647，改善 **8.46%**，方向未改。

## 判定與下一個 gate
- **完成**：這批 21 月原始研究檔 SHA／普通股雙市場准入，及一次真實 single-cutoff + 四段 walk-forward 診斷；單一 pooled Ridge 在整體 MAE 上勝過 20 日 rolling baseline。
- **不得發布**：歷史母體仍 `CURRENT_MASTER_ONLY`（survivorship bias）、PIT `NOT_VERIFIED`、公司行動 `UNADJUSTED`、來源 ML 授權未由操作者核准；2026 Q1 和 2026-07 均有落後 baseline，且 20 日重疊 label 不能當獨立樣本。不將 `candidate_beats_baseline_mae` 轉換成 Registry promotion。
- 後續正式候選需控制公司行動、母體與資料授權，另定新的未使用期間或明確的前瞻驗證，再評估是否升級；舊的正式 Risk baseline 與 Janus User／Owner 不變。

## 可重跑程式
`research/colab/monthly_folder_io.py` → `risk_pilot.py` → `run_risk_folder_pilot.py`。在 Colab 挂載相同 Drive 並 `git pull main`，依 [Colab README](../../research/colab/README.md) 的 21 個月 glob + `--cutoff 2026-03-31` 重跑產出包含來源與敏感度／分段結果的 JSON。模型輸出僅研究，`publication_allowed=false`。本收據使用 Python/Pandas/NumPy/scikit-learn（原執行環境 3.13／2.2.3／2.3.5／1.8.0），並保存逐月原始 manifest SHA 與品質於本輪研究 JSON；不得將原始行情提交到 GitHub。

