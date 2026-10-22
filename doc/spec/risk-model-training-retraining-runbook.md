# D07 Risk｜XGBoost 建模、每日推論與重訓週期操作規則

更新：2026-10-22。權威：GitHub main／真實 dev runtime；原始研究從 Google Drive `janusChatGPT` 讀取。**本文件是可重跑與部署契約，並非已發布的聲明。**

## 1. 角色與目標
Risk 的唯一預測目標：未來 **20 個上市／上櫃市場交易日** realized annualized volatility（年化波動率），不能直接解讀成上漲機率、下跌機率、最大跌幅或買賣建議。以全部合格普通股 pooled XGBoost regressor 而非每檔獨立模型。現行候選：`risk-xgboost8-2025h2-v1`；正式 deterministic Risk baseline 在 registry promotion 之前不可覆寫。

## 2. 八個時間 t 可知因子／公式
`vol20` / `vol60`：每日 ln(close_t/close_t-1) 平方平均開根號 × sqrt(252)；分別需要20/60筆完整相鄰市場交易日 return。
`drawdown60`：close_t / max(close最近60交易日) − 1。
`abs_return5`：abs(close_t/close_t-5 − 1)。
`volume_ratio20`：volume_t / mean(volume[t-20:t-1])，分母零→null。
`atr14_pct`：最近14交易日 TR=max(high−low, |high−prior_close|, |low−prior_close|) 的平均／close_t。
`abs_overnight_gap5`：最近5日 abs(open_t/prior_close−1) 的平均。
`log_turnover20`：ln(1+最近20市場交易日成交金額 TWD 的平均)。
上市/上櫃日曆各自對齊；停牌/資料缺日不可當成隔日、不可forward-fill或補零。訓練、每天推論同一特徵程式／順序／單位。若 corporate action 未核對，風險輸出維持非validated，不自行校正股價。

## 3. 2026Q3 封存研究週期（歷史診斷，不是新holdout）
週期ID：`2026Q3-20261022`。原始 Drive 2025-01～2026-09 21個月 `r1` 月檔，共799,468 OHLCV列（TWSE普通股≥90%／TPEx普通股≥70%研究涵蓋，非PIT認證）。2025-07-01開始訓練訊號，只有 label成熟於2026-06-30以前才入訓：369,194行／223獨立訊號日。2026-07-01至2026-09-30為指定測試訊號範圍，實際最後可評分訊號2026-08-31，74,487行／43獨立訊號日。2026-09成熟標籤延遲，不將未成熟訊號算作失敗或成功。所有模型相同股票/訊號日期/標籤，歷史period已檢視，不是 untouched test。

| 模型 | MAE | RMSE |
|---|---:|---:|
| Rolling Vol20 | 0.154224 | 0.210698 |
| Ridge5 | 0.140003 | 0.183075 |
| Ridge8 | 0.135385 | 0.178479 |
| XGBoost8 | **0.129701** | **0.172598** |
| MLP8 | 0.129612 | 0.171706 |

MLP和XGB差異不足以證明MLP長期較好；XGBoost選為**正式候選**，非已啟用。XGBoost固定：240樹、深度3、learning_rate0.05、subsample0.8、colsample_bytree1.0、lambda10、min_child_weight25、hist、seed20261022。標準化用於Ridge／MLP，**XGBoost八因子原值直接入樹，不使用Ridge的scaler**。程式 `research/colab/run_risk_time_split_xgb.py`，研究對照 `research/colab/risk_v1.py`。模型封存 `03_models/risk-xgboost8-2025h2-v1.ubj` SHA256 `36c77d0168a1d667223ab915c9b08fd2c1c6608f9f7db2fc046204e922854044`。該封存模型以本地Python `xgboost==3.1.3` 原生 load_model 並在74,487個封存 OOS 行重新預測，MAE=0.12970133625455632，RMSE=0.17259792399697213；99個封存檔SHA256全數吻合。這不是GCS／Cloud Run讀回。

## 4. 每期 immutable cycle layout
`janusChatGPT/Risk 模型｜研究與重訓/<YYYYMM-cycle-id>/`，一次訓練一個 cycle，不可覆蓋：
- `00_control/bundle_manifest.json`：cycle_id、Git SHA、依賴鎖版、seed、完整files sha256／size／模型驗收狀態。
- `01_code/`：使用當輪 Git SHA 對應程式、CLI命令、requirements、執行log；不含token。
- `02_data/source_r1/`：保留已封存月檔原件或**可重建的原件Drive ID／SHA索引**；必須分清是否實際複製。 `02_data/train`／`02_data/test`：有權保存時存實際特徵/標籤快照，無權時只存合法manifest參照/拒絕原因。資料含源授權不得隨意公開。
- `03_models/`：XGB原生UBJ、Ridge JSON、MLP安全模型格式、測試向量及SHA；不得使用任意pickle。
- `04_reports/`：train/OOS、按月/上市/上櫃、交易日block不確定區間、公司行動/歷史PIT/來源可用性、drift與rollback readback。
- `05_readme/`：本次變更、受限用途、可重跑指令和狀態。
正式GCS model candidate只有在source rights、特徵相容／PIT、OOS與可重現性等promotion gate通過後才寫入現有dev Mart bucket；**Drive cycle不等於GCS model registry**。

## 5. 統一批次與更新頻率
- **交易日盤後**：官方Core當日OHLCV確實入庫 → 既有Cloud Scheduler/Controller在同一批次派給Mart，對全市場普通股union按symbol分塊特徵/模型預測，保存每symbol的 analysis_as_of/source_hash/model_version/feature_version/output_hash、預測年化波動、近期對照、缺值與產生時間。**GCS只是儲存，不負責運算**；既有Controller和Mart不能新建相同cron重複跑。
- **每日 UI**：持久化 Risk 語意訊號，非MAE排行。當預測波動/近期波動≥1.20顯示「波動風險升高」警示色；≤0.80顯示「相對緩和」青綠色；其他中性色。「緩和」不是看漲／買進；缺值、過期、ML未驗證全部中性色與原因。這是第一版*呈現門檻*，不冒充已校準的獲利機率。
- **小字**：顯示真正 `analysis_as_of`、實際完成時間（若有）、`更新頻率：交易日盤後`、`model_version`、資料新鮮度。禁止以目前系統時鐘假造最後更新時間；時間缺失就只顯示資料日／未取得。
- **每週**：資料缺漏與成熟預測誤差聚合、上市/上櫃及極端事件分組、漏跑/partial狀態；不重訓。
- **每月**：按已成熟20交易日 outcome 比較 Rolling20/Ridge5/Ridge8/XGBoost8，至少MAE/RMSE/獨立日數/覆蓋/區塊信賴區間與是否劣化；不看仍未成熟的9月標籤。
- **每季**：先評估重新訓練是否具有足夠新資料與顯著改善；若批准新cycle則新模型/新manifest，原版不覆寫，必經shadow/promotion。
- **缺測及rollback**：model artifact/來源/特徵不一致→shadow/正式ML fail-closed、保留原確定性基準及最後合格版本，時間過期明示；不得以research模型數值偽裝正式validated。

## 6. Promotion的不可省略驗收
1. 來源訓練權利與 retention、歷史下市股／survivorship／PIT、有據公司行動調整基準。
2. 新增未觸碰前瞻 cohort，先記預測再等20市場交易日標籤成熟；跨月/市場、尾部及成本/流動性劣化檢查。
3. GCS candidate UBJ bytes+hash讀回，model loader只接受已核XGBoost原生格式／白名單schema，附feature-order/units與安全 test vector；不可在UI/LLM publish gate外直通。
4. 現行Mart Core資料列提供 open/high/low/close/volume/turnover與市場交易日證據，按與訓練同一程式算出八因子；固定測試向量和dev日批次 shadow parity PASS。
5. 原子registry compare-and-swap切版、可回退到舊版/確定性基準、部署CI PASS、真實Cron/Controller/Mart/job和API/UI讀回；有一項未滿足不得自稱ACTIVE。
沒有新付費資源、不恢復Cloud Run訓練器、不重抓既有21個月資料。

