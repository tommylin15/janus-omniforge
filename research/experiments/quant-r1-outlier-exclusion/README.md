# Quant r1 極端「訓練列」排除研究重跑說明

**研究限定**：此程式不得發布模型、改變 Registry 或 canonical 資料，也不會呼叫任何外部 API。金融股仍納入。

## 來源與原理

- 唯讀輸入：原 Stage05.1 `X.parquet`、`Y_NOT_X.parquet`；檔名可在本地為 `.bin`，但**位元組必須是原始 Parquet**，SHA256 固定在 `run.py`。
- 研究版參數：既有 `research/experiments/quant-forward-202607/evidence.json` 的 `model_expanding12` 與 `manifest`，或既有研究包 `Janus_Quant_202607_forward_simulation_研究包.zip`。
- 只有成熟於 2026-07-01 前且 reason=OK 的資料進訓練。十一個數值因子以凍結 r1 訓練 scaler 的均值、標準差計算 `max_j(abs((x_j-mean_j)/std_j))`；**不使用 Y 作極端度排序**，也不包含類別 `market_code`。
- 依此極端度排序，分別移除 2%、5%、10% 的**訓練整筆樣本**，每版重 fit `StandardScaler` + `LogisticRegression(C=1, solver='lbfgs')`。同一評估期間 2026/07–08 成熟資料全部保留，禁止為了 Brier 好看而排除測試難例。
- 輸出日期等權／列加權 Brier、AUC、log loss、分月／市場、20日期 block CI、每日指標與逐筆比較。**這不是把每個特徵兩端各刪2%**；不同於先前雙側 winsorization 實驗。

## 本輪已驗證環境

Python 3.13.5、numpy 2.3.5、pandas 2.2.3、scikit-learn 1.8.0、scipy 1.17.0；使用唯讀的有界研究版 Parquet reader（`reader.py`，需本機 `libsnappy`／`libzstd`）。`reader.py` 不具備生產用途或通用 Parquet 相容承諾。可在配有系統壓縮套件的研究運算環境重跑，不預設 Colab 一定備齊。

```bash
# 使用原始研究 ZIP
export JANUS_QUANT_RESEARCH_INPUT_ROOT=/your/research/input-dir
export JANUS_QUANT_RESEARCH_OUTPUT_ROOT=/your/output-dir
python run.py

# 或直接使用 GitHub 的證據 JSON（需複製到可存取位置）
export JANUS_QUANT_RESEARCH_EVIDENCE_JSON=/your/path/evidence.json
python run.py
```

輸入資料夾內需要 `X.parquet.bin` 和 `Y_NOT_X.parquet.bin`。若採 ZIP 模式，同資料夾內另外放 `Janus_Quant_202607_forward_simulation_研究包.zip`。

## 重跑與既有收據核對

本輪在完全同一份 SHA 驗證 X/Y 及凍結 model JSON 上重跑程式，三組日期等權 Brier 與保存收據逐字數值一致，基準模型凍結參數出分與在本機重新 fit 最大差約 `6.025e-8`。

此研究期已被多次檢視；所有 CI 僅 exploratory，不能升級模型。程式不重建真實 PIT／公司行動資訊。