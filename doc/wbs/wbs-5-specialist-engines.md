# WBS-5｜五分析師引擎與研究模型

更新：2026-10-20。唯一研究資料契約：[官方歷史行情→Colab→Drive每月資料夾](../spec/research-collection-gas-drive-colab.md)；五角色輸出：[Specialist SPEC](../spec/specialist-engines.md)；唯一工作狀態：[TODO](../todo.md)。舊 B5～B8 Core/BQ/Cloud Run 訓練路徑不再是本 WBS。

## D07-PRE：資料與舊路線退役
1. Colab 直接抓 TWSE／TPEx 官方歷史整市場每日行情，採現行普通股公司名冊白名單（歷史下市股票缺口標 PROBE），股票母體為 TWSE/TPEx 普通股、ETF 排除；每市場×資料集×月上市 ≥90%、上櫃 ≥70% 才可標記當前名冊的研究資料涵蓋達標（仍為 PROBE，不宣稱 PIT）。只盤點目前持股/觀察股的公開欄位與有效值，時間欄位貼標但不阻擋第一輪採集。
2. 私有 Drive `janusChatGPT/資料源/YYYY-MM/`，OHLCV 先以壓縮 CSV、universe、quality、manifest 存放；其他資料集按取得授權續補，各資料有 source/SHA、限流及 checkpoint，不填不存在的資料。
3. 舊 specialist-retrain／GCP／BQ研究路線已於2026-10-20依實機收據結案，不重開；只保留archive追溯。

## D07：五角色建模
- Quant：動能／相對強弱，OHLCV、成交量額、指數。
- Risk：波動／回撤／CVaR／Beta，個股與指數。
- Valuation：PE／PB 河流、殖利率、財報估值因子。
- Fundamental：月營收、EPS、淨利與財務品質。
- Event：來源公告與事件修訂；沒有合格人審標籤／使用許可時保留規則，不訓練分類器。
- Colab 人工執行各自 baseline／challenger／成熟標籤 OOS、回測防 future leakage 與 hash／版本。資料達上市90%／上櫃70%不是模型可發布的證據；各角色獨立 promotion。
- Janus Mart 只做已驗證 model artifact 的接收、驗證、版本、推論、rollback；不在 Cloud Run/BQ fit 模型。

## 正式服務不受研究重構影響
上市櫃全市場低成本 screening 仍依正式 Core 資料門檻（上市 ≥90%、上櫃 ≥70%）；Deep Coverage 只處理 watchlist ∪ holdings 的 dirty 股票與角色；Owner ETF/私有交易和正式行情/分析/UI/API、Stage48h、每週 Iceberg、備份繼續正常。LLM 沒有 canonical number／最終發布權力。

## 驗收
D07-PRE 檢查真實 API 月檔／覆蓋與來源授權（舊GCP/BQ退役已結案，不重驗）；D07 驗 Colab OOS→Janus registry；D08 驗個股/CEO/Admin/Owner UI。各段 `DOC_UPDATED`、`DEPLOYED`、`OOS_VALIDATED`、`RUNTIME_REMOVED` 不得混為同一個 PASS。

## 方案 A 與 D07 交付責任（2026-10-21）
A-CHANGE由WBS-5負責事實/狀態/盤前盤後facts，WBS-6負責API/UI，依[方案卡](../execution-cards/a-change-analysis.md)集中驗收。A不等D07。
D07唯一模型/X/Y表在[Specialist SPEC](../spec/specialist-engines.md)，窗口/清洗在[時間契約](../spec/model-feature-time-contract.md)，不在WBS複製公式。
| 切片 | 責任/相依 | 驗收 |
|---|---|---|
| D07-FEATURE | 資料/研究工程；依D07-PRE可用資料 | 清洗/交易日/as-of/公司行動/成熟label與train-serving一致；既有Core不重建 |
| D07-MODEL | 模型研究；依feature | Risk現有Ridge先行，Quant其次，其他按獨立期數；同OOS baseline/challenger，失敗保留rules |
| D07-SERVE | Mart/API/Admin；依各角色OOS | model/schema/hash/preprocessor受控匯入、真實推論、回退與缺值行為 |
切片不是新的獨立queue，唯一狀態在TODO。


## D07模型生命週期責任（2026-10-21）
沿原FEATURE/MODEL/SERVE三切片：FEATURE含Colab採集清洗貼標與各角色建議資料量；MODEL含notebook/OOS/export；SERVE含GCS candidate/registry/shadow、日週推論、outcome與每月評估/retention分類。唯一契約[模型週期](../spec/model-lifecycle.md)、操作[AI卡](../execution-cards/d07-model-lifecycle.md)。日常事實報告UI由A-CHANGE、手動CEO由D08，不重複派工；自然長horizon outcome到期前只標pending，不拖延已完成管線驗收。

