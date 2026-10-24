> **2026-10-24 最終四模型決策：**04 Valuation 保留 PE/PB 倍數、殘差和 XGBoost challenger 研究，**同時擁有 [估值參考區間功能](../spec/valuation-range.md)**。原第五模型 `valuation_range` 撤案；04 共用 EPS/BVPS、歷史倍數、單位、期間、PIT、來源授權、公司行動與同一 publication/rollback，前台只顯示一張區間卡。情境是確定性分位計算，無獨立訓練 Y、第五模型或 Registry role。04 XGBoost 研究尚未發布不阻止情境先依自己的來源/公式/發布 gate 開發。此為契約更新，**非 runtime/UI 已完成**。

> **最新執行入口（2026-10-23）：** [四模型目前版本總索引](../research/00-四模型最新版本索引.md)；個股收檔／大盤產業收檔改為兩本 v3.8.4 Colab Notebook，ChatGPT 貼標使用 `label_four_models.py`（含產業 PIT preflight），四角色研究訓練使用 `janus_train.py`。本文件其他 v3.8.2 或更早 Colab 執行說明僅供歷史研究，模型正式發布另行驗收。

# 04｜Valuation 估值：XGBoost Colab 建模與 AI 指令

更新：2026-10-23。**Drive 已有 Notebook，ChatGPT 真實訓練／OOS／正式發布狀態仍待驗收**。
交付 Notebook：`04_Valuation估值_XGBoost.ipynb`；角色代碼 `valuation`。
本版改用XGBoost challenger，保留Ridge／Huber及同業基準。月末估值資料足以做月頻研究，不假裝取得每日三年估值。

### 2026-10-23 最新實作方式（覆蓋本文末尾較早的 Colab-only AI 指令）

- Drive 已存在 [04_Valuation估值_XGBoost.ipynb](https://drive.google.com/file/d/1vOFFKsky_NstE9_8F4Nvk3Z4DHgvN5ho/view)；**Notebook 存在不等於已訓練/OOS PASS/ACTIVE**。優先採用 ChatGPT 可用 Python/研究執行環境試做，Colab 可選；在執行環境取不到完整 Parquet 原始檔時不得用摘要或 fixture 冒稱實跑。
- 以 CURRENT.json 固定的 release/manifest/Parquet SHA 驗證，沿用本文特徵/標籤/PIT/公司行動/按時序 purge/OOS，禁重抓資料。先跑 各自 log(PE)/log(PB) 的 baseline/XGBoost、固定向量重載、UBJ/hash/模型卡，附真實品質和缺口收據；預設 publication_allowed=false。
- 必須待 Quant、Fundamental、Valuation 三模型**都具可部署證據**，才與 Risk v1 一次實施共用版本化 loader/跨 Job 快取。不同 Cloud Run Job execution 不共享 RAM，優先實測 GCS 不可變模型+每 execution 單次載入及 image layer 替代；不提前改 Risk、不增建付費或常駐服務。完整流程見 [模型生命週期](../spec/model-lifecycle.md) 和 [D07 AI 卡](../execution-cards/d07-model-lifecycle.md)。

## 1．模型回答什麼

以當時可得的財務品質、成長、產業和規模，估計股票所屬可比市場的**相對定價倍數**。同一Notebook內建立兩個獨立XGBRegressor：
- `pe`：Y=log(PE)，限有效正PE與可比獲利口徑。
- `pb`：Y=log(PB)，限有效正PB及正淨值適用股票。
各自schema、樣本、模型、報告與狀態分開。PE不足可只交PB研究成果，不能對虧損公司硬算PE。

這是相對市場定價，不是內在價值、不保證價格回歸，也不是預測明日股價。合理價文字改用「同業模型參考倍數／情境價格」。

## 2．必要資料、樣本與時點

必要：valuation月末PE／PB、symbol、market、實際估值日期、來源；financials中可核對的財務數值／單位／財務期／公告時間；可比產業／cohort。
只在每個月實際有觀測的月末交易日留一列，FinMind日頻若存在也抽成一致月末規則；不得將月末快照forward-fill成20個訓練樣本，或用某月唯一早月值冒充月末。

以月末當時已公開的財報as-of join。期末尚未公布的本季數值不可使用。只有事後修訂財務與現行產業名冊時可另做 `RESEARCH_NON_PIT`，在模型卡明示；無可比財務欄位時只產真實倍數／自身歷史與baseline報告，不靠缺值補值硬訓練。

金融／非金融cohort分開；銀行、保險等適用性再依實際欄位核對，不能共用不適用的毛利率或CFO品質公式。若某cohort訓練樣本不足，保留UNKNOWN／UNSUPPORTED，不把無關產業併為「同業」。

## 3．X與防止代數洩漏

優先最小X：可比ROE、營收成長、營益率（適用時）、負債比、log1p(帳面總資產TWD)、market、可追溯industry。實際缺欄位時在看test前固定縮小特徵集、另升schema；至少需可核對的成長與品質資訊，不能只用股票代號記憶倍數。
財報定義與分母合法性逐項記錄；公司行動／單季累季口徑不明先不算。類別編碼僅在train建立，未見類別UNKNOWN。

禁止X：當日PE／PB／殖利率、當日股價、市值、價格倒算EPS／BVPS、其他可把Y重建的同日代數組合；**訓練PE時也不放當日PB，反之亦然**。同日同業target聚合亦不進X；若需要價格動能另立明示研究版本，首版不加。
EPS／BVPS只在模型輸出之後作情境價格換算，不進當期倍數X。自身歷史PE/PB分位可獨立顯示為事實baseline，不以同日分位偷偷透露Y。

至少在target建表後做欄位allowlist與代數洩漏測試；排除不適用目標而非把負PE取abs或加常數取log。

## 4．樣本深度與baseline

**2026-10-24 最新補收決策：研究/補收門檻為「每檔一般普通股、各自 PE 或 PB 分支 ≥30 個真實有效且不同月份的月末觀測」；已撤銷新補收固定近兩年限制。** 先以現有 CURRENT 的36個月及合法可用的既有更早資料盤點，每檔每分支不足30時再定向追溯所缺的月份及其相依財報；不能把負／零PE/PB、IPO前月份、空值、重複同月、前填或未公告財報填成有效樣本。普通股身分、合併別/單位、來源權利、公司行動、月末觀測與公告 as-of 均須核實；不足則 PROBE / limited，不能為30而擴至全市場盲抓。詳見 [普通股30有效月末盤點](../research/valuation-min30-ordinary-preflight-2026-10-24.md)。**此30月是04研究補收目標，不覆蓋04前台確定性估值情境既定24有效月初版條件。**

已收36個月末是研究起點；3～5年／36～60個月末及12～20季相容財務為成熟目標。可用月數要扣財務warmup、as-of缺口與倍數不適用。實際若沒有30個有效訊號月，不硬稱18 train／6 validation／6 test已成立；縮為固定參數PROBE並報期數限制。

按月份排序，所有股票同月同fold；可用擴張窗每3或6月驗證，最後一段test固定。當期Y不需等未來價格，但資料本身必須已可得。另做60／120交易日效用時才使用相應label maturity與purge，不混成同一訓練目標。

Baseline：
- **train-only**各industry/cohort log倍數中位數，驗證／test不更新；同業不足時依預先定義退至同市場＋金融分類train中位數並標示。
- 相同X的Ridge或Huber，scaler只fit train。
- 同月leave-one-out同業中位數可另作「當期同業描述」報表，不能冒充事前train-only預測基準或混入X。

預設每個訓練cohort至少10個不同股票及12個不同月份才擬合該cohort模型；不達則pooled模型只在有效同類cohort中共享，並獨立列樣本數。這是研究防呆設定，不保證模型有效。若金融與非金融特徵不相容，分別建模型，不以一份混亂schema強塞。

## 5．XGBoost、輸出與驗收

PE／PB各用 `objective="reg:squarederror"` 預測log倍數；起點max_depth=2、learning_rate=0.05、n_estimators上限400、min_child_weight=50、subsample=0.8、colsample_bytree=0.8、reg_lambda=20、seed20261022，validation MAE early stopping 30輪。最多6組設定。

主指標log倍數MAE，另log RMSE、原倍數MAE／中位絕對百分比誤差（限正合法目標）、分市場／cohort／月份結果及時間block增益區間。exp(predicted_log_multiple)是log尺度反轉的參考倍數，不宣稱是條件算術平均數。若做偏差校正只用train/validation估計並保存版本。

相對偏離：`log(observed_multiple)-predicted_log_multiple`；正為相對模型偏高，負為偏低，不直接推論應買／應賣。validation殘差可估研究參考區間，但要用test報實際coverage；沒有足量校準月份就不提供區間，不假定常態。
情境價格只在當時有可比正EPS／BVPS時做 `multiple * EPS_or_BVPS`，並列口徑與日期；否則僅倍數。禁止用當日price／PE逆算EPS後再宣稱模型獨立得到合理價。

獨立效用評估：偏低組未來60／120交易日超額報酬、排名相關與樣本涵蓋；股票／benchmark調整基準一致、成熟後才評分。未有足夠日行情或基準時列PENDING／UNAVAILABLE，不能以當期擬合很好證明獲利。

必要測試：負PE／負淨值適用性；金融cohort分離；目標／代數等價X阻擋；未來財報不可as-of回填；月末日期／日轉月減重；train-only cohort median；無EPS/BVPS不產情境價格；UBJ重載與exp轉換一致。

每月新估值／新財報檢查後產新研究截面；正式已上線模型可依價格與財務dirty狀態重估，每月評估、每季檢討是否重訓。固定資料不足時交baseline與缺口，四份Notebook交付不等於四模型都必須勝出。

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
依 tommylin15/janus-omniforge main的PROJECT_RULES及doc/colab-models/04-valuation-xgboost.md，開發獨立04_Valuation估值_XGBoost.ipynb，不使用Superpowers。

唯一讀取JanusDataset_v3_202610/canonical/CURRENT.json固定的Parquet release。核真實valuation/financials/產業schema與日期，只以有效月末截面建樣本；不將月末估值擴成每日樣本，不重收資料、不用今日資料倒填歷史。

同一Notebook分別建立logPE與logPB XGBRegressor、train-only同業中位數及Ridge/Huber baseline，各自樣本/狀態。限制適用正倍數及正淨值，金融/非金融cohort分開。X只用本文allowlist的成長/品質/帳面規模及分類；禁止股價/市值/同日PEPB殖利率/倒算每股數與同日target聚合洩漏。財報嚴格as-of或明示NON_PIT研究，不造公告日。無可用財務X時交baseline/缺口而非硬fit。

依月份切分、validation選型/區間、test鎖定，淺樹最多6組設定。報log與原倍數誤差、分市場/cohort/月、獨立期數與不確定性；60/120日成熟超額報酬只作獨立效用，不訓練成股價模型。情境價格需外部可比EPS/BVPS，否則只顯倍數。

重用共用loader/split/export；Notebook內嵌固定Git版本與SHA，可新Colab CPU獨立Run all；資料/模型/報告到janusChatGPT/模型研究/valuation/<run_id>，逐fold續跑，保存UBJ、schema、前處理、模型卡、test vectors與hash。預設不上傳GCS、不改active、不執行完整收集/訓練。

完成targeted tests，特別驗證代數洩漏、財報時點、適用性與序列化；回寫GitHub及Drive給ai專用/janusChatGPT/CoLab程式。提供Notebook、commit、實際測試與使用者步驟；不要把相對定價叫內在價值或把文件完成叫模型有效。
```
