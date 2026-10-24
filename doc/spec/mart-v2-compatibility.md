# Mart compatibility 現況

> **2026-10-24 研究精簡決策優先**：本文涉及獨立資料稽核、逐來源補證、全歷史 PIT／精確時間校準、例行週月稽核及自然驗收等待的要求已取消，不再是待辦或發布前置。依 [研究精簡政策](research-simplification.md)，保留必要日期／單位、基本防洩漏與操作安全；歷史證據不改判 PASS。


使用者已要求刪除舊五角色，不留 compatibility 執行入口。原 sidecar、舊 AI 契約與驗收腳本已移除；歷史成果物保留作稽核，不重寫、不遷移、不執行封存程序。

目前 canonical report schema 為 `packages/contracts/mart.v2.json`，五分析師使用獨立 `packages/contracts/specialist.v1.json`，CEO shape 為 `packages/contracts/ceo.v1.json`。既有歷史 public report index 可繼續讀取，不授予新 specialist publication 權限。

現在的執行與限制見 [五分析師契約](specialist-engines.md)，舊契約僅見 [封存證據](../archive/mart-compatibility-before-specialist-removal-2026-10-03.md)。
