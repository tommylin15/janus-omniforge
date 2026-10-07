# B3 每日盤後 liquid-500 screening

狀態：implementation 已新增；deployment／live acceptance 仍需實際 evidence，BigQuery 未切 default。

## 日常路徑

沿用 controller 與 `janus-intelligence-mart`（1 CPU／1 GiB），交易日台北 16:30、等待同日 14:30 ingestion 與 08:30 data-supplement 成功。既有 `schedule.holiday_overrides` 休市日 skip；日曆不可讀時不 dispatch。Occurrence 保存 `SCREENING_DATE`，worker 只接受同日 immutable Core manifest；資料尚未 EOD ready 時 fail closed，不改用前一日成果。

`MART_OPERATION=market-screening` 只讀 public OHLCV／benchmark／可用 valuation，日期最多往前 241 日、membership 最多 500 檔、總列數最多 150,000，selected columns 保留來源／PIT 欄位。產出 5/20/60/120D 報酬與相對市場強弱、20D 平均成交金額／年化波動、可用 PE/PB/殖利率與 deterministic ranks。原 candidate rank 仍採 5D heuristic；缺值不排名、stale EOD 不列 discovery candidate。沒有財報／事件模型、OOS training、五 specialist 或 CEO calls。

Cache identity 包含 Core snapshot／manifest hash、table fences、analysis date、PIT membership、feature version、date bounds。無變更先驗 immutable artifact hash 再 reuse，reader／BigQuery 尚未建立。`screening/<identity>.json` 與每次 execution 的 `screening-manifest.json` 保存 lineage／quality／telemetry；寫入後 readback，相同 execution replay 不改原 receipt。沿用 Mart retention 的 90 日 bounded derived policy；未知 GCS I/O 保持 null。

## 固定 snapshot canary

```powershell
.tmp/specialist-venv/Scripts/python.exe scripts/gcp/b3-screening-canary.py --output .tmp/b3-canary.json
```

須用升級權限存取既有 dev credentials。沿用 B2 固定 B0 manifest 與 500 檔 membership；只查既有 `janus_core_dev.b2_core_fixed_20261007` 的 OHLCV／benchmark mapping。BigQuery 正常 query/result API、先 dry-run、整輪 <=1 GiB billed bytes、每 query <=60 秒；mapping 在 query 前、後及整批完成前驗證，不能證明 snapshot 就拒絕。

Valuation 仍由同一 bounded PyIceberg read 提供，不建立新 shared table。Candidate elapsed 排除共用 valuation read，不能當作完整冷啟動／Cloud Run 加速證據。Compare 包含 row multiset、null、provenance 與全部 screening output hash；row order 不影響 identity。沒有通過 cost/performance/failure acceptance 前維持 PyIceberg，不因一次 fidelity PASS 切 default。

## Dev execution／reuse

將既有 fixed Core event（executionId／analysisAsOf／coreSnapshotId／coreSnapshotUri／coreSnapshotHash 及版本欄位）寫到既有 dev Mart `acceptance/specialists/` 的 immutable input。執行既有 Job，execution override：

```text
MART_OPERATION=market-screening-acceptance
MART_ACCEPTANCE_INPUT_URI=gs://gen-lang-client-0593591102-dev-mart/acceptance/specialists/<input>.json
MART_AI_ENABLED=false
MART_OOS_EVALUATION=false
```

保存確切 execution name，查該 execution 的 bounded logs，再讀回 `screening-manifest.json` 與 referenced artifact/hash。第二次同 input 必須 `reused=true`、artifact 相同、growth=0；`specialist_count=0`、`llm_api_tokens=0`、`ceo_triggered=false`。Controller definition/runtime image/occurrence readback 與上述 live evidence 都成立後才結案 B3。
