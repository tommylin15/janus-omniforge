# B4 Deep Coverage specialists 結案證據 — 2026-10-07

## 結論

B4 **CLOSED / PASS**。本次只收斂 Deep Coverage runtime 的 universe、dependency-selective execution、immutable cache/reuse 與真實 dev acceptance；**不代表** B5 ML/OOS data path、月度 retrain/reconciliation、完整模型品質或 champion promotion 已完成。

## 實作範圍

- Deep Coverage universe 固定為 `active watchlist ∪ effective holdings`，沿用既有去識別化 target projection；不把 B3 liquid-500 screening 混入。
- Fundamental / Valuation / Quant / Risk / Event 依各自 output-affecting dependency hash 決定 dirty；只有 dirty role 計算，其他 role reuse immutable artifact。
- cache identity 包含 symbol、role、accepted/rejected PIT dependency state、feature version、engine version、model version；舊 artifact immutable。
- rejected evidence 也會參與 invalidation，避免新增 future/quality-rejected evidence 時錯誤 reuse 舊 status。
- Deep Coverage operation 不執行 market screening、OOS retraining 或 CEO/LLM；正常路徑 `llm_api_tokens=0`。
- reuse reference 保留 source Core snapshot identity、artifact hash 與 cache identity，不能把舊 artifact 假裝成新計算。

主要 implementation SHA：
- `850299fa50f32de0eeb89055d2d6e0515a6993cc` — selective specialist execution。
- `e3b6f6f7429029ff60ce827e8f7edf1c945c3165` — Deep Coverage dependency cache。
- `c5167224e142fa854b90f45da2de61431152a244` — B4 regression tests。
- `e9db123dd5b37f0747803cdc32318dcb0a4fe4d8` — expose `deep-coverage` runtime operation。
- `752e551110cc67e18403b2ce2f00774f5b2a0c7f` — rejected evidence 納入 dependency invalidation；這是本次 live acceptance 驗證的 runtime code SHA。

## Tests / CI / deployment

修正版 Deploy dev workflow `37634230788`：
- `test-mart`：**116 passed, 7 warnings**。
- `deploy-mart`：SUCCESS。
- `Verify intelligence-mart`：SUCCESS。
- 其他不相干 ingestion/API/migration jobs 正確 skipped；沒有為 B4 擴大部署範圍。

新增 regression 覆蓋：
- selected Event-only dirty update 不執行 price/risk compute。
- event dependency change 只 invalidate Event。
- rejected future Event evidence 也會只 invalidate Event。
- Deep Coverage 不讀 liquid-500 membership。
- no-change execution 五 role 全 reuse。
- event-only change 為 1 computed / 4 reused。

## 真實 dev runtime acceptance

Workflow `37636276994`：**SUCCESS**。前置 gate 已確認 deployed Mart image 的 `JANUS_GIT_SHA=752e551110cc67e18403b2ce2f00774f5b2a0c7f`。

固定相同 Core snapshot：
- hash：`sha256:c81b476dfa9a2bade3e82c806f2f9bdfb04c5f97947265c08b0b44807955aac9`
- Deep Coverage symbols：5
- specialist outputs：25（5 symbols × 5 roles）
- `screening_count=0`
- `llm_api_tokens=0`
- target artifact `private_fields_exposed=false`，manifest/target readback contract PASS。

第一次 Cloud Run execution `janus-intelligence-mart-qrnwm`：
- specialist_count：25
- computed：25
- reused：0
- elapsed：92.954 s
- peak RSS：413.53 MiB

第二次 Cloud Run execution `janus-intelligence-mart-jp6kn`：
- specialist_count：25
- computed：0
- reused：25
- dirty_specialists：0
- elapsed：56.506 s
- peak RSS：269.33 MiB

因此已以真實 dev evidence 證明相同 immutable input 在第二輪不重新計算五 specialist，且 B4 沒有誤觸 B3 screening 或生成式 LLM。

## 完成判定

B4 所需的 implementation、targeted tests、CI、Mart deployment/verify、真實 Cloud Run Deep Coverage、artifact/target readback、no-change reuse 均有證據，故 B4 正式 CLOSED。

尚未完成、不可混入 B4 的範圍：
- B5：Iceberg → BigQuery SQL reduction → bounded/versioned GCS Parquet → ML/OOS data path。
- 月度第一個週六 10:30 retrain/calibration/OOS/reconciliation effective schedule/readback。
- 各 specialist 完整 ML/OOS 品質、Event labeled classifier、歷史 membership replay、champion promotion。
- B8 fallback/FinOps 最終比較與 B9 specialist/OOS 集中 acceptance。

下一個 active work：**B5 ML / OOS data path**。
