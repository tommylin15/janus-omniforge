# B9 五 Specialist／OOS 品質驗收：首輪唯讀證據

更新：2026-10-10（Asia/Taipei）  
狀態：**PARTIAL / MODEL QUALITY NOT VERIFIED**，此頁不是 B9 結案。  
範圍：B0～B8 不重做；B7 快取 freshness PASS 與 B9 模型品質獨立判定。

## 真實 dev 證據

- 新增獨立唯讀 GCS audit 與 GitHub Actions；不觸發月度重訓、champion promotion、canonical write 或 LLM。
- 固定 Core fence：sha256:687fae3ea802ef255bd33ecf5e21a6d25801c467f8836181dae9fc3ef97a344e，和 B7 最新受驗證 Core 同源；audit 當下是否仍為所有 Core 的最新來源尚未獨立驗證。
- 首輪 [Actions #38061211051](https://github.com/tommylin15/janus-omniforge/actions/runs/38061211051) 6 項測試 PASS、GCS readback FAIL：稽核程式混淆 specialist logical output hash 與 immutable JSON full-byte SHA256。未修改原始 artifacts。
- 修正後 [Actions #38061288253](https://github.com/tommylin15/janus-omniforge/actions/runs/38061288253) **SUCCESS**，對 25 份 persisted specialist JSON、29 組 OOS evaluation、manifest／pointer hash 完成 GCS readback。對應 source SHA 3734031aa4a2bee5480210209ccbbb899aa8b1b4；六項單元測試 PASS。這是 **artifact readback PASS**，不是 B9 quality PASS。
- 最新獨立 [B9 Actions #38061999283](https://github.com/tommylin15/janus-omniforge/actions/runs/38061999283) **SUCCESS**：9 項單元測試（含 GCS logical vs byte SHA、v5 PIT lineage／tampering negative cases）PASS；既有 immutable **25 specialist／29 OOS** 真實 readback 再次 PASS。既有 v4 persisted predictions 共 **1,536 筆逐模型 prediction records** 未嵌入逐筆來源授權及 sample provenance，保留 legacy/not verified，不事後覆寫。
- B9 新程式碼在 [main 2aea429](https://github.com/tommylin15/janus-omniforge/commit/2aea429df00144158ce08efe5ec6a50c300cccc2) 將新的 OOS evaluation protocol 改為 **taiwan-purged-monthly-v5**，逐筆寫入 already-fenced sample source authorization、sample provenance、feature/label available-at。這只屬未來新 evaluation 的契約，不會改寫既有 v4 GCS immutable results；**尚無 v5 真實 dev OOS output readback，不宣稱完成 live integration**。
- [Mart selective CI #38062072521](https://github.com/tommylin15/janus-omniforge/actions/runs/38062072521) **SUCCESS：143 passed、7 warnings**，包含既有 model walk-forward／OOS regression。CI success 不構成 model quality PASS。
- 此次沒有重訓、BigQuery 工作、Cloud Run Job 變動、champion 升級、publication 或 owner data mutation；固定 execution 的原始 OOS／specialist artifacts 均 immutable。

## 五角色 OOS 觀察

| Specialist | artifacts | Taiwan OOS evidence（5／20／60／120 日） | 尚未通過的 gate |
|---|---:|---|---|
| Fundamental | 5 | LightGBM：141／35／8／2 predictions | Rank IC／after-cost 缺值；未達可發布模型品質，核准財報時間投影明示 strict_pit=false |
| Valuation | 5 | LightGBM、CatBoost：各 144／35／8／2 predictions | Rank IC／after-cost、calibration／champion comparison 缺證據 |
| Quant | 5 | Linear、LightGBM、CatBoost、Qlib：各 189／44／8／2 predictions | 五日各僅 60 校準機率，Brier 約 0.251；其他 horizon 校準樣本不足；Rank IC／after-cost 缺值 |
| Risk／Regime | 5 | statsmodels Markov：23 folds、452 OOS returns、Gaussian baseline 相對 log-score +0.3884 | 僅 research challenger，未達 regime stability／正式 champion／發布 gate |
| Event／Catalyst | 5 | deterministic parser／rules | 無台灣在地 labeled classifier OOS，不能視為已驗證 ML |

25 份正式 specialist 產物均標示 model_status=oos_not_validated；其中 Event 1 blocked、Fundamental 1 blocked、Valuation 1 blocked。日常結構化輸出／白話模板仍保留 no-LLM／no-publication 權限邊界。

歷史 Deep Coverage 僅五個標的，低於十檔跨股票 decile／Rank IC 所需數量。因此月度 evaluation 即使 29 組均有樣本，跨股票 Rank IC、top-decile／after-cost 評估仍是 null，不能當成 0 或 PASS。歷史 PIT membership replay 尚未驗證；individual persisted predictions 也缺乏獨立的 source authorization/provenance 欄位。Event classifier 完整 OOS 不存在。不得將 evaluated 的流程狀態冒充模型品質。

## 五個 Specialist 逐項解法與驗收方案（2026-10-10 決定執行方向；尚未驗收）

以下是 **B9 工程解法／待驗收契約**，不是已通過的模型結果。所有模型共用固定 Core source fence、PIT / source authorization / provenance、標籤成熟與 purge、時間外測試、immutable evaluation、quality-vs-promotion 分離、正常 0 LLM token。不得使用 synthetic return/label 使驗收過關。

### 共同資料與計算策略

- **Daily serving 保持不變**：正式 liquid-500 每日只做輕量 screening；五 Specialist 僅運行 active watchlist ∪ effective holdings，不改成 500×5。
- **OOS research cohort 獨立**：先盤點現有 Core 曾驗證的歷史 watchlist/holdings membership、官方歷史資料及市場 membership；如果能由具有效日期的來源構成至少 10 檔同一 OOS 截面，使用 bounded research-only 回放並保留當日母體、納入/排除原因與 immutable snapshot。不能用現在 500 名單冒充過去 500、不能補造當年成分。若沒有合格歷史 membership，交叉截面 Rank IC／decile／after-cost 保留 null，另計個股時序能力；新增來源或超出已核准回補範圍須先走核准，不逕自擴量。
- **統一品質檢查**：每個 model/horizon 顯示 eligible/train/calibration/OOS counts、fold 日期、label availability、source/time policy、baseline 與 challenger 差異、Rank IC/ICIR/IC decay、decile（足夠截面時）、Brier/校準、hit rate/turnover/cost-sensitive performance。缺值不補 0；30 bps 僅研究敏感度。對照 baseline 的結果為劣勢、樣本不足或不穩定時不 promotion；訓練成功本身不等於合格。
- **產物及治理**：使用已實作的 OOS v5 prediction-level provenance、來源授權和 PIT availability 欄位；未來產生的 v5 immutable artifact 必須真實 dev readback，v4 不改寫。保留 SHAP／deterministic contributions、繁中規則白話、public/private isolation、Admin 只能讀 persisted 真實 quality/reuse/status；champion 和 publication 需獨立授權 gate。

### 1. Fundamental（基本面）

- **資料修正**：沿用 MOPS 等官方已授權財報；以同一份報表的 EPS、歸母淨利年增率及可比較期間/單位/合併口徑建立特徵。缺原始歷史公布版次時依已核准時間投影（公開／上傳時間優先，其次期末+90天），成果保留 `financial_history_policy.strict_pit=false`、時間依據分布，原 canonical 版本/接收時間不改。
- **模型/對照**：deterministic 財務品質特徵與簡單規則作服務 baseline；LightGBM 只用標籤已成熟的擴張視窗，按時間 OOS 比較 naive/no-skill／規則 baseline，保留 SHAP 解釋與缺資料原因。
- **PASS 所需**：官方財報 feature/PIT/單位 negative tests、真實受控 OOS fold、baseline 指標、不可得指標的 insufficient 原因、immutable provenance/readback、未驗證預測不得發布機率。成績沒有優勢可完成研究評估但不升 champion。

### 2. Valuation（估值）

- **資料修正**：沿用既有 TWSE BWIBBU 個股官方 PE／PB／殖利率歷史日期回補（僅核准 Deep Coverage、最多 36 月）。虧損公司 PE、缺殖利率維持 null，不填假倍數；公司/月份/日期/來源 hash 驗證。
- **模型/對照**：deterministic 相對估值作服務 baseline，LightGBM／CatBoost 各自按同一 5/20/60/120 日成熟價格標籤 OOS 對照常數／規則基準；DCF/reverse-DCF 僅在完整自由現金流、股數與核准假設存在時提供，缺值則 `unavailable`，不得拿 PPE 支出代替 FCF。
- **PASS 所需**：官方歷史價值/PIT/readback、兩 challenger 的逐 horizon OOS/SHAP/baseline、DCF 正反面缺值驗證與 source fence，未驗證數值不具 publication authority。

### 3. Quant（量化）

- **資料修正**：不能拿五檔當足夠 cross-sectional 回測。先用有歷史 PIT membership、真實台灣 OHLCV/benchmark 和來源授權的 bounded research-only cohort 增加可評估截面；當前每日 Deep Coverage 不擴張。對 5/20/60/120 日逐窗驗 label 成熟、非重疊 OOS cohort、未來洩漏與交易日期對齊。
- **模型/對照**：Linear 及固定 5 日動能規則為 baseline；LightGBM、CatBoost、Qlib DoubleEnsemble 固定版本/seed/single-thread 比較 IC/ICIR/decay、成本後 turnover/Sharpe/drawdown、Brier 與相對 no-skill Brier，不能以目前 5 日 Brier≈0.251 自稱有效。
- **PASS 所需**：至少合規樣本下的 model-by-model/fold-by-fold 結果、跨截面數量限制、SHAP/prediction reconstruction、真正的 baseline improvement 與未達標時 challenger-veto evidence。

### 4. Risk／Regime（風險／市場狀態）

- **資料/模型**：Riskfolio-Lib 歷史 CVaR、beta、drawdown 作 deterministic 主路徑；statsmodels 兩狀態 Markov 保留至少 252 筆訓練 returns 的 prior-only 逐月擬合、固定參數 forward filtering，不可用全樣本事後 smoothing。已觀察的 452 OOS returns、+0.3884 平均 log score 只是研究證據。
- **補充驗證**：對 Gaussian baseline 比較月/波動環境分段 log score、月間穩定性、狀態切換頻率、極端波動時的誤判/校準；保存未收斂/缺少歷史的 reason，必要時只展示 CVaR 等 deterministic 結果，不輸出 regime probability。
- **PASS 所需**：前視測試、數值收斂、不同 regime 的 OOS 對照與穩定性、真實 runtime readback，沒有足夠可信證據不 promotion。

### 5. Event／Catalyst（事件／催化）

- **資料解法**：從現有已授權的 MOPS/TWSE 等正式事件來源建立可稽核繁體中文標記資料，先由 rules/parsers 產生候選，再由人工檢查事件類別、正/負/中性方向與時點；記錄 reviewer、event ID、去重、來源、發布時間、label version 與分類歧義，**不將規則或 LLM 自動標籤冒充人工真值**。
- **模型/對照**：沿用 deterministic 事件數、嚴重度與規則主路徑；選 license/version 可稽核、可在既有 CPU/1GiB 界限推論的本機 multilingual Transformers encoder + bounded classifier head，先作 offline research training，再以同事件/同發行人群組防洩漏的 chronological holdout 比較 parser/rules baseline 的 macro-F1、類別 Precision/Recall、calibration、drift/unknown。無授權標記資料則 `classifier_probability=null`。
- **PASS 所需**：標記來源授權、人工 ground truth 的標註一致性/樣本分布、真正的 holdout OOS、baseline vs classifier、CPU/RSS、無外部推論 API、immutable model/version/readback。缺有效標記時維持 Event deterministic 功能但 ML 品質 **NOT VERIFIED**。

### 執行次序與完成判定

先共用盤點 source+historical membership → 補 Fundamental/Valuation 核准範圍官方歷史數據並建立 Quant OOS cohort → 在既有 Risk OOS 上補穩定性 → Event 人工標註與本機模型 → 對五角色執行一次整合 targeted/CI/dev artifacts readback、驗證 Admin truthfulness。不要重送 B7 月度 retrain、重跑 B8、提高 1 CPU／1GiB、啟用新付費資源或自動 promotion。

**兩種不同 PASS 不混用**：deterministic 功能可用／OOS 計算及 immutable readback PASS，不等於 ML 有經證明的預測優勢；凡缺合法樣本、baseline 對照、source/PIT 或統計意義，就保持該模型 quality partial/insufficient，不讓 B9 被誤判結案。


## 最新實測增補：B9 v2 逐模型唯讀診斷（2026-10-10）

- 實作 commits [c9f97ea](https://github.com/tommylin15/janus-omniforge/commit/c9f97ea8d38465c8e8f817006d7c56e3049f8c12)（逐模型 OOS descriptive scorecard／三項 negative/coverage tests）與 [bb25c97](https://github.com/tommylin15/janus-omniforge/commit/bb25c97d8eac35641a747ab8b26135041274be8c)（僅將匿名彙總數字輸出 Actions log）。
- [B9 Actions #38063424389](https://github.com/tommylin15/janus-omniforge/actions/runs/38063424389) **SUCCESS**：12 targeted tests PASS；原 immutable 25 specialist／29 OOS GCS 真實讀回 PASS，output `b9-specialist-oos-quality-readback-v2`，v4 prediction 1,536 筆 lineage 仍 legacy missing（未改寫），Event 仍無分類器 OOS。[Selective CI #38063424379](https://github.com/tommylin15/janus-omniforge/actions/runs/38063424379) SUCCESS。這些是**診斷與完整性** PASS，不是模型品質 PASS。
- 新的零訊號基準為 **excess_return 恆等於 0**；對同一 OOS prediction/label 比較平方誤差，`model_minus_zero_mse > 0` 表示模型較差。這只是一個 *descriptive no-skill baseline*，不等於真實可交易策略、已訓練基準模型、交易成本、信賴區間或 promotion 證據。
- **5 日實測差值**（model MSE − zero MSE）：Fundamental LightGBM **+0.0007073**；Valuation LightGBM **+0.0003647**、CatBoost **+0.0052061**；Quant Linear **+0.0004681**、LightGBM **+0.0004064**、CatBoost **+0.0011109**、Qlib DoubleEnsemble **+0.0003907**。**七個 5 日模型全部未勝過零訊號 MSE 基準**，不得以 predictions/folds 存在為由提升模型地位。
- **20 日** Fundamental LightGBM／Valuation 兩模型／Quant 四模型的上述 MSE 差值也均為正；**60／120 日各僅 8／2 筆**，雖有部分負差值但完全不足以支持可靠優勢，不得選擇性引用。5 日同日橫斷面最多：Fundamental **2 檔**、Valuation／Quant **5 檔**；所有 horizon 都不足十檔同截面，無合格 Rank IC／decile／after-cost cross-section。
- **Quant 5 日機率**四模型相對常數 0.5 機率 Brier 改善約 **−0.00106～−0.00111**（負值表示未勝過常數 0.5）；20／60／120 日有效校準不足。Brier baseline 不使用當期觀察到的類別率反向調參。
- **Risk**：23 個 prior-only 月度 OOS folds／452 returns，Markov 相對 Gaussian 月度平均 log-score 改善 **15 個月為正、8 個月非正**；整體既有 +0.3884/return 仍未補證 regime state stability、極端期校準、正式 promotion。**Event**：沒有獲授權的人審標記 holdout／classifier OOS；Parser／Rules 可繼續 deterministic 輸出，但 classifier_probability 應保持 null。
- 新 scorecard 保存每 model/horizon 的 MSE、常數 baseline、機率樣本與 Brier、同日股票數、月度 regime 勝負及缺口 reason；**只讀既有 artifact**，無 B7 retrain、BQ/canonical write、GHCR/Cloud Run 更新或 champion/publishing 動作。

**B9 後續研究解法不變，但優先順序更明確：**先驗證真正歷史 membership/source fence 與財報可用時間、建立合規跨股票 OOS cohort，並加入 trained baseline/challenger 與成本敏感對照；現有 Fundamental／Valuation／Quant 的 5 日 ML 不應升級。Risk 補 regime 分環境穩定性；Event 先取得有審核紀錄的真實繁中 labels，再做離線 CPU bounded classifier。任何缺樣本／證據的角色保持 NOT VERIFIED；**五角色皆有 remediation，不代表五角色品質已解決。**

## B9 剩餘驗收

1. 建立有真實來源／PIT 歷史 membership 的 evaluation cohort，不擴成每日 500×5 五模型運算。
2. 對充分樣本逐模型／horizon 驗證 label maturity/purge、IC/ICIR、decile spread、calibration、cost/turnover、regime stability、champion-vs-baseline；缺樣本維持 insufficient。
3. Fundamental／Valuation 保留核准的資料優先且非 strict PIT 語意，不能宣稱嚴格歷史版次已證明；Event 需要經授權標記資料、local classifier 和真實 OOS。
4. 將 prediction-level provenance/source authorization、隔離邊界、SHAP／contributions、版本與 artifacts 一起稽核，最後才對每個 Specialist 決定是否通過品質 gate。
5. 任何 champion promotion 必須有真實 Taiwan OOS、對照、審核與持久化 evidence；不得自動 promotion。

完整 acceptance 維持 [active TODO](todo.md) B9 與 [Specialist SPEC](spec/specialist-engines.md)。B9 ACTIVE／PARTIAL，C 組尚未啟動。
