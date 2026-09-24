# Janus WBS — 建議里程碑

## 建議里程碑

| 里程碑 | 範圍 | 完成定義 |
|---|---|---|
| M0 | WBS 0–1 | 雲端 workspace、monorepo、CI/CD、IaC 可運作 |
| M1 | WBS 2–4 | PostgreSQL Free Tier VM → 2330 Source → Stage → DuckDB／Iceberg Core，bounded query 可冷啟動 |
| M1.5 | WBS 3 | 5 檔 canary 連續 3 個交易日後擴全市場，Stage／Core／Admin Data Operations 閉環通過 |
| M1.75 | WBS 4J | 個人交易、筆記、關注股、Private Core／Mart 與最小 Flutter 通過隔離及重跑驗收 |
| M1.9 | WBS 4R | 個人多產業曝險、年度績效／XIRR、投資屬性與 deterministic 壓力測試通過驗收 |
| M2 | WBS 5 | 市場／板塊／話題／候選健康度 Mart、30% gate 與 blocked 正確 |
| M3 | WBS 6 | 擴充 FastAPI、公開 Flutter 與 Admin governance／reports 完整讀取 persisted Mart |
| M4 | WBS 7–8 | UI 實機驗收後完成 DQ 強化、監控、安全、PIT、canary／rollback |
| M4.5 | WBS 8 Dev Pilot／Production Readiness | Pilot Entry Gate 通過；既有 Dev environment 持續運作 6 calendar months；Data／Analysis／Reliability／Operations／Cost／Security evidence 可回顧；完成 Production Go／Extend／No-Go review；沒有人工 GO 前不得宣稱 production-ready 或建立 production environment |

Janus 舊 WBS 4C 已因 Chat／Agent hard split 退役，不再列入 Janus 里程碑；歷史規劃見[封存 WBS](../archive/wbs-4c-janus-assistant-plan-superseded-2026-09-23.md)。

## Approved six-month Dev Pilot evolution mapping

Repository 沒有正式 `pilot_started_at`，因此只使用相對月份；不得把本表解讀為
已開始 Pilot，也不得把 Planned 工作寫成 Completed。

| Pilot Month | WBS | Goal | Evidence |
|---|---|---|---|
| Pilot M1 | `WBS-5-MART-FACT-PACKS`, `WBS-5-MART-AI-ROLE-CONTRACT`, `WBS-5-MART-AI-VALIDATION`, `WBS-5-MART-V2-COMPAT` | 建立 Fact Pack、role/CIO contract、validator、immutable lineage 與 mart.v1 additive compatibility；不取代既有 publication path | contract/schema fixtures、deterministic replay、validator negative cases、v1 compatibility tests |
| Pilot M2 | `WBS-5-MART-AI-PROVIDERS` | governed Gemini/OpenRouter provider abstraction、五角色 AI stage、structured failure；優先 shadow／non-authoritative | provider contract tests、capability／parameter checks、failure／retry evidence、interpretation artifacts |
| Pilot M3 | `WBS-5-MART-CIO-SYNTHESIS`, `WBS-5-MART-RERUN-CACHE` | CIO、精確單角色重跑、dependency invalidation、content-addressed reuse、execution lineage | CIO validator tests、rerun call graph、cache hit／audit evidence、new Pilot baseline／epoch |
| Pilot M4 | `WBS-6-FLUTTER-ADMIN-SHELL`, `WBS-6-ADMIN-OVERVIEW-BATCH`, `WBS-6-ADMIN-STOCK-WORKBENCH` | Flutter Admin operational migration：總覽、批次、個股、中文狀態、retry／repair；static Admin 暫留 | Flutter responsive／A11y tests、backend Admin auth acceptance、retry／repair lineage、legacy compatibility |
| Pilot M5 | `WBS-6-ADMIN-ANALYSIS-PROFILE` | Production profile versioning、role/CIO prompt、model picker、5–10 test symbols、compare、rollback、per-role override | version history、locked guardrail、comparison diff、rollback drill、cost／latency／token evidence |
| Pilot M6 | `WBS-8-PILOT-MART-AI-EVALUATION`, `WBS-6-ADMIN-LEGACY-RETIREMENT` | reliability、partial/failure、cost、cache、accessibility、browser/device、usefulness、rollback evidence；決定 legacy Admin 是否可退役 | evaluation report、rollback／browser acceptance、operational burden、GO／EXTEND_PILOT／NO_GO review evidence |
