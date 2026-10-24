> **2026-10-24 政策更新**：研究數字與歷史結論保留；本文舊有逐來源／全歷史 PIT 補證、精確時間校準及新前瞻成熟等待不再是工作或發布前置。取消例行稽核，依 [研究精簡政策](../spec/research-simplification.md) 按需評估；不把取消視為 PASS。

# Valuation 04 v22｜歷史回溯可續跑補收（2026-10-24）

狀態：**CODE_DELIVERED, TESTS_PASS, LIVE_COLAB_NOT_EXECUTED**。研究、非 canonical；publication_allowed=false。

# Janus 04 Valuation｜v22 歷史回溯補收（2026-10-24）

## 為什麼要 v22

第21版 v21 的 `may_need_pre_existing_history_before` 在第20版輸出為空，所以設60月也沒有往 2023-10 以前補收；同時會因 `NULL_MULTIPLE` 重抓 `PER=0` 的月份，實際抓資料卻不產生有效月末增益。

本版把 2023-10～2026-09 既有36月全部視為已讀研究盤點範圍，不以重抓零／負倍數來硬補30；僅對 **研究候選上市/上櫃普通股，單檔單PE/PB分支 <30個正倍數月末**，用已核對的當前主檔上市日和既有正值月數，選擇有界歷史（2021-10～2023-09）定向查詢。官方今日主檔只當安全候選，不代表歷史 PIT。

## 如何執行

1. 保留原第20版6份盤點產物，路徑：`/content/drive/MyDrive/給ai專用/janusChatGPT/模型研究/valuation/preflight_30_valid_monthends_20261024/`。
2. Google Colab 開啟 `22_Valuation_04_FinMind_歷史回溯_定向補收_可續跑.ipynb`，按「執行全部」，授權掛載 Google Drive。
3. 首次使用當前官方 TWSE/TPEx 公司主檔，儲存 `official_master_v22.json`。之後從固定快照、輸入 SHA256 讀回；公司名冊或研究資料有異動不會靜默改計畫，需新版本資料夾。
4. 同一個執行流程讀回舊 v21 `raw/`+`receipts/` 並驗 SHA，**不修改**舊資料。建立 `frozen_plan_v22.json`、`v22_tasks.csv`、`v22_pairs.csv`。
5. Notebook 預設 `RUN_FETCH=True`、`MAX_CALLS_PER_RUN=5`，執行期間才詢問 FinMind 免費 Token（不存檔），以至少8秒間隔對 FinMind API 發出**真實**歷史查詢。成功就保存 raw response、SHA256 receipt。失敗保持 pending；配額拒絕則停止。
6. 每輪查看 `00_run_summary_v22.json`、`v22_valid_month_gain.csv`、`v22_task_status.csv`，包含實際請求數、歷史正值候選月新增數、已完成/未完成。若有5筆成功但新增0，下一輪拒絕擴大，先修策略。有效增益確認後可自行逐步調大單輪上限（最大25）。
7. 如中斷/重啟，再按「執行全部」沿用同一 frozen plan + receipts；已驗 SHA 的成功任務會跳過。

研究輸出寫入 `janusChatGPT/模型研究/valuation/backfill_candidates/FINMIND_MIN30_HIST_V22_20261024/`。**v21原目錄不會被本程式修改**。

## 這輪驗證及範圍

- 已用 v20 的真實 CSV 與 v21 frozen_plan 中有上市日證據的部分股票**離線**驗證：1018短缺分支中產生約311個早於2023-10的新歷史任務候選，另707分支因未確認有效現況、上市日、正值覆蓋過低或IPO不足而HOLD。這不是完整官方主檔讀回後的最終數。
- 流程模擬單元測試（IPO前排除、零正值低效阻擋、空回溯欄位仍產生真舊月、原receipt SHA校驗、計畫漂移禁止、resume零額外HTTP、30月研究計數）通過4/4。
- 2026-10-24 本地未使用使用者 Token 發出 FinMind 真實請求；只靠 Notebook 交付不可宣稱新資料已落盤。

## 不得誤認

- 一個正 PE 或 PB 月份也不等於正式已驗證月末：FinMind 資料為日序列，以月內最後實際觀測作**研究候選**，沒有官方交易月末/PIT/財報口徑/來源授權保證。
- `PER=0`、上市之前、PBR非正、多次同月紀錄、缺資料的假設補值都不能為湊滿30而轉成有效。
- `MIN_EXISTING_POSITIVE=12` 只作**補收效益初篩**，低於此數先HOLD待人工/替代合法來源查核；正式研究與模型仍依每分支30有效月及訓練/OOS合格性獨立判定。
- 財報缺季374組的來源核查不因此直接成為新 API 任務；v22 先修復估值歷史與有效月末補收，後續依本次新結果確定所需財報才補。
- `publication_allowed=false`，不修改 canonical、Registry、Risk ACTIVE、live API／UI 或持股資料，不新增付費來源。

## 核對連結

- [v22 補收Notebook](https://github.com/tommylin15/janus-omniforge/blob/main/research/colab/22_Valuation_04_FinMind_歷史回溯_定向補收_可續跑.ipynb)
- [v22 選擇器與收據程式](https://github.com/tommylin15/janus-omniforge/blob/main/research/colab/valuation_min30_v22.py)
- [四項定向測試](https://github.com/tommylin15/janus-omniforge/blob/main/research/colab/test_valuation_min30_v22.py)
- [Drive ZIP](https://drive.google.com/file/d/1aHB4oDy1otKB1i4WvctWjtYLxqHvjsyP/view)
