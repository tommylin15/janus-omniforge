# WBS-5-MART-FACT-PACKS 驗收紀錄（2026-09-30）

目前判定：`WBS-5-MART-FACT-PACKS` **完成，Gate 2 通過**。Implementation、tests、deployment、原 bounded acceptance target recovery 與 pinned real-data replay 均通過。此紀錄不代表五位 AI 分析師已開始每日工作。

## 實作與相容性

- `analysis.py` 建立 Fundamental／Valuation／Positioning／Quant／Event Risk 五份 deterministic Fact Pack，保存 `fact_pack_version=1.0.0`、analysis-as-of、Core snapshot、feature version、facts、missing data、evidence／provenance IDs、evidence hash、Fact Pack hash 與 deterministic regression baseline。
- `mart.v1` contract 為 additive `1.1.0`：新增 `FactPackV1` 與 optional `MartScopedAnalysisV1.fact_packs`，保留既有 roles／features／consumer surface，沒有 schema major migration。Fact Packs 隨 scoped report 的 Iceberg `payload_json` 保存；LLM narrative 與治理／publication 分層，基準分數不是完整 AI 研究。
- Financial evidence 缺 availability time／authoritative publication time 時 fail closed；future、未核准來源與不合格 provenance 不進 facts。LLM 開關不改 deterministic facts／baseline。

## Live failure 與最小修復

- 原 bounded acceptance [run 36664077657](https://github.com/tommylin15/janus-omniforge/actions/runs/36664077657) failed；`janus-ingestion-core-lfjrk` 於 `2026-09-30T03:41:22.980190Z` 回報 `TIMEOUTERROR`，duration 902,893 ms。這筆失敗沒有改寫成成功。
- Mart `janus-intelligence-mart-d6hgs` 的兩次 task attempt 都回報 `INFAILEDSQLTRANSACTION`。IAP 唯讀 PostgreSQL server log 證明原始錯誤為 Pilot outcome 查詢 `permission denied for table mart_report_index`；未 rollback 的 transaction 又阻止 queue transition，留下過期 lease 的 `running` execution。`claimed=false / idle` 的 exit(0) 不算 Fact Pack acceptance。
- 修復 commit `9be6a15e391340ee5571cdd609abbaecfa3335a0`：`pending_outcomes()` 在 explicit transaction 內執行，失敗時 rollback 後仍可記錄 queue retry／failure；版本化 migration `035_mart_outcome_read.sql` 只授予 outcome 查詢所需八個公開 metadata 欄位 SELECT，並納入既有 migration runner。
- Migration 經既有 dev VM IAP 套用成功；marker 存在。獨立 ACL 驗證：必要 `execution_id` SELECT=true、直接 table INSERT=false、額外 `artifact_uri` SELECT=false。未新增私人資料、直接 publication 寫入或 GCP 資源權限。

## Tests 與 deployment

- 本機 targeted tests：`tests/test_intelligence_mart_runtime.py`、`tests/test_intelligence_mart_pipeline.py`、`tests/contract/test_contract_registry.py`、`tests/test_portfolio_deploy_contract.py`，**47 passed**。
- Pilot／public consumer／ACL／security regression：`tests/test_pilot_readiness.py`、`tests/test_public_mart_api.py`、`tests/test_postgres_mart_roles.py`、`tests/test_security_finops_contract.py`，**22 passed**；本次本機驗證合計 **69 passed**。
- 回歸測試模擬 outcome query abort，證明 rollback 後能保存同 execution 的 `retrying / PERMISSIONERROR`，不把原始錯誤掩蓋成 transaction failure。
- `git diff --check` 與 WSL `bash -n scripts/gcp/apply-private-storage-postgres-migration.sh` 通過。Commit／push 前已執行 `/ponytail-review`：Lean already. Ship.
- [Canonical dev deployment 36675717825](https://github.com/tommylin15/janus-omniforge/actions/runs/36675717825) success：Mart targeted CI **30 passed**、deploy／verify success；其他 runtime deployment skipped。[Portfolio contract 36675717822](https://github.com/tommylin15/janus-omniforge/actions/runs/36675717822) success。
- Cloud Build `0c14bbe8-cae9-498a-8dee-f5e20720fc2c`；`janus-intelligence-mart` 獨立 inspect 為 `Ready=True`，immutable image digest `sha256:6adfb7c7053f1b1b0eca803d4288296b90b52c155ade85f3bc30ce7a42058904`。

## Pinned real-data replay

原 target `4a429cb4-68ea-4506-985d-12bb817ea775` 與前次 `265f3276-53de-47ce-b836-d2326fc4b671` 使用同一：

- `analysis_as_of=2026-09-24`、symbol `2330`。
- Core execution `051642c0-b367-49f6-b0fb-308fbe07425c`。
- Core snapshot `sha256:7d2ced21d2dc5717f0e33037474c4417e432381288ed9fe53f2e535cab75bfa3`；manifest hash `sha256:c541f7baf3221c274db8ca892e35ddb8834dea002aa3f53a1bd80f3aede50223`。
- Core `core.ohlcv_v1` snapshot `3011184405508199324`；target 的 persisted scoped analysis snapshot `1930062826805744877`。

獨立唯讀驗證使用既有 PyIceberg／PyArrow 讀兩個 manifest 指定的 metadata location／snapshot ID 與 execution filter，沒有使用 latest snapshot 替代。Core manifest 的 raw-byte SHA-256 也與 persisted input fence 一致。兩筆 scoped payload 的十份 Fact Pack 逐一重算 `fact_pack_hash`／`evidence_hash`、核對 provenance／baseline／missing data；同 as-of 五個 hashes 完全相同，manifest `llm=[]`。十份 payload 也全部通過 `FactPackV1` JSON Schema／date format 驗證。

再從 pinned Core 讀出 2330 的 18 筆 OHLCV，以 repository `load_core_datasets()`／`analyze()` 重新計算；五份 Fact Pack 與 persisted target **完全相同**，deterministic hash 為 `sha256:89b5a9df12b65ed13d6d63bd5ce9801fe3f08dbf3f9b870b4567570aa277cb96`。此步為讀取真實 GCP dev input 的受控 replay，沒有寫回 Core／Mart 或呼叫 LLM。

## Runtime recovery

修復後以既有 Mart Job 序列化處理過期 leases，不新增 analysis execution、不並行 Iceberg writer：

- `janus-intelligence-mart-5jj6f` Completed=True；control execution `17ac0620-359e-5ab1-a627-ee0f6caa89af` succeeded，6 reports／30 validated Fact Packs／0 publishable，processor duration 6,242 ms。
- `janus-intelligence-mart-8rx8c` Completed=True；control execution `d2644b04-53a0-497b-9a4c-a6653d487195` succeeded，1 report／5 validated Fact Packs／0 publishable，processor duration 6,145 ms。
- `janus-intelligence-mart-94rfx`／`1cfea149-748c-42d8-b927-a21c9c2a2038`、`janus-intelligence-mart-4mnpl`／`4b8d3161-0f81-44bb-b549-86b51f7fc5ed`、`janus-intelligence-mart-lcjds`／`265f3276-53de-47ce-b836-d2326fc4b671` 依序恢復 succeeded；原 retry_count=1 保留，沒有重置歷史 retry lineage。
- 原 target：`janus-intelligence-mart-bdfbz` Completed=True，completion `2026-09-30T06:22:58.674147Z`；control execution `4a429cb4-68ea-4506-985d-12bb817ea775` succeeded。Processor log `2026-09-30T06:22:53.868365Z`：1 report／5 validated Fact Packs／0 publishable、duration 5,410 ms、retry_count=0。獨立 IAP PostgreSQL 查核前五筆舊 target 全部 succeeded，publication index 的原 metadata URI／snapshot 與 `insufficient_data / blocked` 維持。

## 驗收界線

此 bounded snapshot 僅含 OHLCV，不代表最新全市場／全資料集 coverage。基本面／估值／法人／benchmark／事件缺值照實保存；量化 evidence 有 13 筆合格行情引用，少於 20 筆的 return／Beta 仍 missing。Report 保留 `insufficient_data / blocked`，沒有填值、放寬 publication gate 或公開發布。

Fact Pack contract 完成與完整研究資料 coverage、五個 AI role、provider、CIO、natural daily workload 是不同判定。後續工作依 active TODO 的獨立 WBS／模型 gate 執行；Production、付費來源、付費模型與新 GCP 資源沒有獲得授權。
