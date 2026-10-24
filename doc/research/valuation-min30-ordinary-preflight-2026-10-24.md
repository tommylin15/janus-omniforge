# Janus 04 Valuation｜普通股「至少30個有效月末」定向補收前盤點

更新：2026-10-24。狀態：**POLICY_UPDATED／PREFLIGHT_NOT_LIVE_VERIFIED**。研究限定，`publication_allowed=false`；FinMind 財報 API 請求數 **0**。

## 使用者最新決策（取代固定兩年補收）

不再限定新補收 2024-10～2026-09。只在**04 Valuation 研究所需的上市／上櫃一般普通股**中，按 `PE` 與 `PB` 兩研究分支**分開計算每檔 ≥30 個不同月份的真實有效月末觀測**（30 含本數）。先讀既有研究 CURRENT 的實際月末紀錄，保留 2023-10～2026-09 的36份 Parquet 及任何原已存在的更早月份，**只對不足30的 stock×branch 實際資料缺口有界往前追溯**，不得一次抓全市場、不得硬湊30或限於新近兩年。

`pe_ratio>0`／`pb_ratio>0` 是最初的月末*觀測覆蓋預篩*，需再檢查真實月末日期、財報 as-of、倍數分母、PIT、公司行動、金融/非金融適用性、普通股主檔、上市期間及來源權利才能算正式有效。0／負倍數、股票尚未上市或收入缺失不能靠重抓就假定必可變成有效月份；達不到30的分支維持 `INSUFFICIENT_HISTORY／PROBE／BLOCKED` 並附原因，不能用其他股票、連續補值、重複日或未來資訊填滿。

04 Valuation 前台估值區間情境既有**最低24有效月**是*不同*的可計算產品參數；本次30月目標專用於 **04 XGBoost／baseline 研究樣本盤點與定向補收**，不自動升級或改寫前台門檻。

## 已核實的基礎（上版歷史盤點，不是新30月合格數）

- 先前研究 CURRENT `release-0bbae8d9c1ca7d8d`、CURRENT SHA256 `0b64ac6927805fb98260121da94624d7e08ac423f0aa13b8349d4c304f0135cd`。
- 財報初篩約 1,977 股票代號；2025Q3～2026Q2 income+balance 紀錄有 1,965 檔；原2024Q4～2026Q2有98組股票×報表整季無紀錄待查。**這不是30個月有效 PE/PB 股票清冊、不是已確認一般股與 PIT、也不是現在應發的 API 請求數**。
- 研究 CURRENT manifest 提供估值 36 個月檔 2023-10～2026-09，但截至本次**未使用使用者 Colab 真實解碼全部逐股月末並核公司主檔**，故 `eligible_symbols`、`PE>=30`、`PB>=30` 與真正資料需補數維持 UNKNOWN。

## 新版盤點 Colab 與輸出

**[Drive 新版 ZIP](https://drive.google.com/file/d/1F0NgMrUBHqoet0TraEPLMOX-F1SYZ0MP/view)**，存於唯一授權根 `janusChatGPT/模型研究/valuation`，內含可直接執行的 `20_Valuation_普通股_30有效月末_定向補收前盤點.ipynb`、README，以及有 `archive_` 前綴的舊初盤1,977／98 CSV（供追溯，不能當新版結果）。

Colab 掛載 `/content/drive/MyDrive/給ai專用/janusChatGPT`，固定 CURRENT/manifest bytes SHA，取研究窗口 `as_of` 前最多60月中真正已存在的 valuation Parquet；官方當前 TWSE／TPEx 公司主檔只作**普通股候選**，不是歷史上市 PIT。各月真值去重後，按 `symbol×PE/PB` 輸出：
- `01_普通股估值與季報逐股核對.csv`：已有正 PE/PB 有效月份預篩、距30缺額；
- `02_PE_PB_30有效月末缺口逐月查核.csv`：沒有月份行／倍數空值／經濟非正分開；
- `03_30有效月末_股票分支短缺清單.csv`：需多少、是否須追溯早於研究包月份；
- `04_財報無紀錄_相關性待核查.csv`：依已有財報季度查核整份缺季，但**不等於FinMind請求**；
- `00_summary.json`：總結、限制、request=0。

`RUN_FETCH=False`；Notebook **不呼叫 FinMind 財報 API**。完成 Colab 的實際 master、逐月 val、季度資料讀回且核實缺口後，才另外編出有界 FinMind 收集計畫：只限研究必要的 `stock×dataset×實缺時段`，紀錄 token 額度、重試、raw bytes SHA、provenance／rights／PIT 缺口。FinMind 並不能證明舊首次公告版本。

## 驗證與界線

本地 Python syntax PASS、最小模擬 33月／2股 PE/PB 正值與非正值分支／月份去重／零 API／輸出報表 PASS；**這是模擬測試，不是 Colab+真實 Parquet／官方主檔驗收**。不變更 canonical CURRENT、Risk ACTIVE、Registry、現役 Mart/API；無新付費服務。

本頁覆蓋同日先前 [固定兩年盤點](valuation-2y-ordinary-preflight-2026-10-24.md) 的補收範圍與新的盤點程式；原先兩年 ZIP 已以 `ARCHIVED_已取代` 更名，保留歷史原樣。
