# TWSE／TPEx 大盤與產業資料包 Preflight｜完整操作 SOP

> 文件狀態：**READY_FOR_OPERATOR／尚未執行本 SOP 正式驗證**（2026-10-23）。本文件是交給使用者或另一個 AI 執行的 runbook，不是執行收據。先讀 [既有盤點與抽樣證據](market-sector-data-package-preflight-2026-10-23.md)、[PROJECT_RULES](../PROJECT_RULES.md)。**本次只編寫 SOP，不執行資料檢驗、不更改原始資料、模型或部署。**

## 0. 目的、邊界與一次完成定義

本任務僅對已採集的 **2025-01～2026-09，21 個月份 × TWSE/TPEx 兩市場 × 大盤/產業兩類**研究資料，建立可重跑、可中斷、可稽核的全量機械 Preflight，確認是否可封存為 **RESEARCH_ONLY 指數資料包**。不執行補收、重新貼標、四模型訓練、任何 canonical Core/Mart 寫入、Risk ACTIVE 變更、GCP 部署或對外 publication。

現有 Drive 導覽盤點：四來源各 21 個月份目錄，合計 **84 月份目錄**；`twse_sector` 另有 **422 個交易日日目錄**。需要實際核對的 **partition 為 485 個**（其他三來源各 21 個月 partition，合計 63；TWSE sector 為 422 個日 partition），**不是 84 個驗證單位**。每個 partition 的必要檔案：`receipt.json`、`raw-<sha256>.json`、`normalized-<sha256>.json`；按既有盤點推算 **1,455 個必要檔案**，此數字為預期數／非已完成 bytes 驗證收據。過去的 `error_latest.json` 可以留存，不可用它取代當前 verified receipt 或任意刪掉。

「完成」必須同時滿足：
1. 每月一份可讀 `preflight_summary.json`、`preflight_issues.csv`、`checkpoint.json`；21 個月均已完成正式驗證且機械 gate PASS。
2. 在相同固定來源版本下，**2025-01～2026-09 全範圍**原 CLI 再跑一次，`status=PASS`、`issue_count=0`、`verified_months_by_source` 四項均為 21，檢查分區與來源總量是否符合實際完整基準。
3. 全量原始檔與標準化檔的 SHA256、receipt／schema、主鍵、OHLC、價格指數分類、同市場交易日集合均過；必要的獨立交易日檢查與授權核對**分別留狀態與證據**。
4. 生成固定研究版輸入清單 `frozen_manifest.json` 及其 SHA256、完整的 exception/修復讀回、執行程式 Git commit SHA 與時間戳；封存後不得無聲變更。
5. 僅宣告 **market/sector research package mechanical preflight PASS**；歷史 PIT、股票→產業對照、資料用途授權、四模型準入與 publication 仍是**另外的 gate**，不得隨資料包 PASS 自動提升。

## 1. 權威來源、目錄與禁止操作

- GitHub 唯一現役 repo：`tommylin15/janus-omniforge`，branch `main`。
- 唯一允許的 Drive 根：`janusChatGPT`；Colab Drive 掛載預期位置 **`/content/drive/MyDrive/給ai專用/janusChatGPT`**，不得使用舊的 `個人用`。
- 原始資料包：`資料源/大盤產業_免費來源_2025H1_試跑`；[Drive 目錄](https://drive.google.com/drive/folders/1XozCP8UGKqh_UeL87YxavHTuMYhHyx8t)。資料夾名稱保有 `2025H1` 歷史名稱，但涵蓋區間是 2025-01～2026-09；**不得因名稱而改動檔案路徑**。
- 建議獨立輸出位置：`資料源/JanusDataset_v3_202610/reports/market_sector_preflight_v1/`。產物不得寫在上述原始資料包之內。
- 已提交的唯讀驗證 CLI：[market_sector_package_preflight.py](../../research/chatgpt/market_sector_package_preflight.py)。
- 離線回歸測試：[test_market_sector_package_preflight.py](../../tests/test_market_sector_package_preflight.py)。
- 現有資料形態：
  ```text
  大盤產業_免費來源_2025H1_試跑/
    twse_market/YYYY-MM/{receipt.json, raw-<sha>.json, normalized-<sha>.json}
    tpex_market/YYYY-MM/{receipt.json, raw-<sha>.json, normalized-<sha>.json}
    tpex_sector/YYYY-MM/{receipt.json, raw-<sha>.json, normalized-<sha>.json}
    twse_sector/YYYY-MM/YYYY-MM-DD/{receipt.json, raw-<sha>.json, normalized-<sha>.json}
  ```
- **禁止**修改／覆蓋／移動／刪除原始 `receipt.json`、`raw`、`normalized` 或成功月分區；禁止未經有界診斷直接重抓全部資料；禁止更新 `canonical/CURRENT.json`、Core／Mart、模型 Registry 或 promotion。
- 如驗證環境只有 Google Drive「資料夾清單」，沒有可對全部 JSON 位元組執行 Python/SHA 的檔案系統，**不要宣告全量 PASS**。應於有 Drive mount 或完整唯讀同步副本的 Python 環境執行。本 SOP 由操作者選擇 Google Colab（**只用來執行驗證，不收檔**）或等價的本機 Linux／Work 沙盒；需記錄使用的環境及其資料根路徑。

## 2. 開始前的環境檢查（只執行一次）

以下示範使用已掛載 Drive 的 Colab；若由另一個 AI 在其他可存取完整檔案的 Python 環境執行，替換 `ROOT` 即可。

1. 在 Colab 掛載使用者已授權 Google Drive（如 `from google.colab import drive; drive.mount("/content/drive")`），確認目錄存在與可讀，**不須重新收檔**。
2. 取得 GitHub **main** 的最新版本（在 Colab 另開 shell/命令格執行）：
   ```bash
   cd /content
   git clone --branch main https://github.com/tommylin15/janus-omniforge.git
   cd /content/janus-omniforge
   git rev-parse HEAD
   ```
   已存在 repo 則執行 `git fetch origin main && git checkout main && git pull --ff-only origin main`，**不可強制覆寫現有本機工作**。每批沿用同一個已記錄 commit；若程式更新需新開驗證輪次，不能混同一份 PASS。
3. 核對資料位置：
   ```bash
   ROOT="/content/drive/MyDrive/給ai專用/janusChatGPT"
   SOURCE="$ROOT/資料源/大盤產業_免費來源_2025H1_試跑"
   REPORT_BASE="$ROOT/資料源/JanusDataset_v3_202610/reports/market_sector_preflight_v1"
   test -d "$SOURCE/twse_market" && test -d "$SOURCE/tpex_market" && \
     test -d "$SOURCE/twse_sector" && test -d "$SOURCE/tpex_sector"
   echo "四個來源目錄存在；只代表掛載與定位成功"
   ```
4. 在**不讀寫真實資料**的條件下先執行現有回歸測試：
   ```bash
   python -m unittest discover -s tests -p 'test_market_sector_package_preflight.py' -v
   ```
   記錄 Python 版本、UTC 執行時間、Git commit SHA、三項測試的實際結果。**測試 PASS ≠ 真實資料 PASS**。若測試 fail，停止進入真實資料驗證，先修測試／程式並在 main 留版本記錄。
5. 建立獨立的 `REPORT_BASE` 報告目錄。所有結果先寫新子資料夾，不直接覆寫已成功報告。

## 3. 驗證項目與已實作／仍需人工核對的分界

| Gate | 內容 | 目前 CLI | 若不符的處置 |
| --- | --- | --- | --- |
| G01 結構 | 四來源、每月目錄；TWSE 產業交易日日分區及每分區 receipt | 有 | BLOCKED，列明 source/month/date |
| G02 收據 | `VERIFIED`、source/period、`RESEARCH_ONLY`、HTTPS host、取得時間 | 有（取得時間僅驗有值） | BLOCKED，核對 receipt 與實際來源 |
| G03 原始可信度 | raw/normalized 檔名、receipt 雙 SHA256、實際 bytes SHA256 | 有 | BLOCKED，不自動覆蓋成功檔 |
| G04 normalized schema | JSON list、`trade_date`、`market`、`index_id`、數值有效 | 有 | BLOCKED，依實際 row/path 報告 |
| G05 行情合理性 | 大盤唯一 TAIEX/TPEX、OHLC `low ≤ open/close ≤ high`；產業 `sector_price_index`、close 正值 | 有 | BLOCKED，禁止以填補虛值修正 |
| G06 唯一鍵與筆數 | 重複 (trade_date,index_id)、receipt rows 與日期上下界、每交易日大盤 1 筆／產業至少 10 筆 | 有 | BLOCKED，逐日定位 |
| G07 內部日曆 | 同一市場大盤 vs 產業日期集合一致；10–25 個市場交易日/月 | 有 | BLOCKED，但**雙方同日缺漏不一定被發現** |
| G08 外部交易日基準 | 每市場獨立官方日曆／獨立可信來源交叉核對，區分兩市場差異、補班及休市 | **未在目前 CLI 自動化** | 標 `PENDING_INDEPENDENT_CALENDAR`；不可冒稱已獨立驗過 |
| G09 授權／PIT | 按實際網址與用途留授權及歷史可用時間，不能把 fetched_at 當 published_at | **非本 CLI gate** | 獨立清單列 `NOT_VERIFIED/PASS/BLOCKED`，不自動賦予 ML 使用權 |
| G10 個股產業 mapping | 有效日期版本化 `symbol → industry_id → index_id`、上市／上櫃、產業編碼與指數名稱跨版映射 | **非本 CLI gate** | 下游產業 X 持續 BLOCKED，不阻止純市場資料包機械封存 |
| G11 重現性 | 固定 code SHA、各檔 raw/normalized/receipt digest、報告 SHA 與 frozen manifest | CLI 有 summary，但**不直接生成獨立 frozen_manifest.json** | 操作者依第 7 節另製 manifest、覆核一致性 |

注意：現有 `verified_partitions` 在程式內代表「成功解出可分析的 normalized partition 數」，**即使 partition 另有 checksum 等 issues 仍可能被計入**。因此不能單看此數字宣稱通過；以 `status`、`issue_count`、`issues`、每來源覆蓋與 SHA 檢查完整判定。TWSE sector 每日指數種類不保證永遠完全同數，須保留各月變化與官方 schema 變動證據，不隨意假定 37 種永恆不變；TPEx sample 19 種亦同。

## 4. 每次只驗證一個月份（21 小批，可隨時停止）

建議順序為 `2025-01, 2025-02, ..., 2026-09`。一個月份同時涵蓋四來源，且 TWSE 產業只驗該月交易日日分區；不按四來源拆成互不對齊的驗收結論。**一個月執行→寫 checkpoint→檢視缺口→停下／交接→下月**；不要自動跑完 21 個月。

於 `/content/janus-omniforge` 執行以下 Bash；**每批僅修改 `MONTH`**。若在 Colab 請放在 `%%bash` 程式格。每次重跑使用新 `RUN_ID`，舊收據保留：

```bash
set -u
cd /content/janus-omniforge
ROOT="/content/drive/MyDrive/給ai專用/janusChatGPT"
SOURCE="$ROOT/資料源/大盤產業_免費來源_2025H1_試跑"
REPORT_BASE="$ROOT/資料源/JanusDataset_v3_202610/reports/market_sector_preflight_v1"
MONTH="2025-01"                           # 每一批只改這一行
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$REPORT_BASE/batches/$MONTH/$RUN_ID"
mkdir -p "$OUT"
git rev-parse HEAD > "$OUT/git_commit.txt"
python --version > "$OUT/python_version.txt" 2>&1
date -u +%FT%TZ > "$OUT/start_utc.txt"
python research/chatgpt/market_sector_package_preflight.py \
  --root "$SOURCE" --start-month "$MONTH" --end-month "$MONTH" \
  --output "$OUT" > "$OUT/console.log" 2>&1
RC=$?
printf '%s\n' "$RC" > "$OUT/exit_code.txt"
date -u +%FT%TZ > "$OUT/end_utc.txt"
python - "$OUT" "$MONTH" "$RC" <<'PY'
import hashlib, json, sys
from pathlib import Path
out, month, rc = Path(sys.argv[1]), sys.argv[2], int(sys.argv[3])
p = out / "preflight_summary.json"
report = json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
status = "PASS" if rc == 0 and report and report["status"] == "PASS" and report["issue_count"] == 0 else ("BLOCKED" if rc == 2 and report else "ERROR")
checkpoint = {
    "month": month, "status": status, "exit_code": rc,
    "git_commit": (out/"git_commit.txt").read_text().strip(),
    "summary_sha256": hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None,
    "partition_count_observed": report.get("verified_partitions") if report else None,
    "issues": report.get("issue_count") if report else None,
    "report_path": str(out),
    "note": "partition_count_observed 不是嚴格驗證通過數，必須看 issue_count"
}
(out / "checkpoint.json").write_text(json.dumps(checkpoint, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
print(json.dumps(checkpoint, ensure_ascii=False, indent=2))
PY
```

**判斷**：
- `exit_code=0` 且 summary `PASS`、`issue_count=0`：該月 **CLI 既有機械 gate PASS**；另記獨立日曆及授權狀態，勿混入。
- `exit_code=2`：該月 **BLOCKED**，讀 `preflight_issues.csv`；可先保留問題並進下一月，不要將此月列完成 PASS。
- 其他退出碼、找不到 report、Drive 掛載失敗：**ERROR／未完成驗證**，不得當成資料缺漏。
- 一個月完整紀錄須含四來源的各 1 月 `verified_months_by_source`、分區數（TWSE 產業日分區浮動）、`issues`、三個報告、commit SHA 與輸出目錄；CLI PASS 但外部日曆還沒核對時可記 `CLI_PASS / CALENDAR_PENDING`。

若操作者不使用 Colab，將 `cd`、`ROOT` 換成其已獲權存取的完整唯讀本地資料鏡像。驗證時應確保鏡像是同一版資料，不可混入同步中途的新檔；若檔案不齊應先確認同步完成，勿把連線未下載當作原始資料不存在。

## 5. 每批結束必須留下的進度（避免 AI 用量中斷）

一份 `checkpoint.json` 只對**該次 run／該月份**有效；不可僅口頭回報。更新（或由執行者建立）`REPORT_BASE/progress.md` 或 `progress.csv` **單一總進度索引**，每月至少記：

`month,cli_status,independent_calendar_status,authorization_status,partition_count_observed,issue_count,run_id,git_commit,report_uri,summary_sha256,reviewer,updated_at_utc`。

多次重跑同一月份時，索引指向經覆核的最新有效 run，舊 checkpoint 仍保留。每次回覆使用者或另一個 AI **只報這一個月的實測結論／問題代碼／報告位置／下月號**，不承諾未驗證的後續月份。交班前讀回 report、checkpoint 和單一索引；如 Drive 複製或上傳尚未讀回，不算持久化成功。

推薦月份批次：`2025-01` 至 `2025-12` 依序，再 `2026-01` 至 `2026-09`，共 21 次。已 `CLI_PASS` 且 digest/程式版本未變者不用重跑；BLOCKED 月份定向修復後保留舊問題收據，用新 `RUN_ID` 重新驗證並更新索引。

## 6. 出現異常時的處理決策樹

1. **工具錯誤、Drive 401/403、檔案尚未同步／run 中斷** → 標 `ERROR`／`INCOMPLETE`；先確認權限、完整掛載及重試單月；不要把連線錯誤記成市場資料無值。
2. **`MISSING_MONTH/MISSING_DAILY_PARTITIONS/MISSING_RECEIPT/MISSING_PAYLOAD`** → 檢查原始 Drive 實際檔案與同源成功的其他月；登錄確定缺口的來源、期別及 path。只有實際缺收才交給既有採集器做**定向補收**，不可在 preflight 工具自行產生假行。
3. **`PAYLOAD_SHA_MISMATCH`、`BAD_CHECKSUM_DECLARATION`、`RECEIPT_IDENTITY`** → 暫停該月 release；保留異常 raw／normalized／receipt 及 SHA 證據，不把檔名改成期望 hash、不自行改 receipt；查採集 checkpoint／版本及檔案損壞原因，按授權的 versioned 修復後重驗。
4. **`INVALID_NORMALIZED_JSON`、`DATE_FORMAT`、`INVALID_DATE`、`PERIOD_MISMATCH`、`MARKET_MISMATCH`、`MISSING_INDEX_ID`、`DUPLICATE_KEY`、`ROW_COUNT_MISMATCH`** → 檢查 parser/schema drift、時區／民國西元轉換、重複資料及原始回應。不可改數字或臆造補值。
5. **`BAD_CLOSE/OHLC_INVALID/INDEX_TYPE/MARKET_INDEX_ID/SECTOR_BREADTH_LOW/MARKET_ROWS_PER_DAY`** → 對照原始交易所 payload；價格指數／報酬指數不可混淆，逐檔定向排錯。
6. **`TRADING_DAY_SET_MISMATCH`、`SESSION_COUNT_OUT_OF_RANGE`** → 分別以 TWSE 與 TPEx 基準查缺日。兩市場不強迫日期相同；不能以週一至週五、另一市場或推測的休市日造數。原始月資料雙方日期一致仍須另做獨立來源基準核查。
7. **舊 `error_latest.json` 與新 `VERIFIED` 並存** → 根據 receipt、payload SHA、時間與實際資料判定；保留舊錯誤以便稽核，不以舊 error 自動否決新 verified，也不忽略新 verified 本身的錯誤。
8. **授權條款／產業歷史對應不明** → 保留 `RESEARCH_ONLY`；將授權或 crosswalk 按用途精確標 `NOT_VERIFIED/BLOCKED`，不反向把機械驗證報告改寫為已核准訓練。

對修復動作若需修改 collection script、parser、或更換資料來源，須獨立 commit、更新測試、保留原始證據及新版本檔案；這已**超出此文件編寫範圍**，由後續執行者依具體問題決定，且不可破壞既有成功資料。

## 7. 21 批完成後執行一次全量驗證與封存

**僅當 21 個月的有效 checkpoint 均為 `CLI_PASS` 且定位到同一組 code/data 版本**才執行最後全量命令。若有 BLOCKED，先清楚報缺口並停止「PASS 宣告」，可保留其他月份已驗成果。

```bash
set -u
cd /content/janus-omniforge
ROOT="/content/drive/MyDrive/給ai專用/janusChatGPT"
SOURCE="$ROOT/資料源/大盤產業_免費來源_2025H1_試跑"
REPORT_BASE="$ROOT/資料源/JanusDataset_v3_202610/reports/market_sector_preflight_v1"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
FINAL="$REPORT_BASE/final/$RUN_ID"
mkdir -p "$FINAL"
git rev-parse HEAD > "$FINAL/git_commit.txt"
python research/chatgpt/market_sector_package_preflight.py \
  --root "$SOURCE" --start-month 2025-01 --end-month 2026-09 \
  --output "$FINAL" > "$FINAL/console.log" 2>&1
RC=$?
echo "$RC" > "$FINAL/exit_code.txt"
echo "Full-run exit code: $RC"
```

接著在同一個 `%%bash` 或 Bash shell 執行以下**只寫輸出報告、不改原始資料**的清單封存命令；它依據已通過 CLI 檢驗之 `receipt.json` 及檔案 SHA 產生每 partition 的 pinned 清單，並核對總數。若驗收失敗仍可產出調查清單，但**不得以 `frozen_manifest.json` 名稱代表發布就緒**：

```bash
python - "$SOURCE" "$FINAL" <<'PY'
import hashlib, json, sys
from pathlib import Path
from datetime import datetime, timezone
root, out = Path(sys.argv[1]), Path(sys.argv[2])
summary = json.loads((out/"preflight_summary.json").read_text(encoding="utf-8"))
if summary["status"] != "PASS" or summary["issue_count"] != 0:
    raise SystemExit("full-range CLI is not PASS; do not freeze")
records = []
for part in summary["partitions"]:
    folder = root / part["path"]
    receipt_path = folder / "receipt.json"
    raw = receipt_path.read_bytes()
    receipt = json.loads(raw)
    hashes = receipt["checksums"]
    for filename, digest in hashes.items():
        actual = hashlib.sha256((folder/filename).read_bytes()).hexdigest()
        if actual != digest:
            raise SystemExit("changed since preflight: " + str(folder/filename))
    if hashlib.sha256(raw).hexdigest() != part["receipt_sha256"]:
        raise SystemExit("receipt changed since preflight: " + str(receipt_path))
    records.append({
        "source": part["source"], "period": part["period"], "path": part["path"],
        "receipt_sha256": part["receipt_sha256"],
        "raw_filename": next(n for n in hashes if n.startswith("raw-")),
        "raw_sha256": next(d for n,d in hashes.items() if n.startswith("raw-")),
        "normalized_filename": receipt["normalized"],
        "normalized_sha256": hashes[receipt["normalized"]],
        "rows": part["rows"], "trading_days": part["trading_days"],
        "index_count": part["index_count"], "source_url": receipt.get("source_url"),
        "retrieved_at_utc": receipt.get("retrieved_at_utc")
    })
if len(records) != 485:
    raise SystemExit(f"expected 485 partitions from previously observed Drive baseline; found {len(records)}; investigate and reconcile")
manifest = {
    "kind": "JANUS_MARKET_SECTOR_RESEARCH_FROZEN_INPUT",
    "status": "PREFLIGHT_MECHANICAL_PASS", "classification": "RESEARCH_ONLY",
    "publication_allowed": False,
    "git_commit": (out/"git_commit.txt").read_text().strip(),
    "created_at_utc": datetime.now(timezone.utc).isoformat(),
    "source_root": str(root), "partitions": records,
    "independent_calendar": "SEPARATE_EVIDENCE_REQUIRED",
    "source_authorization": "SEPARATE_EVIDENCE_REQUIRED",
    "industry_membership_crosswalk": "NOT_VERIFIED"
}
dst=out/"frozen_manifest.json"
dst.write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
digest=hashlib.sha256(dst.read_bytes()).hexdigest()
(out/"frozen_manifest.sha256").write_text(f"{digest}  frozen_manifest.json\n", encoding="ascii")
print("pinned partitions:", len(records), "manifest SHA256:", digest)
PY
```

覆核 `FINAL/preflight_summary.json`：`status=PASS`、`issue_count=0`、`verified_months_by_source` 四項 21、`partitions` 長度 485（若真實基準不同，先查明原因，**不能為湊數任意改掉 485 基準**）；`frozen_manifest.sha256` 與實際檔案一致；輸出均可重新讀回。封存 manifest 是資料指紋，**不是**新 canonical 資料源、也不是模型正式准入／發布授權。若在執行過程原始 Drive 檔案更動，該月與全量驗證需重新讀回。

## 8. 最終交付、驗收判定與下一階段

最後提供使用者及 GitHub（允許回寫正式驗收文件但不得覆寫本 SOP 的歷史決策）以下內容，Drive 原始報告留在單一報告目錄：

| 交付檔 | 用途 |
| --- | --- |
| `batches/YYYY-MM/<RUN_ID>/checkpoint.json` | 每次小批完成與可斷點續跑的實際收據 |
| `batches/.../preflight_summary.json`、`preflight_issues.csv`、`console.log` | 單月全來源 SHA/schema/日曆問題及 stderr |
| `progress.md` 或 `progress.csv` | 跨 AI、跨聊天唯一 21 月進度索引 |
| `final/<RUN_ID>/preflight_summary.json`、`preflight_issues.csv` | 全期間實際最終驗收收據 |
| `final/<RUN_ID>/frozen_manifest.json`、`frozen_manifest.sha256` | 研究資料包固定輸入 digest / provenance |
| `final/<RUN_ID>/acceptance.md` | 版本、執行者、範圍、機械 gate、外部日曆與授權狀態、各異常、下游限制 |

結論語意：
- `NOT_STARTED`：只有文件、未執行此 SOP 正式驗證（目前）。
- `PARTIAL`：部分月份已驗但尚未達 21/21；不可把資料夾存在性視為完成。
- `BLOCKED`：已執行月份有實際檔案／checksum／schema／日曆不符且尚未修復；可繼續其他月份，不能封存全期 PASS。
- `ERROR`：工具／權限／同步／執行中斷，沒有完整驗證結果，不能誤判資料損壞。
- `CLOSED／PASS (RESEARCH MECHANICAL PREFLIGHT)`：限定範圍 21/21 月及全量 485 partitions 真實讀回及 hash 檢查 PASS、清單及報告已讀回，**仍不代表獨立日曆、用途授權、PIT、四模型訓練或 publication PASS**。

完成機械 Preflight 後可另啟獨立「市場/產業特徵輸入」工作包：獨立日曆、資料來源授權、歷史產業 membership PIT crosswalk、指數 taxonomy 映射、衍生 lookback 與 feature-as-of／future leakage、四模型 X/Y 相依圖。過去提到的模型 X **34 欄是四模型指定 X 欄位數總和，不是本批市場指數個數，也不是全部待衍生特徵／貼標欄位總數**；不可用 34 當資料包驗收門檻。

## 9. 給下一個 AI 的可直接複製指示

> 任務：依 GitHub `main` 的 `doc/research/market-sector-preflight-operation-runbook.md`，對 Drive `janusChatGPT/資料源/大盤產業_免費來源_2025H1_試跑` 執行 2025-01～2026-09 四來源大盤/產業資料包之 **RESEARCH_ONLY** Preflight。開始先核對 `doc/PROJECT_RULES.md`、上述 runbook、`research/chatgpt/market_sector_package_preflight.py`、`tests/test_market_sector_package_preflight.py`。本次每輪**只做一個月**：全量讀回當月 TWSE/TPEx market/sector 的 raw/normalized/receipt、重算 SHA、schema、OHLC、唯一鍵、交易日集合、筆數，依 runbook 產 `preflight_summary.json`、`preflight_issues.csv`、`checkpoint.json` 和 `progress.csv`，立刻寫到 `janusChatGPT` 的獨立 reports 目錄並**讀回驗證**，回覆該月證據、問題、下個待驗月後就**停止**。不要連續跑第二個月，除非使用者再次要求。異常標 ERROR／BLOCKED，保留來源檔案與舊錯誤，不改 verified receipt、不重抓全資料、不造缺值、不做模型訓練及 canonical／Risk Registry 操作。若 CLI 或測試有真實缺陷，先獨立修 GitHub main、跑必要測試並記錄 commit，該輪版本重置。21 個月都完成後再照第 7 節全量跑一次、凍結研究 input manifest、讀回所有報告並明確區分機械 PASS 和獨立日曆／授權／PIT／模型 publication gate。不得以資料夾存在、fixture PASS、sample PASS 宣稱全量完成。限 GitHub main 與 Drive janusChatGPT 白名單，不使用未授權付費資源。
