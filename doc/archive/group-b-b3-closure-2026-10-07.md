# B3 每日盤後 liquid-500 screening 結案 — 2026-10-07

狀態：**CLOSED / PASS**

## 結論

B3 已完成 implementation、targeted tests、dev deployment、固定 Core snapshot 的 PyIceberg／BigQuery deterministic canary、兩次 Cloud Run reuse acceptance，以及 batch-controller 真實 occurrence readback。每日盤後 liquid-500 screening 已具備正式 dev runtime evidence；BigQuery **沒有切成 default**，PyIceberg 維持預設 reader。

## Acceptance evidence

- B3 implementation／workflow 主線已進 GitHub `main`；market screening 沿用既有 `janus-intelligence-mart`，資源維持 **1 CPU / 1 GiB**。
- B3 live acceptance base evidence：`doc/archive/group-b-b3-live-acceptance-2026-10-07.json`。
  - `tests=true`
  - `deploy=true`
  - `canary=true`
  - `live=true`
- 固定 snapshot canary：
  - PyIceberg 與 BigQuery hybrid compare PASS。
  - 使用既有 shared catalog mapping；不使用 BigQuery Storage Read API。
  - 整輪維持既有 **1 GiB** execution budget、每 query **60 秒** timeout。
  - 本輪不宣稱 BigQuery 已通過 production cutover；`default_reader=pyiceberg`、`cutover=false`。
- 兩次 fixed-snapshot Cloud Run acceptance：
  - 第二次 `reused=true`。
  - `artifact_growth_bytes=0`。
  - `screening_count=500`。
  - `specialist_count=0`。
  - `llm_api_tokens=0`。
  - `ceo_triggered=false`。
- Controller 最終 recovery workflow：GitHub Actions run `37628720592` **SUCCESS**。
  - recovery evidence：`doc/archive/group-b-b3-controller-recovery-2026-10-07.json`，`status=pass`。
  - 真實 occurrence：`market-screening/2026-10-07/16`。
  - `scheduled_at=2026-10-07T16:30:00+08:00`。
  - state：`status=succeeded`。
  - Mart execution：`janus-intelligence-mart-7f8jl`。
  - dependencies：`ingestion/2026-10-07/14`、`data-supplement/2026-10-07/08`。
  - runtime env：`MART_OPERATION=market-screening`、`MART_AI_ENABLED=false`、`MART_OOS_EVALUATION=false`、`SCREENING_DATE=2026-10-07`。
  - controller tick execution `janus-batch-controller-d7kfq`、probe execution `janus-batch-controller-6zjgr` 均成功。

## 驗收期間修復

B3 最後 controller evidence 一度因 acceptance harness 問題被誤判：

1. 早期 workflow 依賴 Cloud Logging 即時 index，execution 成功但 JSON evidence 尚未可見。
2. 改成 GCS direct readback 後，probe wrapper 使用 `gcloud --args` 時含逗號，list-type flag 將參數拆開，導致實際只執行部分 Python expression。
3. commit `84f2c1b6a898e5f098cf5f935d831a1ff3a38a6b` 將 wrapper 改成無逗號 expression；bounded controller-only recovery workflow 再以真實 Cloud Run + PostgreSQL occurrence + GCS immutable evidence 完成驗收。

這些是 acceptance harness 問題，不是 screening workload 本身失敗。舊的 failed／partial JSON 保留作可稽核歷史，不覆蓋本結案判定。

## 邊界

B3 **不代表**以下工作已完成：

- 五 specialist Deep Coverage。
- `active watchlist ∪ effective holdings` 的完整深算與 dirty dependency graph。
- ML baseline／OOS champion acceptance。
- 每月第一個週六 10:30 retrain／calibration／reconciliation runtime readback。
- BigQuery default cutover。
- On-demand CEO。

下一步依 B 組 WBS 進入 **B4：Deep Coverage specialists（持股／關注股）**；B3 不再重跑。
