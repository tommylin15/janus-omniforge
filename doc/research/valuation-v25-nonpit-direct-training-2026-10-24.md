# Janus／OmniForge 04 Valuation｜v25 直接真資料試訓（2026-10-24）

## 本次使用者決策／界限
使用者指示：**不以供應商逐筆稽核/PIT 完整證據為本次研究試訓前置**，使用既有真實數據直接訓練。此授權只降低**研究**等待成本，**不**授權真實缺值造值、不允許使用當期 PE/PB 代數還原 Y、不更改 canonical / Registry / Risk ACTIVE / publication。狀態 **RESEARCH_NON_PIT_PROBE**，`publication_allowed=false`。

## 真實輸入、特徵與時間
- 固定舊研究 release `release-0bbae8d9c1ca7d8d`，來源為已執行 v22、經 v23 重播的 **4,000 個股票×月份真實 FinMind 歷史月內最後觀測估值快照**（2021-12 至 2023-09），其中交集日期與財務有四因子值者 2,074 列。此僅為 v22 優先補收之股票樣本，非全市場隨機樣本。
- 財務來自同一 release P0/P1 **1,181,442 列實測 `inventory.csv.gz`**；選同一來源 MOPS 中文原始科目 `資產總計`／`負債總計`／`權益總計`／`本期淨利（淨損）`，拒絕把另一來源不同單位的英文欄位混進同一樣本。數值按研究假設，非正式公告時點認證。
- 訓練 X = `roe_proxy=net_income/equity`、`debt_ratio=liabilities/assets`、`log_total_assets=log(assets×1000)`、`market_code`，四項，不含當期 target、PE/PB、股價、市值。原正式 schema 的 `revenue_yoy` **無可用歷史同季對照，因此未參與這版訓練**；`roe_proxy` 亦非已核定的年度化 ROE。這是縮減特徵的四因子研究候選，**不是正式五因子實作完成**。
- 財務可用時點使用 `fiscal_quarter_end+90days` **研究假設**，不宣稱 `published_at`/PIT 真實回推；月末標 FinMind 該月最後實際觀測，不宣稱已驗證官方最後交易日。
- 所有股票同月同 fold：**train 2023-03..06**，**validation 2023-07**，**test 2023-08..09**。未拿 test 挑最佳參數。三個候選為 train-only 分市場中位數、Ridge alpha30、固定配置 XGBoost depth2/140樹；分別用 log(PE) 和 log(PB) 作 Y，非正倍數列排除。
- 採用 2026-10-24 本機 Python、pandas、numpy、sklearn、xgboost；詳細版本、來源 SHA256 與每個模型 artifact SHA256 存 `report.json`。

## 實際模型比較（測試集，主要指標 log 倍數 MAE；低為佳）

| 模型 | PE 370筆/185檔/2月 | PB 622筆/311檔/2月 |
|---|---:|---:|
| train-only 市場中位數 | 0.8208 | 0.4942 |
| Ridge | 0.8004 | 0.4663 |
| XGBoost | **0.7920** | **0.4326** |

訓練：PE 765列、PB 1,141列，各4個不同月份；驗證：PE 200列、PB 311列，各1個月。**PE 驗證 log MAE 為基準0.8135、Ridge0.8629、XGB0.9026，未勝基準**，因此不可據 test 稍好宣稱已確定升級；PB 驗證基準0.5024、Ridge0.4757、XGB0.4383，PB 值得繼續，但 validation 只有一月、test 只有二月與選股偏差。XGB 原生 `.ubj` 實際產生並重載比對測試向量。

## 實作與交付
- 本輪已在 ChatGPT Python 環境**實際訓練** PE/PB 各一組 Ridge 與 XGBoost，非 mock。執行了真資料與時點防護、按月 split 與 UBJ 重載一致性 **3/3 PASS**。
- 完整本機來源、測試、兩個 `.ubj`、Ridge 系數、PE/PB 每模型真實 test predictions、train/val/test 全指標與 `report.json` 已封裝 **`Janus_Valuation_v25_真資料直接試訓_NON_PIT_20261024.zip`**。來源真實庫以既存 v23 與 P0/P1 ZIP SHA 引用，未複製整份大檔。
- 尚未以具完整 PIT、官方月末、歷史一般股 cohort 的全市場資料建立正式 X/Y，未實測 2024–2026 OOS、未完成 5-feature `revenue_yoy` 模型，**不得發佈**。
- 下一步：若要求模型真正可用，應從原 CURRENT 36 月估值與更完整季度資料取得同窗營收 YoY，再做擴張月份 OOS、完整五因子訓練／baseline／model schema 比較。本輪不再全市場補資料。

此報告是研究實跑驗收，不變更既有 canonical、CURRENT、Risk ACTIVE、Registry 或 serving。