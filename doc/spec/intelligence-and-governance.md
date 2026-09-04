# Janus SPEC — Intelligence、Aggregator 與 Runtime

## 9. Mart + ML／AI／LLM Job

職責：

- 只讀 versioned Core snapshot；禁止即時補抓。
- 產製特徵、ML artifacts、五角色輸出、Evidence Validator、Aggregator。
- 套用 governance snapshot 與 publication policy。
- LLM 依合格 evidence 產生繁體中文結構化摘要。
- 寫入 Mart、report metadata、publication index 與 `mart.report.ready.v1`。

資料超市至少區分：

- `mart_screening_signals`：全市場日頻異動、技術面、量能與流動性篩選。
- `mart_core_alpha`：個人關注股深度追蹤層的基本面、事件、核准新聞與另類資料綜合特徵；表名暫不重命名以避免無價值 migration。
- `mart_risk_portfolio`：波動、回撤、流動性、滑價與信用風險；不直接執行交易。
- `mart_alternative_sentiment`：核准文本的聲量、情緒、來源分布與不確定性；不得把無來源模型判讀當作事實。
- `mart_scoped_analysis`：以 `scope_type`（market／industry／symbol）與 `scope_id` 保存五角色輸出、screening／risk／sentiment 摘要、aggregate score、bull／bear、contradictions、contributions、Devil's Advocate 反證、evidence、缺失資料、prompt version 與 CIO 結構化摘要；產業 scope 另保存 membership snapshot。未來私人個股整合由 Private Mart 保存對公開 symbol-scope artifact 的 reference／overlay，不把私人交易資料寫入公開 Mart。
- `mart_market_regime_daily`：每日市場狀態、資料日期、多空依據、總經／流動性風險與 confidence；狀態字彙固定且可版本化。
- `mart_sector_rotation_daily`：產業 membership snapshot、5 日法人買超力道、力道變化、20 日成交金額與「漲潮／輪動／觀望／退潮」等 deterministic 狀態；供排行與選用泡泡圖讀取。
- `mart_topic_trends_daily`：核准文本來源的熱門話題、相關產業／股票、聲量變化、來源分布、不確定性與 evidence。
- `mart_candidate_health`：候選股的 1–100 健康度、籌碼狀態、白話 AI 分析、風險、完整度與來源；分數只能由版本化 deterministic Mart 聚合產生，LLM 只能翻譯已通過 Validator 的 evidence。
- `mart_daily_brief`：只組合同一 `analysis_as_of`、已發布的市場狀態、板塊輪動、熱門話題與候選股；不重算上游分數。

User App 最小個股健檢契約：

```yaml
stock_id: "2330"
stock_name: "台積電"
mart_health_score: 85        # 1..100；不是獲利機率
chips_status: "大戶偷偷買進中"
ai_whitepaper_analysis: "這家雞排店最近接到了蘋果和輝達的大訂單，生意爆滿…"
analysis_as_of: datetime
data_status: publishable | partial | stale
confidence: number | null
evidence_refs: string[]
```

- `chips_status` 是受控字彙的顯示文案，必須可回溯 Positioning evidence，不可由 Flutter 自行推斷。
- `ai_whitepaper_analysis` 不得加入 evidence 未出現的數字、客戶或訂單；示例比喻只能建立在已驗證事實上。
- 分數不完整或未通過發布政策時，不得為了 UI 填滿而產生預設健康度或文案。

私人 ledger 的交易類型至少包含 `BUY`、`SELL`、`CASH_DIV`、`STOCK_DIV`；依類型驗證 date、symbol、shares、price、fee、tax 與 currency，金額／股數一律使用固定精度 decimal。私人 Mart 最少包含 `mart_user_positions`、`mart_user_realized_pnl`、`mart_user_unrealized_pnl` 與 `mart_user_annual_pnl`；每筆結果必須帶 `user_id`、ledger version、valuation date、cost-basis method、currency 與 lineage。成本法在 MVP 固定為移動平均法；FIFO 只在完成稅務／會計語意與回歸測試後才能開放。

個人風險與顧問功能排在上述私人 P0 後：

- `user_investment_profile` 保存 risk tolerance、investment horizon、primary goal 與 minimum cash ratio；目前值使用 bounded private index，歷史 revision 進 Private Iceberg，且只在使用者明確選取時加入聊天室 context。
- `mart_user_exposure` 以現金、持股市值與有效日期的多產業 membership 計算曝險；一檔股票可屬多個產業，分攤方法與 membership snapshot 必須版本化，前端與 LLM 不自行計算。
- `mart_user_annual_performance` 在現金流語意、股利與更正事件通過回歸後提供 XIRR；無根、多根或資料不足時回傳 typed status，不填 0。
- 投資組合 stress test 先由 deterministic scenario 計算資產與現金水位變化，再由目前 conversation 選定的 `codex | chatgpt | gemini` profile 解釋；模型不得修改數值、替使用者下單或輸出保證性建議。
- 新聞與情緒沿用公開 Core provenance／`mart_alternative_sentiment`；Gemini Google Search grounding 是對話當下的外部補充，只保存必要 query／citation metadata，不把未授權新聞全文寫入 Private Iceberg 或公開 Core。

五角色：Fundamental、Valuation Risk、Positioning、Quant、Event Risk。

每個角色使用 repository 版控的固定 structured prompt；不提供 Admin 編輯、產業或個股 override。Mart execution 把 prompt version／content hash 固定進 immutable governance snapshot，修改只影響新 execution。prompt 只能要求 evidence-grounded structured output，不得注入 secret、未核准來源或解除 Validator／publication policy。

主要規則：

- Fundamental：12 月營收、12 季財報，一般／金融業分流。
- Positioning：5／20／60 日正規化，單日買超不直接判多。
- Quant：20／60／120 日相對強弱、量能、波動、回撤、Beta、ATR、turnover；少於 20 筆有效行情 score=null。
- Event Risk：只納入 PIT 合格事件；可觸發 manual review。
- 參考停損 `last_close - 2 × ATR(14)`，只作風險參考。
- Devil's Advocate 是 Aggregator 的強制反證階段，不是第六個可自行補資料的角色；必須引用既有 evidence。

## 10. Aggregator 與發布治理

初始權重：Fundamental 25%、Valuation 20%、Positioning 20%、Quant 25%、Event Risk 10%。

```text
effective_weight = base_weight × completeness × confidence × data_quality / 100
```

- 開發期有效完整度 <30% 或沒有有效分數：`insufficient_data`。
- aggregate ≥60：偏多；≤40：偏空；其餘中立。
- 必須同時輸出 bull、bear、contradictions、contributions。
- confidence 必須明示「資料／分析信心度，非獲利機率」。

發布矩陣：

| 條件 | analysis outcome | `PublicationStatusV1` |
|---|---|---|
| FUTURE_DATA／INVALID_SOURCE_URL／MISSING_CRITICAL_SOURCE | invalid | blocked |
| manual_review_required=true | review_required | blocked |
| critical event | risk_blocked | blocked |
| high event 且 risk score ≥75 | risk_blocked | blocked |
| completeness <30% 或無有效分數 | insufficient_data | blocked |
| 驗證及政策通過 | complete | publishable |

`insufficient_data` 只屬 analysis outcome／reason，不是 publication lifecycle 狀態；只有 `publishable`／`published` 可進公開 service index。

所有權重與門檻除已核准發布政策外，均視為開發期保守設定；正式值須 PIT 回測與人工 revision。

## 11. DuckDB／Iceberg runtime boundary

- Ingestion Cloud Run Job 內嵌一個 bounded DuckDB instance，負責 Stage → Core 的 deterministic merge 與 Iceberg commit；單 task、單 writer，限制 threads、memory、timeout 與 temp directory。
- Core query API 在 FastAPI Cloud Run Service 內嵌另一個 read-only DuckDB instance。這是另一個 process，不是第二份持久資料庫；兩者共用 GCS Iceberg snapshots 與 PostgreSQL catalog metadata，不共享本機 DuckDB 檔案。
- Query runtime 不得寫 Core；寫入仍由 ingestion Job 序列化，避免並行 Iceberg commit 衝突。
- DuckDB 本機資料、spill 與 temp 均為可丟棄暫存；GCS 保存 Iceberg data/metadata，PostgreSQL 只保存 catalog、control、publication、audit、服務索引與隔離的私人 ledger。
- backfill 必須拆批並限制 scan rows／bytes、memory、timeout；超過單機與 Cloud Run 執行限制時，再評估分散式引擎，不預先恢復 Trino。
