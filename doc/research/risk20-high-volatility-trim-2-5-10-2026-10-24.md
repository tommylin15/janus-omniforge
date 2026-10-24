> **2026-10-24 政策更新**：研究數字與歷史結論保留；本文舊有逐來源／全歷史 PIT 補證、精確時間校準及新前瞻成熟等待不再是工作或發布前置。取消例行稽核，依 [研究精簡政策](../spec/research-simplification.md) 按需評估；不把取消視為 PASS。

# Risk20｜訓練 Y 上尾端排除 2%／5%／10%｜研究收據（2026-10-24）

**結果：RESEARCH_EVALUATED／NO_CHANGE_TO_FROZEN_CANDIDATE；publication_allowed=false。** 不更新既有 Risk ACTIVE、Registry、canonical、serving 或部署。

本輪接續 [Risk20 XGBoost12 研究定版](risk20-xgboost12-research-freeze-2026-10-24.md)，不更動該版12因子、原始樣本或已封存模型。基礎 X SHA256 `3b55e1868d19ed481b603fc3822f7d3523adfcea269ec89a01f00fdf1c27fedb`，Y SHA256 `08e6666976e34693411544f51b1de5e526c5855d44fe5277f501c7f3d10fa3a3`；研究來源 Git SHA `28fd738d509ab9936bf997b7024430372ac9ceac`。

## 作法及重現條件

四折 expanding walk-forward F3–F6，固定 84 個測試交易日、140,315 列。每一折**只用成熟的 train Y** 計算第98／95／90百分位並排除大於門檻的列，分別重訓三組XGBoost12，共12次。保留完整 validation／test、同一特徵順序、相同時序 purge／early stopping與參數；原參考模型 UBJ 重載逐列 prediction parity <1e-6，12個新 UBJ 重載預測也 <1e-6。本輪 xgboost 3.1.3，原封存 Colab xgboost 3.4.1，因此不聲稱原始訓練 bit-identical；同樣本基準以原封存預測對齊。未執行因子X極端值裁剪、Y雙尾剔除或 Huber。

## 相同完整測試集：四折日期等權 MAE（越低越好）

| 訓練排除最高Y | MAE | 逐列 MAE | RMSE | 相對原始MAE | 事後高實現波動 Top10% MAE |
|---|---:|---:|---:|---:|---:|
| 0%：原 XGB12 | **0.125219** | 0.125198 | 0.167221 | 基準 | 0.269295 |
| 2% | 0.129248 | 0.129223 | 0.174536 | **+3.22%**（較差） | 0.330458 |
| 5% | 0.135538 | 0.135502 | 0.185371 | **+8.24%**（較差） | 0.386114 |
| 10% | 0.146535 | 0.146493 | 0.203823 | **+17.02%**（較差） | 0.452598 |

在 Top10% 高波動 cohort，原始模型低估 96.85%，剔除 2/5/10% 後分別低估 99.99%／100%／100%。事後已實現Y分群只能用於研究診斷，絕不可當作T時點 eligibility。

## 各折與日期區塊不確定性

| 測試折 | 原 XGB12 | 排除2% | 排除5% | 排除10% |
|---|---:|---:|---:|---:|
| F3（5月） | 0.127631 | 0.135746 | 0.147773 | 0.165447 |
| F4（6月） | 0.118210 | 0.124341 | 0.134527 | 0.151125 |
| F5（7月） | 0.117358 | 0.124235 | 0.132291 | 0.147133 |
| F6（8月） | 0.138167 | 0.133220 | 0.128299 | 0.123309 |

**注意 F6 例外**：8月三種排除都改善該折，不能說所有月份都惡化，也不能事後按月份挑模型。

以同日期原MAE減新MAE作配對差、20日連續日期區塊 moving-block bootstrap 2,000 次（非股票逐列視為獨立）：
- 2%：-0.004029，95% CI [-0.007832,+0.000302]，**INCONCLUSIVE**。
- 5%：-0.010319，95% CI [-0.018953,-0.000601]，**NO_IMPROVEMENT**。
- 10%：-0.021316，95% CI [-0.037010,-0.004821]，**NO_IMPROVEMENT**。

## Drive 研究證據（janusChatGPT 內）

- [各折截尾門檻／剔除數／模型 SHA](https://drive.google.com/file/d/1UMc8tLOEjBAazYX5DhUPN_v4PR3m4jrk/view)
- [完整同樣本切片指標（含 Top1／2／5／10%）](https://drive.google.com/file/d/1u5LfMENKi9fMb984yXhhvDhqb6XOCeW4/view)
- [84個日期配對誤差](https://drive.google.com/file/d/1dTyZbsllXvUgQ4hbyXsLEaRG2tI1p_cS/view)

## 本輪裁定

**維持完整樣本 XGBoost12 研究定版；不採用按訓練 Y 上尾分位數直接排除的做法。** 真實高波動並非自動等於資料錯誤。未來若能確認公司行動／股價口徑污染，應依可證實的異常原因個別修復或排除，而非無差別刪除高 Y。

2026/05–08 為已被檢視的回溯月份，不能視為 untouched forward OOS。歷史 PIT／公司行動／交易日曆／來源授權尚未獨立驗證。保留12組各折模型、全量配對預測、逐日誤差、各折門檻與hash、完整 Python研究程式於本輪 ZIP（SHA256 `f328f43024a6096a2422acc8bae428582c0e35f6a5a708456e1dba7d4d978937`）。本輪**未將完整模型二進位檔提交 GitHub**，研究結果不改變正式服務版本。
