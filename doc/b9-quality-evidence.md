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

## B9 剩餘驗收

1. 建立有真實來源／PIT 歷史 membership 的 evaluation cohort，不擴成每日 500×5 五模型運算。
2. 對充分樣本逐模型／horizon 驗證 label maturity/purge、IC/ICIR、decile spread、calibration、cost/turnover、regime stability、champion-vs-baseline；缺樣本維持 insufficient。
3. Fundamental／Valuation 保留核准的資料優先且非 strict PIT 語意，不能宣稱嚴格歷史版次已證明；Event 需要經授權標記資料、local classifier 和真實 OOS。
4. 將 prediction-level provenance/source authorization、隔離邊界、SHAP／contributions、版本與 artifacts 一起稽核，最後才對每個 Specialist 決定是否通過品質 gate。
5. 任何 champion promotion 必須有真實 Taiwan OOS、對照、審核與持久化 evidence；不得自動 promotion。

完整 acceptance 維持 [active TODO](todo.md) B9 與 [Specialist SPEC](spec/specialist-engines.md)。B9 ACTIVE／PARTIAL，C 組尚未啟動。
