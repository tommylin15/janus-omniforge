# Janus／OmniForge｜四模型研究資料包 Phase 1 全量 Preflight SOP（2026-10-23）

> **現行主入口／一次驗全量。** 使用者指定：以 Google Drive `janusChatGPT` 內的研究資料包為主要驗收對象，**一次啟動檢驗全範圍，不再每個月停止等待人工確認**。本文件是操作規格，並非 live 完成收據。參閱 [PROJECT_RULES](../PROJECT_RULES.md)、[最新四模型索引](00-四模型最新版本索引.md)、[市場資料包子流程](market-sector-preflight-operation-runbook.md)。

## 1. 資料與權威範圍

唯一 Drive 根：`/content/drive/MyDrive/給ai專用/janusChatGPT`（**不是** `個人用`）。

**第一順位／四模型主要輸入**
- `資料源/JanusDataset_v3_202610/canonical/CURRENT.json`。每輪開始僅固定讀取其所指的 release/manifest，**不可把舊 release 當目前 CURRENT**；驗證結束必須比較 pointer SHA 是否變動。
- 對該 manifest **全部引用**的檔案逐位元組驗 SHA256；核對 Parquet schema、row count、五類原生資料：`ohlcv`、`revenue`、`financials`、`valuation`、`corporate_actions`；另含 `invalid.csv` 與 `conflicts.csv`。不得僅以 metadata 或歷史驗收紀錄取代真實檔案核對。
- 使用已實作的 `research/chatgpt/label_four_models.py --verify-only` 與 `janus_precision.load_release` 查核 release、鍵值衝突隔離和必要的產業 PIT precheck；**不執行貼標、不產正式 X/Y、不訓練**。
- 四模型指定 X **34 個席位**：Risk 8、Quant 11、Fundamental 10、Valuation 5，以 GitHub `research/chatgpt/janus_precision.py` 的 `RISK/QUANT/FUND/VAL` 為現行程式依據。席位有定義 ≠ 實際特徵已可用／歷史 PIT 合格／訓練達標；需分別記錄每個席位的來源及缺口。

**第二順位／外部研究關聯輸入**
- `資料源/大盤產業_免費來源_2025H1_試跑`：`twse_market`、`tpex_market`、`twse_sector`、`tpex_sector`，**2025-01～2026-09 全期同一輪**，由既有 `research/chatgpt/market_sector_package_preflight.py` 完整驗證。
- 既有 Drive 導覽基準為 84 個月來源目錄、422 個 TWSE 產業日分區，合計 485 個待驗 partition、預期 1,455 個必要檔案；僅是先前 inventory 基準，必須以本輪 real bytes/SHA 校對。舊 `error_latest.json` 是歷史嘗試，不自動覆蓋較新成功 receipt。
- 市場指數資料 **不等於** `symbol → industry_id → index_id` 有歷史有效期的 crosswalk；`industry_membership.parquet` 不可缺證據就將現在產業倒灌至過去。市場來源或對照失敗時，非相依因子可獨立列為可研究，不要把四模型全部誤判資料損壞。

## 2. 一次執行範圍及狀態界線

採 **一個 run ID／一套固定 code SHA／一次掃描完整 CURRENT release 與 21 個月四種市場資料**。內部可分 source/partition、持續紀錄進度與問題，但不再有「驗完一月就停、下一月另待指令」限制。若資料環境中斷，沿用既有已驗 SHA 的有效證據或重跑新 run，保留失敗收據，不因要加速跳過校驗。

每項分開報：
1. `research_dataset_mechanical`：CURRENT/manifest/每檔 bytes SHA、rows/schema、loader 與資料衝突。
2. `market_sector_mechanical`：所有 market/sector raw、normalized、receipt，唯一鍵、OHLC、日期對齊。
3. `independent_calendar`：獨立交易日依據；CLI 內部日期相等**不代表**官方交易日完整。
4. `industry_membership_pit`、`source_use_authorization`、`model_feature_readiness`：各自 `VERIFIED/PARTIAL/BLOCKED/UNKNOWN`，不可隨前兩項 PASS 自動放行。
5. `publication_allowed=false`：任何 research PASS 都不得修改現有 Risk 狀態／Registry／GCS／PG／Core／Mart。

## 3. Colab／等效已掛載 Drive 的 Python 環境：一鍵全量

若執行器無法直接掛載**全部** Drive 原始檔與 Parquet（例如僅能透過 Drive connector 列檔），應標 `BLOCKED_RUNTIME_ACCESS`，不宣稱已跑完。以下整段放在**同一個** Colab `%%bash` cell，先 clone/pull GitHub `main`，確保已有 pandas、numpy、pyarrow；測試通過後一次跑完整區間，不在月別停頓。

```bash
set -u
cd /content/janus-omniforge
ROOT="/content/drive/MyDrive/給ai專用/janusChatGPT"
DATASET="$ROOT/資料源/JanusDataset_v3_202610"
MARKET="$ROOT/資料源/大盤產業_免費來源_2025H1_試跑"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$DATASET/reports/four_model_preflight/$RUN_ID"
mkdir -p "$OUT/market_sector"
git rev-parse HEAD > "$OUT/git_commit.txt"
python --version > "$OUT/python_version.txt" 2>&1
date -u +%FT%TZ > "$OUT/start_utc.txt"

python -m unittest discover -s tests -p 'test_market_sector_package_preflight.py' -v > "$OUT/test.log" 2>&1
TEST_RC=$?
printf '%s\n' "$TEST_RC" > "$OUT/test_exit_code.txt"
if [ "$TEST_RC" -ne 0 ]; then
  echo "Regression failed; do not claim full-data PASS. See $OUT/test.log"
  exit 3
fi

# A. 所有 CURRENT 引用檔案 raw bytes SHA + Parquet row metadata + CSV row count。
export DATASET OUT
python - <<'PY'
import csv,hashlib,json,os
from pathlib import Path
import pyarrow.parquet as pq
root=Path(os.environ['DATASET']).resolve()
out=Path(os.environ['OUT'])
p=root/'canonical/CURRENT.json'
cur_bytes=p.read_bytes();cur=json.loads(cur_bytes)
mp=(root/cur['manifest']).resolve()
if not mp.is_relative_to(root) or cur.get('format')!='parquet' or mp.parent.name!=cur.get('release'):
    raise ValueError('CURRENT_CONTRACT')
manifest=json.loads(mp.read_bytes())
if manifest.get('release_id')!=cur['release'].removeprefix('release-') or manifest.get('publication_allowed') is not False:
    raise ValueError('RELEASE_CONTRACT')
issues=[];inventory=[];release=mp.parent
for rel,expected in sorted(manifest['files'].items()):
    f=(release/rel).resolve()
    if not f.is_relative_to(release):
        issues.append({'path':rel,'code':'UNSAFE_PATH'});continue
    if not f.is_file():
        issues.append({'path':rel,'code':'MISSING_FILE'});continue
    h=hashlib.sha256()
    with f.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    observed=h.hexdigest()
    rows=None
    try:
        if rel.endswith('.parquet'):
            rows=pq.ParquetFile(f).metadata.num_rows
        elif rel.endswith('.csv'):
            with f.open('r',encoding='utf-8-sig',newline='') as stream:
                rows=max(0,sum(1 for _ in csv.reader(stream))-1)
    except Exception as e:
        issues.append({'path':rel,'code':'SCHEMA_OR_ROWS_ERROR','detail':type(e).__name__})
    if observed!=expected.get('sha256'):
        issues.append({'path':rel,'code':'SHA256_MISMATCH'})
    if rows is not None and rows!=expected.get('rows'):
        issues.append({'path':rel,'code':'ROW_COUNT_MISMATCH','declared':expected.get('rows'),'actual':rows})
    inventory.append({'path':rel,'sha256':observed,'rows':rows,'declared_rows':expected.get('rows'),'sha_ok':observed==expected.get('sha256')})
summary={'status':'PASS' if not issues and len(inventory)==len(manifest['files']) else 'BLOCKED',
         'release':cur['release'],'current_sha256':hashlib.sha256(cur_bytes).hexdigest(),
         'manifest_sha256':hashlib.sha256(mp.read_bytes()).hexdigest(),
         'file_count_declared':len(manifest['files']),'file_count_read':len(inventory),
         'tables_declared':manifest.get('tables'),'invalid_rows_declared':manifest.get('invalid_rows'),
         'unresolved_conflict_rows_declared':manifest.get('unresolved_conflict_rows'),
         'issues':issues,'classification':'RESEARCH_ONLY','publication_allowed':False}
(out/'preflight_inventory.json').write_text(json.dumps({'summary':summary,'files':inventory},ensure_ascii=False,indent=2)+'\n')
(out/'input_pinned.json').write_text(json.dumps({'release':cur['release'],'current_sha256':summary['current_sha256'],'manifest_sha256':summary['manifest_sha256']},indent=2)+'\n')
print(summary['status'],len(inventory),'/',len(manifest['files']),'referenced files')
PY
HASH_RC=$?
echo "$HASH_RC" > "$OUT/hash_exit_code.txt"

# B. 對整個 CURRENT release 執行既有真實 loader + PIT precheck；不做貼標。
python research/chatgpt/label_four_models.py \
  --dataset-root "$DATASET" --output-root "/content/janus_preflight_unused_output" \
  --verify-only > "$OUT/research_verify.json" 2> "$OUT/research_verify.stderr"
RESEARCH_RC=$?
echo "$RESEARCH_RC" > "$OUT/research_exit_code.txt"

# C. 大盤／產業 2025-01～2026-09 一次掃完，不逐月停。
python research/chatgpt/market_sector_package_preflight.py \
  --root "$MARKET" --start-month 2025-01 --end-month 2026-09 \
  --output "$OUT/market_sector" > "$OUT/market_sector.log" 2>&1
MARKET_RC=$?
echo "$MARKET_RC" > "$OUT/market_exit_code.txt"

# D. CURRENT 未變、分開判定機械驗收與研究因子可用性。
python - <<'PY'
import csv,hashlib,json,os
from pathlib import Path
from datetime import datetime,timezone
root=Path(os.environ['DATASET']);out=Path(os.environ['OUT'])
read=lambda n:int((out/n).read_text().strip())
try:inv=json.loads((out/'preflight_inventory.json').read_text())
except Exception:inv={'summary':{'status':'ERROR','issues':[{'code':'INVENTORY_NOT_PRODUCED'}]}}
try:res=json.loads((out/'research_verify.json').read_text())
except Exception:res={}
try:market=json.loads((out/'market_sector/preflight_summary.json').read_text())
except Exception:market={}
pinned=json.loads((out/'input_pinned.json').read_text()) if (out/'input_pinned.json').exists() else {}
actual=hashlib.sha256((root/'canonical/CURRENT.json').read_bytes()).hexdigest()
stable=actual==pinned.get('current_sha256')
dataset_pass=read('hash_exit_code.txt')==0 and inv['summary']['status']=='PASS' and read('research_exit_code.txt')==0 and stable
market_pass=read('market_exit_code.txt')==0 and market.get('status')=='PASS' and market.get('issue_count')==0 and len(market.get('partitions',[]))==485
from sys import path
path.insert(0,'research/chatgpt')
from janus_precision import RISK,QUANT,FUND,VAL
roles={'risk':RISK,'quant':QUANT,'fundamental':FUND,'valuation':VAL}
features={'total_slots':sum(map(len,roles.values())),'roles':{r:{'slots':len(v),'feature_names':v,
 'data_presence_only':dataset_pass,'computed_X_coverage':'NOT_VERIFIED',
 'historical_PIT':'NOT_VERIFIED','publication_allowed':False} for r,v in roles.items()}}
(out/'model_feature_coverage.json').write_text(json.dumps(features,ensure_ascii=False,indent=2)+'\n')
issues=list(inv.get('summary',{}).get('issues',[]))
for condition,code in [(not stable,'CURRENT_CHANGED_DURING_RUN'),(not dataset_pass,'RESEARCH_DATASET_NOT_PASS'),(not market_pass,'MARKET_SECTOR_NOT_PASS')]:
    if condition:issues.append({'code':code})
with (out/'preflight_issues.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=['path','code','detail','declared','actual'],extrasaction='ignore');w.writeheader();w.writerows(issues)
summary={'status':'MECHANICAL_PASS' if dataset_pass and market_pass else 'PARTIAL_OR_BLOCKED',
 'research_dataset_mechanical':'PASS' if dataset_pass else 'BLOCKED',
 'market_sector_mechanical':'PASS' if market_pass else 'BLOCKED',
 'independent_calendar':'PENDING_INDEPENDENT_EVIDENCE',
 'industry_membership_pit':res.get('industry_membership_precheck',{}),
 'source_use_authorization':'NOT_VERIFIED',
 'model_feature_readiness':'NOT_CERTIFIED','publication_allowed':False,
 'current_sha256_stable':stable,'git_commit':(out/'git_commit.txt').read_text().strip(),
 'market_partitions_seen':len(market.get('partitions',[])),
 'issue_count':len(issues),'market_issue_count':market.get('issue_count'),
 'completed_at_utc':datetime.now(timezone.utc).isoformat()}
(out/'preflight_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
(out/'checkpoint.json').write_text(json.dumps({'run_id':out.name,'status':summary['status'],'summary':str(out/'preflight_summary.json'),'pinned':pinned},ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False,indent=2))
PY
FINAL_RC=$?
echo "$FINAL_RC" > "$OUT/final_exit_code.txt"
date -u +%FT%TZ > "$OUT/end_utc.txt"
echo "Full Preflight reports: $OUT"
```

> **執行注意**：這是一個全量操作 cell，不是本文件撰寫時已成功執行。若某步因 Drive mount、記憶體、權限、套件失敗，應記為 `ERROR/UNKNOWN`，不誤當資料損壞；若資料本身有 SHA/schema 或日曆問題，記為 `BLOCKED`。CLI `verified_partitions` 不等於無問題通過數，須核 `issue_count`。全量市場 partition 數與先前 485 基準若不同，必須調查原因，**不為湊數修改歷史基準**。需要更嚴格的 PIT/跨資料表/來源授權，另以證據逐模型審核。

## 4. 交付與完成定義

- `input_pinned.json`：固定 CURRENT release、pointer/manifest SHA。
- `preflight_inventory.json`：全部 manifest 引用資料檔之實讀 hash/rows/metadata。
- `research_verify.json`：既有 loader 的完整驗證及產業 PIT 前置結論。
- `market_sector/preflight_summary.json`、`preflight_issues.csv`：大盤產業全期摘要/問題。
- `model_feature_coverage.json`：四模型共 34 個席位及「已定義／已衍生／PIT可用／完整覆蓋」狀態，**目前不得僅由 source 有檔就宣稱 34 因子 PASS**。
- `preflight_summary.json`、`preflight_issues.csv`、`checkpoint.json`、`git_commit.txt`、`test.log`：本輪證據、執行狀態、缺口、可重驗入口。

正式完成機械 gate 須全檔 SHA/schema/row、loader 與全期市場資料均驗收通過，並讀回報告和固定 digest；`model_feature_readiness` 另由各模型實際 X 數量、有效窗口、缺值、PIT/時間、Y 成熟和依賴品質判定。**機械 PASS 不等於四模型準備好訓練，更不等於模型可發布**。

### 本次只查得的 live 證據（不得視作 full-run）

2026-10-23 Drive `CURRENT.json` 實讀指向 `release-0bbae8d9c1ca7d8d`，其 manifest 宣告 155 個檔案項目、ohlcv 799,468 rows、financials 1,181,442 rows、revenue 92,910 rows、valuation 78,730 rows、corporate_actions 891 rows、unresolved conflicts 266 rows，`publication_allowed=false`。**尚未對全部 Parquet 實讀核 SHA，亦未透過 Colab 全量運行本 SOP。** 歷史 `release-b21384aebef3cd70` 不得冒充 current。

## 5. 禁止事項

全程不重抓、不清掃、不覆寫 `CURRENT.json`、raw/normalized/receipt、模型資料，不做 X/Y 正式貼標或模型訓練，不改 Risk ACTIVE/Registry/Core/Mart/GCS/PG，不開啟 publication，不新增付費服務。全量跑完後只根據實際錯誤定向提出修復，保存來源 provenance、權利限制與可重跑證據。
