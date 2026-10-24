> **2026-10-24 政策更新**：研究數字與歷史結論保留；本文舊有逐來源／全歷史 PIT 補證、精確時間校準及新前瞻成熟等待不再是工作或發布前置。取消例行稽核，依 [研究精簡政策](../spec/research-simplification.md) 按需評估；不把取消視為 PASS。

# D07｜Quant v3.6 ChatGPT 真資料研究試訓（2026-10-23）

狀態：**RESEARCH_EVALUATED／NOT DEPLOYABLE**。本文件只記錄單次 research run 的已觀察事實；非模型正式發布、GCS candidate、Registry 或 dev LIVE 讀回。不可作為 Risk v1 改版或跨 Job 快取提前施工的依據。

## 輸入與原始碼證據

- Drive [`01_Quant趨勢_XGBoost.ipynb`](https://drive.google.com/file/d/1TtaQUUjlvKmlBzV2ZRFqmrxXndzbVDnV/view) v3.6；內嵌共用原始碼 SHA256：`5cf141b9526e375e51fc9c67070faad645aef26c12dbe98f8615ea7bf027ed73`，與原樣取出的 Python 核對 PASS。
- Drive `JanusDataset_v3_202610/canonical/CURRENT.json` 指向 `release-0bbae8d9c1ca7d8d`；CURRENT SHA256 `0b64ac6927805fb98260121da94624d7e08ac423f0aa13b8349d4c304f0135cd`、release manifest SHA256 `7b80d441efabbc307d359ea5d15cd9202ccee5e2930cf4c3cc337496c95eb542`。完整 OHLCV 21 個月檔案逐檔依 manifest SHA256 核對：**21/21 PASS**，共 **799,468 筆**。無重新收檔、未修改 canonical。
- 執行器為 ChatGPT Python（非 Colab）；XGBoost 3.1.3。當前 ChatGPT Python 缺 pyarrow 且無法經 pip 連外，使用具限定 schema / encoding、Thrift + 系統 ZSTD 的本地 Parquet reader，只改 IO 介面；特徵、時間 purge、模型參數及 XGBoost fit 使用 Notebook v3.6 來源。原本的 `features_labels.parquet` 輸出僅改為**本地不可發行**的 `features_labels.pkl` 中間資料，不納入模型候選包；正式環境仍應使用 pyarrow 並比對輸出 parity。讀取器不等同 production 支援。
- 固定 research run ID：`e6245444fb2d0214`；模型 UBJ SHA256：`d100d226a2c1b8a691249521734223b2bb121b388cc090f34b9cce4f12939df8`，`publication_allowed=false`。

## 樣本與 OOS

| 項目 | 實測 |
|---|---:|
| 原始資料／股票數 | 799,468 筆／1,979 檔 |
| 可用研究樣本 | 578,699 |
| 暖機／缺市場連續窗口而排除 | 184,946 |
| 未成熟 20 交易日標籤而排除 | 35,823 |
| train／validation／test | 363,353／54,713／90,498 筆 |
| train／validation／test 獨立訊號日期 | 220／31／51 |
| train 截止／validation 截止／test 起始 | 2026-04-02／2026-06-17／2026-06-18 |
| XGBoost `best_iteration` | 17 |

主 Y 是未來 **20 個市場交易日**的未還原價格上漲標籤，歷史資料 `historical_pit=NOT_VERIFIED`，訓練狀態 `RESEARCH_UNADJUSTED_PRICE_NON_PIT`。

| 90,498 筆測試集 | Brier ↓ | LogLoss ↓ | AUC ↑ |
|---|---:|---:|---:|
| 固定訓練盛行率 | 0.243168 | 0.679463 | 0.500000 |
| Logistic baseline | 0.248301 | 0.690370 | 0.557151 |
| XGBoost | **0.240060** | **0.673153** | **0.561539** |

- XGBoost Brier 比固定基準少 **0.003107**（相對約 **1.28%**）。TWSE Brier 0.241855 vs baseline 0.244224；TPEx 0.237530 vs baseline 0.241678。
- 分月份：2026-06 Brier 改善為 **−0.006889**（退步），07 月 **+0.005103**、08 月 **+0.004844**。訊號測試日期至 8 月，9 月資料用於使 20 日標籤成熟。
- 為控制重疊 20 日標籤，依測試集 51 個獨立訊號日期做 **20 日連續區塊循環 bootstrap，3,000 次**。Brier 改善量 95% 指示區間約 **[−0.003398, +0.011027]**，**涵蓋 0**，不宣稱統計穩定優勢。
- 測試集中實際上漲率約 **38.33%**、模型平均預測上漲率約 **47.78%**，顯示機率仍有校準偏差；`calibrated_probability=null`。不能直接供 UI 做已認證的上漲機率。
- 原生 UBJ reload 與固定測試向量相等（最大差 0），model hash/readback PASS。此為**本地**讀回，非 GCS／dev runtime readback。

## 已完成與剩餘門檻

**PASS（本次有界任務）**：完整原資料 hash、可重跑的真實 Quant fit、時間 OOS、分市場與分月份診斷、模型原生安全 UBJ 載入與 test-vector parity、單次結果與程式來源收據。

**未完成／有實際原因**：調整/排除公司行動價格污染，歷史 as-of／PIT 和實際來源用途，確認校準與未碰觸 OOS 的穩定性（目前 20 日 block CI 涵蓋 0），訓練與正式 Core/Mart serving 特徵 parity，GCS immutable candidate、dev shadow、CI、Registry／PG、API/UI/rollback。不得拿本次 OOS 反覆調參再稱新 holdout；新增版本須另取未看過的時間段或前瞻 shadow 驗證。

**後續順序**：Quant 如實維持研究狀態；接續 D07 的 Fundamental、Valuation 獨立試做／可佈版門檻。只有三角色**全部具 DEPLOYABLE 收據**後，才與 Risk v1 一起整合跨 Job 模型快取；目前不變更 Risk v1。

詳細本地研究產物為對話中的 `Quant_v36_ChatGPT_真資料試訓_研究報告.md` 與 `Quant_v36_研究候選_20261023.zip`（後者不包含 Parquet 訓練資料或 pickle 中間檔）。此兩檔尚非 Google Drive／GCS 的正式持久化研究存檔。
