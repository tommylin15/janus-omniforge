> **最新執行入口（2026-10-23）：** [四模型目前版本總索引](../research/00-四模型最新版本索引.md)；個股收檔／大盤產業收檔改為兩本 v3.8.4 Colab Notebook，ChatGPT 貼標使用 `label_four_models.py`（含產業 PIT preflight），四角色研究訓練使用 `janus_train.py`。本文件其他 v3.8.2 或更早 Colab 執行說明僅供歷史研究，模型正式發布另行驗收。

# 02｜Risk 風險：XGBoost Colab 建模與 AI 指令

更新：2026-10-22。狀態：**獨立 Notebook 開發規格；既有 XGBoost8 候選沿用**。
交付 Notebook：`02_Risk風險_XGBoost.ipynb`；角色代碼 `risk`。
本份專注重現／下一期研究，不接手目前另一工項的 dev rollout 或重新部署。Risk v2大盤／產業新因子仍依原待辦後續討論。

## 1．唯一主目標

預測未來20個市場交易日的年化實現波動率：
`RV20(T)=sqrt(252/20 * sum(log(close[t]/close[t-1])**2, t=T+1..T+20))`。
這是RMS報酬定義，**不是去均值樣本標準差**。輸出0.30代表年化波動30%，不是20日跌30%、上漲機率或最大損失。

全市場合格普通股pooled XGBRegressor；八因子順序固定，預測裁剪為非負。每股有自己的X／結果，但不是每股獨立fit。

## 2．既有成果如何沿用

正式參照：
- [Risk重訓手冊](https://github.com/tommylin15/janus-omniforge/blob/main/doc/spec/risk-model-training-retraining-runbook.md)
- [Risk模型卡](https://github.com/tommylin15/janus-omniforge/blob/main/doc/spec/risk-model-card.md)
- GitHub `research/colab/risk_pilot.py`、`risk_v1.py`、`run_risk_time_split_xgb.py`。

既有候選 `risk-xgboost8-2025h2-v1` 不改名、不覆蓋；其封存UBJ與2026Q3已檢視OOS保留。Notebook提供：
1. `MODE="research"`：新資料release的試訓／後續重訓，預設使用。
2. `MODE="reproduce_archived"`：只在使用者指定合法封存模型與相同input manifest時，比對原模型／原樣本；新Parquet若有修訂，不要求硬湊原MAE，報差異來源。
歷史重現可另行讀已明確指定的原封存cycle測試向量，屬稽核例外；新訓練仍只用CURRENT指定Parquet。

舊2026-07～09研究範圍已被檢視，不能當新獨立test。不得重新跑過一次就改為untouched holdout。新前瞻評估先留預測，再等20個市場交易日結果成熟。

## 3．必要資料與八因子

OHLCV至少open/high/low/close、股數volume、TWD turnover、trade_date、market、symbol，以及可查證市場交易日。turnover不可拿成交量冒充；市場日缺一日就不壓縮成連續報酬。

| 固定順序 | 定義／最低需求 |
|---|---|
| vol20 | 20個相鄰交易日log return平方均值開根號×sqrt(252)，至少21價格 |
| vol60 | 同上60日，至少61價格 |
| drawdown60 | close／最近60交易日最高close−1；不是完整最大回撤 |
| abs_return5 | abs(close_T／close_(T−5)−1) |
| volume_ratio20 | 當日量／前20日量均值；不含當日於分母，分母0則缺值 |
| atr14_pct | 14日TR平均／close；TR=max(high−low, abs(high−前收), abs(low−前收)) |
| abs_overnight_gap5 | 最近5日abs(open／前收−1)平均 |
| log_turnover20 | log1p(最近20日平均TWD成交金額) |

XGB使用八個原值float32，**不使用Ridge scaler**。Ridge5／Ridge8的scaler僅以train fit。必要八欄缺值時列不可用，先不改舊模型輸入規則。
沿用既有訊號時點可得的shock feature guard，保留版本；不可用未來label shock篩掉不利test結果。公司行動未核對時保留非validated狀態，不猜還原係數。加入市場beta／產業／quantile／MDD是不同版本，不納本次v1 Notebook。

## 4．Y、時間切分與訓練

依市場日曆建立T+20，最後行情真正可用才成熟。跨停牌、漏日或價格基準不一致的窗口列原因；不以「往後20筆非空觀測」代替20交易日。

既有模型重現設定固定：
`n_estimators=240, max_depth=3, learning_rate=0.05, subsample=0.8, colsample_bytree=1.0, min_child_weight=25, reg_lambda=10, objective="reg:squarederror", tree_method="hist", random_state=20261022`。
重現模式不開early stopping、不重新挑參數；xgboost=3.1.3。

新研究模式可沿固定240樹起點與預先登記的最多6組淺樹設定；若開early stopping，上限500樹／30輪耐心、validation專用，輸出best_iteration並驗重載一致。
預設擴張窗、至少120 train訊號日、20 validation日、20 final-test日；train標籤全部在訓練截止前成熟，20交易日purge。同股票／日期對照Rolling20、Ridge5、Ridge8、XGB8；不得各模型dropna後各用不同test表。
18～24月可PROBE；3～5年是成熟研究目標。本版不額外收歷史，只列實際可用日期與後續缺口。

## 5．驗收、輸出及循環

主指標MAE，另RMSE；同樣本對照四種方法、分市場／月份／流動性／高波動區間。按20交易日block估增益區間；至少40個可評分日期才報該bootstrap區間，未達則明示不足。若追加QLIKE，先轉variance且固定正值floor，不能直接把volatility代入variance公式。

預測欄位：symbol、market、signal_date、cutoff、predicted_rv20、baseline_vol20、ratio、model_version、feature_version、source_release、status。近期波動為零時ratio=null。可展示研究用「波動升高／相近／緩和」；1.20／0.80只是既有呈現門檻，不是分類器或機率，未validated仍受正式UI發布限制。

每交易日固定模型推論；每週資料健康；每月成熟20日誤差；每季評估是否人工開新訓練cycle。新增樣本前先核成熟，重訓結果不直接覆蓋champion。

必要測試：跨月61價窗口／缺市場日拒絕；八因子順序與TWD單位；相同close版本去重、衝突版本隔離；T+20成熟截斷；未來價格改動不影響歷史X；未來shock不能影響可用樣本；UBJ重載非負預測一致；歷史重現模式不能冒充新holdout。

## 共通資料與操作契約

- 唯一輸入：`/content/drive/MyDrive/給ai專用/janusChatGPT/資料源/JanusDataset_v3_202610/canonical/CURRENT.json`。啟動時解析其實際結構，固定指向的 release／manifest 與 SHA；同一 run 不追隨中途更新的 CURRENT。
- 只讀該 release 的 Parquet。先讀現有 manifest/schema 和 `reports/模型試訓準入.csv`、`驗收總表.csv`，再依欄位建立明示 mapping；本文的特徵名稱是模型契約，**不代表原檔已有同名欄位**。缺欄位列清楚來源、角色及影響，不回讀舊 CSV／raw 偷補，不在訓練 Notebook 重新收集。
- 普通股 pooled panel，一個角色共同學習多股票；不逐股建模型。ETF 排除；Owner 現金、成本、張數、交易與個資禁止進 X、模型包或公開輸出。上市 ≥90%、上櫃 ≥70% 是分市場研究涵蓋門檻，不是預測準確率，也不要求每檔滿歷史窗口。
- 讀入時驗雜湊、唯一鍵、日期、單位、空值、來源與修訂；衝突列隔離並報原因。合法零與缺值分開。缺日不填零、未來數值不向過去補。公司行動與歷史母體不足可做明示限制的 PROBE，不能冒稱已通過正式發布。
- 財務欄位依當時可得時間 as-of join。缺可靠歷史公告／首次版本時，只能使用明示的 `RESEARCH_NON_PIT`／事後修訂資料實驗；**不可拿期末＋15天／50天的收檔等待規則當公告時間**。實驗和可正式發布資料分開報告。
- Colab CPU 即可；初版以 `xgboost==3.1.3` 對齊既有 Risk 候選，`tree_method="hist"`、`device="cpu"`、執行緒不超過4。實作時鎖定並驗證 pandas／numpy／pyarrow／scikit-learn 相容版本，保存實際環境；不得每次安裝 floating latest。
- 四份 Notebook 可各自從新 Colab runtime「全部執行」，只依賴已完成資料包，不要求先執行其他模型 Notebook。共用 loader／split／artifact 模組只維護一份；交付 Notebook 內嵌固定 Git SHA 對應原碼與 SHA256，可獨立攜帶，不在執行途中下載 main 漂移版本。
- 預設 `MODE="research"`、`UPLOAD_TO_GCS=False`、`publication_allowed=false`。切換發布必須另走既有受控匯入／shadow／promotion，不能因研究分數好就自動啟用。
- 依輸入 release、feature/label/config/dependency hash 組成 run fingerprint。相同設定重跑沿用已完成的資料處理及 fold；變更任一契約建立新 run。斷線最多重跑未完成的 fold，不偽稱能接續 RAM 中的 fit。

## Colab 儲存格與交付物

| 儲存格 | 使用者操作／程式責任 | 必須產出 |
|---|---|---|
| 1 | 安裝鎖版依賴、由本人掛載 Drive | 環境版本、根目錄存在檢查 |
| 2 | 設角色設定、執行模式、seed、截止與預算 | config.json；不含 token |
| 3 | 讀 CURRENT 一次、固定 release、驗 manifest／檔案 SHA | input_manifest.json、欄位 mapping、資料準入報告 |
| 4 | 清洗、時點對齊、建立 X／成熟 Y | features/labels Parquet、拒絕原因、原生期數與缺值表 |
| 5 | **訓練前**凍結日期切分、baseline、指標與選型規則 | split_manifest.json、evaluation_plan.json |
| 6 | baseline → XGBoost；依 fold 存續跑點 | fold metrics／predictions／模型與訓練 log |
| 7 | 鎖定參數後一次最終評估；最新無 Y 列另做示範推論 | 評估報告、分市場結果、預測與未成熟狀態 |
| 8 | 匯出安全模型格式，重新載入核對固定測試向量 | model.ubj／各目標模型、schema、preprocessing、test_vectors |
| 9 | 寫模型卡、逐檔 hash，manifest 最後保存 | 完整候選包、中文結論與下一步；預設不呼叫 GCS |

建議新產物路徑為 `janusChatGPT/模型研究/<role>/<run_id>/`，分成 `control/`、`data/`、`models/`、`reports/`；這是本次指定的輸出規格，不宣稱目錄已建立。共享輸入以固定 release 引用，不複製整包原始資料。既有 Risk 封存 cycle 仍保持原位、不可覆蓋。

每份 Notebook 都須顯示：資料截止、原始期數、warmup 損耗、成熟標籤數、train/validation/test 的股票數與**獨立日期／月份數**、基準與候選結果、PROBE／研究候選／不足及理由。失敗保留已完成產物，不能吞例外印「成功」。

## 切分、選型與模型包共同規則

按唯一時間分組，同日／同公告月份的股票不能分散 train/test；禁止隨機切股票列。標籤 `mature_at` 必須早於該 fold 訓練截止，清除跨入下一段的標籤區間。需要 scaler／補值／截尾／編碼時只在 train fit；未知產業類別使用固定 UNKNOWN，禁止全資料 target encoding。

early stopping 只能看內部 validation，最終 test 不傳入 `eval_set`。若要校準，使用未參與該輪 fit／early stopping 的時間後段或嚴格 OOF 資料。最多6組預先登記的淺樹設定，單執行緒管理 folds，避免多層平行耗盡 Colab；基準不足可降到固定參數 PROBE，不能挪用 test 調參。

評估計畫在看 test 前固定：主指標、同樣本比較、研究樣本下限、各市場允許退化及不確定性方法。預設候選須主指標勝過最佳有效 baseline；按時間 block 的增益95%區間若含0則記 `INCONCLUSIVE`，不誇稱穩定勝出。各市場主指標相對 baseline 退化超過5%列 `REVIEW_REQUIRED`；5%是本版研究選型容忍設定，不是統計定律。樣本不足仍可交研究包，但不產生 promotion PASS。

`model.ubj` 使用 XGBoost 原生 save_model；禁止 pickle/joblib 或在模型包內執行任意 Python。保存特徵**順序／型別／單位**、label 定義、前處理／校準參數、best_iteration、模型／資料 hash、Git SHA、版本、seed、測試向量與預測容忍值。early stopping 的有效樹數必須在重新載入與正式 loader 推論時相同；不能拿全部樹與 Colab 最佳輪預測混用。

## 後續發布、回收與本次邊界

本次交付是文件與 AI 開發指令；Notebook 程式、實際訓練及 GCP 發布分別驗收。文件完成不代表四個模型完成。來源權利、PIT／公司行動、OOS、訓練／推論一致性依現役契約判定。

候選包未來才上傳既有 dev Mart 的 `models/candidates/<role>/<model_version>/`，以 create-only／hash 讀回／manifest-last 保存；Colab 不改 active pointer。正式執行沿既有 Scheduler→Controller→Mart，模型每角色載入一次、批次推論。深度分析母體依當前正式契約與 runtime 指定，不由這份 Notebook 擴大排程或新增服務。

精簡預測與成熟結果按月保存、版本分開，依現行生命週期36個月政策及有效引用保護；月度評估比較本月成熟與近3/6/12月 cohort。研究歷史已看過的 test 可供下一輪訓練，但不能重新命名為未觸碰 holdout。

## 依據

- [專案規則](https://github.com/tommylin15/janus-omniforge/blob/main/doc/PROJECT_RULES.md)
- [資料包／採集入口](https://github.com/tommylin15/janus-omniforge/blob/main/research/colab/README.md)
- [X/Y與時間契約](https://github.com/tommylin15/janus-omniforge/blob/main/doc/spec/model-feature-time-contract.md)
- [模型生命週期](https://github.com/tommylin15/janus-omniforge/blob/main/doc/spec/model-lifecycle.md)
- [XGBoost sklearn介面](https://xgboost.readthedocs.io/en/stable/python/sklearn_estimator.html)、[原生模型儲存](https://xgboost.readthedocs.io/en/stable/tutorials/saving_model.html)：2026-10-22查閱；stable會前進，實作須使用鎖定版本的相容API。官方一般範例的隨機切分不得照搬股票panel；其中評估集在本案必須改為validation，不能用最終test。

## 可直接交給 AI 的開發指令

```text
在 tommylin15/janus-omniforge main 依 PROJECT_RULES、doc/colab-models/02-risk-xgboost.md，以及現役Risk模型卡/重訓手冊開發，不使用 Superpowers。

交付獨立 02_Risk風險_XGBoost.ipynb。新訓練只讀JanusDataset_v3_202610/canonical/CURRENT.json指向的Parquet。沿用risk_pilot.py、risk_v1.py、run_risk_time_split_xgb.py定義，新增最小Parquet adapter及共用程序，不另複製一套八因子公式；用相同資料fixture驗證新舊adapter的X/Y一致。

唯一主Y為未來20市場交易日年化RMS波動。固定八因子順序、float32原值XGB、非負輸出；baseline Rolling20、Ridge5、Ridge8，同股票日期樣本比較。預設research；封存模型重現另設reproduce_archived，核原manifest和hash，不覆蓋risk-xgboost8-2025h2-v1，不把已看的2026Q3當新holdout。不加入beta/產業/MDD/quantile等v2項目，不接手其他工項的rollout。

實作時間分組、label maturity purge、bounded training、逐fold斷點、MAE/RMSE與分市場/月份/block不確定性、中文報告、UBJ與固定test vectors重載。Notebook從新CPU runtime可以Run all，內嵌固定版本共用模組及SHA、依賴鎖版，不依賴其他模型Notebook。

產物存janusChatGPT/模型研究/risk/<run_id>，保留舊Risk研究cycle原位；manifest記實際release、樣本、公式、依賴、Git SHA與PROBE限制。預設不上傳GCS、不啟用模型、不執行完整收集/訓練；以小樣本targeted tests驗功能。

完成後回寫GitHub與Drive給ai專用/janusChatGPT/CoLab程式，回報Notebook連結、commit、真實測試及使用者Colab步驟。歷史重現差異要解釋，不能為匹配舊MAE而修改真實資料。
```
