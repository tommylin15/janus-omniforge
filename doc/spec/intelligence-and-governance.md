# Janus SPEC — Intelligence、Aggregator 與 Runtime

## 9.0 Current truth 與 approved next-version design

目前實作邊界：`analysis.py` 產生 deterministic features、五個 score/feature
payload、evidence 與 aggregate；`runtime.py` 以 immutable Core snapshot 執行
deterministic Mart，`gemini.py` 只提供可選的單一 Gemini evidence-only narrator。
`OpenRouter` 目前屬私人 Agent Gateway provider，不是 Mart provider。五個獨立 AI
analyst、CIO synthesis、其 deterministic validators、Analysis Profile、content-
addressed reuse 與 Flutter Admin workspace 尚未實作；本節以下的 next-version
能力均標為 **Planned**，不得當作現有能力。

下一版核准架構為：

`Core immutable snapshot → Evidence Validation → Deterministic Fact Engine →
5 evidence-grounded AI Analysts → Deterministic AI Output Validator → CIO /
Synthesis AI → Deterministic Synthesis Validator → Governance / Publication Gate →
Immutable Mart artifacts`。

Deterministic Fact Engine 的正式定位是 Fact Pack，分為 Fundamental、Valuation、
Positioning、Quant、Event Risk 五包。它負責數字、PIT、feature calculation、歷史
比較、missing-data semantics、provenance、evidence refs 與 baseline score；baseline
score 保留作 regression／drift／outcome reference，但不等於完整研究分析。

## 9. Mart + ML／AI／LLM Job

職責：

- 只讀 versioned Core snapshot；禁止即時補抓。
- 產製特徵、ML artifacts、五角色輸出、Evidence Validator、Aggregator。
- 套用 governance snapshot 與 publication policy。
- LLM 依合格 evidence 產生繁體中文結構化摘要。
- 寫入 Mart、report metadata、publication index 與 `mart.report.ready.v1`。
- 每次 Mart execution 以 create-only GCS object 保存 `model.json`、`evaluation.json` 與
  `governance-diff.json`；manifest 只引用其 URI 與 SHA-256。PostgreSQL governance
  revision 只保存 snapshot／diff artifact reference，不保存大型 payload 或 diff JSON。

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

Supply-chain Intelligence 未來沿用相同 Mart／PIT／publication 邊界，概念輸出至少能
表達 direction、magnitude、confidence、lead_time、affected nodes／companies、company
exposure、expected metric／period、evidence、contradictions、market expectation／
priced-in assessment 與 expectation gap。leading indicator → exposure → expected impact
→ market expectation → expectation gap 的 deterministic contract 只在相應 WBS unlock
後實作；本次只定義 contract 與 planning。

AI analyst／CIO 只能使用 immutable Fact Pack 與 validated evidence，不能改 canonical
numbers、baseline score、publication status 或 governance outcome，也不得把
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

- `chips_status` 是受控字彙的顯示文案，必須可回溯 Positioning evidence，不可由 Flutter 自行推斷。
- `ai_whitepaper_analysis` 不得加入 evidence 未出現的數字、客戶或訂單；示例比喻只能建立在已驗證事實上。
- 分數不完整或未通過發布政策時，不得為了 UI 填滿而產生預設健康度或文案。

私人 ledger 的交易類型至少包含 `BUY`、`SELL`、`CASH_DIV`、`STOCK_DIV`；依類型驗證 date、symbol、shares、price、fee、tax 與 currency，金額／股數一律使用固定精度 decimal。私人 Mart 最少包含 `mart_user_positions`、`mart_user_realized_pnl`、`mart_user_unrealized_pnl` 與 `mart_user_annual_pnl`；每筆結果必須帶 `user_id`、ledger version、valuation date、cost-basis method、currency 與 lineage。成本法在 MVP 固定為移動平均法；FIFO 只在完成稅務／會計語意與回歸測試後才能開放。

個人風險與顧問功能排在上述私人 P0 後：

- `user_investment_profile` 保存 risk tolerance、investment horizon、primary goal 與 minimum cash ratio；目前值使用 bounded private index，歷史 revision 進 Private Iceberg，且只在使用者明確選取時加入聊天室 context。
- `mart_user_exposure` 以現金、持股市值與有效日期的多產業 membership 計算曝險；一檔股票可屬多個產業，分攤方法與 membership snapshot 必須版本化，前端與 LLM 不自行計算。
- `mart_user_annual_performance` 在現金流語意、股利與更正事件通過回歸後提供 XIRR；無根、多根或資料不足時回傳 typed status，不填 0。
- 投資組合 stress test 先由 deterministic scenario 計算資產與現金水位變化，再由目前 thread 選定的 OpenRouter／Gemini API／Codex runtime 與模型解釋；模型不得修改數值、替使用者下單或輸出保證性建議。
- 新聞與情緒沿用公開 Core provenance／`mart_alternative_sentiment`；Gemini Google Search grounding 是對話當下的外部補充，只保存必要 query／citation metadata，不把未授權新聞全文寫入 Private Iceberg 或公開 Core。

五角色：Fundamental、Valuation Risk、Positioning、Quant、Event Risk。

### Planned AI analyst、CIO 與 prompt contract

五個角色是獨立的 evidence-grounded analysis stage，可平行執行。每個 stage 輸入
immutable Fact Pack、validated evidence、`analysis_as_of`、Core snapshot identity、
immutable system guardrail、versioned role methodology prompt 與 provider/model/
parameters。輸出至少包含 `stance`、`thesis`、`key_findings`、`positive_evidence`、
`negative_evidence`、`contradictions`、`change_drivers`、`risks`、
`missing_information`、`what_would_change_my_view`、`confidence` 與 `evidence_ids`。

System Guardrail 不可由 Admin 編輯，至少禁止 fabricated numbers、future data、未披露
missing information、無 evidence ID 的 claims、修改 deterministic facts、決定
publication，並明示 confidence 不是 profit probability。Role Methodology Prompt
（五角色及 CIO）可由唯一 Admin 編輯，但每次修改都建立 immutable version、content
hash、author、timestamp 與 Analysis Profile reference；Output Schema 由系統控制。

### Planned CIO、validation、rerun 與 reuse

CIO 只讀 deterministic Fact summaries、五份 validated role analyses、baseline signals、
evidence refs 與 governance constraints，輸出 overall stance／thesis、supporting／
opposing roles、contradictions、bull／bear、principal risks、watch items 與 change
since previous analysis。CIO 沒有 publication authority；role 與 CIO 都必須通過
deterministic validator。Validator 至少檢查 schema、evidence existence、numeric
grounding、`analysis_as_of` fence、future leakage、missing-data honesty、claim/evidence
coverage、provider/model/prompt lineage 與 immutable input identity。invalid role 必須
留下 structured failure，不寫 placeholder；一個 role 失敗不得宣稱 five-role full
success。

正式 rerun semantics：Fact Pack 未變時單角色重跑只執行該 role、validator、CIO、CIO
validator 與 governance recalc，其他 role artifact reuse；Core／相關 Fact Pack 改變
時先重建受影響 Fact Pack；prompt/model 改變不重算 facts；CIO prompt/model 改變只跑
CIO；governance 改變只做 deterministic governance evaluation；全部重跑只放在進階。

Role artifact 的 content-addressed identity 至少包含 `fact_pack_hash`、`evidence_hash`、
`role_prompt_hash`、provider、model、model parameters、system guardrail version 與
relevant schema version。相同 identity 可 reuse immutable artifact，但每次 reuse 都要
留下 audit／lineage，不得重複 AI call。Facts 與 interpretations 分開保存，例如
`executions/{execution_id}/facts/*`、`executions/{execution_id}/interpretations/*`、
`synthesis/cio.json`、`validation/*` 與 `manifest.json`；實際 storage contract 仍依
既有 GCS／Iceberg boundary 設計。

Governance／Publication Gate 仍是 deterministic：`complete`、`insufficient_data`、
`invalid`、`review_required`、`risk_blocked` 是 analysis outcome；`publishable`、
`blocked`、`published`、`superseded` 是 publication lifecycle。AI 不得自行宣告
`publishable`，`insufficient_data` 不得當成成功或公開狀態。

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
