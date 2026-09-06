# TODO 完成紀錄（2026-09-05）

## WBS 3：Admin Data Operations

- 在 WBS 5 persisted Mart consumer 完成前，將 Admin Analysis action 與「Mart 分析」hidden／disabled，且不得建立無 consumer 的 queued execution；Collection queue consumer、lease recovery、terminal state、item persistence 與指定來源／日期 backfill runtime 維持可用。
  - Dev revision：`janus-web-00037-g25`
  - Live Playwright 與 API smoke 通過；Analysis POST 回 400 且 execution IDs 不變。
  - 五檔 backfill／replay／failure execution 均由 persisted worker claim 至 terminal state。

## WBS 4J：個人記帳、筆記與關注股獨立 MVP

- 建立最小 `services/api` FastAPI app、Google OIDC User auth boundary 與 journal／notes／watchlist API。
- 建立隔離的 append-only ledger、版本／冪等／ownership guard 與私人 PostgreSQL → Private Iceberg Core pipeline，支援 checkpoint、冪等寫入與失敗重跑。
- 建立私人 positions／realized PnL／unrealized PnL／annual PnL Mart，採移動平均成本法，缺價不顯示 0。
- 建立 journal、note revision、watchlist typed contract，完成私人資料匯出與可稽核、可重試的刪除工作流。
- 建立最小 Flutter「關注／筆記／我的」流程；今日／公開探索保持 disabled。
- 完成超賣、更正、note revision、watchlist、50-symbol、費稅、跨年、估值日期、重跑冪等、刪除與 A／B 隔離驗收。
- 驗證 User／Admin audience 混用、偽造或 client 指定 `user_id` 均被拒絕，email 變更不改變資料所有權。
- 不實作券商同步、自動下單、公開績效排行榜或 FIFO 切換。

### 驗收證據

- 2026-09-05：GCP dev 真人 Google User login 與 PostgreSQL watchlist A/B 隔離通過；兩個 Google `sub` 對應不同 UUID。
- WBS 4J targeted tests：14/14 passed；migration 014、獨立 User OAuth、Private bucket 與 dev `janus-api` 已部署。
- pipeline 首寫、checkpoint 重跑冪等與 Iceberg metadata snapshot 通過。
- deletion request `cffb8921-1f22-411b-8497-70bfdf8dad85` 由 execution `janus-private-pipeline-n7ml8` 完成，A rows／user 已刪除且 B 保留。

## WBS 4C：多供應商私人助理

- `WBS-4C-ENGINE-SECURITY`：以 `openrouter | gemini | codex` 取代舊固定三 profile 草稿，固定 provider／model／assistant／skill 分離、thread runtime／model 綁定與禁止 silent fallback。
- 新增共用 `AgentEventV1`、model capability、credential mode、私人 context 外送 disclosure／consent，以及 owner／thread／turn／request／參數／期限綁定的 approval contract；禁止 approval 擴張 Admin、交易／筆記／watchlist mutation 或下單權限。
- 驗證：targeted pytest 8／8、Python compile、JSON parse 與 `git diff --check` 通過；未建立或部署任何雲端／付費資源。
