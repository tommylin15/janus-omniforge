# D07-PRE｜Colab 原生台股歷史資料採集（唯一正式研究入口）

2026-10-20：新研究路徑為 **官方 TWSE／TPEx → Colab Python → 私有 Drive 每月資料夾 → Colab 五分析師**。GAS／GAS Loader 已退役，不需要 GAS MCP、Apps Script API 或 GCP Job。Colab MCP 可用時可作選配操控介面，**不是**採集或訓練前置條件；目前 ChatGPT 無已連線的 Colab MCP，尚無 Colab 真實執行收據。

## 2026-10-23｜四模型最後一步研究因子工廠（v3.8 候選）

已將 Colab 單一採集 Notebook 最後加一格共用特徵派生；候選 [v3.8 ZIP（Notebook+Python+targeted tests）](https://drive.google.com/file/d/1QfCs0zeReUlp3hJzgVqsZv75xab40G2Z/view) 已存 `janusChatGPT/CoLab程式`。**Drive 原 v3.6 Notebook 未覆寫**，且擴充前備份已放在 `CoLab程式/_archive`；Colab 採集與全量因子實跑尚未驗證。v3.8 在一般增量採集後預設 `FACTOR_BUILD=True`，可設 `FACTOR_ONLY=True` 不重抓舊資料而只以現有 `CURRENT` 建因子，`RECHECK_ONLY=True` 則完全不變更資料。生成 `derived/four_model_features/` 的 X 候選、隔離 Y 候選、factor_catalog、SHA 收據，不更改 canonical，不替代正式模型的 PIT／貼標／train-only preprocessing。產業/指數/法人等未有合格實收資料時明確標 PENDING。詳 [研究資料 SPEC](../../doc/spec/research-collection-gas-drive-colab.md)。

## 四角色獨立訓練 Notebook 開發文件

2026-10-22 使用者指定前四角色各自一份XGBoost Notebook。完整Colab步驟與AI程式開發指令：[Quant 趨勢](../../doc/colab-models/01-quant-xgboost.md)、[Risk 風險](../../doc/colab-models/02-risk-xgboost.md)、[Fundamental 營運](../../doc/colab-models/03-fundamental-xgboost.md)、[Valuation 估值](../../doc/colab-models/04-valuation-xgboost.md)。四份文件已交付；Notebook實作與實際訓練仍按D07驗收。Event另議，不在本輪建立第五份。

新模型只讀下述Parquet CURRENT release，產物按角色/run_id寫入 `janusChatGPT/模型研究`；下方舊r1命令僅供歷史試點重現。Risk沿用既有XGBoost8，不重做已完成模型選型或另接手部署。

## 現行正式 Colab／Drive v3.5 長期增量＋完整安裝格＋TPEx 空日修復（2026-10-22）

**單一 Notebook**：[Drive `00_資料收集.ipynb`](https://drive.google.com/file/d/1403NtnW0sQ5VuATycDiFvEsHztOvlMvH/view)；掛載根目錄 `/content/drive/MyDrive/給ai專用/janusChatGPT/資料源/JanusDataset_v3_202610`。模型不再讀下方舊版 `資料源/YYYY-MM` 路徑，應只讀 `canonical/CURRENT.json` 指定不可變 Parquet release；原始來源位於 `data/YYYY-MM`，成功 checkpoint 與原始來源保留。

- **已實際讀回**：21 個月 r1 OHLCV、153 個 v3.1 Parquet 月分區、`CURRENT.json`；資料格式整併 CLOSED。
- **仍待 Colab 實機補收**：TPEx 估值最新剩 7 個未達標月份；季財報依新品質報告各別核對。v3.5 自動納入新月份的 OHLCV、兩市場估值與營收、財報等未達研究門檻且已到期缺口，依有限請求數／分鐘續跑；`BUDGET_STOP` 轉成 `BUDGET_PAUSED` 狀態，不代表來源故障。FinMind 的 `TaiwanStockPER` 可用於上櫃歷史估值補缺，Yahoo 可嘗試近期季財報，但不可倒填歷史估值。
- **最後一格自動驗收**：`reports/驗收總表.csv`、`資料收集完成度.csv`、`模型試訓準入.csv`、`逐期缺口與原因.csv`、`定向補收建議.csv`；各角色研究試訓准入 PASS／PARTIAL／BLOCKED，不等於模型 OOS／PIT 與正式 promotion PASS。
- **驗收實情**：v3.5 Notebook 16 個 cells、7 個內嵌模組，**Drive 第1個 code cell 已恢復完整10行安裝與掛載**；真實官方 raw HTML/日期/續查測試 8/8 ＋ 2027/03 跨年度回歸 7/7 PASS，原 Drive 檔案 SHA256 下載一致；**尚無 v3.5 Colab 實際補齊剩餘 7 個月**。對應規格：[研究資料契約](../../doc/spec/research-collection-gas-drive-colab.md)。

**22 個上櫃估值缺月處理（v3.4）**：2026-10-22 前次官方回報總 264 批／待補 22 個 TPEx 估值月批（2024-10、2025-01 的 `VALUATION_UNRECOGNISED_EMPTY` 可重現來源結構問題）。新版 TPEx 優先查官方歷史日期 `pera_result.php?o=htm&d=民國年/月/日` 的整市場 HTML 匯出，必須核對「資料日期」才存月末快照；僅明確無資料時倒查前十個曆日。這是來源 adapter 修正，**不是**用 FinMind 大量逐股重新收集。若官方 HTML 版型改變、已確認 parser 錯誤，允許對所有因此略過的 22 個月份執行有界 `TaiwanStockPER` 歷史補缺；來源 401/403/429、CAPTCHA/Forbidden 則停止，不以備援規避來源限制。官方成功結果和 FinMind checkpoint 都可續跑。**新的 Colab 執行結果尚未取得，22 個月不可提前標已完成。**

**v3.5 最新補收進度（2026-10-22）**：前版 v3.4 在 Colab 真實執行官方 264 批後，研究門檻尚缺 TPEx valuation **2024-10、2025-01～05、2026-02（7 個月）**。Drive raw 經讀回發現 **2025-05-30 和 2026-02-27 的官方 HTML 含正確日期，但 tbody 空、共0筆**；這應是當日空行情並允許向前找前一交易日，**不是** `TPEx_HTML_SCHEMA_UNRECOGNISED`。另 v3.4 安裝儲存格只剩單行 import，是程式交付缺陷；v3.5 已恢復 10 行完整 setup。重新開啟原 [正式 Notebook](https://drive.google.com/file/d/1403NtnW0sQ5VuATycDiFvEsHztOvlMvH/view) 驗證第一格有 `pip install`、`drive.mount`、`ROOT`，再執行全部；不要使用 Colab 已開啟的 v3.4 分頁。**7 個月尚待 v3.5 實際補跑，補收狀態維持 PARTIAL**。已成功月份不重抓。

**長期操作要點**：`END_MONTH_OVERRIDE=None` 時，以台灣時間「上個完整月份」為截止；如 2027/03 開啟則自動查至 2027-02，2027-03 需等4月完整封存。OHLCV 仍從 2025-01 起、官方月營收 2022-10／估值 2023-10／季報 2022Q4 起持續增量，不因滾動 36/48 月刪掉舊期別；已完成行情月檔不因年度 revision 更新而重抓。原始年份封存檔留在 `data/YYYY-MM`，只有 Parquet `CURRENT.json` 是研究模型入口；請求上限與時間上限需重跑同一份 Notebook 續收。詳細指令保留在 [Drive v3.3 README](https://drive.google.com/file/d/169hlWe8qNn60mH71-LKNXE2RNKiPKNct/view)。**目前僅程式交付／本地測試 PASS，未取得 v3.4 Colab 實際補收驗收。**\n\n以下保留**歷史 r1 採集器操作方式**，不再作為 v3 模型讀取入口：

## 1. Google Colab 一次設定

本專案使用者的單一 Drive 根目錄在 `MyDrive/給ai專用/janusChatGPT`；Colab `--drive-root` 固定指向 `/content/drive/MyDrive/給ai專用/janusChatGPT/資料源`，不得改回 MyDrive 直下的舊範例。若 Google Drive 資料夾再次移動，先實際確認掛載後路徑，再調整執行命令；既有 `r1`、已封存月份與 checkpoint 不因路徑修正重抓。

在 [Colab](https://colab.research.google.com/) 建立個人的 notebook，手動授權掛載 Drive，再執行：

```python
from google.colab import drive
drive.mount('/content/drive')
!pip -q install requests pandas numpy scikit-learn pytest
!git clone -q --depth 1 https://github.com/tommylin15/janus-omniforge.git
```

## 2. 整批歷史 OHLCV（**只收 TWSE／TPEx 上市上櫃普通股**）

第一批建議 **2025-01 至 2026-09**（都是已結束月份）；程式先抓最新官方上市／上櫃公司基本資料建立普通股白名單，再逐日抓 TWSE MI_INDEX、TPEx 官方上櫃歷史行情。**不使用** `STOCK_DAY_ALL` 當歷史 API，也不逐檔下載：同一天每市場原則上只請求一次。空值保持空值、未核准歷史股票保持缺口。

```bash
!python janus-omniforge/research/colab/collect_tw_equities.py \
  --drive-root '/content/drive/MyDrive/給ai專用/janusChatGPT/資料源' \
  --start 2025-01 --end 2026-09 --revision r1 \
  --max-requests 20 --max-minutes 10 --interval 2
```

**2026-10-20 休市日修復**：已按交易所公告將 2025／2026 年已知休市日（含元旦、春節「僅結算不交易」日）列為 `SCHEDULED_CLOSURE`，跳過行情 API 請求但在 checkpoint、manifest、quality 保留日期證據。正常交易日回傳空行情仍視為失敗；不把 API 故障當成休市。既有完成 checkpoint 不需重抓；若 Colab 已 clone 舊版，先更新：

```bash
!git -C /content/janus-omniforge pull --ff-only origin main
```

**分段斷線續跑（Colab 無須一直開）**：建議每次手動執行 `--max-requests 20 --max-minutes 10`，先達到請求數或時間上限就回報 `PARTIAL`，正常停止；再次連上 Colab、掛載**同一個 Drive**，更新 GitHub 後執行**同一命令**，從缺少的日期續抓。即使免費 Colab 中途斷線，已成功的一天會立刻寫入同一個 10 日 checkpoint，最多重抓當日未完成的請求；檔案存 Drive，非 Colab 暫存 `/content`。時間限制預留 90 秒安全餘裕以防長請求／Drive 寫入；來源長時間重試可能仍超時。**沒有背景自動執行：斷線後需由使用者重新連線並啟動。** 用 `r1` 繼續，不要換版號、刪 checkpoint 或重抓已封存月份。

重跑**相同指令**會從已完成 checkpoint 繼續。每 10 個平日／市場使用同一份壓縮 checkpoint，**每完成一個交易日就更新保存**；兩市場皆完成整月才寫入最終 manifest，先驗證全部 SHA256，再移除該月份的 checkpoint。單次 20 次請求為建議的短批次控制用量，不是 API 官方配額；若來源拒絕或限流，保留錯誤並停止，不繞過。實際採集速度由來源反應及 Colab 免費執行時長決定，不保證一輪完成兩年。**尚未結束的月份不封存**，避免當月早期資料被誤標完整。

Drive 範例結構：

```text
janusChatGPT/資料源/
  _control/universe-r1.json              # 這個 revision 的現行公司名冊/來源摘要
  2025-01/
    ohlcv-r1.csv.gz                       # 該月兩市場所有合格股票行情
    universe-r1.csv                       # TWSE/TPEx 名冊快照
    quality-r1.json                       # PROBE、涵蓋率與已知缺口
    manifest-r1.json                      # 各檔 SHA256、來源日期/證據
  2025-02/
    ...
```

這是**第一階段 OHLCV**，其他因子在同月份資料夾依資料集補檔；不應把未取得的財報、法人、事件硬補零。單月已封存檔不能無聲覆蓋；資料修訂要用 `r2` 並保存 manifest hash。**目前公司名冊不含歷史已下市股票**，此版標記 `historical_survivorship=CURRENT_MASTER_ONLY`、`historical_pit=NOT_VERIFIED`，不是完整 PIT 母體；不可因此把 70% 全市場門檻或模型上線宣稱 PASS。來源網站使用規範、內容保存與 ML 訓練授權仍須逐一遵守。

## 3. 直接讀每月資料夾跑 Risk OOS 試點

```bash
!python janus-omniforge/research/colab/run_risk_folder_pilot.py \
  --cutoff 2026-03-31 --result '/content/drive/MyDrive/給ai專用/janusChatGPT/資料源/risk-r1-oos.json' \
  /content/drive/MyDrive/給ai專用/janusChatGPT/資料源/2025-*/ \
  /content/drive/MyDrive/給ai專用/janusChatGPT/資料源/2026-*/
```

Risk 資料讀取器現在依每月 `manifest`／`quality`／原始 OHLCV 與名冊交叉驗證，按上市普通股 TWSE ≥90%、上櫃普通股 TPEx ≥70%（月度股票數與交易日有效股票筆數兩項皆達標）決定是否進入研究；缺日不可填零。這是現行普通股名冊下的 **PROBE 研究准入**，不改寫不可變的 `r1`、不補造歷史下市股、不代表 PIT 認證或模型 promotion。

在同一 revision 的月份資料夾中只可有一個 `manifest-rN.json`；新增 r2 並存時，執行前先選定 revision 或另行指定目錄清單。Risk 仍以歷史20日波動 baseline 對 Ridge challenger，採成熟標籤、cutoff 分割及 OOS，不會自動上線／回寫正式 Janus。已於 2026-10-21 在研究執行環境用 Drive 21 個 r1 月檔真實完成一次 single-cutoff OOS 與四段 walk-forward 診斷，詳見 [研究收據](../../doc/archive/d07-risk-oos-real-2026-10-21.md)；以上並非 Colab console 收據、CI PASS 或可發布證明。新版 CLI 也輸出兩市場逐月/逐市場 baseline vs Ridge 指標、未調整價格單日 >35% 變動窗口的敏感度（不是官方公司行動認證）、四段固定 cutoff 診斷、來源 hash 與 `publication_allowed=false`。

本地：`PYTHONPATH=. python -m pytest -q tests/test_collect_tw_equities.py tests/test_research_risk_pilot.py`。
### 3A. Risk v1（八因子）與 v0 相同樣本 OOS

已用真實 21 個月 r1 月檔在 ChatGPT Python 研究環境做 v0／v1 對照，見[2026-10-22研究收據](../../doc/archive/d07-risk-v1-ohlcv-oos-2026-10-22.md)。**Colab 尚需執行同一最新版程式重跑，研究環境數字不能代替 Colab 驗收。**

新版本只加三個既有 OHLCV 衍生因子：`atr14_pct`（14日ATR／close）、`abs_overnight_gap5`、`log_turnover20`。原五因子保留為 v0，三種方法（Rolling20／v0／v1）必須用**完全相同的成熟標籤與有效股票日期**公平比較；資料缺日不補造，排除未驗證的極端價差窗口做敏感度情境。市場指數／產業／公司行動在本批r1尚未具備正式資料證據，**不能冒充已加入模型**。

在 Colab 掛載 Drive、更新 GitHub 後執行：

```bash
!git -C /content/janus-omniforge pull --ff-only origin main
!cd /content/janus-omniforge && python -m pytest -q tests/test_risk_v1.py tests/test_research_risk_pilot.py tests/test_collect_tw_equities.py
!python /content/janus-omniforge/research/colab/run_risk_v1_comparison.py \
  --cutoff 2026-03-31 \
  --result '/content/drive/MyDrive/給ai專用/janusChatGPT/資料源/risk-v1-comparison.json' \
  /content/drive/MyDrive/給ai專用/janusChatGPT/資料源/2025-*/ \
  /content/drive/MyDrive/給ai專用/janusChatGPT/資料源/2026-*/
```

輸出包含 source hashes、分市場／分月指標、四段固定 cutoff 診斷、label maturity、`publication_allowed=false`；**不是模型 bundle**，GCS 上傳／正式 Risk 切版都不在這一步。舊版研究結果保留，不覆寫。

## 4. 新版模型與每日窗口
研究月檔與每日推論窗口不同；一個20交易日特徵可能跨兩個月份，60/120日需更早歷史。每日更新X並推論，不等於每日重訓。
正式建模規格：[五角色模型/X/Y](../../doc/spec/specialist-engines.md)、[清洗/時間/成熟標籤](../../doc/spec/model-feature-time-contract.md)、[D07 AI卡](../../doc/execution-cards/d07-specialist-b9-oos.md)。
本 README 的命令是 Risk 研究試點；Risk 官方市場交易日對齊、四段 OOS 診斷與研究准入已加入 GitHub，其他角色的 feature/multi-fold/notebook 仍依 D07 開發。risk_pilot.py的舊ZIP CLI仍在程式中，正式操作使用本頁run_risk_folder_pilot.py；後續D07先核相容測試再移除無現役引用的舊CLI。


## 5. 完整開發與模型發布流程
[模型生命週期](../../doc/spec/model-lifecycle.md)列五角色建議資料量、採集/清洗/貼標/訓練/測試/封裝/發布；[AI操作卡](../../doc/execution-cards/d07-model-lifecycle.md)含現有可執行命令及未來exporter完成後的候選上傳範例。
目前 Drive 已實收並封存 2025-01～2026-09 共21個月 r1；延伸到2025以前先補對應交易日曆、來源支援和歷史普通股母體。新增pipeline/五角色notebook/模型bundle/匯入尚待D07實作，不能直接把示範當現成工具。
GCS只收模型業務candidate；Janus受控驗證、shadow與registry啟用才算發布。正式每日推論由既有Controller/Mart運作，不需Colab每天開機；每月評估後才人工回Colab決定重訓。

