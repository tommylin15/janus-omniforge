# D07 四模型 v3.8.2｜收資料／貼標兩入口（2026-10-23）

## 唯一兩個工作入口

1. **Colab 收集**：`00_資料收集_v3.8.2_Colab.ipynb`（`research/colab/00_資料收集_v3.8.2_Colab.ipynb`）。保留 v3.8.1 原始採集模組、授權限額、官方 fallback、10 日 checkpoint、來源品質、v3.7 大盤 C1 probe、不可變 Parquet `canonical/CURRENT.json`。`FACTOR_ONLY=False` 預設做增量補收；`RECHECK_ONLY=True` 可只驗資料；`FACTOR_ONLY=True` 可跳過收集並搭配 probe。此 Notebook **沒有**四模型 X/Y 計算與貼標。
2. **ChatGPT 貼標**：`research/chatgpt/label_four_models.py`。本地需有完整的 `CURRENT.json`、manifest、全部指定的 Parquet／conflicts。處理 SHA256、列數、欄位、日期缺口、收入連續月份、RMS 預測目標與 X/Y 物理隔離；寫入獨立 output root 的 `derived/four_model_precision/v3.8.2-<digest>/`，嚴禁修改 canonical，`publication_allowed=false`。

依賴：`factor_factory_v1.py` 與 `janus_precision.py` 是**第二支程式的純運算 helper**，不是第三條收集管線；`janus_train.py` 保留未來 ChatGPT 側四模型 XGBoost 研究介面，**不在 Colab 跑模型**。既有四份 v3.8.1 模型 Notebook 只作研究歷史參考，含 Colab mount 的格子不得當未來模型執行入口。

### 在 ChatGPT 工作環境

```bash
python -m pip install numpy pandas pyarrow scikit-learn xgboost
python research/chatgpt/label_four_models.py \
  --dataset-root '/mnt/data/JanusDataset_v3_202610' \
  --output-root '/mnt/data/JanusResearch' --verify-only
python research/chatgpt/label_four_models.py \
  --dataset-root '/mnt/data/JanusDataset_v3_202610' \
  --output-root '/mnt/data/JanusResearch'
python -m pytest -q tests/test_four_model_split.py
```

**ChatGPT 可以透過已授權的 Drive 連線讀檔，但不能假定 Colab 專屬的 `/content/drive` 自動在 ChatGPT 本地出現。** 必須透過已驗證的 Drive 檔案讀取或檔案包，把 `CURRENT.json` 指向的實際 immutable release 同步至可讀工作目錄；沒有 Parquet 檔就維持 BLOCKED，不補造資料。較大 release 可分批同步，核對 SHA，絕不先把 manifest 的 row count 當完成實跑。

### 研究時點與發布政策

Quant 與 Risk 交易日切分及成熟 H=20；Fundamental 使用真實 m+1 與 m−11 月份，strict 必須有公告可得證據；Valuation logPE/logPB 的當日價格/倍數不得作 X，財務比率/cohort/effective-dated mapping 未驗時標 BLOCKED。`research_only` 不可提升為正式 canonical；現役 Risk v1 不改、不重訓、不切 ACTIVE。模型在 ChatGPT 端以版本固定輸入執行、不使用訓練資料外的未來資訊，四模型品質、OOS 與 publication gate 獨立驗收。

### 雙保存版本

GitHub main `research/colab/`、`research/chatgpt/`、`tests/`、`doc/research/` 為工程版本；Drive `janusChatGPT/CoLab程式/` 存同名收集 Notebook、貼標與 helper、測試以及文件。文件記錄兩份檔案 SHA，以實際 commit 和 Drive 讀回為準。原 v3.8.1 包保留為歷史候選，不覆寫。

### 驗收界線

- 本地：Notebook JSON/cells/code compile、沒有貼標和訓練副作用、貼標器 dry-run／正向導出／SHA 拒絕／缺交易日／缺月份／maturity 與兩份 X/Y 隔離；保留 pytest 收據。
- 雲端：Colab OAuth / 官方來源新採集沒有在此工作環境直接執行，不宣稱 PASS；ChatGPT full dataset 端到端與四模型實際重訓亦須等完整 release 本地可讀後另行驗證。

## 個股歷史產業歸屬 PIT 貼標前檢查（2026-10-23）

ChatGPT 側 `research/chatgpt/label_four_models.py` **每次** `--verify-only` 與研究貼標前，均呼叫 `research/chatgpt/industry_membership.py` 的 `check_industry_membership`。

- 指定研究輸入：`derived/factor_inputs/industry_membership/industry_membership.parquet` 與同目錄 `manifest.json`，不是 Colab 收到的市場／產業指數。必須驗證 Parquet SHA、row count、schema、每筆來源在 manifest 登記之 SHA/授權用途、歷史首次公開時間、官方主要產業時間區間唯一性。
- 主要產業一時點唯一（TWSE_OFFICIAL/TPEX_OFFICIAL 按市場），次產業／theme／supply_chain 可多重重疊；`valid_to` 右開。交易日 X 只允許 `published_at` 嚴格早於該台灣交易日的來源證據，今日分類不得倒填歷史。
- preflight 結果納入貼標輸出 `industry_membership_precheck.json`、`readiness.json` 與輸出版本身份；缺失、schema 無效、授權未知、PIT 未證、覆蓋率不足須明列 `MISSING/BLOCKED/PARTIAL_COVERAGE`。仍允許**不依賴產業**的其他候選 X/Y；產業因子和指數 crosswalk **未自動加入**任何模型 X。使用 `--require-industry` 可要求完整 `VERIFIED` 才允許任何輸出。
- 本地 pytest：41 passed, 6 skipped（缺 pyarrow）；尚無已驗證的逐股歷史產業名冊、正式 index crosswalk 或 live 全量驗收。現役 Risk/Registry/CURRENT 均未更動。
- Drive 白名單 `janusChatGPT/CoLab程式` 保存新 label、helper、測試與 `README_產業歸屬貼標前檢查.md`。舊 v3.8.2 ZIP 仍屬歷史候選，非本次新 code。
