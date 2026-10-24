> **2026-10-24 政策更新**：研究數字與歷史結論保留；本文舊有逐來源／全歷史 PIT 補證、精確時間校準及新前瞻成熟等待不再是工作或發布前置。取消例行稽核，依 [研究精簡政策](../../doc/spec/research-simplification.md) 按需評估；不把取消視為 PASS。

# Janus / OmniForge Valuation P1 — 原始來源封包與歷史會計口徑查核

日期：2026-10-24；研究限定（`publication_allowed=false`）。來源依 GitHub `main`、現行研究 `release-0bbae8d9c1ca7d8d` 及已凍結 P1 清冊；**不**修改 `canonical/CURRENT.json`、Registry、Risk ACTIVE、Core/Mart，不啟動訓練，不新增付費 API／訂閱，不擴大到全市場補收。

## 已有實證與範圍

來源：先前 `Valuation_P1_來源證據與安全輸入_20261024.zip` 內的 `exception_evidence.csv`（SHA256 `92aaa683f5a2c1c9c56ae9c66f0b5eeb617176cdb86c95f90ed79c1eafbf4c38`）與 `source_record_links.csv`（SHA256 `9c3d5484d40133bd8eb7e7e29d45064728421ef8fb7fbef509e6b30a82da5269`）。113 組例外，1,113 筆 source links，涉及 1101／1102／1103／1104／1201 五家公司，共 15 季。上述紀錄只是 frozen inventory row 的導出指紋，**不是當初官方或 FinMind 回應的 request ID、原始 response hash 或修訂版本證據**。

本輪在實際凍結清冊執行 dry-run：FinMind 去重後 107 個 query task；MOPS 原始／前季證據 114 個 task（包含因缺同年 Q3 無法差分的補證工作）；HTTP request 實行 0、取回新 FinMind response 0、找回原始 canonical response 0、正式來源單位／期間／合併別／修訂認證 0、歷史 PIT 0。這不是資料錯誤率，而是現有採集鏈缺少 row-attached 原始證據。

## 來源與能夠證明的項目

- [FinMind 官方基本面資料](https://finmind.github.io/tutor/TaiwanMarket/Fundamental/)：`TaiwanStockBalanceSheet`、`TaiwanStockFinancialStatements`、`TaiwanStockCashFlowsStatement` 的 API v4 `/api/v4/data` 回傳 `date`、`stock_id`、`type`、`value`、`origin_name` 等欄。`date` 是**財報期末**，不是歷史首次公告時間；`type=..._per` 不當作金額。新請求可逐筆核對現在的 `type`、`value`、`origin_name`，不能自證當初的採集版、合併別或修訂。
- [MOPS 財務比較 E 點通](https://mopsfin.twse.com.tw/)：正式分類為資產負債表（時點）、綜合損益表（累計）、現金流量表（累計）；[說明及使用限制](https://mopsfin.twse.com.tw/terms) 指出資料庫每日更新，可能和申報站有一日落差。這是一般來源說明，**不是**現行 118 萬筆資料的逐列單位、合併別與第一次發佈時點認證。
- MOPS 舊頁端點如 `https://mops.twse.com.tw/mops/web/t163sb05`：需有對應公司／季度的完整報表 HTML、原始 XBRL 或申報公告封包，包含可稽核的報表類別／revision／來源 id。現階段沒有經驗證的 row→raw MOPS request 關聯，因此**不**自動猜測 POST API schema 或將網頁值套用到 canonical 舊列。
- 1103、1201 在 2022Q4 的資產／負債數值有對稱差額，權益一致；可能是來源版本／重分類，但沒有原始修訂鏈不宣稱原因已確認。

## 程式及 Colab

`valuation_p1_raw_evidence.py` 可從先前兩個已凍結研究 CSV 建立 107＋114 筆請求／證據計畫；預設 **無 HTTP**。`16_Valuation_P1_原始來源封包查核.ipynb` 自包含固定 SHA256 的 Python source，會驗證前次研究 ZIP 的兩份 CSV SHA256，Colab ROOT 僅 `MyDrive/給ai專用/janusChatGPT`。

```bash
python valuation_p1_raw_evidence.py \
  --exceptions exception_evidence.csv \
  --links source_record_links.csv \
  --out research_only_evidence
```

若要在 Colab 有界下載**現在的 FinMind 快照**，明確把 Notebook `RUN_FETCH=True`，限定 1103／1201，每輪至多 4 requests、2 stocks、240 秒，3 MB/response；遇 HTTP 401／403／429 中止並保留已有 checkpoint。`FINMIND_TOKEN` 僅從 Colab Secrets 讀取，不進任何 CSV、raw 檔、Git 或一般 log。`response_sha256`、實際回應原始 bytes、UTC 擷取時間與對應股票／季度／欄位、HTTP 狀態，均可讀回；有相同 `type/value` 僅升級 `CURRENT_SNAPSHOT_EXACT_FIELD_MATCH_NOT_HISTORICAL_PROOF`，**不**升級 arithmetic／PIT gate。

MOPS 若有已下載的官方原始 bytes，可用 `--mops-packet ... --mops-url ... --mops-symbol 1103 --mops-quarter 2022Q4 --mops-dataset balance`，產生 immutable raw SHA 與證據收據；現有程式**不會**未經驗證便將 MOPS HTML 當作已認證的資料列。

## 產物及後續安全 Gate

- `finmind_request_plan.csv`、`mops_source_evidence_tasks.csv`：去重 source tasks，已包含 2022Q3 前季依賴。
- `raw_evidence_receipt.json`：實際拿到的 bytes 與經證明的限制，`publication_allowed=false`。
- 若已手動啟用 fetch：`responses/<task_id>/<sha256>.json`、`receipts/0001-<hash>.json`、`snapshots.json`（研究 checkpoint）以及 `snapshots_field_anchors.csv`。
- MOPS 原檔匯入：`mops_packets/<symbol>/<quarter>/<dataset>/<sha256>.bin`，來源網域白名單與獨立 receipt。
- 任何 FinMind `date` 不得當 `published_at`；報表期末不得當公告時點；2022Q4 無 2022Q3 的 YTD 流量不作跨年差分；EPS 不乘 1,000，不作自造單季差分。
- 要成為正式算術特徵輸入，至少還須 row-level 單位、報表期間、合併／個體、revision、raw field 精確錨定，並排除同概念不同來源重複列；要成為**歷史 as-of 訓練**輸入還需可追溯的首次申報／當日有效版，不得以今日 API 資料倒填。

驗收：本地測試 16/16 PASS、實際 113 例外轉化計畫 PASS、Notebook Python code cell AST parsing PASS；**真實 source bytes capture 尚未執行（0 HTTP）**；因此「程式交付」PASS，「取回原始歷史財報來源和 PIT 依據」BLOCKED。執行完成與否不可從程式寫好推定。
