# Janus SPEC — 非功能需求與 Release Gate

## 14. 非功能需求

- 冪等、可重跑、可追溯、可安全失敗。
- Stage → Core 寫入前的 required key、type、duplicate、time／future-leakage 與 quarantine 屬不可延後的安全邊界；完整跨源校準、quality score、DQ dashboard 與門檻調優排在 Admin／Flutter User UI 自動化、實機與 A11y 驗收之後。
- GCP services 同區以避免跨區成本。
- 統一 execution／trace ID；log redaction。
- 監控來源成功率、latency、freshness、schema drift、fallback、Job 狀態、publication 與 API error。
- 設定 Cloud Billing US$1／US$5／US$10 告警、GCS lifecycle、Artifact Registry cleanup、Workstation 自動停止。
- 不宣稱固定 $0；費用以當期定價與實際帳單為準。

## 15. Release Gate

- 2330 完成 Source → Stage → Core → Mart → API → UI 閉環。
- 同一 `analysis_as_of` 可從 `mart_daily_brief` 追溯市場狀態、板塊輪動、熱門話題、候選股及其 Core／Mart snapshot。
- 私人交易可從 PostgreSQL ledger 重建 Private Core／Mart；跨年損益、更正事件與所有權隔離通過測試，且不出現在 public index。
- 筆記、關注歷史、chat messages、context snapshot 與 citations 可從 Private Iceberg 依 authenticated user 讀取、匯出與刪除；PostgreSQL 不保存正文或完整對話 payload。
- 私人助理 OpenRouter／Gemini REST API／Codex App Server 可切換且 lineage 可追溯；驗證 Cloud Run scale-to-zero／cold start／timeout／重連、Core／Private／外部資料源 provenance、容器內 MCP stdio、遠端 Streamable HTTP／legacy SSE、動態工具、GCP Skills revision、統一 events、Codex managed auth／Items／Turns／Approvals、雲端暫存 sandbox、未授權 mutation 拒絕及 Gemini Google Search Grounding／免費額度。Codex owner-scoped auth 必須通過 A／B rotation／舊版銷毀、orphan auth deletion、session eviction／logout、cleanup retry、刪除期間拒絕寫入與 secret non-persistence；共用 auth／固定 owner 的 dev POC 不算完成。Codex 不使用直接 OpenAI API fallback；App Server dev POC 與人工 production gate 未通過不得發布。
- PIT 無 future leakage；排除樣本有原因與 provenance ID。
- blocked 不進公開 latest／history；查無資料不即時運算。
- 兩個 Job、FastAPI、Admin Web、User App 與各內嵌 DuckDB runtime 的 IAM、timeout、retry、監控與 rollback 通過。
- 全市場日頻與個人關注股深度 membership／cadence／50-symbol 營運護欄通過驗證；Admin 看不到 user-to-symbol 對應，未核准的高頻、新聞或社群來源保持 disabled／blocked。
- pytest、FastAPI contract tests、Flutter analyze／test、Vitest、Playwright、TypeScript、production build 通過。
- iOS Safari、Android Chrome、iPad Safari、VoiceOver、TalkBack、WCAG AA 實機通過。
- 無 secret、raw payload、敏感 URL、未授權來源外洩。
- 私人資料刪除狀態可查詢；`CLEANUP_PENDING` 不顯示成功，且 Iceberg snapshot／orphan file、GCS object version 的實際清除期限已有 GCP dev 證據與使用者文案。
- runbook、備份、還原與 rollback 演練完成。

## 16. Production Readiness／Dev Pilot Gate

Release gate 通過不代表直接進入 production。MVP／Dev 驗收後，必須先通過
Pilot Entry Gate，使用既有 Dev environment 執行 6 個 calendar months 的
Dev Pilot；只有 Entry Gate 通過時才記錄 `pilot_started_at`。Pilot 期間
production promotion 保持 blocked，不要求建立 staging 或 production environment，
也不自動新增 production-only GCP infrastructure。

Pilot evidence 至少涵蓋以下類別；本節只定義 evidence scope，不預設尚未決定的
pass threshold：

- Data：ingestion success／failure、freshness、coverage、missing data、schema
  drift、quarantine／retry、source stability。
- Analysis：result availability、deterministic／reproducible portions、
  provenance／citations／source coverage、適用時的 PIT／future-leakage evidence、
  model／provider／analysis revision lineage，以及人工判斷是否仍具研究價值。
- Runtime／Operations：Cloud Run Job／Service 與 Scheduler reliability、retry／
  idempotency、適用時的 cold start／timeout／reconnect、manual intervention
  frequency 與 recurring operational failures。
- Cost：actual Cloud Billing evidence、可取得時的 provider usage／cost evidence、
  resource growth trend；billing budget notification 不等於實際 spending cap。
- Security／Privacy：secret handling、owner isolation、auth lifecycle、private／
  public data boundary，以及 relevant delete／cleanup evidence。

每份用於 Pilot 判斷的重要分析結果，都必須能從現有 metadata 或 lineage 合理
追溯 data／snapshot 或 analysis time boundary、relevant source／provenance、
application／code／image revision、適用時的 analysis／skill／config revision
與 provider／model、execution identity／time，以及 result status／material warning。
這是 logical evidence requirement，不建立特定 database column 或 storage implementation。

六個月 Pilot 完成後，人工 review 至少回答：資料是否足夠可靠、分析是否具有持續
使用價值、系統是否能長期自動運作、維運負擔是否可接受、實際成本是否與價值相符，
以及 production architecture 是否有 evidence 支持升級。Outcome 為 `GO`、
`EXTEND_PILOT` 或 `NO_GO`；任何 outcome 都不得自動建立 production resource。
Production Go 不能只因「所有功能開發完成」而通過。
`GO` 只允許開始 production architecture／migration planning，不能取代後續的
人工 production approval。
