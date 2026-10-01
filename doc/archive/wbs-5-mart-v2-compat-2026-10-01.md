# WBS-5-MART-V2-COMPAT 結案（2026-10-01）

判定：**完成**。`mart.v1` 維持 canonical，AI references 採 additive sidecar；未建立／切換 `mart.v2`。

## 實作與驗證

- 原 contract commit `49c7eaca1d30ed16d7e885bac58795c8e2f575e2` 已提供 `mart_compat.v1`、registry、base identity／same-role reference／sidecar hash validation 與 future migration plan。
- 本次 commit `b7876863037abd030cebbc1359c7aafb48b55cda` 補齊 canonical CI 的 compatibility／registry tests，以及既有 dev pinned report／artifact 的 bounded 驗收。沒有修改 `mart.v1.json`、report writer、publication index 或舊 API consumer。
- 本機 Windows pipeline／runtime／AI contract／compatibility／registry／public consumer：96 passed。初次擴大測試另有三項既有 Linux worker 測試因 shebang／`/tmp` 在 Windows 失敗（101 passed／3 failed）；未改 worker，後續 Linux CI 同組 worker tests 全數通過。WSL 未安裝 pytest，未宣稱已跑 WSL tests。
- [push CI 36810194740](https://github.com/tommylin15/janus-omniforge/actions/runs/36810194740) 96 passed；[canonical dev run 36810205260](https://github.com/tommylin15/janus-omniforge/actions/runs/36810205260) 96 passed、deploy／verify success。只部署既有 Mart Job；其他 runtime skipped。
- Cloud Build `54db2228-9d4c-4048-a3de-685977f63457` SUCCESS；獨立 Job inspect：Ready=True、JANUS_GIT_SHA 匹配 `b787686...`，image digest `sha256:4972c6887bf1eaeda7dd338a093b8803f8d806580d4bafd938254cd1b0ce2a2b`。
- 部署 smoke execution `janus-intelligence-mart-9xslv` 成功；bounded pinned-report execution `janus-intelligence-mart-mfg8c` Completed=True、succeededCount=1，completion `2026-10-01T03:32:16.471955Z`（台北 11:32:16）。

## 真實 dev artifact acceptance

使用既有 Job 的 execution-only args：`python,scripts/gcp/verify_mart_ai_contract.py,--manifest-uri,<下列 manifest>,--verify-compat`；`ENVIRONMENT=dev`、1 task、180s timeout。不改 persistent Job command／env，不建立新 GCP resource。

Pinned source：`gs://gen-lang-client-0593591102-dev-mart/executions/4a429cb4-68ea-4506-985d-12bb817ea775/manifest.json`；symbol 2330、as-of 2026-09-24、report schema `1`，Core snapshot `sha256:7d2ced21d2dc5717f0e33037474c4417e432381288ed9fe53f2e535cab75bfa3`，deterministic hash `sha256:89b5a9df12b65ed13d6d63bd5ce9801fe3f08dbf3f9b870b4567570aa277cb96`。

讀取既有 Gate 4 acceptance 的 30 份 interpretation／validation fixtures，核對 raw-byte／content hash；取五角色已 validated 的 insufficient-data fixtures，重新執行 validator 並建立十個 references 的 create-only sidecar。讀回 sidecar 通過 base／hash／same-role source 驗證，原 report／manifest／metadata 未改。

Sidecar URI：`gs://gen-lang-client-0593591102-dev-mart/acceptance/mart-compat/c75c064295a2f0ac060bc0fedae3972ce5c370aa50a8febbb2840f07711a170b/sidecar.json`。

- Content hash：`sha256:c75c064295a2f0ac060bc0fedae3972ce5c370aa50a8febbb2840f07711a170b`。
- Raw-byte hash：`sha256:a130e3f4c4b2acd5877734b744336330aaa6f1dcf6e2ee405b59e253c32f28a6`。
- 獨立 operator 唯讀 readback：sidecar＋十個引用 objects 共 11 個；content hashes、role／status、execution／scope／as-of／Core lineage、source interpretation hashes 與 publication_authority=false 全部通過。Raw-byte hash 與 GCP execution log 一致。

本次真實部分為 GCP runtime、pinned canonical report、immutable storage 與 lineage；角色輸出是既有 validation fixtures。`provider_calls=0`、`publication_writes=0`、`five_role_success=false`；不是 GCP 五分析師真實研究或自然每日工作成功。

## 後續邊界

Future v2 必須另外完成 shadow／candidate／consumer opt-in／cutover／rollback gates，見 [相容策略](../spec/mart-v2-compatibility.md)。下一項為 `WBS-5-MART-AI-PROVIDERS`，須重新確認 Sol 與各自 acceptance；本次不自動開工。
