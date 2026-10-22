# D07-PRE｜Colab → Drive v3 單一 Parquet 研究資料契約
更新：2026-10-22。狀態：21 個月 r1 行情已驗收；Drive v3.1 Parquet `CURRENT.json` 與 153 個分區檔已實際讀回，**資料格式整併 CLOSED**；官方／第三方缺口補收 **PARTIAL／未結案**，Risk OOS、歷史 PIT、模型正式發布另依 D07 gate。檔案路徑因既有 GitHub 連結保留，**內容正式覆蓋舊 GAS→ZIP 方案**。

## 唯一資料路線
**官方 TWSE／TPEx 與經允許的 Yahoo、FinMind → Google Colab 手動採集、定向補收、斷點與品質處理 → Drive `janusChatGPT/資料源/JanusDataset_v3_202610/data/YYYY-MM/` 原始來源檔 → `canonical/CURRENT.json` 指向不可變 Parquet release → Colab 因子／標籤／模型 OOS → Janus Mart 受控匯入。** 無需 GAS、GAS Loader、GCP 重訓 Jobs、BQ ML/OOS；Colab MCP 若將來可用只作操作介面，不列前置必要條件。目前 ChatGPT 尚未連上 Colab MCP。禁止把程式已提交冒稱 Colab 現場已執行。

## 普通股母體及歷史限制
- 僅 TWSE／TPEx 上市上櫃**普通股**；以官方公司基本資料（TWSE `opendata/t187ap03_L`、TPEx `mopsfin_t187ap03_O`，必要時官方 CSV）建立白名單，ETF、ETN、基金、權證、債券及非普通股在**下載後入庫前**過濾。優先用官方名冊，而非單靠四碼。
- 歷史按**每日整市場**查詢 TWSE `MI_INDEX` 日期 API 與 TPEx 歷史每日行情，不把 OpenAPI `STOCK_DAY_ALL` 目前快照誤用成歷史 API；每市場×交易日約一筆 HTTP 請求。遵守回應錯誤／429 與限流，不迴避來源限制。
- **重要限制：官方最新公司名冊並非歷史逐日有效名冊，包含不了當時曾上市但已下市的股票。** 首版明列 `historical_survivorship=CURRENT_MASTER_ONLY`、`historical_pit=NOT_VERIFIED`、`research_70pct_certified=false`（舊 r1 原檔欄位維持不變），只能做研究 PROBE；符合 TWSE 90%／TPEx 70% 的現行名冊涵蓋率即可進 Risk OOS 研究，不需等歷史下市名冊補完。不得將此准入當成歷史 PIT 認證、來源授權或模型正式發布核准；若要主張完整歷史母體須另取得適用分母證據。
- 研究每個 dataset×month **分市場獨立准入：上市普通股 TWSE ≥90%；上櫃普通股 TPEx ≥70%（等號通過）**。第一輪 OHLCV 的研究准入須**同時**檢查：(1) `CURRENT_MASTER_ONLY` 普通股快照為分母、當月至少有一筆有效 OHLCV 的不同股票數為分子的月度股票涵蓋率；(2) 同一普通股快照數 × 各市場 manifest 已收交易日數為分母、有效 OHLCV 列數為分子的股票交易日涵蓋率。兩項皆依上市90%／上櫃70%判定，等號通過；已核准休市不算交易日，來源失敗不得假冒休市。這仍不是歷史 PIT 分母認證，模型缺日窗口、公司行動、來源授權須獨立保留旗標。正式 Core 原本同為 90%／70%，但其品質驗收與本研究 PROBE 仍獨立。Owner 個人行情／ETF 顯示不變。缺值不可補造；來源時間貼標，不得倒填 published_at／observed_at。

## 2026-10-22 實際採集與驗收（覆蓋舊月檔讀取入口）

- **唯一模型讀取契約**：Drive `JanusDataset_v3_202610/canonical/CURRENT.json` → `release-b21384aebef3cd70`，分別存 `ohlcv/`、`revenue/`、`valuation/`、`financials/`、`corporate_actions/` 的 Parquet。現場已讀回 153 個 Parquet 分區；manifest 研究資料版本 `3.1.0`、`status=RESEARCH_DATA_ONLY`。格式整併範圍依實際 Drive 檔案與 manifest **CLOSED**，不包含歷史 PIT／正式模型認證。
- **尚未完成**：官方月營收 96/96 批、估值 50/72 批、損益表 24/32 批、資產負債表 22/32 批、現金流量表 22/32 批；上櫃估值 22 個月缺批，2025Q3 起財報有缺口，2026Q3 仍在預留公告期，勿標成已正式失敗。
- **新版操作入口**：[Drive 00_資料收集.ipynb v3.2](https://drive.google.com/file/d/14qqdkRehe89JGtlzks1AmP3054LB9uk0/view)（單一正式 Colab Notebook）。已本地確認 Notebook 16 個 cells／7 個內嵌模組可編譯、補缺與驗收 targeted tests 4/4 PASS，**尚未在 Colab 執行新版實際補收與重新產出驗收總表**。舊版移入 Drive `CoLab程式/_archive`。
- **限定補收**：只排尚未完成的 TPEx 估值月批及已過公告預留期的 2025Q3～2026Q2 季財報；已達研究市場門檻者跳過。先試官方單批，必要時採 FinMind `TaiwanStockPER` 歷史估值或 FinMind／Yahoo 季報，成功 checkpoint 不重抓。FinMind 以股票×資料類型整合缺月窗口；達時間／請求上限記 `BUDGET_PAUSED`，不是資料損壞。
- **驗收報告**：新版 Notebook 最後核對 manifest 檔案 SHA、`CURRENT.json`、實際 Parquet 覆蓋，顯示繁體中文資料類型、角色試訓期間與 PASS／PARTIAL／BLOCKED、分市場逐期缺口原因及補收建議；落地 `reports/驗收總表.csv`、`模型試訓準入.csv`、`逐期缺口與原因.csv` 等。新版實跑前不可將其視為已發布報告。
- 第三方值保留來源與期別，但不因可做研究試訓就宣稱歷史公告時間、PIT 與模型 promotion 已驗證。

## 舊 r1 原始月檔與效能（保留為上游格式）
```text
janusChatGPT/資料源/
  _control/universe-r1.json
  2025-01/
    ohlcv-r1.csv.gz
    universe-r1.csv
    quality-r1.json
    manifest-r1.json
  2025-02/
    ...
```
- 一個月份一個 Drive 資料夾；相同月份的新資料來源或修訂使用 `r2` 等版次檔名，不能無聲覆蓋已使用的資料。
- 每個來源／市場以 10 個平日作單一壓縮 checkpoint；Colab 暫停後重跑只抓未完成批次。**整月資料與 manifest 校驗後刪除該版中繼 checkpoint**，避免大量碎檔。來源原始回應 SHA256、日期與已收錄 row count 列入 manifest。
- 上述 r1 原始月檔最初僅 OHLCV；v3 已另建 Parquet 研究資料層（部分 valuation、financials 與 corporate_actions 已有值）；其他因子缺少的保留 `UNAVAILABLE`，不造空資料或假數字。
- 尚未結束的月份不得封存，並遵守人工 Colab 執行／限速／休市日及中斷續跑。個人非商業研究不等於自動取得所有 ML 訓練、保存和散布權；不得寫入 Owner 私有成本、現金、交易、OAuth token 或秘密。

## D07／上線界線
Quant/Risk 先建立 baseline＋challenger；Valuation/Fundamental 視實際資料，Event 沒有合格標註時 rules only。完整 PIT、成熟標籤、OOS／walk-forward、評估 hash 與訓練授權到齊才可進入受控 Janus Registry；LLM 無 canonical number／最終 publication 權力。已退役舊 GCP/BQ 研究路線按 [唯一結案收據](../archive/d07-gcp-bq-retirement-live-2026-10-20.md) 維持 CLOSED，正式 Stage/Core/Mart、Owner 和週 Iceberg 不受影響。

**實作與操作**：[Colab 唯一 README](../../research/colab/README.md)；**唯一進度**：[Active TODO](../todo.md)。

## 日常窗口與衍生因子（2026-10-21）
月資料夾只作研究保存分區，不限制每日模型窗口。讀取跨月最長lookback與warmup後，在Colab做共用清洗/時點整合/X/Y；正式每日推論沿既有Core/Mart增量，不等待當月研究檔封存，不每天重抓整月。
唯一前處理、窗口、label及train-serving一致性見[因子時間契約](model-feature-time-contract.md)；各模型選型/X/Y見[五分析師](specialist-engines.md)。新因子需求先核既有正式及研究欄位，缺資料保留缺口，不因本節自動新增來源/付費/擴大歷史回補。


## 訓練資料量與生命週期
資料取得與模型需要的年數/樣本量按[模型生命週期](model-lifecycle.md)第2節逐角色規劃。Risk 3–5年、Quant主要5年、基本面5–7年月季、估值3–5年、Event以去重人審數為主均為研究目標，不是已實收或全功能前置。
保留既有21月OHLCV試點先行；有界延伸歷史先補年份日曆/歷史母體/授權。來源實際不足時列可用量與缺口，不假造；正式Core TTL不為研究年數自動擴大。

