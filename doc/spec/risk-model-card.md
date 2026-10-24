# Janus Risk 模型卡｜候選 XGBoost8（2026Q3）

> **2026-10-24 研究精簡決策優先**：本文涉及獨立資料稽核、逐來源補證、全歷史 PIT／精確時間校準、例行週月稽核及自然驗收等待的要求已取消，不再是待辦或發布前置。依 [研究精簡政策](research-simplification.md)，保留必要日期／單位、基本防洩漏與操作安全；歷史證據不改判 PASS。


更新：2026-10-22；**模型選型：XGBoost8 研究候選**。部署狀態：**CANDIDATE_PENDING_BOUNDED_PROMOTION_ACCEPTANCE**，不等於DEV ACTIVE。詳細流程：[完整重訓/日批操作手冊](risk-model-training-retraining-runbook.md)。

## 1. 用途與不適用事項
輸入某股票訊號日及之前八個OHLCV歷史因子，輸出未來20個市場交易日的**年化價格波動率**，作「波動升高／相近／緩和」警示，輔助操作風控。非上漲/下跌機率、非未來20日價格幅度、非最高可能虧損、非合理價、非持股金額建議。公開模型不接受Owner現金/成本/張數。僅適合來源受控的TWSE/TPEx普通股，ETF及當時無可用窗口者不能套用。

## 2. Model registry候選
`risk-xgboost8-2025h2-v1`；XGBoost `3.1.3` `XGBRegressor` 240樹、深度3、0.05 learning rate、subsample0.8、colsample_bytree1.0、min_child_weight25、reg_lambda10、squared error、seed20261022。raw UBJ `risk-xgboost8-2025h2-v1.ubj`，280,660 bytes，SHA256 `36c77d0168a1d667223ab915c9b08fd2c1c6608f9f7db2fc046204e922854044`。八因子固定順序 `vol20,vol60,drawdown60,abs_return5,volume_ratio20,atr14_pct,abs_overnight_gap5,log_turnover20`。**XGB不需StandardScaler**；以float32 inputs推論，結果裁剪至非負。輸入不得包含label欄位。

## 3. 原始資料與分割
2025-01～2026-09、21個月r1 SHA provenance，799,468原始普通股OHLCV，名冊只含**2026年現行母體**，不是歷史退市PIT名冊。train 2025-07起訊號截至2026-06-01，20日Y成熟截至2026-06-30：369,194行、223訊號日；test 2026-07～09區間，僅7～8月訊號於9/30前成熟：74,487行、43訊號日。來源：Google Drive `janusChatGPT/資料源`；訓練與測試快照封存在 `Janus-Risk-Cycle-2026Q3-20261022.zip`。訓練CSV.gz hash `d798d38765b4b230fac57cee1d41cf02264417da5be9abc113d77cc3673bfacf`；測試hash `858124bf1e08c2b0eb9000ade3a05d0fa8f1f1b7735736f235942d7d2b19278c`。

## 4. 研究OOS結果（相同股票/日期/答案）
Rolling20 MAE 0.154224 RMSE0.210698；Ridge5 0.140003／0.183075；Ridge8 0.135385／0.178479；**XGBoost8 0.129701／0.172598**；MLP8 0.129612／0.171706。XGB相對簡單baseline MAE改善15.90%，但測試只有43個訊號交易日且研究者早已檢視2026年7/8月資料，不是獨立test。MLP分數雖更低0.000089，但差距極小，不選較重的深度學習依賴。正確分市場/每月OOS和block uncertainty另見週期原始報告，未做新期間可遷移因果保證。

## 5. Artifact完整性
2026-10-22：臨時Python環境驗證週期bundle_manifest 99個檔案 SHA/bytes均符合；XGBoost UBJ原生load_model成功，對封存74,487筆test重新預測，MAE **0.12970133625455632**、RMSE **0.17259792399697213**，與收據完全符合。**不是** Colab console/GCS/Mart/CI/runtime acceptance。

## 6. 風險與禁止發布狀態
- `publication_allowed=false` 表示候選仍未切 ACTIVE；本次首次發布不再等待新前瞻20日 mature OOS、全市場歷史 PIT 名冊、全公司行動紀錄。不可據此宣稱那些嚴格驗證已完成。來源 gate 以已有適用 OGDL 開放資料即 PASS（TWSE 11549／TPEx 11370）；不再逐月查核舊 r1 採集 API 授權映射，此來源映射屬接受限制、不得冒稱原模型由該開放 dataset 訓練。仍需實際窗口公司行動污染處理、cutoff 無 future leakage、八因子及 GCS/serving parity、Registry CAS／rollback，才可判定能 promotion。
- 2026年現行名冊導致歷史 survivorship bias，是**已接受的首次發布研究限制**，不得標成歷史 strict PIT。原始 OHLCV 未全數調整，實際 train/test/serving 窗口發現不可比的公司行動必須排除或有據調整；來源自動存取與 ML／保存／部署權利必須逐來源核對。
- 此模型預測方向是volatility高低，沒有估未來報酬機率；請勿用回測 MAE 當成買賣策略收益。
- 欠行情/特徵/來源、model SHA不符、超過更新期都fail-closed回 deterministic Risk 基準，不顯「低風險」等樂觀資訊。
- XGB未調過以新holdout為準的閾值；Risk高風險/緩和的20%比值只是使用者訊號UI第一版顯示規則，獨立評估後才可正式開啟。

## 7. UI/更新節奏
展示「Risk分析師｜波動風險升高／相近／緩和」、可讀理由、分析日及模型版本和資料新鮮度；警示深橘、相對緩和青綠、未知/過期中性。**不顯示MAE與模型分數當作股票訊號**；不把青綠當買進。每交易日盤後只對去識別持股與觀察股 symbol union 更新固定模型推論（普通股；ETF N/A），全市場仍可作 screening，每週資料檢查、每月成熟標籤OOS評估、每季重訓檢討；訓練不在Cloud Run執行，正式批次重用Scheduler→Controller→Mart。

## 8. 紀錄維護
啟用後每日 immutable prediction 到第20市場交易日及 EOD 完成才回收 mature label，未成熟為 PENDING；每次月度評估只新增不可覆寫evaluation receipt；每次重訓新建cycle_id與對應manifest、資料快照/來源索引、訓練程式 Git commit SHA、bundle/registry收據。禁止更新或覆蓋此版已封存模型卡數字及受限狀態，變更另立新版模型卡。
