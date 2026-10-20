# Janus — 唯一 Active TODO

更新：2026-10-20。**只列尚未完成的工作與原定驗收，不收納歷史失敗、已結案工程、無具體異常的推測性追查。** 狀態以 GitHub `main`／真實 CI、deployment 與 runtime 為準；結案遵循 [PROJECT_RULES §1.1.1](PROJECT_RULES.md)。

## 1. 現行優先順序

| 優先 | 工作包 | 已完成 | 尚需完成 |
|---|---|---|---|
| **P0** | **STAGE-48H** | 48h Stage TTL／過期資料受控實刪、跨 execution shared raw/provenance、四 Jobs 更新與獨立讀回 PASS | **自然 18:30 Stage-only 執行驗收；Admin 六桶 OAuth 登入後一鍵正向驗收** |
| **P1** | **D07-PRE｜Colab／Drive 資料源** | 官方歷史整市場 Colab 採集器、普通股白名單、每月資料夾/續跑/雜湊及 Risk 資料讀取已實作並有本地 targeted tests；舊 GAS/GCP/BQ 研究路線退出 | **Colab 官方 API 實抓 → 每月資料夾品質／SHA 讀回 → 補歷史已下市股票母體證據／正式 70% 分母** |
| **P2** | **D07｜五分析師建模** | 五角色規格、OOS／registry 責任界線已定案 | **Colab 模型訓練與 OOS；Janus Mart 受控模型匯入、推論與 Admin 品質呈現** |
| **P3** | **D08｜CEO／Admin／Owner 報告** | 原 Gateway 技術驗證可重用 | **有效 Fact Pack → CEO 手動請求 → Gateway／validator → immutable 報告與 Owner UI／Admin 管理驗收** |

## 2. STAGE-48H｜僅餘兩項原定驗收

- [ ] **每日自然排程**：於 2026-10-20 18:30 Asia/Taipei 發生後核對正式 `janus-ingestion-daily`／Stage-only occurrence、終態、到期資料處理結果與週 Iceberg 維護不變。**時點尚未到，不因等待自然事件重啟已通過的部署或歷史清理**。
- [ ] **Admin 六桶正向操作**：真實 Admin OAuth 授權操作，一鍵讀回既有六桶 metadata、權限與部分失敗顯示；匿名拒絕 401 已 PASS，不能代替 Admin 正向驗收。

已完成證據：[GHCR／四 Jobs #39355867356／#39356643823](https://github.com/tommylin15/janus-omniforge/actions/runs/39356643823)、[獨立 readback #39358461946](https://github.com/tommylin15/janus-omniforge/actions/runs/39358461946)、[Stage 實刪 4,927 件／96,321,204 bytes #39355428497](https://github.com/tommylin15/janus-omniforge/actions/runs/39355428497)、[shared raw/provenance #39358645373](https://github.com/tommylin15/janus-omniforge/actions/runs/39358645373)、[48h dry-run 零候選 #39359037869](https://github.com/tommylin15/janus-omniforge/actions/runs/39359037869)。歷史細節集中 [Operations](spec/operations-and-testing.md)，不在 Active TODO 重複列流水帳。此項由原 Stage 對話承接，與 D07-PRE 分開。

## 3. D07-PRE｜Colab 官方歷史資料採集與每月資料夾

**新架構（2026-10-20）**：GAS 方案已退役，不保留 GAS 安裝、OAuth、Loader 或人工 GAS 實跑待辦。程式：`research/colab/collect_tw_equities.py`、`monthly_folder_io.py`、`run_risk_folder_pilot.py`；Drive 結構：`janusChatGPT/資料源/YYYY-MM/{ohlcv-r1.csv.gz,universe-r1.csv,quality-r1.json,manifest-r1.json}`。官方 TWSE/TPEx 逐日整市場取數，最新公司名冊白名單先排除 ETF 等；來源請求限速，10 平日 checkpoint，完整月封存後驗 hash 並清掉中繼碎檔。資料研究用途 `PROBE`、現行名冊歷史涵蓋限制明確保留。此前 GAS 程式僅存 Git 歷史及舊 Drive 備份，無現役引用。

- [ ] **Colab 真實歷史採集驗收**：先跑閉合月份範圍（建議 2025-01～2026-09），讀回 TWSE／TPEx 真實來源、API schema、實際成功／休市／失敗日期、股票數及每月資料夾 manifest SHA；已有程式及 fixture PASS 不等於真人 Colab 已執行。
- [ ] **正式歷史母體／品質修復**：現行公司名冊無法收錄已下市股票；如要宣稱歷史普通股全市場與每市場×dataset×月份 ≥70%，需先補歷史合格名冊證據、查核適用分母及公司行動；首輪資料只能是 `PROBE`，不造假完成。
- [ ] **Colab Risk OOS**（屬 D07 品質驗證）：對真實封存月資料直接執行 OOS，和 baseline 比較；不可因生成模型或存檔而自動 publication。

[唯一研究資料 SPEC](spec/research-collection-gas-drive-colab.md)；[Colab 執行說明](../research/colab/README.md)。已結案舊 GCP/BQ 研究清理保持 CLOSED，不重開。

## 4. D07｜五角色模型與正式介接

- [ ] **模型與研究評估**：Quant／Risk 優先；Valuation／Fundamental 依資料可得性；Event 缺合規真人標籤維持 rules。與 deterministic baseline 在同一時間外 OOS／成熟標籤／資料來源下評估，禁止 future leakage。
- [ ] **受控模型匯入與應用**：Colab model／evaluation 版本及 hash → Janus Mart Registry、推論、rollback、Admin 模型品質／狀態展示；不恢復舊 Cloud Run/BQ 訓練器。

[D07 唯一任務卡](execution-cards/d07-specialist-b9-oos.md)。

## 5. D08｜CEO／Admin／Owner 報告

- [ ] **正式整合與驗收**：具來源的有效 Fact Pack → Owner 手動 request → 現有 OmniGateway／Gemini → validator → immutable GCS／PG → Owner history／UI 與 Admin 設定／權限／回滾 readback；LLM 不決定 canonical 數字或最終 publication。

[D08 唯一任務卡](execution-cards/d08-ceo-admin-owner-report.md)。正式報告依賴 D07 有效模型輸出，但**已結案的 FINOPS-AB／D06／舊 B5～B8 不得成為重新施工的前置條件**。

## 6. 已結案、不再列待辦

D01～D05、DRL-01、FINOPS-AB（含 D06）、既定背景持股／關注股補收、Admin v2、舊研究 GCP 工作及排程退役、BigQuery 舊 ML/OOS 中介資源清理，均依已核准的原驗收邊界 **CLOSED／PASS 或 USER_ACCEPTED**。收據保留在 [結案索引](wbs/completed-index.md)／[Operations](spec/operations-and-testing.md)／[archive](archive/d07-gcp-bq-retirement-live-2026-10-20.md)，**不因未列舉所有理論可能性新增待辦**。新缺陷須有實際證據，再依當次工作包處理。
