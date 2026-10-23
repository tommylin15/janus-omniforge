# Janus／OmniForge｜Colab 四模型研究工作流（03～11）

本套 Notebook 對應使用者指定的第 3～11 階段，**全部可在 Google Colab 操作**。流程使用 GitHub `tommylin15/janus-omniforge` 的已實作程式，**不新增或覆寫 canonical，沒有正式發布權限**。每支 Notebook 可單獨開啟；自動讀取同一個研究 run 的 `ACTIVE_RUN.json`，固定 `CURRENT.json` SHA、manifest SHA、Git SHA。若 upstream source 或 code 變動，fail closed。

使用順序：

1. `03_收檔驗收與Drive同步.ipynb`：掛載 Drive；固定 release、研究 run 與 Git SHA；逐檔 SHA + footer row count；可選用 GitHub Actions artifact 比對與唯讀保存。預設不需要 GitHub Token。
2. `04_資料包全量Preflight.ipynb`：呼叫 `label_four_models.py --verify-only` 和 `market_sector_package_preflight.py`；2025-01 至 2026-09 一次全期。
3. `05_四模型XY建立.ipynb`：呼叫既有 `label_four_models.run()`；以 `training_panel` 實算各模型 X/Y 並分開保存，記錄 34 個 X 指定席位的可用性；Valuation 缺證據型 mapping 時標 BLOCKED。
4. `06_Quant訓練.ipynb`、`07_Risk研究驗證.ipynb`、`08_Fundamental訓練.ipynb`、`09_Valuation訓練.ipynb`：呼叫 `janus_train.run()`；比較第 5 階段 X/Y 的 SHA，一致才結案。`mode=retrospective`，不冒稱真正 forward OOS。四支可以依順序分別執行。
5. `10_模型結果同步Drive.ipynb`：訓練產物 hash 檢查後歸檔到 `janusChatGPT/模型研究/<role>/<run_id>/<fingerprint>/`。
6. `11_候選模型評估.ipynb`：依 `reports/result.json`、baseline、成對時間區塊增益、切片回報研究建議，不更動 Risk ACTIVE。

**掛載路徑**：`/content/drive/MyDrive/給ai專用/janusChatGPT`，不是 `個人用`。只有 Stage 03 能建立新研究 run；如需重開新 run，將它的 `NEW_RUN=True`。不要切換 `ACTIVE_RUN` 的任何 SHA 去套用舊訓練資料。

**GitHub Actions artifacts**：Stage 03 對既有 Drive 研究 release 做完整真實驗收；Actions ZIP 只有在設定 `GITHUB_RUN_ID` 時額外下載留存研究證據。此步**不會將未知 ZIP 檔內容升格／覆寫不可變來源**，也不自動啟動第二階段採集；不設定 Run ID 需保持 artifact 狀態 UNKNOWN。

**Valuation evidence**：模型必須有 `janusChatGPT/模型研究/_config/valuation_financial_mapping.json`，至少包含 `metrics.roe`、`metrics.debt_ratio`、`metrics.log_total_assets`、`metrics.revenue_yoy`、具日期和 evidence 的 `cohorts`、有效 `calendar_evidence`。實際欄位精確配置依 GitHub `janus_precision.valuation_panel`，不得假造會計科目、單位、歷史 PIT 或產業歸屬。現有資料不足時 Stage 05/09/10/11 會保留 partial/block 收據而不是出空模型假通過。

**已知驗證界線**：2026-10-23 初步檢查全部 155 個 CURRENT 引用檔 SHA 及 153 個 Parquet footer rows 已通過，但 `revenue/2022-09.parquet` 的 `unit_basis` physical schema 不一致。本套 Colab Stage 04 loader 能進一步確認是否可完整解碼。TWSE/TPEx 485 分區是前一輪預期基準，不得為湊基準修改資料。

**本套版本的驗收**：Notebook JSON schema、所有 Python code cell 語法與基本契約的靜態檢查可在 ChatGPT 完成；沒有替你登入 Colab 執行 Google OAuth、也沒有宣稱 live Drive 全量 04～11 已 PASS。正式 runtime acceptance 以各 stage 的 `*_status.json` 與實際結果為準。
