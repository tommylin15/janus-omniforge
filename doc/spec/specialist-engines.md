# D07｜四模型角色、X/Y 與估值區間情境

> 2026-10-25：四模型本版正式上線依SEQ-06…08；分析因子與報告頻率見[分析Mart](analyst-input-mart.md)。新reference X契約不是發布artifact schema的替代品；Valuation mapping及真實覆蓋須驗，調校留2027 Q1。

> 2026-10-24 批次與快照改以 [統一流程](unified-batch-flow.md) 為準。四模型按可發布規劃，既有artifact/Registry真實狀態不改判；訓練仍外部執行、無週月例行模型稽核、無GitHub業務cron。本輪未測試／部署。
更新：2026-10-24（撤銷第五模型；04 Valuation 統合研究及前台估值區間）。方案 A 先交付事實解讀；模型設計已整理，不代表訓練/驗證/上線。狀態只看 [TODO](../todo.md)，資料窗口與前處理唯一契約見 [因子與時間](model-feature-time-contract.md)，研究來源見 [Colab/Drive](research-collection-gas-drive-colab.md)。

**2026-10-22 使用者指定：前四角色各一份獨立 XGBoost Colab Notebook，baseline 保留；Event 另議。** 詳細操作與可直接交給 AI 的開發指令：[Quant 趨勢](../colab-models/01-quant-xgboost.md)、[Risk 風險](../colab-models/02-risk-xgboost.md)、[Fundamental 營運](../colab-models/03-fundamental-xgboost.md)、[Valuation 估值](../colab-models/04-valuation-xgboost.md)。本次完成文件，不代表四份 Notebook 或模型已訓練。

## 2026-10-24 最終決策：僅四模型，04 統合區間情境

使用者決定**正式撤銷第五模型**：只有 Quant、Risk、Fundamental、Valuation 四個模型角色。取消獨立 `valuation_range` 與 Event/Catalyst 的第五模型訓練、Registry role、publication 與排程；不刪歷史 artifact。

04 Valuation 保留 PE/PB 相對定價、Ridge/Huber/XGBoost 的 log 倍數研究，並直接負責透明歷史 PE/PB 分位 × 可比 TTM EPS/BVPS 的**確定性情境區間及單一前台估值卡**。04 研究模型與情境各自走品質 gate，但共用財報/PIT/修訂/每股基礎/歷史倍數及一套版本化發布管理。相關 [04 區間子契約](valuation-range.md) 與 RV-01…06 專屬 04，沒有新的第五模型。

**實作差異：**現役 `packages/analysis_product.py` 與 Mart specialist 還有五筆 deterministic baseline／`event` 角色，屬既有 API/schema 相容現況，非第五個正式模型目標。須先驗 consumer、Owner/UI、API、rollback 才可遷移該 event baseline 成 A-CHANGE 事實；保留公告原文、公司行動、修訂去重與事件提醒，不可直接刪現役資料或服務。以下早期 Event 訓練設計均由本決策覆蓋。

## 1. 目前程式與建議
查證 main d7083890738a8660786110d0c73d58d8fe183c15：
- 正式 specialists.py 為 deterministic-unpromoted-v1；數字及規則不等於經 OOS 的預測。
- `research/colab/risk_pilot.py` 五因子 Ridge v0 已有真實 21 月 OOS；另 `risk_v1.py` 增加 `atr14_pct`、`abs_overnight_gap5`、`log_turnover20` 三因子，於同股票日期樣本比較 v0/v1。2026-10-22 研究環境 v1 MAE 0.127537、matched v0 0.133647；但未在 Colab 正式重跑，PIT／公司行動／授權／新樣本尚未達 promotion，不代表已部署。詳見 [v1實測收據](../archive/d07-risk-v1-ohlcv-oos-2026-10-22.md)。
- 研究採集首版僅 OHLCV；正式 Core 有資料不代表 Drive 研究集已有同欄位。其餘 X 均為待資料對照/建置，不能假稱可訓練。
- 模型先全市場普通股 pooled panel，按市場/產業特徵或分層評估，不為每檔訓練一套；排除 ETF。Owner 現金/成本/股數不進公開 X。
- 順序：A 事實/變化可獨立交付；D07-PRE→Risk→Quant→Fundamental/Valuation（資料足夠才訓練）；04 Valuation 的估值區間功能自行驗算公式／來源並合流同一 04 發布與 UI；事件事實 alerts 仍以 rules 為基準；四個研究模型各自 promotion。

## 2. 模型／X／Y／輸出矩陣
表內 challenger 是建議研究候選，需贏過 baseline 才採用，不承諾準確率。
| 角色 | 首版 baseline → challenger | X：可用時才啟用的特徵 | Y：預測目標／訓練單位 | 對小白的輸出 |
|---|---|---|---|---|
| Quant 價格趨勢 | 既有動能/相對強弱規則；Logistic/Ridge → 淺層 XGBoost；首版20日p_up，其他target/horizon獨立 | 5/20/60/120日報酬、20/60日相對市場報酬、MA20/60距離、量比、20日波動/成交金額；法人5/20日買賣超除以同窗成交股數；可用產業相對強度 | 股票×交易日；5/20日未來報酬、超額報酬；分開建 p_up 與 p_outperform，定義見時間契約 | 現況轉強/轉弱；通過校準才顯「未來5/20交易日上漲／勝過市場機率」，附適用期間、反證及不確定性 |
| Risk 風險 | Rolling20／Ridge5／Ridge8 → 既有 XGBoost8；分位另案 | 現有 vol20/vol60/drawdown60/abs_return5/volume_ratio20；擴充 ATR14/price、120日回撤、Beta/市場波動、流動性/跳空（OHLC齊備） | 股票×交易日；先未來20日 realized volatility；後續20日累積報酬 q05/q50/q95、最大回撤分開建模 | 「未來波動可能較近期大」；校準後的風險區間。歷史CVaR不是最大損失預測，分位區間不是保證 |
| Fundamental 營運 | 同月去年／上一期成長延續／ElasticNet → 淺層 XGBoost；先月營收 | 月營收YoY、3月合計YoY/加速度；可比EPS、毛利/營益率、ROE、負債權益、CFO/淨利；缺欄位/資料年齡 | 股票×公告期；主目標下一個月營收YoY（百分點誤差）；次目標下一季可比EPS水準/差額，不用每日重複財報膨脹樣本 | 「營運改善/放緩」「成長是否延續」；下次公告待確認項。無足夠期數保留規則，不能硬訓練 |
| **Valuation（04 倍數研究＋區間情境）** | 自身歷史／train-only同業中位數／Ridge/Huber → XGBoost 解釋 log(PE) 或 log(PB) | 當時可得成長/ROE/負債/獲利率、規模、產業、利率若有；同業因子及有效樣本 | 股票×估值日（研究抽月末減重複）；Y為當期可比市場倍數，排除目標倍數及其代數等價欄位進X；未來60/120日超額報酬僅作獨立效用評估 | 「較自身歷史/可比同業偏高或偏低」＋同一 04 輸出的唯一估值參考區間；情境以同口徑 TTM EPS/BVPS × 自身歷史 PE/PB 分位，不是內在價值或報酬預測 |

## 3. 各角色必要限制
- Quant：p_up、p_outperform 不能互換；價格基準明示，預測描述不冒充可成交績效。沒有證實獲利的模型可被淘汰，baseline 仍服務。
- Risk：原 vol20 定義為 log return 平方平均開根號×sqrt(252)，不是去均值樣本標準差。保留版本以便試點可重現；換 log target/公式必升版。現行 drawdown60 是距60日最高收盤回落，並非60日完整最大回撤。
- Fundamental：月營收需至少13個月才能算當期YoY，3月合計YoY需15個月；季度YoY需5季，可比TTM需4季，同期TTM比較需8季。窗口不足只停相依公式。
- Valuation：虧損PE不適用；負淨值PB不可照套；金融/非金融同業分開，無可比群不硬配。價格/同日PE、EPS倒算價格等代數洩漏不得作模型X。情境價格須有可比EPS/BVPS，否則僅倍數比較；不強行做DCF。
- Event 僅保留既有事實／A-CHANGE 及相容讀端，不列第五個模型訓練、選型或發布；公告去重、修訂與來源權利仍須保留。
- 解釋重要因子僅為模型關聯，非因果。先用穩定規則短句；可用 permutation 等輔助，不為SHAP另建服務。

## 4. 訓練、驗證、正式服務
先不選 LSTM/Transformer/強化學習/五個LLM：目前表格與低頻資料、獨立時間樣本尚不足，先驗證低複雜度 baseline/challenger。
研究在人工 Colab；Janus Mart 只匯入合格 artifact、同版前處理、推論、registry與rollback。正式數字仍從Core/serving，Drive不直接當正式行情來源。
按角色記錄 feature_schema/order/units、preprocessing、model/hash、label/benchmark/horizon、as_of/cutoff、training period、OOS、資料權利、missing/age、有效市場及適用母體。不同角色可用不同模型，不平均成總買進分數。
正式 Core 與研究資料皆採上市90%／上櫃70% 的數字門檻，但母體、分母、驗收與發布 gate 不同；達標不代表 PIT 完整或模型有效。嚴格時間外驗證/成熟標籤/歷史母體/公司行動/來源權利與原promotion不放寬。
D08只讀已驗證Fact Pack，LLM無canonical/publication權；A模板解讀不需要D08/LLM。

## 5. 評估指標與發布門檻
| 角色 | 最少評估 |
|---|---|
| Quant | Brier/log loss、機率校準、分市場/多空分段、PR/命中率與涵蓋率；回歸MAE/秩相關；另算成本後效用、流動性與不可成交 |
| Risk | MAE/RMSE，追加QLIKE需正variance與一致尺度；分位用pinball loss、實際覆蓋率、分位不交叉與尾部表現 |
| Fundamental | MAE（YoY百分點/EPS元）、對季節性baseline增益、轉盈轉虧與產業分段；不對零負值用MAPE |
| Valuation | PE/PB 研究：時間外倍數殘差、cohort 穩定性及獨立效用；情境：自身歷史分位算式 parity、來源/as-of、公司行動、24/60月、缺值、Owner/API/UI、回滾。**04 一套資料與發布治理，前台一張卡** |
訓練前固定評估計畫/可接受退化幅度，不看最終test後調門檻；樣本按日期/事件block估不確定性，不能把相關股票列數當獨立日數。簡單baseline可勝出；沒有穩定增益則不promotion。保留現有有效模型回退，不能只用訓練分數驗收。

## 6. 官方方法參考
2026-10-21查閱：[LightGBM objectives](https://lightgbm.readthedocs.io/en/stable/Parameters.html)、[scikit-learn 時序切分](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html)。套件支援不證明金融有效性；版本需鎖定。股票panel需自行按交易日分組與label maturity purge，不能直接把逐列 TimeSeriesSplit 當合格金融切分。


## 7. 資料量、部署與成效閉環
各角色試點/成熟研究的年數與標籤數、Colab八階段、GCS候選/registry、日週批次、成熟結果與36月回饋保存，統一見[模型生命週期](model-lifecycle.md)。建議量不是已收量，也不是所有功能共同硬門檻；21月OHLCV可先Risk PROBE，基本面/事件按原生獨立期數判斷。實作指令見[生命週期AI卡](../archive/document-cleanup-2026-10-25/execution-cards/d07-model-lifecycle.md)。

