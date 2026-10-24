# Janus 04 Valuation｜v23 有界研究整併與模型準入（2026-10-24）

## 執行結果（真實 v22 FinMind raw × 原 research release 對帳）

- 現有 frozen release：`release-0bbae8d9c1ca7d8d`；CURRENT SHA256 `0b64ac6927805fb98260121da94624d7e08ac423f0aa13b8349d4c304f0135cd`；manifest SHA256 `7b80d441efabbc307d359ea5d15cd9202ccee5e2930cf4c3cc337496c95eb542`。
- 本地已從 `janusChatGPT/模型研究/valuation/backfill_candidates/FINMIND_MIN30_HIST_V22_20261024/raw/` **實際讀回 311/311 筆 JSON**；服務回應 `status=200`，解析請求 stock_id／上市下限／實際日期／月內最後交易觀測。比對原版 `v22_valid_month_gain.csv` **311 個請求全數逐股吻合**。
- v22 來源中共有 **4,000 個股票×月份的最後實際觀測快照**，保留 PER/PBR（包括非正值）、原始 SHA；其中依 v22 指定 PE/PB 分支確實正值者 **2,672 個**（PE 2,649、PB 23），去重後交叉對帳 PASS。
- 對 1,980 檔**今日普通股候選名冊**：原正倍數月末 PE 1,134/PB 1,796 檔達 30 個；加上 v22 指定分支的正值候選後 PE **1,325**、PB **1,799**，任一分支達 30 的股票為 **1,799** 檔。此為候選月末覆蓋 **PRECHECK**，非歷史 PIT/官方月末收盤或模型認證。
- 全名冊現仍 **836 組**股票×PE/PB 分支不足 30：v22 已跑仍不足 **117**（有補但不足 75、完全無正值新增 42），其餘 **719**（低有效月歷史而先 HOLD 465、IPO/上市下限無早期月份 198、上市日期未知 44、原包完全無估值資料 12）。不自動放大 API。

## 交付資料與合併方法

這是**新的只讀 Research Sidecar Release**，**沒有改寫原版 `JanusDataset_v3_202610/canonical/release-...` Parquet**，也沒有設定 `CURRENT` 或任何 publication 狀態：

| 檔案 | 用途 |
| --- | --- |
| `output/01_valuation_v22_monthly_overlay.csv.gz` | 2,672 筆指定分支的正倍數歷史候選，含市場/股票/分支/實際日期/真值/來源SHA |
| `output/01b_all_actual_prehistory_finmind_last_observations.csv.gz` | 4,000 個實際月內最後觀測，帶完整 PE/PB 原值（包括 0） |
| `output/02_recalculated_PE_PB_30month_coverage.csv` | 1,980檔×2分支、補收前後完整覆蓋計算 |
| `output/03_remaining_836_stock_branch_review.csv` | 836分支缺額與明確 HOLD／已補仍不足原因 |
| `output/04_v22_source_raw_provenance.csv` | 每個 v22 任務的 raw SHA256、檔案路徑、股票與日期範圍 |
| `output/05_model_training_gate.json` | 研究 XGBoost 阻擋證據 |
| `output/00_summary.json` | 原 release hash、replayer 的 SHA 對帳、覆蓋數與輸出hash |
| `input/raw/*.json` | 311份直接從 Drive 讀回的不可變 HTTP 原始回應（便於重跑） |
| `input/evidence/*` | 前次 P0/P1 財務欄位與 PIT 稽核結果 |

**如何合併取用**：既有 36 個估值 Parquet 仍以原 release/manifest 唯讀載入；新增的前歷史來源月末是 `2023-10` **以前**，因此可依 `market+symbol+trade_date` 與原估值資料建立 Research-only Union View，禁止與原月份重疊。對未確定實際月末交易日的 FinMind 紀錄，維持 `official_last_market_session_verified=false`，不能當作正式模型 X/Y；不把只有月內早期觀測的資料假定為月底。日後物理 Parquet 建立須用具備 Parquet loader 的環境，保留 source hash，不修改舊 release。

## 模型准入實測：`BLOCKED_NOT_TRAINED`

現役 `research/chatgpt/janus_precision.py` 的 Valuation 04 X 五因子為 `roe/debt_ratio/log_total_assets/revenue_yoy/market_code`。前三者與 revenue 需要可核實財務欄位及公布日、cohort。P0/P1 財報實測 `PIT_VERIFIED=0`、`PIT_UNVERIFIED=1,181,442`、`published_at_populated=0`、19個相關因子全為 `BLOCKED`；不存在合法已驗證的五因子訓練面板，故 **未啟動 Ridge / XGBoost fit**。`publication_allowed=false`，絕不因倍數原始值足夠就謊稱模型可訓練。

`RESEARCH_NON_PIT` 可在明確標示來源口徑後另作診斷實驗，但不得將未公告財務或當期 PE/PB 目標代數組合放入 X，不能用先填/未來補值灌五因子。要正式跑五因子，最短工作是核定 FinMind financial 原始 item+單位+期間+合併範圍、取得真實月末前 `published_at`/版本、產生產業有效時點證據與交易日曆。完成後分 PE/PB 做全市場同月切分、train-only baseline/Ridge/XGBoost、獨立test與 model schema/UBJ parity。**現有資料不足，不能標模型成功。**

## 如何重跑（本套件含完整 311 個 raw，免再次呼叫 API）

```bash
python valuation_v22_integrate.py --input input --output output
python -m unittest -v test_valuation_v22_integrate.py
```

上述本地 3/3 PASS 且完整 311 筆重放，零 FinMind 請求、零 canonical 寫入。本套件僅研究資料，非新模型或現役 serving。


[完整 ZIP／重播程式／資料](https://drive.google.com/file/d/1uA61Z4zyk5SaVQU55WgwOVs753XbmN18/view)
