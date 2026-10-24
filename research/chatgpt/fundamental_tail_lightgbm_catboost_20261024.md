> **2026-10-24 政策更新**：研究數字與歷史結論保留；本文舊有逐來源／全歷史 PIT 補證、精確時間校準及新前瞻成熟等待不再是工作或發布前置。取消例行稽核，依 [研究精簡政策](../../doc/spec/research-simplification.md) 按需評估；不把取消視為 PASS。

# Fundamental 極端營收／低基期優先：LightGBM、CatBoost 研究決策與實測

日期：2026-10-24｜**狀態：HISTORICAL_RESEARCH_EVALUATED**｜**publication_allowed=false**

## 本輪使用者決策（覆蓋 2026-10-24 之前的 DEFER 判定）
1. 金融股不當作優化性排除條件；主要訓練與評分保留金融股。
2. 先處理極端營收成長率與低基期，**不刪掉真實極端樣本，不修改或截斷原始標籤**。
3. 實際試跑 **LightGBM 與 CatBoost**，同 XGBoost 和既有簡單 baseline 比較；不自動升級任何模型。
4. 只做有界研究，不更新 canonical、Registry、Risk ACTIVE、serving、部署或付費設定。

## 來源、共同母體、驗收
- 原實驗資料：研究重建 CSV 73,209 列；舊 12 月預測 23,101 列。
- 新固定 12 月 Fold：**2025-09～2026-08**，**18,106** 同股、同月共同測試列；占原預測 78.38%。本實驗沒有從樣本中排除金融股。
- 每折 5 組獨立 fit：XGBoost／LightGBM／CatBoost 原 YoY MAE，與 LightGBM／CatBoost 預測 `log1p(next_month_revenue)`；再以 `100*(pred_next_revenue/prior_year_target_month_revenue-1)` 換算為未截斷的原 YoY 百分點評分。
- 15 特徵：原研究 13 因子，加 `log1p(prior_year_target_month_revenue)`、`clip(log(trailing_12m_mean_revenue/prior_year_target_month_revenue),-16,16)`。只用已知月份營收數值；實際公告 `published_at` 缺失，**不可標為 PIT verified**。
- 額外固定 gate：訓練折內去年對應月份營收第 10 分位，或 `trailing_12m_mean / prior_target_base > 10`。低基期走 log 營收、其他走直接 YoY MAE；門檻**沒有從測試 Y 選取**。
- 18,106 列 `prior_target_revenue*(1+Y/100)` 與下月實際研究營收 18,106／18,106 可連結，差距皆小於 NT$100。
- 歷史公告時間全缺；曆月代理只能避免已知月份倒灌，不能確證真正公告成熟。**這 12 個月已曝光於前輪研究**，不可將 bootstrap CI 稱為全新 OOS 證明。

## 實際 12 月月份等權 MAE（百分點）
| 方法 | MAE | 中位絕對誤差 | 筆數 |
|---|---:|---:|---:|
| **LightGBM log-level + 固定低基期分流** | **431.645** | 12.322 | 18,106 |
| LightGBM log-level 全體 | 432.807 | 13.518 | 18,106 |
| CatBoost log-level + 固定分流 | 434.971 | 12.502 | 18,106 |
| CatBoost log-level 全體 | 436.519 | 13.996 | 18,106 |
| 前月營收延用 baseline | 481.072 | 12.870 | 18,106 |
| 原組合 baseline | 566.655 | 16.561 | 18,098 |
| XGBoost 直接 YoY L1 | 575.648 | 12.147 | 18,106 |
| LightGBM 直接 YoY L1 | 575.986 | 12.173 | 18,106 |
| CatBoost 直接 YoY MAE | 576.443 | 12.369 | 18,106 |
| 舊研究 XGB L1 | 581.268 | 13.802 | 18,106 |
| Seasonal-zero | 591.322 | 19.427 | 18,106 |

原組合 baseline 8 列缺值保留未填補；配對樣本 18,098。MAE 均以**原始未截斷 YoY**評分。

## 時間區塊配對結果（3 個月份、5,000 次 bootstrap；已曝光診斷）
- combo_baseline → LightGBM log-level + gate：**+134.773**，95% CI [**+32.684, +176.139**]，11／12 月較優。
- combo_baseline → CatBoost log-level + gate：**+131.465**，CI [+25.102, +173.626]，11／12 月較優。
- XGBoost 直接 YoY → LightGBM 直接 YoY：**−0.339**，CI [−1.028,+0.821]，未見單純更換模型家族帶來改善。
- LightGBM 全 log-level → 加固定分流：**+1.161**，CI [+0.797,+1.634]。雖方向大致一致，但相對整體誤差提升很小，**不應因這 12 月就宣稱 gate 必須部署**。
- LightGBM gate 與 CatBoost gate 差距約 3.326 百分點，月份配對 CI 跨零；不能宣稱演算法家族勝負。

## 極端值控制：仍未完全解決
- 真實 |YoY|>=1,000 百分點 **137／18,106（0.76%）**；固定低基期 gate 捕捉其中約 **89.05%**，總體 gate 覆蓋 1,768 列（9.76%）。
- gate 內 1,768 列：原 combo baseline pooled MAE 約 5,198，LightGBM log-level 約 **4,217**。
- gate 外 16,338 列：LightGBM 直接 YoY pooled MAE **23.00**，全 log-level **24.28**；保留一般股票的直接路徑有意義。
- 最差 1% 的 LightGBM gate 預測誤差仍占總誤差 **94.51%**；先前 combo 約 94.52%，尾部仍主導。沒有公告修訂及單位 provenance 時，異常先記 `EXTREME_UNVERIFIED`，不可單憑高誤差剔除。

## 可重跑 artifact、測試與完成判定
研究 bundle 含 `experiment.py`、`test_experiment.py`、2 份固定 SHA 原始研究 CSV、12 折個別預測／metadata、逐筆預測、MAE、配對區塊 CI、低基期與極端切片、最差 100 列、`manifest.json` 與檔案 hash。
- SHA256(`research_panel_reconstructed.csv`) = `c506a363d639599c9daf01cd3761f0e2d7a8b38597a4deb6f5274cd27b0d484e`。
- SHA256(`walkforward_predictions.csv`) = `b3b7cb182b3aba2fb2a465194b050547e5b58ef9fbb0bd2ed4adaaa4fb207c56`。
- **12/12 folds 完成；9/9 本地單元與驗收測試 PASS。**
- 完整且與本地 9／9 測試版本逐字讀回一致的 Python／測試，已提交 GitHub `main`：[`experiment.py`](fundamental_tail_challenger/experiment.py)（commit `246ec0a29e493cd8398c99255618019eb4557657`）、[`test_experiment.py`](fundamental_tail_challenger/test_experiment.py)（commit `437b3d7c4571bba4e3f19a2abb59f05c5172aae0`）。**大型 18,106 筆逐筆 CSV 與固定研究輸入仍在本對話自含 ZIP，不在 GitHub repo**；須解壓至程式預期的相對路徑。

### 下一個研究工作，不自動發布
1. 原始公告、修訂與 `label_available_at` PIT 驗證；完整 Parquet 93,036 列對齊；
2. 極端案例原始營收數值／單位／基期追溯，找出已確認的資料錯誤（不移除真實稀有事件）；
3. 凍結基準與模型規格後，依**尚未曝光**的前瞻月份重新評估原始 YoY、尾部、一般樣本、coverage；
4. 繼續允許 baseline 最佳與 challenger 不足以發布的結論。

**研究判定：LightGBM／CatBoost log-level 路徑有明顯回溯潛力，但仍是 `RESEARCH_EVALUATED`，不是 production/promotion。**
