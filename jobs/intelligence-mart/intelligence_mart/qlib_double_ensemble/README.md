# Qlib DoubleEnsemble bounded adapter

來源：Microsoft Qlib **v0.9.7**，MIT license（見本目錄 `LICENSE`）。

- [原始 model.py](https://github.com/microsoft/qlib/blob/v0.9.7/qlib/contrib/model/double_ensemble.py)
- 原始 raw-byte SHA-256：`699cfd4bf09bae95fc9d95994551d0660d62ebcebde88c7358857aca95641669`
- 僅 vendoring 此單一演算法，未引入 Qlib data provider、workflow、tracking、upstream datasets 或生成式 agent。
- 移除 Qlib base classes 與 DatasetH type dependency，使用 Janus 已驗證的 PIT dataframe；logger 改用 stdlib。演算法仍保留 sample reweighting 與 feature selection。
- 將 feature set 排序以固定 replay、關閉逐輪 loss logging，將 chained inplace fillna 改成明確賦值以相容 pinned pandas。
- 沿用已 hash-lock 的 LightGBM 4.6.0／NumPy 2.2.6／pandas 2.3.3。Janus adapter 固定三個 submodels、20 rounds、seed 17、single thread；僅是 bounded challenger，不代表已驗證 champion。
- 每個子模型使用原生 Tree SHAP，依 ensemble weight 合併至原始 feature 維度，必須重建同一個預測。

Dependency／security review：本地沒有動態 source execution、網路請求、檔案讀寫、pickle 或 eval；只保留受控 numeric training。未新增 runtime dependency 或付費服務。更新版本須重新比對來源、授權、相容性與 replay/OOS tests。
