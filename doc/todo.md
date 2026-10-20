# Janus — 唯一 Active TODO

更新：2026-10-20。**只列尚未完成的工作與原定驗收，不收納歷史失敗、已結案工程、無具體異常的推測性追查。** 狀態以 GitHub `main`／真實 CI、deployment 與 runtime 為準；結案遵循 [PROJECT_RULES §1.1.1](PROJECT_RULES.md)。

## 1. 現行優先順序

| 優先 | 工作包 | 已完成 | 尚需完成 |
|---|---|---|---|
| **P0** | **STAGE-48H** | 48h Stage TTL／過期資料受控實刪、跨 execution shared raw/provenance、四 Jobs 更新與獨立讀回 PASS | **自然 18:30 Stage-only 執行驗收；Admin 六桶 OAuth 登入後一鍵正向驗收** |
| **P1** | **D07-PRE｜GAS／Drive 資料源** | 新研究契約及小範圍 GAS 欄位探測程式已提交；舊 GCP/BQ 研究執行器 **CLOSED** | **公開欄位實測 → 分批 GAS 採集與月 ZIP → Drive 品質／SHA 讀回、Colab 讀取準備** |
| **P2** | **D07｜五分析師建模** | 五角色規格、OOS／registry 責任界線已定案 | **Colab 模型訓練與 OOS；Janus Mart 受控模型匯入、推論與 Admin 品質呈現** |
| **P3** | **D08｜CEO／Admin／Owner 報告** | 原 Gateway 技術驗證可重用 | **有效 Fact Pack → CEO 手動請求 → Gateway／validator → immutable 報告與 Owner UI／Admin 管理驗收** |

## 2. STAGE-48H｜僅餘兩項原定驗收

- [ ] **每日自然排程**：於 2026-10-20 18:30 Asia/Taipei 發生後核對正式 `janus-ingestion-daily`／Stage-only occurrence、終態、到期資料處理結果與週 Iceberg 維護不變。**時點尚未到，不因等待自然事件重啟已通過的部署或歷史清理**。
- [ ] **Admin 六桶正向操作**：真實 Admin OAuth 授權操作，一鍵讀回既有六桶 metadata、權限與部分失敗顯示；匿名拒絕 401 已 PASS，不能代替 Admin 正向驗收。

已完成證據：[GHCR／四 Jobs #39355867356／#39356643823](https://github.com/tommylin15/janus-omniforge/actions/runs/39356643823)、[獨立 readback #39358461946](https://github.com/tommylin15/janus-omniforge/actions/runs/39358461946)、[Stage 實刪 4,927 件／96,321,204 bytes #39355428497](https://github.com/tommylin15/janus-omniforge/actions/runs/39355428497)、[shared raw/provenance #39358645373](https://github.com/tommylin15/janus-omniforge/actions/runs/39358645373)、[48h dry-run 零候選 #39359037869](https://github.com/tommylin15/janus-omniforge/actions/runs/39359037869)。歷史細節集中 [Operations](spec/operations-and-testing.md)，不在 Active TODO 重複列流水帳。此項由原 Stage 對話承接，與 D07-PRE 分開。

## 3. D07-PRE｜只負責新研究資料及 Colab 輸入

- [ ] **實際公開欄位探測**：以既有 `research/gas/field_probe.gs` 驗證 FinMind 等來源可用欄位、資料值、授權用途與缺值，先取小範圍合法普通股樣本；目前僅程式提交，沒有真實採集 PASS 收據。
- [ ] **GAS → Drive 月檔**：批次／checkpoint／續跑、provenance、`YYYY-MM.zip`、quality／manifest／content SHA、實際 TWSE／TPEx 普通股分市場×dataset ≥70% 驗收；來源缺值不造假，ETF 不進研究母體。
- [ ] **Colab 資料讀取準備**：確認實際研究月檔能由免費 Colab **人工執行**、檢查 schema/hash 並重跑讀取；模型 fit、OOS 與 promotion **只列 D07，不在 D07-PRE 重複計工項**。

[唯一研究資料 SPEC](spec/research-collection-gas-drive-colab.md)；已核准 R1：Colab 人工啟動。舊 `specialist-retrain`／GCP Jobs／Scheduler／BQ ML/OOS 清理 **CLOSED**，只有[單一歷史收據](archive/d07-gcp-bq-retirement-live-2026-10-20.md)，不重開。

## 4. D07｜五角色模型與正式介接

- [ ] **模型與研究評估**：Quant／Risk 優先；Valuation／Fundamental 依資料可得性；Event 缺合規真人標籤維持 rules。與 deterministic baseline 在同一時間外 OOS／成熟標籤／資料來源下評估，禁止 future leakage。
- [ ] **受控模型匯入與應用**：Colab model／evaluation 版本及 hash → Janus Mart Registry、推論、rollback、Admin 模型品質／狀態展示；不恢復舊 Cloud Run/BQ 訓練器。

[D07 唯一任務卡](execution-cards/d07-specialist-b9-oos.md)。

## 5. D08｜CEO／Admin／Owner 報告

- [ ] **正式整合與驗收**：具來源的有效 Fact Pack → Owner 手動 request → 現有 OmniGateway／Gemini → validator → immutable GCS／PG → Owner history／UI 與 Admin 設定／權限／回滾 readback；LLM 不決定 canonical 數字或最終 publication。

[D08 唯一任務卡](execution-cards/d08-ceo-admin-owner-report.md)。正式報告依賴 D07 有效模型輸出，但**已結案的 FINOPS-AB／D06／舊 B5～B8 不得成為重新施工的前置條件**。

## 6. 已結案、不再列待辦

D01～D05、DRL-01、FINOPS-AB（含 D06）、既定背景持股／關注股補收、Admin v2、舊研究 GCP 工作及排程退役、BigQuery 舊 ML/OOS 中介資源清理，均依已核准的原驗收邊界 **CLOSED／PASS 或 USER_ACCEPTED**。收據保留在 [結案索引](wbs/completed-index.md)／[Operations](spec/operations-and-testing.md)／[archive](archive/d07-gcp-bq-retirement-live-2026-10-20.md)，**不因未列舉所有理論可能性新增待辦**。新缺陷須有實際證據，再依當次工作包處理。
