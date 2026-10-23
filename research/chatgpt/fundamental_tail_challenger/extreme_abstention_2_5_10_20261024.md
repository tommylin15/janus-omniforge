# Fundamental：極端基期拒絕預測 2%／5%／10% 實驗（2026-10-24）

**狀態：HISTORICAL_RESEARCH_EVALUATED**｜**publication_allowed=false**。此為實驗報告及未部署 serving contract 草案，不是 ACTIVE 模型或 runtime 已驗收。

## 對照實驗
- 2025-09～2026-08，共 12 個已曝光回溯月份，18,106 筆共同股票月樣本（金融股保留）；原始重建 CSV 73,209 列，不得冒稱原 Parquet 93,036 列的全量驗證。
- 先用原 LightGBM／CatBoost／XGBoost 固定預測，僅拒絕異常個案後對其餘重算 MAE；再用相同異常規則在各折**訓練與測試**排除，三種模型全部重新訓練並評分，36/36 折×比例完成。
- 所有真實 Y 和模型已知極端個案保留供離線診斷；「拒絕」代表**正式推論未來不回傳預測值**，不是刪 canonical，絕不使用未來真實 YoY／事後誤差判斷適用性。
- 真實 PIT `published_at` 缺值，只能使用曆月 label maturation proxy；這些回溯月份已先前曝光，信賴區間只能當研究診斷。

## 推論前可判定的三個異常條件（OR）
在當月營收**確實已公告**、下個月營收尚未知時，設 `B=去年下一個目標月份營收(TWD)`，`M=已公告之截至當月近12月平均營收(TWD)`，`G=當月已知營收 YoY(百分點)`。
1. `B <= base_twd_max`：去年目標月低基期。
2. `M / B >= ratio_min`：近期營收相對去年目標月基期失衡。
3. `abs(G) >= abs_known_yoy_min_pp`：**當月已知**營收 YoY 極端變動。

每折門檻僅從折內過去、標籤代理已成熟的 training X 量化，將**訓練期聯集排除率**校準至 2%、5%、10%。測試期不為達到目標比例而偷偷重估門檻，因此實際排除率會不同；各月份完整門檻見研究 bundle 的 `frozen_thresholds.csv`。不得用研究測試集的 Y、後驗誤差或當期測試集分位決定 flag。

範例：2026-08 使用該月**訓練時已凍結**的 threshold：
| 校準排除率 | B ≤ TWD | M/B ≥ | \|G\| ≥ YoY 百分點 |
|---|---:|---:|---:|
| 2% | 548,000 | 10.424027 | 810.225843 |
| 5% | 3,270,000 | 3.151094 | 241.978039 |
| 10% | 9,832,998 | 1.918687 | 114.230745 |

**這些不是 production 現成參數。** 日後需鎖定版本化門檻、訓練 release/fingerprint、實際公告 PIT 與來源授權後再進 serving 驗收。

## 全部 18,106 筆共同樣本：覆蓋、攔截、剩餘 MAE
| 指標 | 2% | 5% | 10% |
|---|---:|---:|---:|
| 被拒絕樣本／實際比例 | 369／2.038% | 894／4.938% | 1,894／10.461% |
| 剩餘可預測 | 17,737 | 17,212 | 16,212 |
| 事後真實絕對 YoY >= 1000 pp（共 137 筆）中被攔截 | 111（81.0%） | 127（92.7%） | 132（96.4%） |
| 被拒絕的非極端樣本 | 258 | 767 | 1,762 |
| 被擋掉的「舊 LightGBM gate」總絕對誤差比例 | 93.354% | 94.742% | 95.865% |

下列以**月份等權 MAE**計算，原始目標是下一月 YoY 百分點、**不裁切真實 Y**：

| 方法 | 2% | 5% | 10% |
|---|---:|---:|---:|
| 既有 LightGBM gate、僅拒絕預測 | **29.335** | **23.911** | **19.985** |
| 既有 XGBoost 直接 YoY、僅拒絕預測 | 29.364 | 23.900 | 19.954 |
| 新重訓 LightGBM gate | 29.741 | 24.049 | 20.137 |
| 新重訓 CatBoost gate | 30.145 | 24.296 | 20.313 |
| 新重訓 XGBoost 直接 YoY | 30.021 | 24.109 | 20.027 |
| 原組合 baseline（同一剩餘樣本） | 36.767 | 30.062 | 25.112 |

舊 18,106 筆樣本未拒絕的 LightGBM gate MAE 為 **431.645**。拒絕後誤差大降，主要是**選擇性預測降低覆蓋率**，不能說模型本身預測能力等比例提升。

3 月 moving-block bootstrap（5,000 次、已曝光 12 月）：既有 LightGBM gate 相對新重訓 gate 的月份等權改善在 2% 為 +0.4065 pp（95% CI [+0.1725,+0.6837]）、5% +0.1385 pp（CI [−0.1033,+0.2912]）、10% +0.1520 pp（CI [+0.0771,+0.2187]）。**改變訓練集未見必要增益**；保留既有研究模型並獨立判斷可預測性更簡單。信賴區間不可冒稱新的未曝光 OOS。

## 候選取捨
- 2%：最高覆蓋率，卻仍漏 26／137 個事後極端 Y。
- 5%：攔截 127／137（92.7%），相對 2% 多拒絕 525 筆但多攔截 16 筆真正極端案例。
- 10%：攔截 132／137（96.4%），相對 5% 多拒絕 1,000 筆只多攔截 5 筆真正極端案例。

**使用者已於 2026-10-24 選定 5% 作為驗證候選（`VALIDATION_CANDIDATE_ONLY`）。** 這取代原本「研究建議優先」的未決狀態，但**不代表 ACTIVE、production gate、threshold production approval、或 publication 核准**。2%／10% 僅保留研究比較；正式 serving 仍不變。可追溯的研究候選設定參見 [`validation_candidate_5pct_20261024.json`](validation_candidate_5pct_20261024.json)。

### 5% 候選：分開評估適用性與預測能力（補充核驗）
- 研究樣本 18,106 筆；gate 避開 894 筆（4.938%），接受 17,212 筆（95.062%）。
- **異常攔截**：若「異常」*事後*定義為真實下一月 `|YoY|>=1000` 百分點，攔截 127／137（recall 92.70%）、漏掉 10 筆；894 筆被拒絕者只有 127 筆達到此事後極端定義（precision 14.21%），其餘 767 筆並非這個閾值的極端樣本，不能隱藏這項 opportunity cost。攔截檢驗標籤不得反用到推論 gate。
- **接受樣本的月份等權 MAE（YoY 百分點）**：LightGBM gate **23.9106**，XGBoost direct YoY **23.9001**，最後已知月營收延用 baseline **25.8937**，原 combo baseline **30.0624**（combo 有 4 筆空值，配對用 17,208 列）。中位 AE 11.5768，90 分位 AE 44.4809。
- LightGBM vs combo baseline：同股同月配對改善約 **6.166** 百分點（原重訓報告以新 fit LightGBM 比 combo 為 **6.028**，不可混寫）。LightGBM vs **更強**的 `last_revenue_carry`：改善 **1.983** 百分點，12 月中僅 **6 月改善**，3 月區塊 5,000 次 bootstrap 約 95% CI **[−0.566,+5.644]**；不支持宣稱已穩定勝過強 naive baseline。LightGBM 相對直接 XGBoost 差 **−0.0105** 百分點，也沒有演算法優勢。
- **跨覆蓋率比較限制**：431.645（100% 範圍）→23.911（95.06% 覆蓋）屬 selective prediction 的案例移交，不是同一母體上模型泛化突然變好。以 gate 留下的樣本給不同模型比才公平。
- **可信度判定**：gate 的回溯攔截能力 **promising**；LightGBM 在接受樣本相對 combo 有實質訊號，但對強 naive 和 XGBoost **不具已證實優勢**。樣本僅 12 個已曝光月份、PIT 仍缺、原完整母體尚未對齊，不能對使用者宣稱正式有效或啟用。

### 下一輪必交的驗證證據
1. 固定研究候選 5% 參數及 SHA；以 2026-08 研究折作**參考凍結值**（去年目標月基期上限 TWD 3,270,000；比率下限 3.151094；已公告 YoY 絕對值下限 241.978039 pp）。不得在待評估 cohort 上重估百分位。這些**不是正式 serving 參數**。
2. 逐股核對公告 `published_at/available_at`、去年對應月份、TWD 單位、來源版次與營收 12 月窗口；無法核對 → `DATA_UNVERIFIED`。
3. 用**未被前次研究曝光**且標籤實際成熟的月度 cohort，保留金融股，比較 LightGBM／XGBoost、combo baseline、`last_revenue_carry`；報告月份等權 MAE、Median AE、P90、coverage、gate recall／miss／precision、正常誤擋個案及產業切片。
4. gate 標記 `ANALYST_ONLY` 時 `model_prediction=null`，分析師只描述已核實的極端現象與來源，不能自動產生未來 YoY、影射真實企業事件或當成模型成功。
5. 只在研究範圍結案；需另有 ACTIVE 授權、serving parity、CI、部署及 live evidence 才能宣稱正式可用。
 所有 12 月樣本已曝光，仍需原始公告 PIT、全量母體及 live serving parity。

## 未來服務與分析師異常說明規格（待另案部署驗收）
- 已公告 X 完整、有效且未觸發 → `MODEL_ELIGIBLE_BY_TAIL_GATE`，仍需通過 ACTIVE、PIT 和其他服務規則才可真正呼叫模型。
- 任何極端旗標／去年基期零或非正 → `ANALYST_ONLY`，**模型預測值 = null**，傳 reason_codes、實際已公布營收及「已確認的異常說明」；不可由 LLM 捏造 corporate action、未來營收、極端原因或替代預測值。
- 欄位缺失、非有限值、公告時間無法驗證／單位異常 → `DATA_UNVERIFIED`，暫停預測、要求資料核對；此品質門檻不算進 2/5/10 的政策性比例。
- 需要版本化門檻、生效時間、原始 source SHA、feature schema、訓練區間、拒絕原因和每次 coverage 統計。部分拒絕**不得包裝為全樣本成功**。
- 用戶可見案例：「本月未提供下一月營收 YoY 模型數值。去年對應月份營收基期偏低，近期營收相對基期放大，可能使 YoY 易受分母影響。實際成因待原始公告／修訂核對。」只陳述已知事實。

## 研究收據
- Repo 版本化判斷邏輯：[`extreme_abstention_gate.py`](extreme_abstention_gate.py)、[`test_extreme_abstention_gate.py`](test_extreme_abstention_gate.py)。
- 本地 36／36 重新訓練折完成、9／9 單元測試 PASS，額外測試：gate 2% 是 5% 的子集、5% 是 10% 的子集；拒絕個案全為空預測、`publication_allowed=false`、12 月份完整。
- 完整研究 ZIP 另含：`refit.py`、`serving_gate.py`、`test_serving_gate.py`、36 折 metadata、36 折原始預測、18,106×3 逐筆評分、月門檻、CI、coverage、source SHA256 和自含研究輸入。
- 未修改 canonical／Risk ACTIVE／Registry／serving／CI／部署；沒有 live acceptance 證據。
