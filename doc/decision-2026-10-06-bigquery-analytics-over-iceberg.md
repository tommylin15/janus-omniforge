# BigQuery / Iceberg Hybrid 歷史決策（已退休）

> **2026-10-24 研究精簡決策優先**：本文涉及獨立資料稽核、逐來源補證、全歷史 PIT／精確時間校準、例行週月稽核及自然驗收等待的要求已取消，不再是待辦或發布前置。依 [研究精簡政策](spec/research-simplification.md)，保留必要日期／單位、基本防洩漏與操作安全；歷史證據不改判 PASS。


2026-10-20 起，此文件**不再是 Active D07-PRE/D07 的建模或資料來源決策**。原 BigQuery ML/OOS SQL 中轉、Core snapshot training export、Cloud Run 月度 `specialist-retrain` 等 B0～B8 研究流程已被 [GAS→Drive ZIP→Colab](spec/research-collection-gas-drive-colab.md) 取代，**不應重啟、保留排程或作為新模型前置**。過往 benchmark、成本與可稽核證據仍可從 Git 歷史與 archive 追溯。

正式 Janus Core Iceberg/PostgreSQL serving、行情、Market Screening、Owner／ETF、API、週維護和備份維持各自現行契約。大數據研究所用 BQ 表／view／排程如無正式服務引用，**立即清理，不需等新研究管線上線**；若有正式引用須明列資源與相依關係再移除，不能依名稱盲刪。

實際 BigQuery 物件是否刪除、釋放多少 bytes 只有 live inventory 與 delete/readback 能證明，不以本文修改宣稱成功。唯一工作佇列：[TODO](todo.md)。
