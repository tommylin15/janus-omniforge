# D07 Risk v1｜OHLCV 三因子增強實測（2026-10-22）

**狀態：RESEARCH_OOS_ONLY / NOT_PROMOTABLE。** 此報告記錄 ChatGPT Python 執行環境上的本地真實 Drive 月檔對照，**不是 Colab Notebook 實跑或 GitHub CI PASS、正式模型 artifact／GCS／Registry 發布收據**。前一版 v0 的 [實測收據](d07-risk-oos-real-2026-10-21.md) 保留，不覆蓋。

## 研究變更（凍結 v0，另建 v1）

- v0 五因子：`vol20, vol60, drawdown60, abs_return5, volume_ratio20`。
- v1 增加三個只用 t 與過去交易日的 OHLCV 因子：`atr14_pct`（14個真實波幅的平均／當日 close）、`abs_overnight_gap5`（近5個交易日開盤對前一有效交易日 close 之絕對跳空平均）、`log_turnover20`（`ln(1 + 20日平均成交金額 TWD)`）。前日若無資料就 null，不跨停牌填補。
- 真實官方大盤指數、產業歸屬與已核准公司行動**不在本次21月Drive r1**；沒有假裝已用到 `Beta`、產業共振或官方市場波動。本版也未訓練最大回撤或 q05/q50/q95。
- 模型：`StandardScaler + Ridge(alpha=10)`；所有合格普通股共用單一模型。v0、v1 與 Rolling20 使用**完全相同合格行**；StandardScaler 在各fold的train fit、label maturity切分、20交易日 horizon，持股／現金不進X。
- 兩個市場官方有行情交易日以月 `manifest-r1.json` 為依據；研究數據仍 `CURRENT_MASTER_ONLY`、PIT未驗、價格未核正式公司行動。研究敏感度排除單日 log return 絕對值超過 ln(1.35) 的相關特徵／標籤窗口，**不是官方公司行動認證**。

## 真實資料基礎及單一 cutoff

- 逐月驗證 `2025-01` 至 `2026-09` 共21個 `r1` SHA256，**799,468** 個原始 OHLCV row，普通股行情總市場交易日 **422**／market；不改動封存原檔。
- 用截至 `2026-03-31` 已成熟標籤訓練，OOS 訊號 `2026-04` 至 `2026-08`，最新標籤成熟不晚於資料截至日 `2026-09-30`。
- 相同對照 cohort：**354,242 train、181,471 OOS**，訓練與對照皆排除研究 shock window；**不同於 v0 舊收據「不排除shock」的 354,483／181,557**，不得直接交叉比較兩份報告的 MAE。

| 同一樣本比較 | MAE（年化波動率） | RMSE |
|---|---:|---:|
| Rolling20 | 0.145996 | 0.194354 |
| Ridge v0 五因子 | 0.133647 | 0.178069 |
| **Ridge v1 八因子** | **0.127537** | **0.168483** |

- 相對 v0 新版 MAE 降低 **4.57%**；相對 Rolling20 MAE 降低 **12.64%**。
- 上市與上櫃各自比較：TWSE v0／v1 = **0.127601／0.122114**；TPEx v0／v1 = **0.142314／0.135313**。

## 預先固定時段之回溯診斷（非 untouched holdout）

| mature train cutoff | OOS signal period | OOS row | Rolling20 MAE | v0 MAE | v1 MAE |
|---|---|---:|---:|---:|---:|
| 2025-09-30 | 2025Q4 | 100,541 | 0.11621 | 0.10767 | **0.10429** |
| 2025-12-31 | 2026Q1 | 92,527 | 0.13553 | 0.14510 | **0.13389** |
| 2026-03-31 | 2026Q2 | 107,019 | 0.14105 | 0.13586 | **0.12917** |
| 2026-06-30 | 2026年7–8月 | 74,452 | 0.15310 | 0.13014 | **0.12661** |

四段 v1 均優於 v0；**2026Q1 對 Rolling20 的改善只有約1.21%**。逐月又看到 **2026-08** v1 MAE 0.12462、v0 0.12447（v1反而略差），不能寫成逐月都勝利。這些時間段已被檢視與用來診斷，不是 untouched locked test。

## 技術驗收與發布判定

- 本地真實資料 OOS **RUN/PASS**；額外四項合成資料 unittest（無未來因子、缺日不造假、成熟標籤切分、非法OHLC拒絕）在研究環境 **4/4 PASS**。GitHub 另提供更完整的 `tests/test_risk_v1.py`，**GitHub 新版 CI 未有完成 PASS 收據**。
- GitHub程式：`research/colab/risk_v1.py` 及 `run_risk_v1_comparison.py`，使用現行`risk_pilot.py` 的官方交易日對齊和 `monthly_folder_io.py` SHA 讀取。Colab 應重新clone或pull最新版 main，跑 [README](../../research/colab/README.md) 既有21月資料夾。
- **不進 GCS candidate、不匯入Mart Registry、不在正式UI顯示ML機率**；保留現有 deterministic Risk baseline，待正版Colab重跑收據、未見期OOS、來源授權、公司行動與PIT/模型相容／live parity之後再評估promotion。
- 真實市場 benchmark/industry、公司行動證據是**下一階段特定因子之資料需求**；不因這次指令新增付費服務或全市場重抓原始OHLCV。

