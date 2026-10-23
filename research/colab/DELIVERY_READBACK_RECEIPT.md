# Janus Valuation 補收 v1：GitHub／Drive 交付讀回收據

- 日期：2026-10-23；用途：研究資料工程候選；`publication_allowed=false`。
- **實作 commit（main）**：`7a1b0ed2e8e9b309bd22435eb0cb00a4367b155b`；已讀回 main head 與八個 Git blob SHA，全部符合提交內容。
- **共用 Python 內容 SHA256**：`c7d05cda416dc64505374f317f7970c31a3efbc509bfe3259025a55d5b26e1dd`；獨立 Colab Notebook 執行時會比對此值。
- **Drive 根及程式目錄**：`janusChatGPT/CoLab程式`，Folder ID `1-a_83LAVVyHzBHafck3xAyDDWRXLTWes`。
- Drive 模組 ID：`1caRUCJoqvBESQLLikyZXj0n0vn9qob4n`；Notebook ID：`1oidP0V8mpDWcM3fDDRE9Zk4_RWFt1DBL`；測試 ID：`1uLIMBgyEoZ8w7WieBC9kDOHq6EMRFvar`；README ID：`1zQC2_2TkPZCZ3j6VZZ_USEGzWOgbd-GK`；ZIP ID：`1yqE7BdIKc7lkC48hKOhYFCRpy0s3VPzW`。
- GitHub 與 Drive 各檔案已做 connector 讀回，檔案位元組長度符合本地來源，GitHub blob SHA 符合。此項 **PASS 僅代表程式版本同步**，不代表 Colab 執行、來源取得或模型成功。
- **本地測試**：`python -m pytest -q tests/test_valuation_backfill.py`，15 passed；Notebook JSON 與 Python code cell 語法檢查 PASS。這些使用 fixture，不是即時資料來源驗收。
- **實際輸入指紋**：Drive `CURRENT.json` 指向 `release-0bbae8d9c1ca7d8d`，指標 SHA256 `0b64ac6927805fb98260121da94624d7e08ac423f0aa13b8349d4c304f0135cd`，manifest SHA256 `7b80d441efabbc307d359ea5d15cd9202ccee5e2930cf4c3cc337496c95eb542`；manifest 記載 155 檔。逐一讀取全部 Parquet/hash 與實際因子覆蓋：`NOT_VERIFIED`。
- **技能可用性**：查找 `recovering-stuck-ci-deploys`，未提供；`/ponytail-review` 無可呼叫入口，改用本地差異／契約檢查與適用測試，**不宣稱曾執行該指令**。
- **未執行**：全量補收、任何模型訓練／模型發布／GCP 部署、Registry 修改、canonical/CURRENT.json 寫入。
- **尚未完成**：live smoke（無 Colab session 或 API secret）、所有原始科目 mapping/PIT 認證、TTM/ROE 等完整衍生因子、產業分類歷史追蹤、實際覆蓋統計；本版工程整體狀態為 `PARTIAL`。
- 原 `LOCAL_TEST_REPORT.json` 是 GitHub/Drive 同步前的本地測試紀錄，其中 `github_commit=NOT_DONE`/`drive_sync=NOT_DONE` 為當時狀態；**本交付讀回收據是較新的同步狀態**。
