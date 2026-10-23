# Fundamental：排除金融股的有界重訓研究（2026-10-24）

**研究狀態**：RETROSPECTIVE_FINANCE_EXCLUSION_RESEARCH_EVALUATED；**publication_allowed=false**，不修改 Risk ACTIVE／Registry／canonical／任何部署。

## 股票排除定義與資料母體
- 本研究按交易所**金融保險類別代碼 17** 的 `(market,symbol)` 精確配對，非單純代碼前綴。台灣證交所公司基本資料 2026-10-23：上市 31 檔；櫃買金融類股交叉核對：上櫃 9 檔。原回溯預測 23,101 列中實際排除 33 檔、366 列，剩 22,735 列。官方名單出處：`https://openapi.twse.com.tw/v1/opendata/t187ap03_L`，`https://ic.tpex.org.tw/introduce.php?ic=U000&stk_code=6878`。
- 產業名單為**現況分類**，沒有舊日歷史產業快照，無法保證 2025 年逐日分類版本完全正確。
- 既有 reconstructed 研究 CSV 比完整原 Parquet 少：與舊 23,101 筆預測對齊後取非金融**共同 17,779 列**，覆蓋非金融原母體 22,735 列的 **78.20%**，12 個已曝光測試月份為 2025-09 至 2026-08。不可混稱全量。

## 既有模型「只重新評分」：23,101 全部→22,735 非金融
| 月份等權 MAE，YoY 百分點 | 含金融 | 非金融 |
|---|---:|---:|
| 原組合 baseline | 560.475 | 568.861 |
| 原 XGBoost L1 | 608.556 | 617.810 |
| Seasonal-zero | 618.939 | 628.194 |

## 真正以非金融股票重新訓練 3 個固定 XGB L1 設計
**12／12 折完成，36 筆折執行紀錄，每折訓練金融列=0、測試金融列=0。** 原研究所用固定 90 棵 XGB L1、depth2、learning_rate=.05、min_child_weight50；同一標籤成熟曆月**代理**，非公告 PIT 驗證。只有 `extended13_reference`、`core10`、`minus_season_calendar` 三組在此次重新 fit，其他 8 組和 Ridge 未重跑。

| 方法 | 17,779 筆共同非金融樣本 MAE |
|---|---:|
| 原先已選定的組合 baseline（舊預測） | **576.410** |
| 原 XGB L1（舊預測） | 591.382 |
| **新 fit 13 因子去季節 sin/cos** | **591.503** |
| 新 fit 10 因子 | 591.881 |
| **新 fit 13 因子** | **591.899** |
| seasonal-zero | 601.432 |
| 新 train-only 近三可用月份選單純 baseline | 612.114 |

## 核心公平比較：同 17,779 列與相同超參數，只變是否讓金融股進入訓練
| 配置 | 含金融訓練→非金融測試 | 非金融訓練→非金融測試 |
|---|---:|---:|
| 13 因子 | 591.897800 | 591.899013 |
| 去季節因子 | 591.424415 | 591.503155 |
| 10 因子 | 約 591.880749 | 591.881220 |

13 因子**平均改善 = −0.001213 百分點**，12 個月份等權 3 個月 moving-block bootstrap 95% CI [−0.052092,+0.062983]，6／12 個月份改善；**沒有可靠的模型改善**。重新 fit 的 13 因子與去季節因子相差僅 0.396 百分點（約 0.067%），不足以升級模型。13 因子對既有最佳組合 baseline，baseline−model = −15.847 百分點，CI [−110.107,+71.390]，未建立穩定優勢；對 seasonal-zero 則改善 9.533 百分點。

去金融後 13 因子**最差 1% 絕對誤差貢獻 95.42%**，尾部問題依舊存在。原組合 baseline 94.61%。不能把這些案例自動當髒資料刪除。

## 驗收與結論
本地 `test_finance_exclusion_retest` **8/8 PASS**；提供重跑 Python、固定來源 SHA256、40 檔金融排除表、17,779 筆逐筆預測、逐月分數、配對區塊統計、訓練折證據和報告。完整自含研究 bundle（重跑 Python、研究輸入、預測、測試、SHA manifest）已寫入並讀回 Google Drive 白名單根 `janusChatGPT/模型研究`：https://drive.google.com/file/d/1Npmh90rYA54XoXt3LzpMmQwGqT547CAO/view 。大型 CSV 與程式保留在 Drive bundle，**並未聲稱完整程式已在 GitHub repo 內**。

**決策**：金融股不是此問題的主要誤差來源，單獨排除金融股沒有必要；維持 DEFER LightGBM／CatBoost。優先定位非金融低基期、接近零收入與企業事件的極端 YoY 異常；等待可信公告 PIT 與獨立前瞻 cohort。不得宣稱模型正式可上線。

限制：原 X 與重建 CSV 不同母體、`published_at` 缺失、已曝光 12 個月、金融產業分類未歷史版本化、舊組合 baseline 沿用原先選擇而非本輪重建。以上任一條件都不支持 publication promotion。