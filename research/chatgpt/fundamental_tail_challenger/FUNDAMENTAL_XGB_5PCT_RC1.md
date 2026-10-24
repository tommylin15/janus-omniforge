# Fundamental 模型候選定版｜XGBoost＋5% 異常拒絕預測（2026-10-24）

**模型 ID：** `fundamental-xgb-nextmonth-yoy-gate05-20261024-rc1`  
**狀態：** `FROZEN_RESEARCH_CANDIDATE_NOT_ACTIVE`  
**publication_allowed=false**，未寫 Registry／canonical／serving，亦未部署或宣稱 production 通過。

## 本次使用者決策與版本定位

採用 **XGBoost（直接預測下一個曆月營收 YoY 百分點）＋5% X-only 異常拒絕預測規則** 作為**最新已凍結研究候選**。金融股保留。這是**可重播的模型權重＋門檻＋特徵順序＋測試**，不是單純指派既有模型名稱；不因定版動作虛構尚未完成的完整 PIT／OOS／live acceptance。

- 最終模型從包含極端樣本的成熟代理標籤資料訓練；**5% 用在推論拒絕**。既有比較顯示「先從訓練集中刪除 5% 再重新 fit」的 XGBoost MAE（24.109pp）比「保留訓練樣本、只拒絕推論」的 XGBoost（23.900pp）稍差；所以不能將此版本誤稱為「訓練集也刪 5%」。
- 原研究重建 CSV 共 73,209 筆（**非原始 full Parquet 93,036 筆**）。最新模型使用截至 2026-10-24 依**保守代理 label maturity** 合格的 47,616 筆，2023-12 至 2026-07 的 32 個月、1,531 檔股票，沒有將 2026-08 代理標籤提前訓練。
- 15 個特徵依舊研究 `experiment.py` 順序；XGBoost `objective=reg:absoluteerror`、`n_estimators=100`、`max_depth=3`、`learning_rate=0.05`、`min_child_weight=50`、`subsample=0.8`、`colsample_bytree=0.8`、`reg_lambda=20`、seed 20261023。**15 因子的確切順序、參數與 hash 以 [機器可讀定版檔](frozen_xgb_5pct_rc1_20261024.json) 為準**。
- UBJ 模型 SHA256：`05fa3167f10c650389c4e481c3e3a7de8a2b70f9133ad867f0404c3eb9758b0c`。
- frozen 5%（三條 OR；只用預測時已知的 X）：
  1. 去年**下一目標月份**營收 `B <= 3,266,999.83471632 TWD`；
  2. 已公告近 12 月平均營收 `M/B >= 3.1528768314559463`；
  3. **已公告當月** YoY `abs(G) >= 246.93646766061153` **百分點**。
  上述為**本次完整研究訓練 X 再校準**之 RC1 凍結值，會和 2026-08 歷史 fold 參考值 `3,270,000／3.151094／241.978039` 略有不同；**不能把兩版混用**。訓練聯集觸發率 4.9983%，實際部署的每月拒絕率不強制恰好 5%。
- 命中任一異常 gate：`ANALYST_ONLY`＋`predicted_next_month_yoy_pp=null`，分析師只描述已驗證營收基期異常，不臆測未來。來源、公告時點、修訂、單位或必要特徵缺失：`DATA_UNVERIFIED`＋`null`。不抹除原始數據、訓練標籤或 canonical。
- 2026-09 已知**研究特徵** 1,546 筆，本地 gate 分流 `MODEL_ELIGIBLE_BY_TAIL_GATE=1436`、`ANALYST_ONLY=87`、`DATA_UNVERIFIED=23`。**因缺歷史公告 PIT，安全模擬 0 筆給出數值**；這不是 live API 的 2026-09 發布成果。

## 效能：不能把歷史模型的 OOS 說成這次的新模型成果

- 先前 2025-09～2026-08 十二個**已曝光**時間折，同股同月 18,106 筆；5% 異常拒絕 894 筆，接受 17,212 筆。先前**逐折重訓**的 XGBoost：月份等權 MAE **23.900pp**、±4pp 命中 **20.07%**、±10pp 命中 **45.08%**、±20pp 命中 **69.05%**。強「最近營收延用」Baseline 依序為 **20.43%／43.66%／66.61%**。
- **以上是前一輪 12 月歷史交叉評估的參考結果；並非本次以最新 47,616 筆訓練之 RC1 權重的獨立前瞻驗證。** 其實際 ±4pp 命中仍偏低，不應向使用者展示為「通常 20% ±4%」。
- 5% 異常機制在已曝光回溯中攔截事後極端 `abs(Y)>=1000pp` 的 127／137（92.7%），但同時拒絕 767 筆未達這個事後定義的樣本。這是 selective prediction 的覆蓋率／機會成本交換，並非單筆準確率突增。
- 新模型的 `model.ubj` 儲存後可重新讀取並重現固定測試向量；本地驗收 **8／8 PASS**；尚無 GitHub CI、dev deployment、正式 Owner API/UI 正向讀回收據。

## 研究產物與權威

- **完整自含候選包**（`model.ubj`、原始 SHA-pinned CSV、訓練與 replay Python、8 個測試、manifest、報告、PIT-null 回放）已上傳並讀回 **Drive 唯一白名單根 `janusChatGPT/模型研究`**：
  [Janus_Fundamental_XGBoost_5pct_RC1_20261024.zip](https://drive.google.com/file/d/1pp2dwWTKhvFWwKbO-LeYjSPCPFg8Afrf/view)
- ZIP SHA256：`af6705e89eb0cef59759d58ac3d7b54a2739074400ea713207e7ef46b5c0a346`。
- 版本合約／模型 SHA／凍結配置請看 [frozen_xgb_5pct_rc1_20261024.json](frozen_xgb_5pct_rc1_20261024.json)；研究對照見 [5% 異常拒絕研究紀錄](extreme_abstention_2_5_10_20261024.md)。
- 目前仍未驗證實際 `published_at/available_at`、source authorization、原 full Parquet 同母體／training-serving parity、未曝光 prospective cohort。**Promotion 至 ACTIVE：BLOCKED**，待真正證據與 runtime／CI 驗收後，才可把 `publication_allowed` 由 false 變更，不能人工跳過。

**本次完成：RC1 研究候選模型版本、真正 XGBoost 權重、5% 門檻、SHA、文件與重跑包；正式 ACTIVE／Registry／serving：維持未修改。**
