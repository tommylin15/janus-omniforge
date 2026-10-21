# D07-PRE｜Colab 原生台股歷史資料採集（唯一正式研究入口）

2026-10-20：新研究路徑為 **官方 TWSE／TPEx → Colab Python → 私有 Drive 每月資料夾 → Colab 五分析師**。GAS／GAS Loader 已退役，不需要 GAS MCP、Apps Script API 或 GCP Job。Colab MCP 可用時可作選配操控介面，**不是**採集或訓練前置條件；目前 ChatGPT 無已連線的 Colab MCP，尚無 Colab 真實執行收據。

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

在同一 revision 的月份資料夾中只可有一個 `manifest-rN.json`；新增 r2 並存時，執行前先選定 revision 或另行指定目錄清單。Risk 仍以歷史20日波動 baseline 對 Ridge challenger，採成熟標籤、cutoff 分割及 OOS，不會自動上線／回寫正式 Janus。模型有效性與真實收據需由 Colab 實跑產生；GitHub 的 fixture tests 只證明解析與封存控制。

本地：`PYTHONPATH=. python -m pytest -q tests/test_collect_tw_equities.py tests/test_research_risk_pilot.py`。
## 4. 新版模型與每日窗口
研究月檔與每日推論窗口不同；一個20交易日特徵可能跨兩個月份，60/120日需更早歷史。每日更新X並推論，不等於每日重訓。
正式建模規格：[五角色模型/X/Y](../../doc/spec/specialist-engines.md)、[清洗/時間/成熟標籤](../../doc/spec/model-feature-time-contract.md)、[D07 AI卡](../../doc/execution-cards/d07-specialist-b9-oos.md)。
本README命令仍是目前Risk研究試點；新版feature/多fold/其他模型需依D07實作，不宣稱已有。risk_pilot.py的舊ZIP CLI仍在程式中，正式操作使用本頁run_risk_folder_pilot.py；後續D07先核相容測試再移除無現役引用的舊CLI。


## 5. 完整開發與模型發布流程
[模型生命週期](../../doc/spec/model-lifecycle.md)列五角色建議資料量、採集/清洗/貼標/訓練/測試/封裝/發布；[AI操作卡](../../doc/execution-cards/d07-model-lifecycle.md)含現有可執行命令及未來exporter完成後的候選上傳範例。
目前命令窗口2025-01～2026-09是21個月，不等已收齊；延伸到2025以前先補對應交易日曆、來源支援和歷史普通股母體。新增pipeline/五角色notebook/模型bundle/匯入尚待D07實作，不能直接把示範當現成工具。
GCS只收模型業務candidate；Janus受控驗證、shadow與registry啟用才算發布。正式每日推論由既有Controller/Mart運作，不需Colab每天開機；每月評估後才人工回Colab決定重訓。

