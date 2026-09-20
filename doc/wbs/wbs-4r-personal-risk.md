# Janus WBS 4R — 個人曝險、績效與壓力測試

## WBS 4R — 個人曝險、績效與 AI 壓力測試（P1）

### 執行環境

本 WBS 的 `dev` 是目前個人實際使用的平行上線環境。實作與驗收優先使用真實 authenticated owner、Private Core／Mart、真實 persisted portfolio data 與實際 API／Flutter workflow；不得以 sample portfolio、placeholder response 或 mock profile 取代主要驗收。Production／staging 僅是未來多人、HA／SLA 或正式營運強化，不是本 WBS 在 dev 真實使用的前置條件。

- 建立 user investment profile：risk tolerance、investment horizon、primary goal、minimum cash ratio；目前值使用 bounded private index，revision history 進 Private Iceberg。
- 建立具 effective time／provenance 的股票多產業 membership；產製 `mart_user_exposure`，版本化多產業分攤方法與 membership snapshot。
- 在交易、股利與更正事件回歸通過後產製 `mart_user_annual_performance` 與 XIRR；無根、多根、缺現金流或資料不足回傳 typed status，不填 0。
- 建立 deterministic portfolio stress scenarios 與 cash-safety result；AI 只使用 WBS 4C 使用者選定的 profile 解釋既有數值，不自行計算或修改結果。
- 提供 `/api/v1/me/investment-profile`、`/api/v1/me/portfolio/summary`、`/api/v1/me/portfolio/exposure`、`/api/v1/me/portfolio/performance?year=` 與 `/api/v1/me/portfolio/stress-tests`；全部只讀 authenticated-user Private Mart。
- 驗證多產業分攤總和、現金水位、跨年／股利 XIRR、無根／多根、scenario 重跑、profile opt-in context、A／B 隔離與模型不可改寫 deterministic result；主要 evidence 取自真實 dev API／runtime／persisted data，unit fixture 只補 deterministic edge cases。
