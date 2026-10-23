# Janus／OmniForge Quant｜20 市場交易日研究驗證與 Q4 多模型診斷

更新：2026-10-23（Asia/Taipei）。**Research only；不可部署；`publication_allowed=false`。**

## 研究證據與狀態

- GitHub main 讀取時 SHA：`351d28e16b45ec345c191e18283af867980c5be6`。來源 05.1 Quant `candidate-21588985ff46345d`，原 X SHA `1b5c2cdd6f7b48427f81351ece2a855f4b97d44d89606ecd0f3fe29f5f8403ae`、原 Y SHA `e00b92ee1eb0d651b4baa5c28c2fa81dc9de6679b7e3e1b37a9a6ce1d1f44d5e`；實際從 Drive 驗檔 SHA 一致。暫存 pickle 由完整 Parquet fallback 解碼，不是新的權威資料。
- 原始 Quant 11／12／14／15 全因子順序、公式見 `feature_manifest.json`。**F14 是 12 因子研究實驗代號**。`label_end_date` 取原資料 `mature_at` 為導出別名；歷史公開時間與真實正式交易日曆 PIT 尚未認證。
- 42 日期 Stage06：73,670 筆，固定訓練盛行率 Brier **0.245136**；Logistic **0.244876**，原始精度重現 `REPRODUCED`。原 XGB best iteration 8、Brier **0.244639**；當前 XGB 3.1.3 best iteration 12、Brier **0.244611**，與原依賴 3.4.1 不一致，**精確版本重現 `BLOCKED`**。不得以接近值替代相等。
- 56 日期：F1 34 日期／57,432 列，F2 22 日期／38,319 列，共 **56 日期／95,751 同評估鍵**。原 Q1–Q3 Logistic C=1 結果 `REPRODUCED`；42／56 不混為一份 OOS。
- 42日期在**新的日期等權主指標**下：訓練正例率基準 0.245161、Logistic 0.244860、跨XGBoost版本再訓模型 0.244622；與上段舊收據的「原始列加權 Brier」是不同加權方式，不能混合排名。
- 這些期間均先前被檢視：分類 **development / retrospective OOS**，不是全新 untouched OOS。Historical PIT、公司行動價格、survivorship、來源機器學習用途 `NOT_VERIFIED`。

## 11／12／14／15 因子，同共同樣本對照

| 因子組 | 筆數 | 日期等權 Brier | 原始列加權 Brier | 折平均 AUC |
|---|---:|---:|---:|---:|
| F10_14 | 95,751 | 0.250454 | 0.250529 | 0.5342 |
| F14_12 | 95,751 | 0.250242 | 0.250311 | 0.5333 |
| expanded15 | 95,751 | 0.251325 | 0.251413 | 0.5359 |
| original11 | 95,751 | 0.251632 | 0.251722 | 0.5304 |


此表第一欄評分才是本研究主指標「日期等權 Brier」，右欄原始列加權用於核對舊報告。**不能用舊的 pooled-row 排名直接取代日期等權排名**。所有候選同日、同股票、同標籤相互配對；native 覆蓋率分開在 `feature_coverage.csv`，不和共同樣本混排名。

## 歷史增加造成退化（固定 12 因子、固定評估鍵）

| 情境 | F1 日期等權 Brier | F2 日期等權 Brier |
|---|---:|---:|
| H0 | 0.246927 | 0.255365 |
| H1 | BLOCKED | BLOCKED |
| H2 | 0.252228 | 0.261107 |
| H3 | 0.252073 | 0.261197 |
| H4 | 0.246952 | 0.259265 |
| H5 | 0.254716 | 0.262799 |


- **H0** 依原 Stage 05.1 的15因子共同資格與日期範圍重訓12因子 Logistic。
- **H1** 只增加暖機歷史，因原始 X/Y 無更早 OHLCV，**`BLOCKED`**；不偽造暖機效果。
- **H2** 新增早期訓練日期，維持原訓練股票集合，增加約 9.9 萬 train 列，兩折均劣化；這支持「早期日期分布」值得優先診斷，不能單獨證明因果。
- **H3** 再放開新增股票，共約10萬以上增量 train 列，與H2差距小；但早期價格缺口與股票上市生命史仍混雜。
- **H4** 固定最近120日期訓練窗，在F1近乎H0、F2落後H0；縮短窗口不保證改善。
- **H5** 全歷史120日期半衰期、加權Scaler＋Logistic，兩折均落後H0；此一半衰期不應推廣為最優。
- `ret120` 缺值 247,310 列，其中可觀測市場日期年齡少於120個市場交易日 235,874、達120個市場交易日以上 11,436；前者仍可能是左截斷，不等於全部新上市；後者包括交易缺價、資料品質與公司行動等未辨根因。**禁止未來補值**。

## 多模型 Q4 首輪（預先限制試驗量）

| 模型家族 | 參數試驗總次數 | 成功 | 失敗 |
|---|---:|---:|---:|
| catboost | 8 | 8 | 0 |
| lightgbm | 8 | 8 | 0 |
| logistic | 8 | 8 | 0 |
| xgboost | 8 | 8 | 0 |


訓練選參使用外層評估之前的嚴格歷史：每折內較早的train-only fit→內層20日期調參→時間分離20日期 sigmoid校準。所有最終模型的標籤成熟截止均早於其被評估訊號。無 random K-fold／SMOTE；淺層樹、偏強正則化、固定 seed；無外層 early stopping 或外層權重搜尋。每家族最多20 trials，實際用量見表與 `parameter_trials.json`（包括所有失敗）。

| 折 | 特徵組 | 模型 | 日期等權 Brier | pooled AUC |
|---|---|---|---:|---:|
| F1 | F14_12 | catboost_innerselected | 0.247042 | 0.5483 |
| F1 | expanded15 | catboost_innerselected | 0.247585 | 0.5391 |
| F1 | two_selected_expanded15+expanded15 | equal_weight_ensemble | 0.252919 | 0.5165 |
| F1 | F14_12 | lightgbm_innerselected | 0.247810 | 0.5412 |
| F1 | expanded15 | lightgbm_innerselected | 0.248045 | 0.5358 |
| F1 | expanded15 | logistic_calibration_frozen | 0.254001 | 0.5255 |
| F1 | F14_12 | logistic_innerselected | 0.246923 | 0.5541 |
| F1 | expanded15 | logistic_innerselected | 0.246941 | 0.5539 |
| F1 | expanded15 | xgboost_calibration_frozen | 0.253878 | 0.5049 |
| F1 | F14_12 | xgboost_innerselected | 0.247345 | 0.5419 |
| F1 | expanded15 | xgboost_innerselected | 0.247980 | 0.5307 |
| F2 | F14_12 | catboost_calibration_frozen | 0.252731 | 0.5425 |
| F2 | F14_12 | catboost_innerselected | 0.256752 | 0.4973 |
| F2 | expanded15 | catboost_innerselected | 0.256567 | 0.5094 |
| F2 | two_selected_F14_12+F14_12 | equal_weight_ensemble | 0.251997 | 0.5582 |
| F2 | F14_12 | lightgbm_innerselected | 0.256717 | 0.4973 |
| F2 | expanded15 | lightgbm_innerselected | 0.256773 | 0.5054 |
| F2 | F14_12 | logistic_calibration_frozen | 0.252204 | 0.5617 |
| F2 | F14_12 | logistic_innerselected | 0.255365 | 0.5126 |
| F2 | expanded15 | logistic_innerselected | 0.258092 | 0.5179 |
| F2 | F14_12 | xgboost_innerselected | 0.256723 | 0.4932 |
| F2 | expanded15 | xgboost_innerselected | 0.256771 | 0.5019 |


**注意：**本段是已被反覆檢視歷史期間上的發展性模型比較；並未獲得新的獨立樣本外驗證。不可因表中單一最低 Brier／AUC 升級正式模型。

## 機率校準與固定等權 ensemble

| 折 | 模型 | 特徵組 | 原始 Brier | sigmoid Brier |
|---|---|---|---:|---:|
| F1 | xgboost | expanded15 | 0.253878 | 0.261968 |
| F1 | logistic | expanded15 | 0.254001 | 0.261859 |
| F2 | logistic | F14_12 | 0.252204 | 0.244429 |
| F2 | catboost | F14_12 | 0.252731 | 0.246793 |


實測 F1 的兩個 sigmoid 校準均使 Brier 惡化，F2 則改善，**不存在跨時段穩定校準增益證據**。

Sigmoid calibrator 僅 fit 在外層起點前已成熟的最後20日期 cohort，底層校準模型的 fit 更早；與全量train raw模型是兩種不同 fit 範圍，不得將「raw全歷史 vs calibrated短窗」解釋為純校準因果增益。前瞻校準、reliability curve與月份漂移仍待驗證；兩模型固定50/50 ensemble不使用外層成績決定加權。

## 日期配對區塊 CI 敏感度

| 日期區塊 | 日均損失改善 (15F－12F) | 95% CI | 判讀 |
|---|---:|---|---|
| 10 | 0.001083 | [0.000040, 0.002404] | CI_EXCLUDES_ZERO |
| 20 | 0.001083 | [-0.000073, 0.002558] | INSUFFICIENT_EVIDENCE |
| 30 | 0.001083 | 樣本不足 | INSUFFICIENT_BLOCKS |


CI先算每日相同股票的 Brier loss 差，維持當日完整市場股票截面，再抽連續日期區塊。56日期中20/30日期區塊的有效獨立證據極少；10日CI即使不跨零，也不能無視多組消融 selection bias 並宣布優勝。CI跨零意指 `INSUFFICIENT_EVIDENCE`，不等於無訊號。

## 已知風險與下一步

1. 42日期原XGBoost需依原始 **3.4.1** 執行環境與精確model artifact重現；本輪3.1.3結果保留mismatch，不覆蓋原報告。
2. 取得 X/Y 對應的更早 raw OHLCV、正式分市場交易日曆、價格調整/公司行動/歷史 PIT/universe membership 證據後，才能做 H1 純暖機隔離，以及 ret120 缺值精確分類。
3. 繼續累積 **鎖定候選後** 的固定前瞻預測，20 個市場交易日實際成熟才回收 Y；不因尚無新 untouched OOS 阻止目前研究診斷。
4. 在固定未觸碰時期重新評估已鎖定候選，採日期等權 Brier、10/20/30 區塊 CI、分市場、月份、流動性、波動、校準與涵蓋率全量揭露；不得為挑正向切片重選結果。
5. 如果加做交易效益，必須先固定T收盤訊號→T+1可成交開盤，明列費率、滑價、交易稅、漲跌停、停牌和20日重疊部位資本預算；本次未量測成本後效益。

## 完成判定（僅對應實證）

- **REPRODUCED**：X/Y原始hash、42日期常數/Logistic、56日期Logistic因子組同樣本歷史數值。
- **RESEARCH_CANDIDATE**：H2/H3/H4/H5對照、多模型有限預算與時間隔離sigmoid研究，僅適用這組development期間及此版本資料。
- **INSUFFICIENT_EVIDENCE**：12因子優於15因子的穩定性、新模型勝過盛行率/Logistic、機率穩定校準或交易效益。
- **BLOCKED**：H1原始暖機純效果、42日期原XGB精確版本、未觸碰前瞻OOS、正式PIT/來源用途/價格調整與model promotion。

**沒有修改 canonical、Risk ACTIVE、Registry、GCP排程、dev serving，亦未啟用付費資源。** 完整來源、因子序、每次試驗、逐筆預測、1,526 筆模型×市場日期指標、fold/slice與校準收據均保存在本套 research-only 交付中。