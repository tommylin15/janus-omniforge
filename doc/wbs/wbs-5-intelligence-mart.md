# WBS-5｜Intelligence Mart 正式職責

> **2026-10-24 研究精簡決策優先**：本文涉及獨立資料稽核、逐來源補證、全歷史 PIT／精確時間校準、例行週月稽核及自然驗收等待的要求已取消，不再是待辦或發布前置。依 [研究精簡政策](../spec/research-simplification.md)，保留必要日期／單位、基本防洩漏與操作安全；歷史證據不改判 PASS。


更新：2026-10-20。本檔僅管 Janus 正式市場與五分析師結果的消費、驗證及推論，不再管研究資料採集或模型訓練。研究唯一來源：[GAS／Drive／Colab](../spec/research-collection-gas-drive-colab.md)。

## 正式留存
現有 Canonical Iceberg Core／PostgreSQL serving、日常 ingestion、market-screening、正式 Mart、Deep Coverage（watchlist ∪ holdings）、Owner 個股／ETF 行情、私人交易／現金、API/UI、Stage48h、週 Iceberg/Mart/Core retention 與備份繼續使用。公開/私人隔離、來源與 provenance、null、dirty cache、immutable Fact Pack、失敗回退保留。

## 新模型研究邊界
GAS 向合格第三方資料源收集公開上市櫃普通股；每月 ZIP 入私有 Drive `資料源`，ETF 完全不計研究母體；TWSE/TPEx 各自 dataset 品質門檻 ≥70%。先盤點現有公開欄位及非空率，時間欄位若有就標記；歷史 PIT 全面稽核不是研究採集阻擋條件。

Colab 人工做五角色 features/labels、模型 fit、OOS、版本；Mart **不再執行** Cloud Run `specialist-retrain`、B5～B8 ML/OOS 數據中轉或 BigQuery 訓練工作。Mart 只負責合格模型的 hash/品質/來源/OOS gate、Registry、正式推論、版本與回滾，未核准模型機率保持 null。

## 退役
舊 Controller 月度 due、手動流程、獨立研究 BQ 資源、雲端 ML/OOS 作業已不再是產品或模型新路線的一環。只要其他正式服務不引用就立刻移除，不等待新 GAS／Colab 完工。共用 `janus-intelligence-mart` 仍服務正式 UI 與週清理，不得整支刪掉；真實 Cloud Run/BQ 的終態必須實機讀回。

## D08／驗收
CEO 按需只用已驗證五角色 Fact Pack，Admin 模型頁維持既有位置；LLM 不產生 canonical number、不擁有 publication/Owner 權限。D07/08 實際完整狀態依 [唯一 TODO](../todo.md)、[D07 執行卡](../archive/document-cleanup-2026-10-25/execution-cards/d07-specialist-b9-oos.md) 與 live evidence。
