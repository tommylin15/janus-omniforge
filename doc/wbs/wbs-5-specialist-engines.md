# WBS-5｜五分析師引擎與研究模型

更新：2026-10-20。唯一研究資料契約：[官方歷史行情→Colab→Drive每月資料夾](../spec/research-collection-gas-drive-colab.md)；五角色輸出：[Specialist SPEC](../spec/specialist-engines.md)；唯一工作狀態：[TODO](../todo.md)。舊 B5～B8 Core/BQ/Cloud Run 訓練路徑不再是本 WBS。

## D07-PRE：資料與舊路線退役
1. Colab 直接抓 TWSE／TPEx 官方歷史整市場每日行情，採現行普通股公司名冊白名單（歷史下市股票缺口標 PROBE），股票母體為 TWSE/TPEx 普通股、ETF 排除；每市場×資料集×月 ≥70% 才標研究資料完整。只盤點目前持股/觀察股的公開欄位與有效值，時間欄位貼標但不阻擋第一輪採集。
2. 私有 Drive `janusChatGPT/資料源/YYYY-MM/`，OHLCV 先以壓縮 CSV、universe、quality、manifest 存放；其他資料集按取得授權續補，各資料有 source/SHA、限流及 checkpoint，不填不存在的資料。
3. 舊 `specialist-retrain`、手動工作流、非共用 ML/OOS BigQuery／Cloud Run 路線一旦證實不被正式服務使用就立即移除，**不等新 Colab 採集上線**。保留實際 GCP 資源證據與刪除讀回，GitHub 修改不等於雲端完成。

## D07：五角色建模
- Quant：動能／相對強弱，OHLCV、成交量額、指數。
- Risk：波動／回撤／CVaR／Beta，個股與指數。
- Valuation：PE／PB 河流、殖利率、財報估值因子。
- Fundamental：月營收、EPS、淨利與財務品質。
- Event：來源公告與事件修訂；沒有合格人審標籤／使用許可時保留規則，不訓練分類器。
- Colab 人工執行各自 baseline／challenger／成熟標籤 OOS、回測防 future leakage 與 hash／版本。資料達70%不是模型可發布的證據；各角色獨立 promotion。
- Janus Mart 只做已驗證 model artifact 的接收、驗證、版本、推論、rollback；不在 Cloud Run/BQ fit 模型。

## 正式服務不受研究重構影響
上市櫃全市場低成本 screening 仍依正式 Core 資料門檻（上市 ≥90%、上櫃 ≥70%）；Deep Coverage 只處理 watchlist ∪ holdings 的 dirty 股票與角色；Owner ETF/私有交易和正式行情/分析/UI/API、Stage48h、每週 Iceberg、備份繼續正常。LLM 沒有 canonical number／最終發布權力。

## 驗收
D07-PRE 檢查真實 API 月檔／覆蓋、GCP/BQ 舊路線停用與來源授權；D07 驗 Colab OOS→Janus registry；D08 驗個股/CEO/Admin/Owner UI。各段 `DOC_UPDATED`、`DEPLOYED`、`OOS_VALIDATED`、`RUNTIME_REMOVED` 不得混為同一個 PASS。
