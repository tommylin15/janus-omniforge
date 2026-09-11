# TODO 完成紀錄（2026-09-11）

本紀錄收納已完成的 WBS 切片與混合 WBS 的完成部分；未完成條件仍保留在
[`doc/todo.md`](../todo.md) 與對應 WBS 文件。

## WBS-3-ADMIN-POLISH

完成 Admin status／execution item 結構化欄表格、sticky header、排序、篩選、分頁、
欄位顯示與按需子表；source health／collection config 使用 repository-level bounded
keyset cursor。完成證據：完整 Python `154 passed`、Vitest `18 passed`、Admin
Playwright `9 passed`、`git diff --check` 通過。`npm.cmd run build` 的 typecheck
通過；lint 僅受既有 `.tmp` 與 `services/agent-gateway/dist` 生成檔阻擋。

## WBS 3 Admin Data Operations — 股票刪除 guard

Control SQLite／PostgreSQL 在刪除 transaction 內重查 collection config、execution、
market membership；Admin service 合併 Core 的 market、report、fundamental 資料集引用。
新增 references endpoint、結構化 409 引用數量與 UI 阻擋原因；任一引用非零時不送出
DELETE。完成證據：control／Admin／Web targeted coverage、完整 Python `154 passed`、
Admin Playwright `9 passed`。

## WBS 3 mixed acceptance — completed guards

Direct VPC egress／firewall negative evidence 與 Free Tier gcloud shape guard 已完成；
證據與限制詳見 [`spec/operations-and-testing.md`](../spec/operations-and-testing.md)。
WBS-3-ACCEPTANCE 的 5-stock scheduled canary 仍為 1/3，未在本紀錄宣稱完成。

## WBS-4C completed portions

WBS-4C-CHAT-API 的 owner-scoped Threads／Turns、bounded SSE replay、cancel、approval、
export、deletion status、provider continuation metadata 與既有 gateway probe 已完成；
三-runtime GCP dev 整合重跑仍留待 `WBS-4C-ACCEPTANCE`。

WBS-4C-ASSISTANT-UI 的多 Threads、Markdown／程式碼區塊、bounded streaming replay、
provider／model selector、MCP／Skills 與 Codex Items／Turns／Approval UI 已完成；
Flutter analyze 無 error、widget test `2 passed`。
