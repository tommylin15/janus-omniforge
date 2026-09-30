# WBS-5-MART-AI-ROLE-CONTRACT 驗收紀錄（2026-09-30）

判定：**完成，Gate 3 通過**。五角色／CIO output contract、locked guardrail、versioned
methodology prompts 與 immutable artifact lineage 已建立；不代表 provider、語意 validator、
CIO synthesis 或自然每日 workload 完成。

## 實作邊界

- `ai_contract.py` 提供 Fundamental／Valuation／Positioning／Quant／Event Risk 五個
  discriminated schema 與 CIO schema，公開 JSON Schema 保存於 `mart_ai.v1.json`，registry
  additive 註冊；既有 `mart.v1` 與 deterministic roles／facts／publication 路徑保持相容。
- 主張使用 `Claim{text,evidence_ids}`；資料不足可保存 `thesis=null`，但須揭露缺資訊。
  格式通過只標 `schema_validated / validation_status=pending`，沒有 semantic validation
  或 publication authority。Invalid output／unknown role 回 structured failure，不保存
  raw provider input／exception 或 placeholder success。
- System guardrail 固定於系統程式；methodology revision 不接受 system/schema override。
  六份 prompts 含 version／author／timezone timestamp／profile reference／content hash。
  Admin editor 留待自身 WBS。
- 每個新 Mart execution 保存 create-only `artifacts/ai-role-contract.json`；舊 execution
  manifest 不補寫。Interpretation artifacts 依內容 hash 保存，lineage 含 execution／scope／
  as-of／Core snapshot、Fact Pack／evidence hashes、feature／governance version、provider／
  model／parameters／profile、schema／prompt／guardrail versions 與 hashes。
- Pydantic 原本已存在 Mart lock，僅補 direct requirement，沒有新增套件或 GCP 資源。

## 本機與 CI／deployment

- Targeted regression：`test_mart_ai_contract`、Mart pipeline／runtime、contract registry、
  public Mart API、portfolio deployment contract，**79 passed**。正式 JSON Schema 的六份
  insufficient-data fixtures 也通過。Acceptance script `py_compile` 與 `git diff --check` 通過。
- 首次擴大測試因缺 `jobs/ingestion-core` PYTHONPATH 在 collection 失敗；補正執行環境後
  通過，沒有以修改測試隱藏失敗。
- Commit／push 前 `/ponytail-review`：Lean already. Ship. 遠端並行 research commits
  已比較後 rebase，沒有 force push／覆蓋 research 工作。
- 實作 commit `a21ce9b5448b89f765e652dfddf07cac47e7ccab`。
  [Canonical dev workflow 36687180475](https://github.com/tommylin15/janus-omniforge/actions/runs/36687180475)
  全部 success；Mart targeted CI **53 passed**，使用 lock 內 Pydantic `2.13.4`。
  Mart／API／ingestion／private pipeline deploy／verify 均 success；後三者由既有 contracts
  paths filter 觸發，沒有增加 runtime。
- 獨立 inspect：`janus-intelligence-mart` Ready=True，`JANUS_GIT_SHA` 匹配實作 commit，
  immutable image digest `sha256:03ceb9128af581c9f9a39a9462092d9c12e4d5de2836b14414e80c3899e68f49`。

## GCP dev bounded acceptance

既有 Job 單次 execution `janus-intelligence-mart-9w9d2`，Completed=True／succeededCount=1，
completion `2026-09-30T08:10:57.717554Z`（台北 16:10:57）。只讀既有 pinned report，沒有
enqueue analysis、Core／Iceberg 寫入、AI provider 呼叫或 publication 寫入。

輸入：`executions/4a429cb4-68ea-4506-985d-12bb817ea775/manifest.json`，symbol `2330`、
`analysis_as_of=2026-09-24`；Core snapshot
`sha256:7d2ced21d2dc5717f0e33037474c4417e432381288ed9fe53f2e535cab75bfa3`；
Mart scoped snapshot `1930062826805744877`。讀取 manifest 指定 metadata location，先核對
raw-byte metadata hash，再以 snapshot ID／execution／scope filter 讀 payload；不用 latest snapshot。

Acceptance 實際保存契約 bundle、六筆故障注入的 structured failures 與 evidence。
同 artifact 重複保存回相同 reference；嘗試覆寫 contract object 被 create-only writer 拒絕，
舊 bundle readback 保持一致。這些 failure 是故障注入證據，不是 AI 研究成品。

- Contract hash：`sha256:e139dd20db6c906d207cd9716e9092972681784580eb6afc4e66da0decc3639d`。
- Schema hash：`sha256:058b4bc72061f1db80e0bce40331cd3becb8635c502d2433e9085a7cd0a60c2f`。
- Evidence hash：`sha256:27544daf7dfbfa12442766850d54eddea3731867a208b9db1e7020f64d29545f`。
- Evidence URI：`gs://gen-lang-client-0593591102-dev-mart/acceptance/ai-role-contract/e139dd20db6c906d207cd9716e9092972681784580eb6afc4e66da0decc3639d/evidence.json`。

獨立唯讀 GCS readback 重算 bundle 與六份 failure 的 raw-byte hashes、各 interpretation
content hash、role set、Core snapshot／guardrail lineage，全部通過；bundle 與 repository
完全相同。原 manifest 沒有補入 AI contract；原 report 仍 `insufficient_data / blocked`，
deterministic hash 維持 `sha256:89b5a9df12b65ed13d6d63bd5ce9801fe3f08dbf3f9b870b4567570aa277cb96`。

可重跑方式：在已部署的既有 dev Job 使用 execution-only args override
`python,scripts/gcp/verify_mart_ai_contract.py,--manifest-uri,<上述完整 gs:// manifest URI>`，
`ENVIRONMENT=dev` execution override、1 task、180s timeout。不要修改 persistent Job command
或建立另一個 runtime。驗收程式在非 dev bucket／environment fail closed。

## 完成語意與後續

可宣稱「五位分析師角色契約已建立」，不能宣稱五位分析師已可靠／每日工作。
Provider、numeric／PIT／claim coverage validator、CIO synthesis、rerun/cache 與 Admin editor
仍依各自 WBS／模型 gate 執行；本次沒有啟用新 provider、付費模型或 Production。
後續 validation／provider 的排序仍須依 active TODO／WBS dependency 判定；本項未修改其他
WBS 的責任或解鎖其 implementation。
