# 2026-10-10｜固定 Preview 新 GHCR 候選 A→B→A 驗收（使用者確認）

## 身份、時間與限制

- **候選 source SHA**：`038498c70e12488f345c3ca0fbe821846ddee4cc`。固定 Preview：<https://preview---janus-api-2oo7qbkd5q-uc.a.run.app/app/>；候選 Revision：`janus-api-00457-wed`。
- **使用者確認日期**：2026-10-10 Asia/Taipei（本次對話確認，約 09:04；UTC 記錄 `2026-10-10T01:03:59Z`）。使用者在上一輪被明確詢問「是否已在新版固定 Preview 完成 A→B→A，資料隔離與 PnL 正確」，答覆「是的都正確」。
- **證據分類**：`USER_ATTESTED`，不是 ChatGPT 持有 A、B 兩套 Google 憑證的重放／抓取驗證；未記錄帳號、owner ID、token、持股或 PnL 值。由使用者本人執行登入，符合 OAuth 必須人工介入。
- **使用者實際確認的範圍**：Google Owner A 私人持股／紀錄可讀；Owner B 不可看見 A 私人資料（含先前提出的 A 識別碼存取拒絕情境）；切回 A 原始資料一致；年度 PnL 正確。上述均綁定本次已明確提問的 **新版固定 Preview**，**不可沿用**舊版 `fbcc5f58…` 的另一筆 A/B proof。

## 非人工證據（另行核對，勿混成使用者實測）

- [GHCR full release #37953986962](https://github.com/tommylin15/janus-omniforge/actions/runs/37953986962)：來源 SHA `038498c70e12488f345c3ca0fbe821846ddee4cc`，完成、SUCCESS。
- [0% candidate #37954588954](https://github.com/tommylin15/janus-omniforge/actions/runs/37954588954)、[新候選 OAuth／MCP 未登入邊界 #37955226220](https://github.com/tommylin15/janus-omniforge/actions/runs/37955226220)：兩個 workflow SUCCESS；包含候選完整 SHA／健康與負向 OAuth/MCP challenge，**負向測試不能替代上述真人登入**。
- [Preview 正向 #37956325838](https://github.com/tommylin15/janus-omniforge/actions/runs/37956325838) 和 [同 SHA 唯讀 #38009514370](https://github.com/tommylin15/janus-omniforge/actions/runs/38009514370)：固定 URL 提供 `038498c70e12488f345c3ca0fbe821846ddee4cc`，source identity、tag 與 100% 正式舊版隔離被 GCP live gate 驗證。
- **MCP 專用唯讀正向檢查**：此輪呼叫已連線的 `Janus Dev Read-only v2` 的 `janus_sources` 及 `janus_private_context(resource=positions, limit=1)`；回傳 `janus.mcp.v1`、`owner` scope 可用且讀取一筆 bounded owner record（API status `partial` 表示這是一筆受限讀取，非全量私人資料已檢驗）。沒有啟動任何 MCP 寫入、token 或私人 payload 未納入報告；此 MCP 為既有 read-only tagged endpoint，**沒有冒充是新候選版本的獨立 owner A/B MCP 測試**。
- [原版 GHCR rollback baseline #38010139996](https://github.com/tommylin15/janus-omniforge/actions/runs/38010139996)：唯讀 live PASS，四 Job 舊版 image/config fingerprint 可回復；共用 lease ref 不存在（404），沒有以 A/B 口頭確認放寬 baseline。

## 發布關卡

- `ops/ghcr-owner-acceptance.json` 應如實記錄 **本次來源人工確認＋前述有來源的自動安全檢查**，而不是將不同來源的真人測試混淆。
- 下一段 Jobs rollout 仍需自己的真實 scheduler fence、四 Job GHCR image/config readback、每 Job 兩次 canary、失敗恢復；API promotion 仍需真正 100% traffic 切換及 rollback rehearsal。**本次 A/B 人工 PASS 不等於 Jobs／API 發布 PASS**。
