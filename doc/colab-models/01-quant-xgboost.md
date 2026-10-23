> **最新 v3.8.2（2026-10-23）執行環境變更：** Colab 只負責資料採集、來源驗證、基本清理與不可變 Parquet；採用 `research/colab/00_資料收集_v3.8.2_Colab.ipynb`。四模型研究因子、貼標、X/Y、訓練與 OOS 改由 **ChatGPT Python 執行環境** 負責，貼標入口 `research/chatgpt/label_four_models.py`，共用模組 `factor_factory_v1.py`、`janus_precision.py`，模型介面 `janus_train.py`。ChatGPT 必須先取得可讀的真實 CURRENT、manifest 與全部 referenced Parquet；不能假設 Colab 的 /content/drive 在 ChatGPT 存在。既有各角色 Colab 研究 Notebook 保留作舊版候選，不再作為新流程建模入口。v3.8.2 本地測試 22 PASS、6 SKIP（缺 pyarrow），尚無 Colab live 或四模型全量 OOS，研究版不得發布、不得變動 Risk ACTIVE。詳細：[拆分說明](../research/four-model-collection-label-split-v382.md)。

# 01｜Quant 趨勢：XGBoost Colab 建模與 AI 指令

更新：2026-10-23。**Drive 已有 Notebook，ChatGPT 真實訓練／OOS／正式發布狀態仍待驗收**。
交付 Notebook：`01_Quant趨勢_XGBoost.ipynb`；角色代碼 `quant`。
本次使用者指定前四角色各一份獨立 XGBoost Notebook；覆蓋舊建議中的 LightGBM challenger 選擇，保留 baseline 與時間／發布規範。第五個 Event 另議。

### 2026-10-23 最新實作方式（覆蓋本文末尾較早的 Colab-only AI 指令）

- Drive 已存在 [01_Quant趨勢_XGBoost.ipynb](https://drive.google.com/file/d/1TtaQUUjlvKmlBzV2ZRFqmrxXndzbVDnV/view)；**Notebook 存在不等於已訓練/OOS PASS/ACTIVE**。優先採用 ChatGPT 可用 Python/研究執行環境試做，Colab 可選；在執行環境取不到完整 Parquet 原始檔時不得用摘要或 fixture 冒稱實跑。
- 以 CURRENT.json 固定的 release/manifest/Parquet SHA 驗證，沿用本文特徵/標籤/PIT/公司行動/按時序 purge/OOS，禁重抓資料。先跑 未來20交易日 p_up 的 baseline/XGBoost、固定向量重載、UBJ/hash/模型卡，附真實品質和缺口收據；預設 publication_allowed=false。
- 必須待 Quant、Fundamental、Valuation 三模型**都具可部署證據**，才與 Risk v1 一次實施共用版本化 loader/跨 Job 快取。不同 Cloud Run Job execution 不共享 RAM，優先實測 GCS 不可變模型+每 execution 單次載入及 image layer 替代；不提前改 Risk、不增建付費或常駐服務。完整流程見 [模型生命週期](../spec/model-lifecycle.md) 和 [D07 AI 卡](../execution-cards/d07-model-lifecycle.md)。

## 1．本版回答的問題與範圍

主模型預測「截至訊號日 T 已知的價量資訊，未來20市場交易日上漲的機率」。採 `XGBClassifier(objective="binary:logistic")`；不是未來股價或買進張數。

預設 `target="up"`、`horizon=20`。同 Notebook 支援獨立5日模型；取得相容市場基準後，才可另外選 `target="outperform"`。每個 target×horizon 各有模型、評估及校準器，不能把 p_up 當成 p_outperform。本版驗收以20日 up 主模型為主，不為湊齊四種組合延後主交付。

## 2．資料與特徵

必要：OHLCV、兩市場交易日序列、普通股母體／市場、來源／調整基準。日曆可由本輪manifest驗證的市場日期建立；不能用每股第20筆非空值代替第20個市場交易日。benchmark、歷史產業、法人只在有實際欄位及來源證據時加入；缺這些不阻擋價量版 p_up。

初版 X：
- ret5、ret20、ret60：close_T/close_(T-L)−1。
- ma_distance20／60：close_T/同窗平均close−1。
- vol20／60、drawdown60、volume_ratio20、log_turnover20：沿共用時間契約與Risk定義。
- market以固定映射編碼。股票代號只作主鍵，不作X；不加入Owner欄位。
- ret120為選配，啟用時需要至少121有效價格並重新報樣本損耗。
- 相對市場20／60日強度及beta需價格／含息基準一致，否則停用，不將缺benchmark補0。

最長預設暖機至少61個連續有效價格。事實異常要先核來源／公司行動；主評估保留真實暴跌。若設定訊號時已知的極端價差排除規則，要在切分前固定並報排除率；不能看未來跌幅決定刪除test樣本。

## 3．Y、成熟時間與可交易績效

`return_H = adjusted_close[T+H]/adjusted_close[T]-1`，`y_up=1[return_H>0]`；H以市場交易日定位。未驗調整價只能作明示的未調整價PROBE，不能稱total return。
`mature_at` 是T+H行情實際可用之時；缺終點、停牌或退市按預先censor規則列原因，不改找有利日期。

若有相容benchmark：`y_outperform=1[return_H-benchmark_return_H>0]`，另外訓練。市場基準若只含含息指數而股票是未調整價格，禁止比較。

機率研究和交易效用分開：T收盤後才有X，不以T同一收盤價成交。預設下一市場交易日可成交開盤進場、T+H收盤退出；一旦無可成交價依預先規則跳過並報涵蓋。費率／稅／滑價做明示config，無已核數值時不宣稱成本後績效已通過，不拿close-to-close結果當實盤績效。

## 4．時間切分、訓練與驗收

現有21月可先PROBE；3～5年是後續穩健性目標，不要求為本版重抓五年。
依可用訊號日期做擴張窗walk-forward，預設至少120 train日、20 validation日、20 final-test日；20日label要按成熟時間purge。此下限僅檢查程式可做研究，不保證跨行情有效。優先保留最近一段未被分析的時間；若全部歷史已看過，標 `RETROSPECTIVE` 並輸出前瞻收集計畫，不能假造新holdout。

Baseline：training prevalence固定機率，以及同X的Logistic Regression；動能規則只作另列方向比較，不把0/1信號當已校準機率。
XGB固定起點：max_depth=3、learning_rate=0.05、n_estimators上限500、min_child_weight=25、subsample=0.8、colsample_bytree=0.8、reg_lambda=10、seed=20261022；early stopping 30輪只用validation。最多6組小範圍設定，不以test擇優。

主指標Brier score；另報log loss、ROC-AUC／PR-AUC（單一類別時NA）、校準圖、預測分位組實際上漲率、分市場／月／流動性、同樣本baseline增益及20交易日block不確定區間。不要只報accuracy或訓練分數。
可選sigmoid校準；若沒有獨立校準期，交原始research score及校準不足狀態，不在UI宣稱可信勝率。成本後效用與機率品質分表。

輸出每筆symbol、market、signal_date、as_of、target、horizon、raw_score、calibrated_probability（不具備則null）、model_version及status。不得合成含Risk／估值的總買進分數。

## 5．更新與專屬驗收案例

每個新EOD更新X及推論；H交易日成熟後回收結果。每月評估是否需要人工重訓，不每日fit。
必要測試：日期分組不跨fold；改未來行情不改歷史X；20日Y定位及未成熟排除；benchmark基準不符拒絕outperform；無下一日開盤不能虛構交易；校準不使用test；UBJ重載機率一致。

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
在 tommylin15/janus-omniforge main 依 PROJECT_RULES、doc/colab-models/01-quant-xgboost.md 開發，不使用 Superpowers。只做 Quant；第五角色和其他模型不開工。

交付可單獨在 Colab CPU 執行的 01_Quant趨勢_XGBoost.ipynb。唯一輸入為 JanusDataset_v3_202610/canonical/CURRENT.json 固定的Parquet release；先核對實際schema及模型試訓準入，不重抓資料，不使用舊r1 CSV當新入口。

主版本做20交易日p_up的XGBClassifier，baseline為train prevalence和Logistic。5日及outperform使用獨立config/estimator；benchmark缺失只停outperform。按本文列明X/Y、時間purge、validation early stopping、獨立校準及test鎖定實作。未調整價格或公告/PIT不足如實PROBE，禁止補造。

主要邏輯置於research/colab既有或最小新增共用Python模組；Notebook內嵌固定版本與SHA，獨立Run all。新增模組/CLI路徑在完成後才寫成可執行命令。固定依賴與seed，逐fold斷點，最多6組參數；分類、校準與交易效用分別評估。

產出中文資料/樣本/缺口/評估報告、features/labels/predictions、XGB UBJ、校準JSON、schema、evaluation_plan、split manifest、模型卡、hash與重載test vectors，存janusChatGPT/模型研究/quant/<run_id>。預設不上傳GCS、不切registry、不執行完整收集或訓練；以合成小樣本測試時間/洩漏/序列化邏輯。

完成targeted測試和文件連結檢查後，回寫GitHub及Drive的給ai專用/janusChatGPT/CoLab程式；回報Notebook連結、commit、實際測試與由使用者在Colab執行的步驟。不要只交規劃，不宣稱未跑的訓練或live驗收PASS。
```
