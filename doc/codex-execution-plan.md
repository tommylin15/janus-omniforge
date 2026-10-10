# Janus — Codex 執行指令

更新：2026-10-10  
用途：B 組下階段工程交接。**A 組、GHCR CI/CD、B7 月度與 derived-cache freshness、B8 均已按目前核准範圍結案；下一個 active 僅 B9；C 不自動啟動。**

權威順序：`AGENTS.md` → `PROJECT_RULES.md` → `todo.md` → 本檔 → 對應 WBS／SPEC → GitHub `main` implementation／runtime evidence。歷史 checkpoint、archive 與 `spec/operations-and-testing.md` 可證明過去做過什麼，但不覆蓋目前 active contract。

## 1. 目前唯一 active 工程組：B

B 組合併：

- `WBS-5-MART-SPECIALIST-ENGINES`
- `WBS-5-MART-RERUN-CACHE`
- [Iceberg canonical + BigQuery analytics hybrid](decision-2026-10-06-bigquery-analytics-over-iceberg.md)
- Admin 對應 specialist evaluation／cache／runtime 狀態接線

主要模型：【Sol】。

### 可直接貼給 Codex 的 B 組指令

```text
請執行 Janus B 組：specialist／增量快取／BigQuery analytics。

先讀：
1. AGENTS.md
2. doc/PROJECT_RULES.md
3. doc/todo.md
4. doc/decision-2026-10-06-bigquery-analytics-over-iceberg.md
5. doc/spec/specialist-engines.md
6. doc/wbs/wbs-5-specialist-engines.md
7. doc/wbs/wbs-5-intelligence-mart.md
8. doc/status.md
只再讀直接相關 code/tests/workflow/runtime evidence，不預設載入整個 repository 或 archive。

本組固定執行語意：
- Iceberg V2/GCS 是 canonical/PIT/provenance/history；BigQuery 只作 analytics compute。
- 每個交易日 EOD canonical data ready 後，約 500 檔跑一次低成本 screening/cross-sectional discovery；BigQuery 通過 fidelity gate 後優先承接。
- 完整五 specialist 只跑 active watchlist ∪ effective holdings，依 dirty dependency/input change 增量更新；無變更 reuse；禁止 500×5 全量深算。
- specialist-retrain、calibration、OOS/evaluation、cache/dependency reconciliation 固定每月第一個週六 10:30（Asia/Taipei）。
- 不建立另一套每週六 500×5 排程；月度重型批次只採第一個週六 10:30。
- BigQuery intermediate 預設 bounded/TTL/可重建；大型 training/evaluation input 用 versioned GCS Parquet；不要為了「留一份」把 BigQuery 中間結果再寫回 canonical Iceberg。
- 禁止 BigQuery Storage Read API、bigquery.readsessions.*、google-cloud-bigquery-storage。
- User/Admin request-time read、Ledger/private owner path、PostgreSQL serving projection 不搬到 BigQuery。
- CEO 不由 daily screening、dirty update、Scheduler 或模型重訓自動觸發。

依下列順序完成可執行工作，不在每個內部步驟停下要求確認：

B0～B6. CLOSED / PASS；不重做已驗收成果。
- B0 baseline、B1 exact-snapshot reader、B2 BigQuery fidelity、B3 liquid-500 screening、B4 Deep Coverage dirty/reuse、B5 ML/OOS Parquet export、B6 derived-cache 均有獨立 live/CI acceptance。
- 完成證據統一由 doc/todo.md 的 B0～B6 archive links 查閱；現階段未有新回歸證據時，不重新部署或重跑已完成步驟。
- 現役 PyIceberg default；BigQuery 實際 cutover 必須等 B8 同 workload gate。

B7. 月度執行與 derived-cache freshness — CLOSED / PASS；不重跑
- 月度首週六 retrain/OOS/原始 reconciliation 的核准 dev 執行已 PASS；不重送 10/08 舊 request、不再派送月度 Job。
- 舊 Core B6 historical 快取已透過獨立 PyIceberg 新來源刷新、25 個月度 specialist refs 唯讀 reconciliation 收斂。2026-10-10 GCP live #38056677635：34 tests、Core sha256:687fae3e…、11,432 rows、new reconciliation pass/current/exact-core、GCS immutable receipt readback PASS。
- 原月度 reconciliation partial 是歷史真實值，不覆寫。B7 證據：doc/archive/group-b-b7-derived-cache-freshness-closure-2026-10-10.md。

B8. Backend / fidelity / FinOps / fallback — CLOSED / PASS；不重跑
- 原同源 screening／ML-OOS 對照、選路、受控故障回退已完成，見 doc/archive/group-b-b8-closure-2026-10-10.md。
- 預設 PyIceberg；BigQuery 僅 ML/OOS 明確 opt-in，無 BigQuery default cutover，禁止 Storage Read API。B8 歷史 snapshot 不替代 B9 current-source 模型品質證據。

B9. Specialist/OOS acceptance
- 完成 Fundamental、Valuation、Quant、Risk/Regime、Event/Catalyst 的 active TODO 範圍。
- structured artifact + SHAP/feature contribution + deterministic plain-language report，正常 path 0 LLM API token。
- Taiwan PIT/data-priority walk-forward OOS、missing-data honesty、source authorization、public/private isolation 保留。
- Admin 只顯示真實 persisted evaluation/reuse/runtime 狀態。

集中驗收：
- 先完成同組 code/migration/tests/docs，再跑 targeted tests。
- 有已授權 BigQuery/Lakehouse dev resource 才跑 live compatibility/canary；沒有就把 resource-dependent gate 標 blocked，不自行建立/啟用/擴 IAM。
- 同一 fixed snapshot 驗 PyIceberg vs BigQuery、daily 500 screening、Deep Coverage selective invalidation、no-change reuse、monthly schedule definition/readback、OOS、failure fallback、FinOps。
- 保留 specialist runtime 1 CPU/1 GiB；資源不足先提出 evidence，不自行升級。
- commit/push 前依 AGENTS.md 做 review；環境中無 /ponytail-review 命令時，不因非系統 skill 缺失停等，但要以實際 diff/contract/test 檢查取代並如實記錄。
- 只有 implementation、tests/CI、deployment、runtime、trigger/workload、integration evidence 都符合時才勾 TODO。partial/blocked 不包裝成完成。
```

## 2. B 組 cadence — 唯一 active 口徑

| 範圍 | 何時跑 | Universe | 主要 compute |
|---|---|---|---|
| Market screening | 每個交易日 EOD canonical ready 後 | liquid-500 | BigQuery 通過 gate 後優先；PyIceberg fallback |
| Deep Coverage inference | input change／dirty 時 | active watchlist ∪ effective holdings | Python／SQL／ML specialist；只跑受影響項 |
| Model/OOS/reconciliation | 每月第一個週六 10:30 Asia/Taipei | 依 model/evaluation contract | retrain／calibration／OOS／cache reconciliation |
| CEO | 使用者明確 Analyze/Re-analyze | authorized symbol request | C 組 provider path；B 組不得自動呼叫 |

「週六」不是 500×5 的固定全量日；「每月」也不是 specialist output 只在月度才更新。

## 3. B 組資料角色 — 唯一 active 口徑

- **Iceberg V2 / GCS**：canonical、PIT、provenance、history、source authorization。
- **PostgreSQL**：User/Admin request-time serving projection、control/publication/audit/bounded index；A 組 hot path 保持。
- **BigQuery**：大量 cross-sectional analytics compute；intermediate 預設 TTL／可重建，不取得 canonical authority。
- **GCS Parquet**：固定某次 snapshot／feature/version 的大型 ML training/evaluation dataset。
- **Mart**：immutable specialist/model/evaluation/report artifacts 與 lineage。

不得建立沒有證據必要性的 full-Core BigQuery duplicate warehouse，也不得把 BigQuery intermediate 當成需要永久備份到 Iceberg 的第二份 canonical。

## 4. 人工授權 gate

下列事項沒有使用者明確授權不得 mutation：

- 啟用新的付費 BigQuery／BigLake API 或第三方付費服務；
- 建立／提高付費 dataset、reservation、catalog、connection、cache 或其他資源；
- 擴大 IAM；
- 遷移現有 PostgreSQL-backed Iceberg catalog；
- 大量不可逆刪除或沒有可靠 rollback／rebuild 路徑的破壞性操作；
- OAuth／MFA／付款／帳號管理。

遇到 gate 只阻擋相依項，其餘 B 組可執行工作繼續；狀態標 partial／blocked。

## 5. C 組

C 組是 B 組之後的下一組，不因完成或閱讀本文件自動啟動。範圍仍為 On-demand CEO provider/runtime、capability/quota/cooldown、Admin analysis profile、User Analyze/Re-analyze/history 與 AI-dependent final visual acceptance。

## 6. 歷史文件處理

A 組已 CLOSED，因此本檔不再保存 A 組開發／Cloud 驗收指令。歷史 A evidence 與過去 runtime 排程留在 archive／operations；active B target 只看本檔、TODO、SPEC 與 WBS。
