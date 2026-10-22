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
正式GCS model candidate 是已凍結原生 UBJ 的待驗證存放區；首次 promotion 另依第6節的**有界安全／一致性驗收**判定，現有候選讀回並不表示 ACTIVE；**Drive cycle不等於GCS model registry**。

## 5. 統一批次與更新頻率
- **交易日盤後**：官方Core當日OHLCV確實入庫 → 既有Cloud Scheduler/Controller在同一批次派給Mart，全市場普通股只執行 screening；Risk XGBoost 對 control.mart_ai_target_symbols(as_of) 去識別持股／觀察股聯集按 symbol 分塊特徵／模型預測（ETF 排除），保存每symbol的 analysis_as_of/source_hash/model_version/feature_version/output_hash、預測年化波動、近期對照、缺值與產生時間。**GCS只是儲存，不負責運算**；既有Controller和Mart不能新建相同cron重複跑。
- **每日 UI**：持久化 Risk 語意訊號，非MAE排行。當預測波動/近期波動≥1.20顯示「波動風險升高」警示色；≤0.80顯示「相對緩和」青綠色；其他中性色。「緩和」不是看漲／買進；缺值、過期、ML未驗證全部中性色與原因。這是第一版*呈現門檻*，不冒充已校準的獲利機率。
- **小字**：顯示真正 `analysis_as_of`、實際完成時間（若有）、`更新頻率：交易日盤後`、`model_version`、資料新鮮度。禁止以目前系統時鐘假造最後更新時間；時間缺失就只顯示資料日／未取得。
- **每週**：資料缺漏與成熟預測誤差聚合、上市/上櫃及極端事件分組、漏跑/partial狀態；不重訓。
- **每月**：按已成熟20交易日 outcome 比較 Rolling20/Ridge5/Ridge8/XGBoost8，至少MAE/RMSE/獨立日數/覆蓋/區塊信賴區間與是否劣化；不看仍未成熟的9月標籤。
- **每季**：先評估重新訓練是否具有足夠新資料與顯著改善；若批准新cycle則新模型/新manifest，原版不覆寫，必經shadow/promotion。
- **缺測及rollback**：model artifact/來源/特徵不一致→shadow/正式ML fail-closed、保留原確定性基準及最後合格版本，時間過期明示；不得以research模型數值偽裝正式validated。

## 6. 首次 promotion：接受限制與不可免除的安全門檻（2026-10-22 最新決策）

本節覆蓋舊版「先等新增20交易日成熟OOS、補全歷史PIT/全部公司行動」的等待要求；**不可把放寬門檻稱作嚴格驗證 PASS**。沿用 `risk-xgboost8-2025h2-v1`，未改訓練資料/基準時保留既有 SHA。

1. **歷史 OOS**：訓練 2025-07 起，僅用 2026-06-30 前成熟的 train Y；測試 2026-07 至 2026-08 的 43 獨立訊號日／74,487 同樣本 rows，XGB MAE 0.129701/RMSE 0.172598；Rolling20 0.154224/0.210698。分市場、逐月原研究報告須有證據，不能由總分臆測。這是已檢視的歷史診斷，不是新的 untouched holdout。
2. **正式上線後 OOS 回收**：先寫入不可覆寫的當日預測（model/feature SHA、core snapshot、source、as-of），等**同市場第20個交易日**與合格 EOD 到齊才生成不可覆寫的 label/result；未成熟 `PENDING` 不計 MAE/RMSE/勝負；每月按市場、月、獨立訊號日對 Rolling20 比較並保存 receipts。訓練與 serving 不能使用未成熟 label，歷史修訂不得覆蓋原始預測。
3. **PIT 有界安全**：八因子僅源自 cutoff 前市場已發生且可用的 OHLCV；禁止未來 bars、未來公開的改版或當日 EOD 未完成即作盤前已知。當天抓取歷史檔的 fetched_at 不可偽稱當時 first published_at；無完整歷史名冊/修訂時誠實註明 `CURRENT_MASTER_ONLY` 與 non-strict PIT，不要求全面追溯才進首次 promotion；確證 leakage 則必修。
4. **公司行動**：針對實際 train/test/serving 特徵與 Y 價格窗口核對；有合格調整因子則整窗同口徑；無可驗證口徑則排除已知污染樣本／股票推論，留理由和恢復條件。不可將超過閾值的真實市場暴跌自動視為公司行動而修平／刪除。任何變更訓練基準/樣本重新評估，必要時重訓並產新模型 hash。
5. **來源准入（最新）**：只要 TWSE／TPEx 有支援八因子 OHLCV 的明確授權開放資料存在，首次 promotion 的來源可用性 gate 就視為 **PASS**；已證實 data.gov.tw/dataset/11549、/11370（OGDL 1.0），不用逐月逐 API 反查 r1 授權或重抓合格原件。僅此 gate 放寬；原 r1 採集來源保留 UNKNOWN（不是該 open-data 端點授權的證明），實際禁止者不得當作已獲許可。使用 OGDL 資料須顯名，其他技術驗收照舊。
6. **必要技術證據**：同一正式樣本研究／serving 八因子公式、順序、單位、缺值和 float32 XGB 直接輸入（無 scaler）固定向量與 prediction parity；僅對持股+觀察股票的去識別 symbol union 推論，ETF N/A；安全 UBJ loader + GCS SHA 讀回、immutable manifest、原子 registry CAS（expected-previous）及可回退到 deterministic/前版；targeted CI PASS。真實 shadow/GCS 10/21 已 PASS，不重跑本項。
7. **切 ACTIVE 之後才完成**：正式 API/UI 可見性、Owner 隔離與自然日批連續性實機讀回；此為發布後 acceptance，不把尚未切換當成本次「可進 promotion」先決等待門檻。若必要防護或 CAS 入口尚不存在，須明確 BLOCKED，不可手動改 JSON publication flag。

**授權核對資料（2026-10-22）**：OGDL-Taiwan 1.0 條款 https://data.gov.tw/license 明列不限目的的重製、改作、公開傳輸及衍生產品/服務，並有來源標示義務；若**實際同一資料集**適用此條款，ML 特徵／訓練與合法模型成果部署原則上可依其廣泛利用授權辦理，展示來源出處必須可追溯。證據範例：TWSE 個股日成交資訊 https://data.gov.tw/dataset/11549 與 TPEx 上櫃股票行情 https://data.gov.tw/dataset/11370 均標示 OGDL-1.0，但**目前 r1 採集路由**是 `www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX`、`www.tpex.org.tw/web/stock/aftertrading/otc_quotes_no1430/stk_wn1430_result.php`，不能僅憑欄位相同把政府平台特定 dataset 授權套用至不同 endpoint；須透過該路由自身條款/資料集映射或合法等價開放資料證實後，才能標示本候選 `ML_SOURCE_RIGHTS_VERIFIED`。以上為有界授權證據，不等於本 candidate 原始21月資料已過授權核對。記錄查閱日 2026-10-22，不會擴查不相關資料集。

正式發布入口必須從現有 repository workflow/CLI 實際確認；**本指令不授權切 ACTIVE**。不新增付費資源，不恢復退役研究管線，不重抓已有合格資料。
沒有新付費資源、不恢復Cloud Run訓練器、不重抓既有21個月資料。



## 7. 實際來源用途核對（2026-10-22；僅 Risk 現有21月與 target 推論）

本次使用者允許**合法開放資料，不限官方**，亦不要求先窮盡官方；以**原資料集的授權與實際使用管道**為單位，而非網站品牌／欄位相似即自動當作有權。本節為截至 2026-10-22 的授權查核證據，非法律意見。

| 資料集／途徑 | 授權來源、核對 URL | 取得 | ML訓練 | 保留衍生品/模型 | 部署／展示 | 對既有候選影響 |
|---|---|---|---|---|---|---|
| TWSE 個股日成交開放資料（CSV，`exchangeReport/STOCK_DAY_ALL?response=open_data`） | [data.gov.tw/dataset/11549](https://data.gov.tw/dataset/11549)，授權 OGDL 1.0；原開放資料 [授權全文](https://data.gov.tw/license) | 在條款和下載方式內允許 | OGDL 授與不限目的衍生利用，包括模型訓練；需正確標示來源 | 同授權、留存及來源標示須遵守 | 同授權，UI出處須明確 | **授權路徑成立，不代表21月原件來自該CSV** |
| TPEx 上櫃股票行情開放資料（CSV，`DAILY_CLOSE_quotes/stk_quote_result.php?l=zh-tw&o=data`） | [data.gov.tw/dataset/11370](https://data.gov.tw/dataset/11370)，OGDL 1.0 | 同上 | 同上 | 同上 | 同上 | **須與現有 `OTC_DAILY` 原始來源對帳** |
| 實際研究 r1 TWSE `MI_INDEX` `https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX` | [TWSE 網站條款 §6/§8](https://www.twse.com.tw/zh/terms/use.html)：非同意方式之自動化下載受限；未經同意重製/改作有限制，政府開放資料平台授權之**特定**資料除外 | **尚無實際 r1 來源條款/授權映射證據** | **UNKNOWN** | **UNKNOWN** | **UNKNOWN** | 本模型訓練來源，不能僅因同類 open-data CSV 欄位相同自動認證 |
| 實際研究 r1 TPEx `OTC_DAILY` `https://www.tpex.org.tw/web/stock/aftertrading/otc_quotes_no1430/stk_wn1430_result.php` | 同一網站另有上櫃行情開放 CSV；本端點與 CSV 路徑不同；資料商品訂購條款不能無證據套用於此免費端點 | 實際用法需明確來源授權 | **UNKNOWN** | **UNKNOWN** | **UNKNOWN** | 本模型訓練來源，待對帳或有權替代 |

依 OGDL 1.0，可在授權適用的資料集上進行多種衍生利用（包括 ML、儲存、部署模型與展示），但**顯名聲明**是取得授權的條件；不可拿一般網站爬得的資料自動擴大範圍。若供應者明示不許或資料不屬該 OGDL 資料集，必須排除/替換；若尚未對帳，只列受影響用途 `TRAINING_SOURCE_RIGHTS_UNKNOWN`，不可假稱 PASS。

**最新有限判定**：開放來源存在即算本輪來源可用性 PASS（2026-10-22 使用者覆蓋舊逐月來源 gate）；不再把 21 月 r1 endpoint 授權映射列為 promotion 等待工作。既有 r1 的實際 API 與政府開放資料集不同，此事只記 provenance 與授權未確證限制；不聲稱原 r1 已獲 OGDL 授權。只有取得確定禁止的實際來源證據時，才需停用受影響用途、採合法開放替代並評估是否須重訓；沒有具體異常不新增假設性待辦。

## 8. 本輪有界工程證據（非 ACTIVE）

- `#39790661297` / commit `5f2576cde9bd8c747f96befcf6e7aa2c5510ee1f`：read-only `completed/success`，preflight 4/4 tests、GCS candidate hash及2026-10-21的1,720筆 shadow讀回 PASS； `BLOCKED_NOT_ACTIVE`，前瞻 OOS `PENDING`。此 Run 不執行八因子固定向量或 CAS。
- `research/colab/risk_matured_outcomes.py`：提供20市場交易日、不可變原預測／label 回收與 Rolling20 同樣本評分的離線純函式，不等於已接上自然月批。 `tests/test_risk_feature_parity.py`：同樣本研究／serving 八因子 float32 對照，仍須 CI 與真正固定 UBJ 的 live prediction parity 收據。
- `risk_shadow.py` 明確拒絕 trade_date/已知 published_at/availability_at 在 cutoff 之後的資料；從未聲稱 fetched_at 等於歷史 published_at。 `market_screening.py` 對全市場僅 screening，Risk 只對 `control.mart_ai_target_symbols(as_of)` 去識別持股＋觀察股普通股；現行十月已寫的舊 shadow 的 1,720 **不是聯集總數**，未經讀回不得虛構 ETF 排除筆數。
- 現有 `.github/workflows/risk-v1-dev-readback.yml` 是唯讀 preflight，`.github/workflows/risk-v1-candidate-dev.yml` 只傳候選，`.github/workflows/risk-v1-manual-shadow-once.yml` 只做一次 shadow。**目前這三者均不是 ACTIVE promotion/Registry expected-previous CAS 入口**。未完成真正可回滾切換入口前，維持 `BLOCKED_NOT_ACTIVE`、`publication_allowed=false`。

### 8.1 來源 gate 最新結論（2026-10-22，覆蓋 §6／§7 較嚴舊語句）

狀態：`OPEN_DATA_AVAILABILITY_PASS_BY_APPROVED_POLICY`。TWSE 開放資料集 [11549](https://data.gov.tw/dataset/11549)、TPEx 開放資料集 [11370](https://data.gov.tw/dataset/11370) 均為 OGDL 1.0，已證明合法開放的 OHLCV 類資料可用；包含可作衍生研究與模型的開放授權條款，使用者採用時須遵守來源標示。**不再將 r1 歷史採集 endpoint 是否與上述 dataset 完全相同作為首次 promotion 卡關原因。**

此 PASS 是「開放替代來源存在」的專案准入政策，**不是**既有訓練檔逐筆授權／來源替換或新的 GCS 模型訓練收據，保留 `r1_source_license_mapping=UNKNOWN_ACCEPTED_LIMIT`。其他有界 PIT 無洩漏、公司行動污染處置、特徵一致性、CAS/rollback 仍須實證；不可把改來源標準當成模型已 ACTIVE。
