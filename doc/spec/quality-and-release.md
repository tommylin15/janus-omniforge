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
- `codex`／`chatgpt`／`gemini` 可明確切換且不混淆 lineage；OpenAI API key／Responses API／Codex API 路徑不存在，Codex tools 無 shell／寫入／Admin／交易 mutation 權限，Gemini grounding 顯示來源且成本 hard limit 可驗證。
- PIT 無 future leakage；排除樣本有原因與 provenance ID。
- blocked 不進公開 latest／history；查無資料不即時運算。
- 兩個 Job、FastAPI、Admin Web、User App 與各內嵌 DuckDB runtime 的 IAM、timeout、retry、監控與 rollback 通過。
- 全市場日頻與個人關注股深度 membership／cadence／50-symbol 營運護欄通過驗證；Admin 看不到 user-to-symbol 對應，未核准的高頻、新聞或社群來源保持 disabled／blocked。
- pytest、FastAPI contract tests、Flutter analyze／test、Vitest、Playwright、TypeScript、production build 通過。
- iOS Safari、Android Chrome、iPad Safari、VoiceOver、TalkBack、WCAG AA 實機通過。
- 無 secret、raw payload、敏感 URL、未授權來源外洩。
- runbook、備份、還原與 rollback 演練完成。
