# 03｜Fundamental 營運：XGBoost Colab 建模與 AI 指令

更新：2026-10-23。**Drive 已有 Notebook，ChatGPT 真實訓練／OOS／正式發布狀態仍待驗收**。
交付 Notebook：`03_Fundamental營運_XGBoost.ipynb`；角色代碼 `fundamental`。
本版先完成月營收預測；季度EPS保留獨立選配，不因季報不足卡住月模型。使用者指定XGBoost作challenger，ElasticNet保留baseline。

### 2026-10-23 最新實作方式（覆蓋本文末尾較早的 Colab-only AI 指令）

- Drive 已存在 [03_Fundamental營運_XGBoost.ipynb](https://drive.google.com/file/d/1e2rA5Sq-UFRKPCP9JEhOx7efSP-ryxmH/view)；**Notebook 存在不等於已訓練/OOS PASS/ACTIVE**。優先採用 ChatGPT 可用 Python/研究執行環境試做，Colab 可選；在執行環境取不到完整 Parquet 原始檔時不得用摘要或 fixture 冒稱實跑。
- 以 CURRENT.json 固定的 release/manifest/Parquet SHA 驗證，沿用本文特徵/標籤/PIT/公司行動/按時序 purge/OOS，禁重抓資料。先跑 下一月營收 YoY 的 baseline/XGBoost、固定向量重載、UBJ/hash/模型卡，附真實品質和缺口收據；預設 publication_allowed=false。
- 必須待 Quant、Fundamental、Valuation 三模型**都具可部署證據**，才與 Risk v1 一次實施共用版本化 loader/跨 Job 快取。不同 Cloud Run Job execution 不共享 RAM，優先實測 GCS 不可變模型+每 execution 單次載入及 image layer 替代；不提前改 Risk、不增建付費或常駐服務。完整流程見 [模型生命週期](../spec/model-lifecycle.md) 和 [D07 AI 卡](../execution-cards/d07-model-lifecycle.md)。

## 1．預測問題與訓練單位

在公司m月營收已公告、資料可得之時，預測其**下一個月m+1的營收YoY百分點**。
一個樣本是股票×營收月份×固定as-of版本，不是每天複製同一筆營收。全市場普通股pooled XGBRegressor。輸出營運成長／放緩的研究預期，不是股價上漲機率。

主Y：`100 * (R[m+1]/R[m-11] - 1)`。m−11是m+1的去年同月。分母非正、單位／合併範圍不可比則不建此Y，保留原因；不是將缺值填成0%。
標籤首次公布或事後修訂必須標明，兩者不可混為同一成效。以m+1公告可得時間為成熟時間，不能以月底視為已知。若m期遲延公告，導致m+1答案在訊號截止前已可得，該列不得算預測樣本，須排除並記錄原因。

## 2．必要資料、可選財報與X

必要：revenue Parquet的symbol、market、fiscal_month、營收金額、來源／單位／revision，以及可取得的published_at／first_observed_at。
月營收千元與元先統一。按fiscal_month排序，缺月不以往前第12筆當去年同月；不可把發布月份當財務歸屬月。

初版月X：
- yoy_m = 100*(R_m/R_(m−12)−1)，至少13個月。
- yoy_3m = 100*(sum(R[m−2:m])/sum(R[m−14:m−12])−1)，至少15個月。
- yoy_change1 = yoy_m−yoy_(m−1)；growth_acceleration = yoy_m−yoy_3m。
- mom_m（100*(R_m/R_(m−1)−1)）、log1p(revenue_twd)、月份季節特徵、market。
- 三個月波動／缺值指標、資料age；需固定各欄min_points。股票代號不作X，產業只有可追溯版本才加入。

財報毛利率、營益率、ROE、負債比、CFO／淨利為**可選**：必須在m期訊號截止前已公布且口徑一致，附age_days。正負／零分母、金融業不適用分別處理，不硬算。沒有公告時間的財報不能當strict歷史X。

若歷史營收只有fiscal_month與今日下載時間，提供兩條明示狀態：
- strict模式只用可證實當時可得的版本，樣本不足時列不足；
- 研究模式以原生月份順序做restated實驗，標 `RESEARCH_NON_PIT`，不冒充可實際執行的歷史交易資訊。不要自行倒填每月10日等時間。

## 3．可用期數與切分

原始至少36個月可開始簡單月模型PROBE；完整15月warmup＋下一月Y會進一步減少訊號月。必報原始／有效月數，不能只報十萬筆股票列。
假如完整48個月且資料皆可比，最早可用X在第15月、最後有Y在第47月，最多33個訊號月；示例可按21 train／6 validation／6 test切分，再依公告成熟移除邊界樣本，**不能假定33月一定全都保留**。
60～84個月為後續成熟研究目標，不為本次自動擴收。

同一fiscal_month的所有股票歸同段；每fold再依實際mature_at判定可否入訓，修訂版本不得跨段形成同一期答案洩漏。有多fold時採3或6個月步進擴張窗；最終test月段鎖定。若只有很少月份，固定參數PROBE與baseline仍可產報告，不宣稱穩定跨景氣有效。

## 4．Baseline、XGBoost與評估

Baseline至少兩種：
1. 成長延續：預測m+1 YoY等於已知m YoY。
2. 季節性營收延續：預測R[m+1]=R[m−11]，對應YoY=0%；清楚標示這是「同月去年」簡單基準。
可加入ElasticNet，以train-only scaler與相同成熟樣本比較。

XGB起點：`objective="reg:squarederror"`、max_depth=2、learning_rate=0.05、n_estimators上限400、min_child_weight=50、subsample=0.8、colsample_bytree=0.8、reg_lambda=20、seed20261022；validation MAE early stopping 30輪。最多6組預先列明設定，不因股票多就加深樹。

主指標MAE（**百分點**）；另RMSE、中位絕對誤差、方向／成長加減速的輔助命中率、分市場／產業／月份。零或負值不使用MAPE。主表保留真實極端值；可附train-only截尾敏感度，不能按test最差樣本刪除。
按月份分組評估不確定性；test只有6月時區間非常粗，明示獨立月數，不把股票bootstrap當時間證據。
predicted_yoy_pp到預測金額的換算需R[m−11]且同口徑：Rhat=R[m−11]*(1+yhat/100)。若yhat<−100導致負金額，保留原始輸出與INVALID_REVENUE_PREDICTION，不靜默截成合理值；可比較有下界的log-ratio新target，但必另升label版本並重新評估。

## 5．EPS選配、更新與專屬驗收

季度EPS不屬月模型必需交付。若後續啟用，另建 `target="next_quarter_eps"`、獨立estimator／split／評估：一股一季一列，至少12個可比原始季度為PROBE起點、20～28季為研究目標；Y為下一季可比單季EPS元，不拿累季差分猜單季EPS、不混用年度／預估或不同每股基準。基本面月模型成功不能替EPS模型通過驗收。

只在新營收／財報公告或有效修訂時更新公開結果；同一公告每天不重訓。下一月公告到齊後評分，每月檢視，相同版本保留原預測。輸出target_fiscal_month、predicted_yoy_pp、baseline、cutoff、來源與資料年齡，保留實際公布時再確認的項目。

必要測試：m+1與m−11分母正確；跨年／缺月不錯位；千元轉元一致；修訂與公告後才可用；15月warmup及無Y排除；季資料不展成日樣本；負值不MAPE；UBJ重載一致。

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
依 tommylin15/janus-omniforge main的PROJECT_RULES及doc/colab-models/03-fundamental-xgboost.md，交付03_Fundamental營運_XGBoost.ipynb；不使用Superpowers。

預設只做月營收下一月YoY百分點的pooled XGBRegressor。唯一輸入為JanusDataset_v3_202610/canonical/CURRENT.json固定release內的revenue，以及有據時可選financials；先核真實schema和原生月數，不重新採集或直接讀raw補洞。

以一股一公告月份建樣本，落實13/15月暖機、m+1對m−11之Y、真正公告成熟、來源版本/單位/合併範圍。沒有歷史可得時間時只交明示RESEARCH_NON_PIT的月份研究，不倒填公告日。EPS另獨立選配且預設關閉，不以日複製財報擴充樣本。

先成長延續及同月去年baseline，可加ElasticNet，再淺層XGBoost；按月份和mature_at切分/清除交叉，validation選型、test不調參。主MAE百分點及分市場/月/產業、獨立月份不確定性；不用MAPE，不偷偷刪test極端值。

共用loader/split/export模組，Notebook內嵌固定版本和SHA、鎖版依賴，可在全新CPU Colab單獨Run all。逐foldcheckpoint；輸出中文準入/缺口/評估、X/Y/predictions、UBJ、模型卡、schema、test vectors、完整hash到janusChatGPT/模型研究/fundamental/<run_id>。

只交程式並以小樣本targeted tests驗證年月/公告/單位/洩漏/序列化；不執行完整收檔/訓練、不上傳GCS或切active。完成GitHub與Drive給ai專用/janusChatGPT/CoLab程式回寫，交Notebook連結、commit、實際測試與Colab操作步驟；不足期數必須仍有可讀報告，不是假成功。
```
