# Janus SPEC — Intelligence、Aggregator 與 Runtime

## 9.0 Token-first 分析引擎

依 2026-10-03 使用者最新指示，舊五角色分數／LLM worker、prompt、validator、sidecar 與契約已刪除，不保留可執行相容分支。歷史 persisted artifacts 仍受保護，不能以程式清理授權大量刪除資料。

正式執行契約見 [Specialist engines](specialist-engines.md)。日常入口只執行約 500 檔 screening，以及 `active watchlist ∪ effective holdings` 的 Fundamental／Valuation／Quant／Risk／Event；不讀取 CEO provider，不因頁面、價格或事件自動觸發 LLM。

舊獨立 provider transport／auth／free gate 保留，但只接受 `ceo`，手動 CEO command／能力權限／語意 validator／實際 synthesis 留待對應 WBS；存在 transport/schema 不代表 CEO 已完成。

## 9. Mart + ML／AI／LLM Job

職責：

- 只讀 versioned Core snapshot；禁止即時補抓。
- 產製特徵、ML 成果物、五分析師成果物、證據驗證器、聚合器。
- 套用 governance snapshot 與 publication policy。
- 日常摘要由規則與繁體中文模板產生；LLM 僅限手動 CEO。
- 寫入 Mart、report metadata、publication index 與 `mart.report.ready.v1`。
- 每次 Mart execution 以 create-only GCS object 保存 `model.json`、`evaluation.json` 與
  `governance-diff.json`；manifest 只引用其 URI 與 SHA-256。PostgreSQL governance
  revision 只保存 snapshot／diff artifact reference，不保存大型 payload 或 diff JSON。

資料超市至少區分：

- `mart_screening_signals`：全市場日頻異動、技術面、量能與流動性篩選。
- `mart_core_alpha`：個人關注股深度追蹤層的基本面、事件、核准新聞與另類資料綜合特徵；表名暫不重命名以避免無價值 migration。
- `mart_risk_portfolio`：波動、回撤、流動性、滑價與信用風險；不直接執行交易。
- `mart_alternative_sentiment`：核准文本的聲量、情緒、來源分布與不確定性；不得把無來源模型判讀當作事實。
- `mart_scoped_analysis`：以 `scope_type`（market／industry／symbol）與 `scope_id` 保存五分析師成果物、screening／risk／sentiment 摘要、aggregate score、bull／bear、contradictions、contributions、Devil's Advocate 反證、evidence、缺失資料、prompt version 與 CEO 結構化摘要；產業 scope 另保存 membership snapshot。未來私人個股整合由 Private Mart 保存對公開 symbol-scope artifact 的 reference／overlay，不把私人交易資料寫入公開 Mart。
- `mart_market_regime_daily`：每日市場狀態、資料日期、多空依據、總經／流動性風險與 confidence；狀態字彙固定且可版本化。
- `mart_sector_rotation_daily`：產業 membership snapshot、5 日法人買超力道、力道變化、20 日成交金額與「漲潮／輪動／觀望／退潮」等 deterministic 狀態；供排行與選用泡泡圖讀取。
- `mart_topic_trends_daily`：核准文本來源的熱門話題、相關產業／股票、聲量變化、來源分布、不確定性與 evidence。
- `mart_candidate_health`：候選股的 1–100 健康度、籌碼狀態、白話 AI 分析、風險、完整度與來源；分數只能由版本化 deterministic Mart 聚合產生，LLM 只能翻譯已通過 Validator 的 evidence。
- `mart_daily_brief`：只組合同一 `analysis_as_of`、已發布的市場狀態、板塊輪動、熱門話題與候選股；不重算上游分數。

Supply-chain Intelligence 未來沿用相同 Mart／PIT／publication 邊界，概念輸出至少能
表達 direction、magnitude、confidence、lead_time、affected nodes／companies、company
exposure、expected metric／period、evidence、contradictions、market expectation／
priced-in assessment 與 expectation gap。leading indicator → exposure → expected impact
→ market expectation → expectation gap 的 deterministic contract 只在相應 WBS unlock
後實作；本次只定義 contract 與 planning。

AI 分析角色／CEO 只能使用不可變更的事實包與已驗證證據，不能改 canonical
numbers、基準分數、發布狀態或治理結果，也不得把
`inferred`／`hypothesis` 寫成 confirmed relationship。所有 signal、claim 與 synthesis
必須可回溯 Core／Mart snapshot、PIT、provenance、effective time、source 與
feature／signal revision。

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

- `chips_status` 是受控字彙的顯示文案，必須可回溯 已驗證法人 evidence，不可由 Flutter 自行推斷。
- `ai_whitepaper_analysis` 不得加入 evidence 未出現的數字、客戶或訂單；示例比喻只能建立在已驗證事實上。
- 分數不完整或未通過發布政策時，不得為了 UI 填滿而產生預設健康度或文案。

私人 ledger 的交易類型至少包含 `BUY`、`SELL`、`CASH_DIV`、`STOCK_DIV`；依類型驗證 date、symbol、shares、price、fee、tax 與 currency，金額／股數一律使用固定精度 decimal。私人 Mart 最少包含 `mart_user_positions`、`mart_user_realized_pnl`、`mart_user_unrealized_pnl` 與 `mart_user_annual_pnl`；每筆結果必須帶 `user_id`、ledger version、valuation date、cost-basis method、currency 與 lineage。成本法在 MVP 固定為移動平均法；FIFO 只在完成稅務／會計語意與回歸測試後才能開放。

個人風險與顧問功能排在上述私人 P0 後：

- `user_investment_profile` 保存 risk tolerance、investment horizon、primary goal 與 minimum cash ratio；目前值使用 bounded private index，歷史 revision 進 Private Iceberg，且只在使用者明確授權時提供給外部助理 context。
- `mart_user_exposure` 以現金、持股市值與有效日期的多產業 membership 計算曝險；一檔股票可屬多個產業，分攤方法與 membership snapshot 必須版本化，前端與 LLM 不自行計算。
- `mart_user_annual_performance` 在現金流語意、股利與更正事件通過回歸後提供 XIRR；無根、多根或資料不足時回傳 typed status，不填 0。
- 投資組合 stress test 先由 deterministic scenario 計算資產與現金水位變化；若外部助理解釋結果，只能使用已授權的 bounded context，且不得修改數值、替使用者下單或輸出保證性建議。
- 新聞與情緒沿用公開 Core provenance／`mart_alternative_sentiment`；Gemini Google Search grounding 是對話當下的外部補充，只保存必要 query／citation metadata，不把未授權新聞全文寫入 Private Iceberg 或公開 Core。

五分析師：Fundamental、Valuation、Quant、Risk、Event。

### Specialist 與 CEO 邊界

五分析師只有 structured metrics／PIT evidence／規則模板報告，不以生成式 prompt 產生日常分析。
CEO 必須由有權限使用者明確 request，只讀最新 validated artifacts；每次新 immutable report、未知／缺失如實揭露、無 publication authority。未完成 command、auth lifecycle、跨角色語意 validator 前不得對外宣稱可用。

## 10. Aggregator 與發布治理

Specialist 第一版沒有經 OOS promotion 的總分或投資方向，不以舊五角色加權公式產生新健康度。`policy.json` 的五分析師權重屬版本化開發設定，未接入正式分數；正式值仍需 PIT 回測及人工 revision。

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

Governance／audit metadata 由 `janus_audit` 擁有；revision head 以 expected version 做
原子 compare-and-swap。Retention 只可分批清除已過期且不是 current head 的歷史 revision。

所有權重與門檻除已核准發布政策外，均視為開發期保守設定；正式值須 PIT 回測與人工 revision。

## 11. DuckDB／Iceberg runtime boundary

- Ingestion Cloud Run Job 內嵌一個 bounded DuckDB instance，負責 Stage → Core 的 deterministic merge 與 Iceberg commit；單 task、單 writer，限制 threads、memory、timeout 與 temp directory。
- Core query API 在 FastAPI Cloud Run Service 內嵌另一個 read-only DuckDB instance。這是另一個 process，不是第二份持久資料庫；兩者共用 GCS Iceberg snapshots 與 PostgreSQL catalog metadata，不共享本機 DuckDB 檔案。
- Query runtime 不得寫 Core；寫入仍由 ingestion Job 序列化，避免並行 Iceberg commit 衝突。
- DuckDB 本機資料、spill 與 temp 均為可丟棄暫存；GCS 保存 Iceberg data/metadata，PostgreSQL 只保存 catalog、control、publication、audit、服務索引與隔離的私人 ledger。
- backfill 必須拆批並限制 scan rows／bytes、memory、timeout；超過單機與 Cloud Run 執行限制時，再評估分散式引擎，不預先恢復 Trino。

## 11.1 Research intelligence gate（Planned）

研究分析依 `macro／market → industry／supply chain → stock signal → portfolio
decision` 逐層組合；任一層的 missing、stale 或 partial 不得由下層或 LLM
猜測補齊。Market Regime 為 bounded deterministic context，可使用當時已核准且
可用的 TAIEX、TPEx、market breadth、turnover、institutional flow、financing leverage
及 FX／rates／futures／macro inputs。未核准或無 coverage evidence 者為 `Unknown`、
`Candidate` 或 `Blocked`，不因本列表獲得核准。

Market Regime 輸出至少保留 `state`（`risk_on | neutral | caution | risk_off |
insufficient_data`）、`analysis_as_of`、`confidence`、`evidence` 與 `missing_data`。
`confidence` 僅可來自 deterministic／explicit quality semantics，不由 LLM 自行產生。

Private Research State 是 owner-scoped、effective-time 與 revision-aware 的 semantic contract：

- `research_thesis`：`symbol`、`thesis`、`supporting_conditions`、`invalidating_conditions`、
  `effective_from`、`effective_to`、`review_after`、`status`、`revision`。
- `candidate_state`：`symbol`、`candidate_status`、可選 `priority／tier`、`rationale`、
  `effective_from`、`effective_to`、`requires_refresh`、`revision`。
- `strategy_state`：current strategy hypothesis、entry／add／reduce／invalidate concepts、
  `evidence_as_of`、effective time 與 revision；不就地 overwrite 歷史策略。
- `decision_record`：decision／decision time、`analysis_as_of`、key evidence references、
  portfolio context 與 thesis／strategy revision references。
- `investment_policy`：risk tolerance、horizon、minimum cash、concentration boundaries 與
  mandate；現有 profile 不足部分為 Schema Extension Candidate。

Supply-chain Research Context 僅沿用 `supply_chain_node`、`supply_chain_edge`、
`company_exposure`、`leading_indicator_definition`、`leading_indicator_observation`、
`supply_chain_signal`、`expectation_signal` 的共用規劃，保留 effective time、
provenance、quality／confidence 與 `confirmed | reported | inferred | hypothesis`。AI inference
不得升級為 confirmed fact，且不得繞過 Gate A–E。
