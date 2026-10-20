# D07-PRE｜Risk Analyst 第一個研究試點

**範圍**：個人非商業研究、上市／上櫃普通股小樣本。這是第一個角色的 **PROBE**，不是全市場 70% 合格月檔，也不是正式 Janus 模型。正式市場資料、Owner 資料、API、Mart、GCP、Scheduler 均不修改。

## GAS 資料入口

將 `research/gas/risk_monthly_pilot.gs` 放入既有私有 GAS 專案，設定 Script Properties：

- `JANUS_RESEARCH_FOLDER_ID`：`janusChatGPT/資料源` 的私有 Drive folder ID（不得放在程式或 GitHub）
- `JANUS_FINMIND_LICENSE_ACK=true`：人工核對來源授權、目前帳戶非商業範圍、留存和訓練條款；若無法確認，不執行採集
- `JANUS_RISK_START_MONTH=2025-01`、`JANUS_RISK_END_MONTH=2026-09`：示例範圍，不是預設自動執行
- `JANUS_RISK_SYMBOLS`：最多 10 個上市/上櫃普通股，盡量各市場都有；勿填 ETF 或任何 Owner 私人資訊
- `JANUS_RISK_REVISION=r1`（選填），`JANUS_FINMIND_TOKEN`（選填；只能放 Script Properties）

手動執行 `janusRiskPilotCollect()`，若回報 `PARTIAL`，重跑同一函式，直到 `PROBE_ARCHIVED`。每回合至多 8 次 FinMind 請求、12.5 秒間隔；已落地的每檔 shard 不重抓，同 revision 已存在的 ZIP 不覆寫。發現資料源限額、條款或帳戶限制時停止並保留原始錯誤狀態，不嘗試繞過。

輸出僅位於 `janusChatGPT/資料源/_pilot_risk/r1/YYYY-MM.zip`；正式月檔 `資料源/YYYY-MM.zip` 由日後全市場合格流程建立。每個試點 ZIP 含規格要求的檔名、檔案 SHA256、來源、時間與 `PROBE` 品質標記；尚無資料的 dataset 保持空檔、標 `UNAVAILABLE`，**不補造**。首版未提供 benchmark、adjusted_close、Beta、Regime probability，不發布模型。

## Colab 人工實驗

在私有 Colab 掛載 Drive，將欲使用的各月 ZIP 路徑傳入：

```bash
!pip -q install pandas numpy scikit-learn
!python research/colab/risk_pilot.py --cutoff 2026-03-31 --result risk_pilot_oos.json /content/drive/MyDrive/janusChatGPT/資料源/_pilot_risk/r1/2025-*.zip
```

> Shell 萬用字元須由 notebook shell 正確展開；Drive 若非位於 MyDrive 此路徑，依實際掛載點調整。此命令為操作範例，非已完成實跑的證據。完整樣本通常需要足夠的 60 日特徵暖機、20 日成熟標籤及 OOS 區間。

`risk_pilot.py` 檢查月 ZIP 欄位與 SHA、股票／日期重複、上市／上櫃市場；先以過去 20 日歷史波動作 baseline，再使用過去 20/60 日特徵訓練 Ridge challenger，目標是**之後 20 個交易日**的已成熟實際波動。訓練只用在 cutoff 已成熟的標籤，OOS 日期晚於 cutoff；輸出兩者 MAE/RMSE、樣本數與來源 hash。研究評估無法自動授權正式使用，所有輸出固定 `RESEARCH_OOS_ONLY_NOT_PROMOTABLE`、`publication_allowed=false`。

建議驗收：既有 10 檔小樣本真實 GAS 取值 → 21 個月 ZIP／manifest hash → Colab 讀回並輸出 OOS 比較。若 challenger 不勝 baseline，保留 baseline，不為了建立 ML 而硬上線。大盤 benchmark、Beta／CVaR、公司行動調整、source training-use 與 70% 全市場品質依現行 D07-PRE 規格另做，不混成試點 PASS。

本地 targeted tests：`python -m pytest -q tests/test_research_risk_pilot.py`。Google GAS 必須經真實執行收據才可標 `COLLECTED`；Colab 必須有真實 OOS 結果才可標 `OOS_VALIDATED`。
