# Mart Codex provider dev 驗收

僅使用既有 dev Mart Job、bucket 與 PostgreSQL；先讀 [專案規則](PROJECT_RULES.md)。
本程序不代表自然 daily workload、CIO 或 production 已完成。

## 授權、Routing 與模型

- 初始化登入／MFA／OAuth consent 由本人在官方流程完成。搬移登入資格、使用帳號 quota
  或變更 Secret IAM 前取得明確授權；原始資格不進 argv、log、repository、artifact 或 Admin 表單。
- 帳號 cache 使用已核准的獨立 `janus-mart-codex-auth` Secret；不得放入 GitHub CI。
  Mart 只具該 Secret 的讀取／新增版本權限，沒有共享 DB bundle 的寫入權。
- 使用者 2026-10-02 指定五分析師 default provider route：**Codex CLI → OpenRouter → Gemini**。
  只有 approved／authorized provider profile 才能進 effective route；Admin reorder 不等於授權。
- Routing 必須 versioned；execution 啟動時固定 effective route、routing config version/hash 與
  provider profile snapshot。後續 Admin 調整順序不得改寫舊 execution。每次 attempt 保存
  provider、transport、model、parameters、reason、latency、可觀察 usage/cost 與 fallback reason。
- Fallback 只在 timeout、transport、rate-limit、provider unavailable、auth/capacity unavailable
  等已核准 failure class 發生；schema／validator／grounding／PIT／missing-data failure 不得藉由
  換 provider 靜默繞過。沒有 approved route 時 fail closed。
- 未由使用者選定前，Codex 預設 `gpt-6.1-sol`＋`low`（輕）；明確 env/profile override 必須保存在
  lineage。Admin 模型選單仍待 `WBS-6-ADMIN-ANALYSIS-PROFILE` 實作，須取得該授權帳號的
  最新可用清單並標示來源／更新時間／失敗狀態，不把快取冒充即時清單。
- CLI preflight 的 `ready` 僅代表 cache 形狀與 CLI capability 通過；真實授權、model access
  與 structured output 仍由 GCP invocation 證明。不可將 subscription 或未知 cost 寫成免費。
- 目前每個 role 使用隔離 workspace／allowlisted env，工具與 Web Search 停用。
  設定 `MART_CODEX_AUTH_SECRET=janus-mart-codex-auth` 時，使用獨立 autocommit DB session lock
  序列化帳號批次；每次 CLI 退出後驗證並保存更新的 cache，讀回成功才允許下一角色。
  完成狀態仍須真實 rotation／cold-start evidence；程式存在不代表 lifecycle 已驗收。

## 2026-10-02 Credential／免費 gate live probe

既有 `janus-runtime-bundle` 已做只輸出 bounded metadata 的安全 probe，不輸出任何 secret 值：

- Fugle：`fugle_api_key` 存在，`2330` quote HTTP 200。
- Gemini：`gemini_api_key` 存在，models endpoint HTTP 200，可見 `generateContent` model；這只證明
  credential／model discovery 可用，**不證明 Free Tier／billing 狀態**。
- OpenRouter：`openrouter_api_key` 存在，key endpoint HTTP 200；metadata 回報
  `is_free_tier=false`，因此不能直接當成 approved-free。

免費限制：

- Fugle 可進免費 source approval，範圍限 Janus owner-private display／bounded latest-quote cache；
  不核准 public redistribution，也不把 operational quote 冒充 canonical Core historical data。
- OpenRouter 只允許 `free_only` profile；必須實際驗證 prompt/completion 都為 `$0` 的 route。
  找不到 `$0` route、free model unavailable 或 metadata 不足時 fail closed，不退到付費模型。
- Gemini 在確認 key 所屬 project 的 Free Tier／billing gate 前，不發 generation request；models
  endpoint 成功不等於 free entitlement acceptance。
- 任何新付費 API／model／subscription 仍需使用者明確授權，不能由 routing reorder 自動打開。

## 有界驗收

1. 以 canonical dev workflow 部署並確認 tests、Ready、Git SHA、immutable image digest。
2. `MART_OPERATION=provider-smoke` 可檢查 CLI/cache，無模型呼叫。
3. 依已核准上限執行 `scripts/gcp/verify_mart_ai_contract.py --manifest-uri <既有 dev manifest>
   --symbol <單一 symbol> --verify-provider`。覆寫 `ENVIRONMENT=dev`、明確 model／reasoning，
   `MART_CODEX_MAX_ATTEMPTS=1`；不得省略 dev gate 或自行增加驗收股數。
4. 該次 execution 固定 `maxRetries=0`，避免 Cloud Run task 重試重複消耗額度。既有 Job 若須
   暫時調整建立 execution，立刻恢復 canonical queue 設定並獨立核對兩者。
5. 讀回 evidence、五角色 interpretation／validation／attempt、sidecar，核對 immutable hashes、
   Fact Pack／Core lineage、實際模型、routing version/hash、失敗 reason 與 usage；原 manifest／metadata
   保持不變。`blocked`、資料不足或 validation failure 不改寫成完整研究成功。
6. 以 `scripts/gcp/verify_mart_ai_targets.sql` 在既有 dev PostgreSQL 執行真實 trigger／ACL
   驗收；所有合成 owner／ledger／watchlist／投影都在同一交易 rollback。此測試不能取代
   target snapshot 與 provider 批次同 execution 的整合驗收。
7. OpenRouter fallback 驗收時只允許已確認 `$0`／free-only model route；若實際 request 沒有
   可驗證的 free metadata 或任何 paid possibility，直接 structured blocked。
8. Gemini fallback 驗收前先確認 Free Tier／billing gate；未確認前保持
   `blocked_pending_free_tier_confirmation`，不得為了測 routing 發 generation request。

Quota、usage／actual cost 不可觀察時保留 unknown；沒有已核准 fallback 時 fail closed。
尚未核准持續批次額度／完成 auth lifecycle 前，不啟用 `MART_AI_ENABLED=true` 的自然批次。

## 2026-10-02 接續方案（已核准；驗收狀態見 status／TODO）

### 跨批次 auth 保存

使用者已核准建立獨立 dev Secret `janus-mart-codex-auth`，只保存 ChatGPT auth cache；不讓 Mart
取得共享 `janus-runtime-bundle` 的寫入權。使用者已明確核准本節 Secret／最小 IAM 與
最多十次呼叫；費用尚未量測，核准不延伸到其他資源或自然每日 AI 批次：

- 既有 Mart service account 僅在該 Secret 取得 `roles/secretmanager.secretAccessor` 與
  `roles/secretmanager.secretVersionAdder`；不取得管理、刪除版本或其他 Secret 的權限。
- Operator 經 stdin 搬移已核准資格，不在 argv／log／artifact 保存原始 token。
- 每個 Job 在使用 auth 前，以既有 PostgreSQL session advisory lock 序列化同一帳號的
  完整模型批次；拿不到 lock 則 structured blocked，不使用舊 cache 競爭 refresh。
  Lock 以獨立 autocommit 連線持有，不能讓 DB transaction 橫跨模型 I/O。
- 拿到 lock 後讀取最新 Secret version；每次 CLI 退出後驗證 ChatGPT cache 形狀，若有
  rotation，立即新增 Secret version 並讀回核對，成功後才能執行下一角色。Secret I/O
  有逾時且不盲目重試 addVersion；保存失敗停止後續模型呼叫並回 required user action。
- 下一個 cold-start Job 從最新 Secret 讀取；runtime bundle 中的舊 cache 不作 silent fallback。
  Artifacts 只保存 Secret version metadata／狀態，不保存 credential hash 或 payload。
- Revoked／過期／refresh 失敗 fail closed；重新登入／MFA 由本人操作。保留舊版本供稽核，
  但 refresh token 已 rotation 時不能假定舊版本仍可登入，不能以盲目 rollback 宣稱 recovery。
- Operator 可撤銷該 Secret 的 Mart IAM／停用最新版本，並保持自然 AI 批次關閉；舊共享
  bundle 的資格移除須保留其他 DB 欄位並另做 operator-controlled 版本更新。

費用依 [Google Secret Manager pricing](https://cloud.google.com/secret-manager/pricing)：
免費額度以 billing account 跨專案合計，6 個 active versions／每月 10,000 access operations；
Enabled 與 Disabled 都計入 active。超額版本為每版本每月 USD 0.06，access 超額為每
10,000 次 USD 0.03。此次兩批驗收最多初始版本＋十次 rotation＝11 版本，若全數超過
免費額度且保留一整月，版本費用最多 USD 0.66（不含既有 Cloud Run／CLI 帳號用量）。
這不是零費用保證；持續排程前需另核准 bounded retention，不能無限累積版本。
權限範圍依 [官方 IAM roles](https://docs.cloud.google.com/iam/docs/roles-permissions/secretmanager)。

### 同 execution target／Core／五角色驗收

已準備 `scripts/gcp/verify_mart_ai_provider_execution.py`。它讀取既有 immutable Mart
`input.json` 與明確 SHA-256，以新 UUID 建立 acceptance execution；重新核對 Core
hash／snapshot／execution fence，使用正式 target projection及正式 provider stage，
只保存 additive AI artifacts，不呼叫 deterministic publication writer。

執行前必須使用 migration replay floor 之後的真實 input；不得把舊 `analysis_as_of` 改成
今天來繞過 PIT。明確設定 execution-only `ENVIRONMENT=dev`、`MART_AI_ENABLED=true`、
`MART_AI_MAX_SYMBOLS_PER_EXECUTION=1`、`MART_CODEX_MAX_ATTEMPTS=1`；Cloud Run execution
仍需 `maxRetries=0`。其餘未 admission 的 target 全數保留 deferred，不能稱完整聯集已分析。

驗收讀回 target／attempt／sidecar／十份 interpretation＋validation hashes、same execution／
Core／scope lineage，並再次執行同 execution 的 stage，證明 immutable manifest replay
不追加呼叫。沒有 targets／preflight blocked／insufficient_data 均照實回報。
此入口讀回各批次的 `auth_lifecycle` metadata；整體跨批次／rotation 必須獨立比對，
單批結果仍回傳 `auth_lifecycle_verified=false`。

已核准最多 **10 次** `gpt-6.1-sol`＋`low` 呼叫：兩個獨立 cold-start dev executions，
每批最多一股×五角色、每角色一次，無 task retry／provider retry／fallback。第二批驗收
最新 auth version 與同 execution target integration；未發生真實 rotation 時，rotation
仍標示 not observed，不能由 cold start 冒充。額度用完即停止，不啟用自然每日 AI 批次。

### Completion boundary

- Credential probe 成功 ≠ provider runtime approved。
- Provider-routing targeted tests 成功 ≠ GCP dev five-role acceptance。
- Deploy success ≠ same-execution target／provider／validator success。
- OpenRouter `free_only` 與 Gemini Free Tier gate 未完成前，兩者不得在 effective route 中執行。
- `WBS-5-MART-AI-PROVIDERS` 只有在 TODO 定義的整體 acceptance 全部具備 evidence 後才能標 completed。