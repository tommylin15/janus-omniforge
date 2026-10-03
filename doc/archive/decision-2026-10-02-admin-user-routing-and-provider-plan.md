# 2026-10-02 Admin／User／Routing／Provider 決策 — 歷史封存

狀態：**Superseded / historical only**
封存：2026-10-03
原始文件 blob：`2ee1f94caa404590ca6f1831d0b762cdee4cd613`

本文件對應 2026-10-02 當時的 Admin、User、行情 routing、AI provider 與工作順序決策。其原始完整內容仍可由 Git history／上述 immutable blob 追溯；本 archive 不重新複製舊 active contract，避免搜尋時把已被取代的內容誤認成目前規格。

## 被取代的主要內容

以下 2026-10-02 規劃已由 2026-10-03 active contract 取代，不得作為新的 implementation 指令：

- 五分析師以每日生成式 LLM workers 執行。
- 五角色共用 `Codex CLI → OpenRouter → Gemini` provider route。
- CIO 作為五角色之後的日常 synthesis runtime。
- 依舊五角色／CIO 設計的單角色 rerun、prompt／provider management。
- legacy static Admin 等待 Flutter parity 後才退役。
- 任何與最新 TODO 不一致的 foreground WBS 排序或 completion gate。

## 目前權威入口

- [`../todo.md`](../todo.md)
- [`../decision-2026-10-03-token-first-specialist-and-on-demand-ceo.md`](../decision-2026-10-03-token-first-specialist-and-on-demand-ceo.md)
- [`../decision-2026-10-03-admin-ui-scope-and-governance.md`](../decision-2026-10-03-admin-ui-scope-and-governance.md)
- [`../spec/specialist-engines.md`](../spec/specialist-engines.md)
- [`../spec/retention-governance.md`](../spec/retention-governance.md)
- [`../ui/admin.md`](../ui/admin.md)
- [`../ui/user-app.md`](../ui/user-app.md)

## 仍具歷史價值的證據

2026-10-02 當時已執行的 credential probe、provider adapter、routing、UI／runtime checkpoint 若有實際 evidence，仍保留其「當時觀察到的能力」價值；但不能推導目前 Token-first specialists、On-demand CEO 或新版 Admin operational convergence 已完成。

歷史 implementation／runtime evidence 的最終判讀仍依 GitHub commit history、`spec/operations-and-testing.md` 與 archive 中對應 checkpoint。