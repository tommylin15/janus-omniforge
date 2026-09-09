# TODO 完成紀錄（2026-09-09）

本紀錄收納已完成的 WBS 切片與混合 WBS 的完成部分；未完成條件仍保留在
[`doc/todo.md`](../todo.md) 與對應 WBS 文件。

## WBS-4C-OPENROUTER

完成 OpenRouter 動態模型目錄、free-only／tools／streaming capability 篩選、
bounded function-call loop、SSE streaming、provider／usage metadata 與 billing
gate。完成證據：`tests/openrouter_provider.test.ts` 3／3、
`npm.cmd run build:agent-gateway`。

## WBS-4C-GEMINI-API

完成 Gemini Developer REST API 免費層、Google Search Grounding、citations／
attribution、查詢時間、quota／429／provider unavailable handling 與 paid-tier
fail closed。完成證據：`tests/gemini_provider.test.ts` 4／4、
`npm.cmd run build:agent-gateway`。

## WBS-4C-SKILLS

完成內建／自訂 Skills 的版本化 prompt、required tools、workflow、owner-scoped
載入與啟用／停用，以及不可執行任意程式的 manifest boundary。完成證據：
`tests/test_assistant_storage.py -k skill`、Python 語法編譯與 `git diff --check`。

## WBS-4C-PRIVATE-STORAGE

完成 migration 016、Private Iceberg assistant events／Skill revisions、PostgreSQL
bounded index、credential-shaped field fail-closed、冪等重跑、A／B 隔離與
Codex auth cleanup pending contract。完成證據：Cloud Build contract
`2b49fbbc-1dde-4091-9664-7ba33447f2ac` 與 GCP dev PostgreSQL／GCS-Iceberg acceptance。

## WBS-4C-CODEX-AUTH-LIFECYCLE（完成部分）

完成 owner allowlist、跨 request login／session provisioning、owner binding、
Secret rotation／舊版銷毀、logout／session eviction、destroy retry 與 deletion
pipeline wiring。GCP dev Cloud Build `9dec1039-0052-420d-9ef1-6719ed46991a`
SUCCESS；checkpoint `60ddd412-f367-4ac9-a5c6-8bbcd6f29e08`。互動式 device-code
真人瀏覽器流程仍未驗收，故主 WBS 不標記為整項完成。

## WBS-4C-CHAT-API（完成部分）

完成 owner-scoped Threads CRUD／fork、message turn、bounded SSE cursor replay、
cancel、approval response、assistant export、deletion status，以及受控 provider
continuation metadata。OpenRouter／Gemini signed gateway live probe 由 Cloud Build
`20050302-861a-4c84-84ad-c96f21903776` 通過，Gateway revision 為
`janus-agent-gateway-00029-5hk`。Chat API 直通 Codex 的 durable turn continuation
仍未完成。

## 暫時權限清理

驗收期間暫時授予 Cloud Build provider bundle accessor 與 dev invoker Token
Creator；驗收後均已移除。Gateway 維持 `min=0`、`max=1`、`concurrency=1`。
