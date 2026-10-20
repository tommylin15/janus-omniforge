# 五分析師｜正式個股輸出與新版研究模型契約

更新：2026-10-20。**研究唯一入口：[官方行情→Colab→Drive每月資料夾](research-collection-gas-drive-colab.md)**。舊 BigQuery ML/OOS 中轉、Core frozen Parquet 必經出口、Cloud Run 月度 retrain 等 B5～B8 研究路線全部退休，僅歷史 Git／archive 可追溯，不作新 WBS/前置驗收。

## 分析師資料及輸出

| 角色 | 第一批既有公開欄位 | 尚待核對／補充 | 個股頁輸出 |
|---|---|---|---|
| Quant | OHLCV、成交量/金額、指數、法人 | adjusted price／公司行動／產業分類 | 歷史動能、相對強度、排名；OOS合格才有預測 |
| Risk／Regime | OHLCV、benchmark，可算 Beta/CVaR/回撤 | adjusted price／無風險利率 | 波動、尾端損失、市場風險 |
| Valuation | PE、PB、殖利率、EPS/ROE | 每股淨值、股數、TTM EPS、FCF、同業分類 | PE/PB 河流、估值位置與情境 |
| Fundamental | 月營收、EPS、淨利、ROE、負債 | 毛利、營益率、營業現金流、CapEx | 營運成長與財務品質 |
| Event／Catalyst | event_id、公告內容/來源/類型 | 事件方向/重大性/人審標籤 | 事件摘要、來源、修訂／不確定性 |

## 研究母體／資料顆粒度

研究只採 TWSE／TPEx 普通股，排除 ETF、ETN、債券ETF、基金、權證。現行官方公司名冊無法完整重建歷史下市股票，第一輪資料只能標研究 PROBE，不得用現行名冊假稱歷史 PIT 或 70% 全市場認證。各市場×dataset×月份有效收集資料 ≥70% 即達**研究採集門檻**；未過門檻標 PARTIAL 不造值，不能當 ML 模型有效性。第一輪盤點對照持股/觀察股的**公開欄位**，不匯出 Owner 成本、股數、現金或交易。時間欄位有就貼 published_at/observed_at/fiscal_period/collected_at/version，初次收集不要求先完成歷史 PIT 稽核或固定24月回補。

Quant/Risk 股票×交易日；Valuation 股票×估值交易日加財務期別；Fundamental 股票×月營收／季報／版本；Event 股票×事件×版本。每月資料夾將不同顆粒度存在各自壓縮 CSV/JSONL，而不是強制合成每日一列。

## 正式服務邊界

現有 Core Iceberg、日常 EOD、market-screening、Mart 確定性計算、持股/觀察股、Owner 私有資料、API、週維護及備份**繼續服務**。研究不經 Cloud Run/Core/BQ 強制搬運，但正式服務仍沿既有合格價、來源與 Core 品質 gate（TWSE ≥90%、TPEx ≥70%），個人持有 ETF 行情不受研究排除政策影響。全市場低成本 screening，watchlist ∪ effective holdings 深度運算和 dirty cache 不變。LLM 無 canonical number 或 publication authority。

## 模型與上線

Colab 人工做五角色 baseline/challenger、特徵標籤、時間外 walk-forward OOS、成熟標籤、防未來洩漏、可重現模型及結果 SHA。Quant/Risk 先行；Valuation/Fundamental 視可得欄位；Event 沒有真正人審及可用訓練權限時只能使用 Parser/Rules，分類機率為 null。未驗證 ML 不顯示虛構報酬機率，保留 deterministic baseline。

正式 Janus Mart 僅收驗證通過的模型版本、註冊/推論/回退；新模型訓練不在 Cloud Run/BQ。五角色 Fact Pack 的 source/provenance、input hash、model_version、analysis_as_of、quality/missing/staleness 可展開，CEO 按需只讀已驗證 Facts。學習資料達70%不能取代模型發布門檻。

執行與狀態：[TODO](../todo.md)、[D07 任務卡](../execution-cards/d07-specialist-b9-oos.md)、[PROJECT_RULES](../PROJECT_RULES.md)。Colab 採集程式已有本地測試，真實歷史批次收據與 OOS 仍待執行；GCP/BQ 舊路線已依既有實機收據結案。
