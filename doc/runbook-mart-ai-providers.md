# Mart Codex provider dev 驗收

僅使用既有 dev Mart Job、bucket 與 PostgreSQL；先讀 [專案規則](PROJECT_RULES.md)。
本程序不代表自然 daily workload、CIO 或 production 已完成。

## 授權與模型

- 初始化登入／MFA／OAuth consent 由本人在官方流程完成。搬移登入資格、使用帳號 quota
  或變更 Secret IAM 前取得明確授權；原始資格不進 argv、log、repository、artifact 或 Admin 表單。
- 帳號 cache 僅放核准的既有 Secret bundle `codex_auth_json` 欄位；不得放入 GitHub CI。
  更新 bundle 時保留其他欄位，經 stdin 傳輸，保留原 version 作 bounded rollback。
- 未由使用者選定前，預設 `gpt-6.1-sol`＋`low`（輕）；明確 env/profile override 必須保存在
  lineage。Admin 模型選單仍待 `WBS-6-ADMIN-ANALYSIS-PROFILE` 實作，須取得該授權帳號的
  最新可用清單並標示來源／更新時間／失敗狀態，不把快取冒充即時清單。
- CLI preflight 的 `ready` 僅代表 cache 形狀與 CLI capability 通過；真實授權、model access
  與 structured output 仍由 GCP invocation 證明。不可將 subscription 或未知 cost 寫成免費。
- 目前每個 role 使用隔離 workspace／allowlisted env，工具與 Web Search 停用。
  子程序更新的 cache 在同一批次供後續角色使用；**尚無跨 Job 的續期資格保存機制**。
  既有 Mart 身分只有 Secret accessor，不自行擴權；這個缺口不得標成 lifecycle 完成。

## 有界驗收

1. 以 canonical dev workflow 部署並確認 tests、Ready、Git SHA、immutable image digest。
2. `MART_OPERATION=provider-smoke` 可檢查 CLI/cache，無模型呼叫。
3. 依已核准上限執行 `scripts/gcp/verify_mart_ai_contract.py --manifest-uri <既有 dev manifest>
   --symbol <單一 symbol> --verify-provider`。覆寫 `ENVIRONMENT=dev`、明確 model／reasoning，
   `MART_CODEX_MAX_ATTEMPTS=1`；不得省略 dev gate 或自行增加驗收股數。
4. 該次 execution 固定 `maxRetries=0`，避免 Cloud Run task 重試重複消耗額度。既有 Job 若須
   暫時調整建立 execution，立刻恢復 canonical queue 設定並獨立核對兩者。
5. 讀回 evidence、五角色 interpretation／validation／attempt、sidecar，核對 immutable hashes、
   Fact Pack／Core lineage、實際模型、失敗 reason 與 usage；原 manifest／metadata 保持不變。
   `blocked`、資料不足或 validation failure 不改寫成完整研究成功。
6. 以 `scripts/gcp/verify_mart_ai_targets.sql` 在既有 dev PostgreSQL 執行真實 trigger／ACL
   驗收；所有合成 owner／ledger／watchlist／投影都在同一交易 rollback。此測試不能取代
   target snapshot 與 provider 批次同 execution 的整合驗收。

Quota、usage／actual cost 不可觀察時保留 unknown；沒有已核准 fallback 時 fail closed。
尚未核准持續批次額度／完成 auth lifecycle 前，不啟用 `MART_AI_ENABLED=true` 的自然批次。
