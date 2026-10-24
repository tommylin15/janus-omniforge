# D07-PRE｜研究資料可行性／最新架構

> **2026-10-24 研究精簡決策優先**：本文涉及獨立資料稽核、逐來源補證、全歷史 PIT／精確時間校準、例行週月稽核及自然驗收等待的要求已取消，不再是待辦或發布前置。依 [研究精簡政策](spec/research-simplification.md)，保留必要日期／單位、基本防洩漏與操作安全；歷史證據不改判 PASS。


**2026-10-20 改版。** 本文先前的 Cloud Run／PyIceberg frozen export／BigQuery→Colab 研究訓練必經路線、兩年 PIT Census 開工 gate、舊 Mart monthly retrain 和 FINOPS-C 必須先行的前提均已失效。唯一有效研究資料規格為 [GAS→Drive 每月 ZIP→Colab](spec/research-collection-gas-drive-colab.md)，工程進度依 [TODO](todo.md)。

## 目前決策
- **資料收集**：GAS 直接存取合格第三方 API，分批續跑，按 `YYYY-MM.zip` 寫入私有 Google Drive `janusChatGPT/資料源`。不經 Cloud Run、Core、BigQuery 或 GCS 中轉。
- **訓練股票**：全部 TWSE 與 TPEx 普通股，排除 ETF／ETN／非普通股。研究 coverage 各市場×各資料集均 ≥70%；正式 Core 90%／70% 與 Owner 支援獨立。
- **先做什麼**：以既有持股／觀察股公開欄位核對資料源，先量測欄位可得性與真實有效值；時間資料以欄位標籤保存，不強制 24 月連續資料或歷史 PIT 時點先達標。
- **建模**：Colab 免費版人工執行，五分析師獨立 baseline/OOS；正式使用仍檢查成熟標籤、future leakage、來源、品質及 rollback。
- **立即清理**：既有 Cloud Run 月度 `specialist-retrain`、手動派送、只為舊訓練研究存在的 BQ/ML-OOS 支線不再保留，正式 Screening、行情、Owner、API、週維護和備份保留。舊程式停用與雲端刪除分別查證，不等新路徑上線。

## 尚未完成
未實測 GAS 全市場抓取、月份 ZIP 封存、Colab 模型、GCP live 停派、BigQuery 實際重疊刪除。保持 `NOT_VERIFIED`，不能拿更新文件或以前 B5/B6 benchmark 當完成證據。

舊 B5–B9 benchmark 只保留為歷史研究證據，不作新資料來源或模型設計的強制條件。
