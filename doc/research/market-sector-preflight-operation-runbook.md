> **2026-10-24 政策更新**：研究數字與歷史結論保留；本文舊有逐來源／全歷史 PIT 補證、精確時間校準及新前瞻成熟等待不再是工作或發布前置。取消例行稽核，依 [研究精簡政策](../spec/research-simplification.md) 按需評估；不把取消視為 PASS。

# TWSE／TPEx 大盤與產業研究資料包｜一次全量 Preflight SOP

> **2026-10-23 使用者變更：停止「逐月執行、逐月交班」模式。** 現行四模型研究資料 Preflight 以 [Drive-first 全量主 SOP](four-model-research-package-preflight-runbook.md) 為唯一執行入口；**市場／產業為其中的關聯輸入驗證項**。本文件保留市場專用的機械 gate 與獨立重跑命令。仍屬操作規格，不是 full-run 完成證據。

## 1. 本次範圍

- Drive 白名單 `janusChatGPT`；實際 Colab mount `/content/drive/MyDrive/給ai專用/janusChatGPT`，不得誤用 `個人用`。
- 研究市場資料源 `資料源/大盤產業_免費來源_2025H1_試跑`，四類 `twse_market`、`tpex_market`、`twse_sector`、`tpex_sector`，一次檢查 **2025-01～2026-09** 全期。
- 先前 Drive 導覽基準：四來源各 21 月、共 84 月來源資料夾；其中 `twse_sector` 是 **422 個日分區**，其他三來源 63 個月分區；預期合計 **485 partition**、每分區 receipt/raw/normalized 三檔，約 **1,455 必要檔**。這是**待查的基準**，不是 bytes 實際驗收 PASS。資料夾雖叫 `2025H1`，並不代表只收半年。
- 存留的 `error_latest.json` 只表示歷史失敗；不能代替更新的 VERIFIED receipt，也不應刪除。
- 現有 CLI `research/chatgpt/market_sector_package_preflight.py` 支援一次掃描完整 start/end 範圍，**不需要逐月呼叫 21 次，也不需另寫 21 組 checkpoint 才可啟動**。

## 2. 一次性全量操作

**整體四模型 Phase 1 優先執行 [主 SOP](four-model-research-package-preflight-runbook.md) 的單個 Colab cell**；該 cell 先固定 Drive `canonical/CURRENT.json` 與其全部五類 Parquet，再執行下面的市場全期命令，不需要任何月份人工停頓。

若只需要針對市場包單獨重跑，先於掛載 Drive 的 Python／Colab 執行環境取得 GitHub `main`，完成現行回歸測試，從 repo 根執行：

```bash
set -u
ROOT="/content/drive/MyDrive/給ai專用/janusChatGPT"
SOURCE="$ROOT/資料源/大盤產業_免費來源_2025H1_試跑"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$ROOT/資料源/JanusDataset_v3_202610/reports/market_sector_preflight_v1/full/$STAMP"
mkdir -p "$OUT"
git rev-parse HEAD > "$OUT/git_commit.txt"
python research/chatgpt/market_sector_package_preflight.py \
  --root "$SOURCE" --start-month 2025-01 --end-month 2026-09 \
  --output "$OUT" > "$OUT/console.log" 2>&1
RC=$?
echo "$RC" > "$OUT/exit_code.txt"
echo "Full-market-sector Preflight exit=$RC reports=$OUT"
```

一個 run ID 覆蓋所有來源／所有分區。遇到個別日期錯誤仍收集其它來源的 issues，**不要在 2025-01 後停止或等待下一個人工指令**。環境中斷則標 ERROR，不能當資料缺失；保留舊輸出，重跑使用新的 run ID 或沿可靠已驗 digest 續做。

## 3. 市場專用機械 Gate

| Gate | 必須驗證的內容 | 判定 |
| --- | --- | --- |
| G01 結構 | 21 月 × 4 來源、TWSE sector 日分區、每分區 receipt | 缺漏 BLOCKED |
| G02 receipt | `status=VERIFIED`、正確來源／期別、`RESEARCH_ONLY`、HTTPS URL、取得時間 | 不符 BLOCKED |
| G03 bytes / SHA | raw / normalized 的真實 bytes SHA256、receipt checksum、檔名與 receipt 一致 | 不符 BLOCKED |
| G04 資料格式 | normalized JSON list、trade_date、market、index_id、正數有限價格 | 不符 BLOCKED |
| G05 OHLC | 大盤 index ID TAIEX/TPEX；`low <= open/close <= high`；產業指數價格／報酬分類不得混用 | 不符 BLOCKED |
| G06 主鍵/rows | `(trade_date,index_id)` 唯一、receipt rows/date bounds 正確，產業至少 10 指數／日 | 不符 BLOCKED |
| G07 內部日曆 | TWSE 大盤 vs TWSE 產業、TPEx 大盤 vs TPEx 產業逐月日期集合相同；大盤每月10–25交易日 | 不符 BLOCKED |
| G08 外部日曆 | 各市場有**獨立**可信的官方／可稽核交易日曆、休市補班基準 | **CLI 未自動化；PENDING** |
| G09 PIT/授權 | 實際來源允許資料取得、保存、研究或模型使用；不可用 fetched_at 冒充 first-published | **另外驗證** |
| G10 歷史產業對照 | `market+symbol+valid_from/to+published_at`、`industry_id -> index_id` crosswalk | **另外驗證** |
| G11 可追溯 | 固定 Git commit SHA、所有 receipt/raw/normalized digest、整輪 summary/issue 收據 | 缺證據 UNKNOWN |

**特別注意**：CLI 的 `verified_partitions` 是可解析 normalized 的 partition 數，**可能包含已發生 checksum 問題的 partition**；只能搭配 `status`、`issue_count=0`、所有來源 `verified_months_by_source=21`、逐檔 SHA 證據判定。TWSE sector 指數數量可能歷史變動，不可強制所有交易日永久固定 37 個。

## 4. 一次全期的結案／異常處置

以實際資料完整性、逐分區 SHA、schema、OHLC、重複鍵、同市場日期集合、報告 readback 和固定版本作 **RESEARCH_ONLY market/sector mechanical PASS** 的條件。先前預期總數 485 若不同，先調查是有漏檔、變更或基準失準，**不得為湊數直接修改數字**。

- CLI `exit=0` 且 summary PASS、`issue_count=0`、四來源月覆蓋各21，才可主張既有 CLI 的 gate PASS；再比對 485 的 baseline 和必要檔案清單，保存固定 digest。
- CLI `exit=2` 是 BLOCKED；讀 `preflight_issues.csv` 列明 source、period、code、path，**不用重新抓所有月份**，待獨立授權的定向修復版本後重驗。
- 掛載、讀檔權限、Python dependencies、中途同步失敗是 ERROR/INCOMPLETE，不能當資料壞掉。
- `independent_calendar`、`source_use_authorization`、`historical_pit`、`industry_membership_crosswalk` 各自保留未驗狀態，不因資料機械 PASS 自動升級。

輸出：`preflight_summary.json`、`preflight_issues.csv`、`console.log`、`exit_code.txt`、`git_commit.txt`；在四模型總 Preflight 另生成 `preflight_inventory.json`、`preflight_quality/research_verify`、`model_feature_coverage.json`、`checkpoint.json`。只寫新的 reports 目錄，原 raw/normalized/receipt 和 canonical CURRENT 全程唯讀。

## 5. 本輪實際證據與限制

2026-10-23 先前 Google Drive inventory 為 84 月來源目錄／422 日分區，並有 TWSE、TPEx 個別抽樣 SHA/行數驗收；[證據摘要](market-sector-data-package-preflight-2026-10-23.md)。GitHub Actions [#39938208461](https://github.com/tommylin15/janus-omniforge/actions/runs/39938208461) selective tests success 只證明測試程式，不等於 485 個 partition 完整實測。這份 SOP 的一次全量執行 **仍需可掛載完整 Drive 資料的 runtime**；僅能列檔的 ChatGPT connector 不可假冒全量 PASS。

## 6. 禁止操作

Preflight 不補收、不清理、不刪除、不改採集器已成功的 receipt，不覆寫 canonical `CURRENT.json`、Risk ACTIVE／Registry／GCS／PG／Core／Mart，不貼標、不重訓、不 publication。遇實際問題列來源與可重跑處置，保留 checksum/provenance。四模型指定的 **34 個 X 因子席位**不是市場指數 34 種，更不是每檔 source 有值的判定門檻。
