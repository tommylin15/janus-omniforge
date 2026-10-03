# Janus SPEC — 非功能需求與 Release Gate

更新：2026-10-03

## 14. 非功能需求

- 冪等、可重跑、可追溯、可安全失敗。
- Stage → Core 的 required key、type、duplicate、PIT／future leakage、source authorization、quarantine 是不可延後的資料安全邊界。
- GCP service／job 優先同區，避免不必要跨區成本。
- 統一 execution／trace identity；log redaction；secret／token／raw private payload 不進一般 log。
- 監控 source success、latency、freshness、schema drift、fallback、batch/job state、publication、API error、retention／storage anomaly。
- Dev billing budget notification 只作提醒，不是 spending cap；actual spend 以 Cloud Billing 為準，不宣稱固定 $0。
- UI、LLM、CEO 不計算／補值／覆寫 canonical number，不持有 publication authority。
- public/private isolation、owner binding、immutable lineage、missing／stale／partial honesty 必須跨 API／Mart／UI 一致。

### 14.1 Dev release 語意

目前 GCP `dev` 是個人真實 parallel-live environment。能力是否可用由該能力自己的 implementation、tests、deployment、auth、runtime、data／integration evidence 判定；不需要另一套 Production environment 才算真實可用。

mock／fixture／localhost 可補 timeout、cancel、disconnect、secret-redaction 等故障情境，但不能代替宣稱 live accepted 的 real-path evidence。

Dev 包含真實個人資料，因此 secret、owner/auth、migration、backup／rebuild、retention、不可逆刪除防護不因環境名稱而降低。

## 15. Capability Release Gate

以下是目前 dev capability 的共同驗收原則，不要求所有功能一次完成：

- Source → Stage → Core → Mart → API → UI 的相關資料鏈可追蹤至 snapshot／provenance／execution。
- PIT 無 future leakage；被排除樣本有原因與 provenance。
- blocked／invalid／insufficient 不進公開 publishable index；missing 不觸發即時計算或 LLM 補值。
- private ledger 可重建 Private derived state；更正事件、跨年計算與 owner isolation 有測試／runtime evidence。
- User／Admin 共用 Flutter codebase但 auth／audience／workspace boundary 分離；legacy static Admin 已退役，不再是 release gate。
- Admin manual retry／rerun 走 backend allowlist、authorization、idempotency／duplicate、dependency／exclusive guard 與 audit；dispatch accepted 不等於 workload success。
- 約 500 market coverage 與 Deep Coverage `active watchlist ∪ effective holdings` 的 scope／quota／deidentification 符合 active contract。
- 高頻、新聞、社群、paid source 等未核准 capability 保持 disabled／blocked，不因 UI 顯示而取得 runtime authority。
- pytest／FastAPI contract tests／Flutter analyze-test／受影響 build／integration tests 按 diff 範圍通過；跨模組／安全／migration／release 才擴大完整驗證。
- 目前實際使用的 browser/device 主流程有 authenticated dev evidence；完整 device／A11y matrix 可依 active WBS 分階段完成。
- private-data deletion／cleanup status 可查；`CLEANUP_PENDING` 不顯示成功。
- runbook、bounded backup／export／rebuild 與必要 rollback 路徑存在；HA／PITR／multi-region 是未來 Production scope，除非另案核准。

### 15.1 Specialist／CEO acceptance

#### 五 specialist

- Production 主路徑為 Python／SQL／ML；正常 path 不產生五個 LLM calls。
- artifact input／snapshot／feature／engine／model version 可追溯；no-change reuse 可稽核。
- OOS／PIT evaluation 決定 champion，不以 upstream benchmark／training success 代替。
- one-specialist failure／missing 不得顯示 full success。
- plain-language output 由 structured output + SHAP／rules／templates 產生；LLM 不改 deterministic facts。
- public/private isolation、evidence、missing-data honesty 維持。

#### On-demand CEO

- 只由具 backend capability 的使用者明確 request。
- 只讀 validated specialist outputs／Fact Pack／provenance。
- provider／model／profile／route、attempt／fallback、timeout／retry、usage／cost 可追溯。
- request accepted 不等於 report succeeded；validator failure 保持 partial／blocked。
- 每次 reanalysis 建立新 immutable execution/report；舊 report 不覆寫。
- upstream specialist update 只標記 freshness／material delta，不自動觸發 CEO。
- `Codex CLI → OpenRouter → Gemini` 只屬 CEO／approved escalation route，不代表 specialist daily runtime。

#### Admin Analysis Profile

- specialist champion/model/version/evaluation 與 CEO provider/model/profile 分開管理。
- capability、quota／cooldown、approval／auth／health、usage／cost 由 backend enforce／record。
- version mutation create-only；rollback 也建立 audit lineage，不覆寫 old effective config。

## 15.2 Admin operational convergence acceptance

- `總覽` 只突出 actionable exception；正常 execution 不佔主畫面。
- `批次` 顯示 backend effective batch／occurrence／latest state／duration／last success，預設最近 3 天，較舊 history bounded 查詢。
- 現行七個 controller batches：`ingestion`、`data-supplement`、`mart`、`data-quality`、`private`、`core-cleanup`、`mart-cleanup`。
- `資料治理` 顯示 Stage/Core/Mart/必要 Private 的 retention、DQ、live objects／active bytes、maintenance、protected refs 與 anomaly；沒有 evidence 顯示 `unknown`。
- live bytes 與 non-current／versioned／billable bytes 分開；不能把 live object size 當帳單數字。
- 第一版不依賴 OpenMetadata/DataHub/Airflow/Kestra/Prefect 或第二套 control plane 才能完成。
- authenticated browser acceptance + 真實 batch／retention／storage telemetry 到位後才可宣稱 operational convergence 完成。

## 16. Evidence Window／Future Production

持續 real use 的 evidence window 用於觀察資料可靠性、模型價值、維運負擔、成本與安全，不是「在此期間不能用」的 gate。

重要 evidence 至少涵蓋：

- **Data**：ingestion success/failure、freshness、coverage、missing、schema drift、quarantine／retry、source stability。
- **Analysis**：specialist availability、deterministic replay、PIT/OOS、provenance、model/evaluation revision、5/20/60 trading-day outcome、relative benchmark、MFE／MAE、valid/excluded reason。
- **CEO**：manual request availability、provider route、latency、failure／fallback、usage/cost、manual intervention、report usefulness（在 capability 已實作後）。
- **Operations**：Cloud Run Job／Service／Scheduler/controller reliability、retry/idempotency、maintenance、storage growth、recurring failure。
- **Cost**：Cloud Billing、provider usage/cost（可取得時）、resource growth；unknown 不補 0。
- **Security／Privacy**：secret handling、owner isolation、auth lifecycle、public/private boundary、delete／cleanup evidence。

每份重要分析結果需可追溯 data/snapshot/as-of、source/provenance、code/image revision、engine/model/profile revision、execution identity/time 與 result status。

若未來真的需要多人／對外／HA／SLA Production，再用 evidence 做人工 `KEEP_DEV_PARALLEL_LIVE`／`GO_PRODUCTION_PLANNING`／`EXTEND_EVIDENCE_WINDOW`／`NO_GO` review。任何 outcome 都不得自動新增 production／paid resource。

## 16.1 MCP／ResearchContext acceptance

ChatGPT MCP capability 的 live acceptance 只約束 MCP 本身，不阻擋其他 Janus 功能。至少驗證：

- OAuth login／expiry／refresh／unauthenticated deny；
- server-side owner binding與 owner isolation；
- allowlisted market/private resources；
- arbitrary SQL／URI／owner injection／mutation rejection；
- bounded records／bytes／date ranges；
- source／as-of／provenance；
- secret／storage locator absence；
- scale-to-zero／bounded cost evidence。

ResearchContext 若進 active TODO，另驗證 same-`analysis_as_of`、PIT、deterministic replay、provenance、stale／missing／partial、owner isolation、bounded output 與 zero canonical-number generation by LLM。

## 16.2 Supply-chain research

Supply-chain Intelligence 仍是 planned/research capability。任何 signal/evaluation 必須保留 revision、effective time、PIT/provenance、hypothesis-vs-confirmed boundary。未經 active TODO／source authorization／cost approval，不得因研究文件存在就啟動 production crawler、paid source 或新 GCP runtime。