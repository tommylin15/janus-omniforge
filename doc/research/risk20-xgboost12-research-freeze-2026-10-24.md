> **2026-10-24 政策更新**：研究數字與歷史結論保留；本文舊有逐來源／全歷史 PIT 補證、精確時間校準及新前瞻成熟等待不再是工作或發布前置。取消例行稽核，依 [研究精簡政策](../spec/research-simplification.md) 按需評估；不把取消視為 PASS。

# Risk20｜XGBoost12 研究定版（2026-10-24）

> 決策：Risk 先以 **XGBoost12** 作為選定的「研究候選」，版本 `risk-rms20-xgboost12-research-20261024`；`RESEARCH_FROZEN / RESEARCH_IMPROVEMENT`、`publication_allowed=false`。這是研究方法及研究 checkpoint 凍結，**不是** Registry promotion、GCS 模型 pointer 修改、dev/prod ACTIVE 更換、API/serving 更新或部署。

## 研究目標及凍結方法

- 主 Y：未來20個市場交易日年化 RMS 波動 `sqrt((252/20)*sum(log(C[T+j]/C[T+j-1])**2, j=1..20))`，年化小數；**不是**去均值標準差 `future_realized_vol20`，更不是 VaR、ES 或最大回撤。
- TWSE/TPEx 普通股 pooled `XGBRegressor`；X 型別 `float32`，沒有 Ridge scaler；輸出 `max(0, raw)`。OHLCV 研究價格口徑：`RAW_UNADJUSTED_NOT_TOTAL_RETURN`，T 日盤後可得 EOD 才可計 X。市場日期不可用股票後20筆非空代替，缺值不填造。
- 凍結 **12 因子順序**：`vol20`, `vol60`, `drawdown60`, `abs_return5`, `volume_ratio20`, `atr14_pct`, `abs_overnight_gap5`, `log_turnover20`, `downside_vol20`, `worst_daily_ret20`, `amihud_illiquidity`, `drawdown_from_high120`。特徵契約：`05.1.1-extended-x-original-y-v1`，完整計算口徑/單位/窗口、NaN 及源資料可用性以 2026-10-23 研究包 `feature_contract.json` 和所釘 Git SHA 為準；不得重新定義原因子來硬湊既有分數。
- 固定日期 split、依 label mature-at 做20市場日 purge、同 `market/symbol/signal_date/Y` 比較；模型與補值器只在 train fit，early stopping 只看 validation。主指標日期等權 MAE，附逐列 MAE/RMSE、variance QLIKE (floor=1e-6)、日期 block、分市場及可服務覆蓋；不得因 test 排名而挑基準或超參數。

## 不可變研究證據

- 原研究 Git SHA：`28fd738d509ab9936bf997b7024430372ac9ceac`；Stage05.1 fingerprint：`07ec943fa3a1784f`。
- 原 X SHA256：`3b55e1868d19ed481b603fc3822f7d3523adfcea269ec89a01f00fdf1c27fedb`；原 Y SHA256：`08e6666976e34693411544f51b1de5e526c5855d44fe5277f501c7f3d10fa3a3`。該 run 的 `CURRENT.json` SHA256：`0b64ac6927805fb98260121da94624d7e08ac423f0aa13b8349d4c304f0135cd`，**不代表往後 CURRENT 永遠固定**。
- [原封存 Risk12 artifact（candidate-77eede082941eecb）](https://drive.google.com/drive/folders/1s9_MzLVUm-BlVb2IxZ_ylP68cHp7Dlm-)：原封存 UBJ SHA256 `11b9196028799e57513e744b2c0b39f9a8ff4123bccae36957a4a7a7719aef14`；原環境 xgboost 3.4.1，14 檔原始 SHA 比對 PASS、8 個 UBJ 測試向量與舊 MAE 重算 PASS，**非 bit-for-bit 重新訓練**。
- [Drive 定版決策備份](https://drive.google.com/file/d/14eh_a11mPi_QNYxsUBtH52IWE8KC7UJd/view)；[Drive 研究成果完整 ZIP](https://drive.google.com/file/d/17J02TZmQzZ2rYjT-d2vdpfJWToHU7Ujf/view)。兩檔位於白名單 `janusChatGPT/Risk 模型｜研究與重訓`。上傳檔案大小讀回：Markdown 6,925 bytes；ZIP 33,445,618 bytes；ZIP 在本輪本地檢查 105 筆目錄與 104 個逐檔 SHA 項目皆無異常。
- 本輪**研究參考 checkpoint** `model_xgboost12_refit.ubj` SHA256 `e00d302b082fb135991dc4e6f146cf4b9b7dbb56311daae27539564a629e05eb`，保存在 `Risk20_research_20261023.zip`；它是 A 階段固定 42 日期／70,485 列研究模型，**不是**四折重新 fit 後的單一正式 serving 模型。四折有各自 UBJ，不混為同一模型。研究 ZIP SHA256 `b654fc10f918e590cdf2f28434a4ce524cee402ae2e9ad5c5044bc74dd7bf8fc`；本輪完整 research bundle 清單及 SHA 收據見 ZIP。
- **基準命名修正**：原封存 `ridge8.json` 實際使用12因子（12係數）；本輪才建立真正 Ridge8/Ridge12 對照。勿把檔名誤認成實際維度。

## 凍結的研究結果（均 retrospective，非 untouched holdout）

| 項目 | 證據／結論 |
|---|---|
| A 固定共同 test | 42 個測試日期、70,485 列：XGB12 日期等權 MAE **0.126800**，XGB8 **0.128023** |
| E expanding-window | 4 folds／84 個測試日期／140,315 列：XGB12 **0.125219**、XGB8 **0.125970**；相對改善約 **0.60%** |
| 日期 block | 配對增益 0.000751；20日 moving-block 95% CI [0.000647,0.000846]；30日 [0.000652,0.000834]；僅支持**已看過期間內研究改善** |
| 覆蓋差異 | 八因子合格且成熟 Y 570,210 列，十二因子 451,733 列，差 118,477 列；共同樣本準確率不可混為可服務覆蓋 |
| B／C／D | B 新增 downside share 無改善，完整 HAR/Amihud20/vol5/Yang–Zhang 仍受逐日源存取阻擋；C 缺 120日回撤擴大覆蓋但 validation/test 反向，INCONCLUSIVE；D 最多6組有界淺樹調參，NO_IMPROVEMENT |
| 已知誤差 | 以真實高波動事後分群量得平均低估約0.108年化尺度；不能把事後分群當 T 日可用的 eligibility |

- **定版後診斷（2026-10-24）：**[訓練Y上尾端排除2%／5%／10%研究收據](risk20-high-volatility-trim-2-5-10-2026-10-24.md)：四折同測試集整體MAE 0.125219 → 0.129248／0.135538／0.146535，5%／10%有證據支持惡化；**不改研究定版、ACTIVE 或 Registry**。

## 發布與後續邊界

- `historical_pit=NOT_VERIFIED`、`corporate_action=NOT_VERIFIED`、`external_market_calendar=NOT_INDEPENDENTLY_VERIFIED`、`source_authorization=NOT_INDEPENDENTLY_VERIFIED`。原資料以觀測市場日期聯集建 grid，並非已獨立驗證交易所行事曆；缺 source 全量證據不可冒稱 VERIFIED。
- **保留**既有 `risk-xgboost8-2025h2-v1` 與原 `doc/spec/risk-model-card.md` 之歷史證據；Risk ACTIVE／Registry／正式預測流程全部不動。研究候選狀態不能推導出目前 runtime ACTIVE 版本，正式狀態須以 runtime 證據讀回。
- 本輪研究**已定版並停止額外調參**。日後有新來源／新方法另開新研究版本，必要時另驗新前瞻成熟 OOS、校曆／公司行動與 train-serving parity；不因本版封存就自動建立發布工單，不新增付費資源。
- 完整依據：研究報告 `report_zh.md`、`experiment_registry.csv`、`split_manifest_research.json`、`evaluation_plan_research.json`、`reproduction_audit.json`、`feature_contract.json`、`paired_date_block_uncertainty.json`、`research_model_card.json` 等同一研究包。研究工作單為**研究凍結完成**，而非 production acceptance。
