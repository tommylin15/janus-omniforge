> **2026-10-24 政策更新**：研究數字與歷史結論保留；本文舊有逐來源／全歷史 PIT 補證、精確時間校準及新前瞻成熟等待不再是工作或發布前置。取消例行稽核，依 [研究精簡政策](../../doc/spec/research-simplification.md) 按需評估；不把取消視為 PASS。

# Fundamental 月營收 YoY 因子消融研究收斂（2026-10-24）

**狀態**：RETROSPECTIVE_RESEARCH_EVALUATED；**publication_allowed=false**。此結論不是正式模型驗證或 promotion。

## 來源與共同樣本
- GitHub 原訓練 SHA：`28fd738d509ab9936bf997b7024430372ac9ceac`；Stage 05.1／08 候選 `candidate-e3ee96cd41cda133`。
- 原始月營收 X：93,036 筆；前輪重建 CSV：73,209 筆，未與原始完整母體等量。
- 原 12 月 historical retrospective OOS 檔：2025-09～2026-08，23,101 筆；新 11 組消融共用 18,106 筆（**78.38%**）。不得把二者當同一測試母體。
- PIT：`published_at` 缺值、`historical_pit=NOT_VERIFIED`；新實驗每月訓練只用測試月以前至少 3 個曆月之標籤代理，**非實際 label_available_at**。測試月份已曝光。

## 原始 23,101 列統計
主要指標：月份等權 MAE（下列單位皆為下一月營收 YoY **百分點**）。
- 驗證集選定簡單組合 baseline：**560.475**。
- log XGB：605.921；XGB L1：608.556；Pseudo-Huber：610.827；seasonal_zero：618.939；growth_persistence：782.371；XGB L2：2214.162。
- 同月份配對、3 月 moving-block bootstrap（5,000 次）：seasonal_zero − XGB L1 = **+10.384**，95% CI [7.620, 12.950]，12/12 月改善；combo_baseline − XGB L1 = **−48.237**，95% CI [−136.977, 40.281]，**不支持穩定勝過組合基準**。
- 組合 baseline 的 10 筆缺值採配對共同樣本（23,091 列），不造假補值。上列皆是已曝光 retrospective 診斷。

## 新因子分組消融（18,106 同股同月）
固定 XGB L1 90 trees、depth 2、learning rate .05、min_child_weight 50、reg_lambda 20、seed 20261023；非原 L1 完全同配置。
- 原 13 因子：581.762；核心 10 因子：581.736。
- 移除季節 sin/cos：**581.298**（改善 0.464 百分點、11/12 月，僅約 0.08% 相對增益）。
- 移除成長變化組：581.710；移除營收尺度組：581.693。
- 加入先前 YoY lags：581.847；加去年目標月基期：581.843；加基期穩定比：581.751；加 6／12 月波動：581.884。**新增組沒有具實務意義的穩定增益**。
- 線性 Ridge 在相同共同樣本上遠差於基準：10 因子約 4519.862；13 因子約 4546.233。
- 低基期極端誤差仍主導：原全樣本中 XGB L1 最差 1% 絕對誤差貢獻約 **95.64%**，未事後刪除任何測試樣本。

## 結論與邊界
**本輪不再引入 LightGBM 或 CatBoost。** 新因子組未達 >5% 的月份等權 MAE 改善，且只有 12 個獨立月份、歷史測試已曝光、重建 CSV 覆蓋不足，繼續加 challenger 會增加選模偏差。結論允許「基準最佳／尚無穩定 ML 增益」，不得把較低 RMSE 或更換目標改寫為改善原任務。

本地研究交付含可重跑 Python、測試（6/6 PASS）、逐筆預測、逐月/切片/配對 CI、特徵覆蓋及 SHA manifest。完整中文研究報告同步於 Drive 授權資料夾：
https://drive.google.com/file/d/1VfU9cFYFbaFUXrv2w9Yr5CwLte9eB-7z/view

**仍需**：完整原 Parquet 93,036 筆的全量因子消融、可信公告歷史版本／PIT、未曝光的前瞻 cohort、原簡單組合基準選擇程式獨立驗證。這些缺口不阻止清楚標記的歷史研究，也不等於 publication 門檻通過。

沒有修改 canonical、Registry、Risk ACTIVE、正式服務或付費資源。
