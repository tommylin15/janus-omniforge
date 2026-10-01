# Janus SPEC — Intelligence、Aggregator 與 Runtime

## 9.0 現況事實與核准的下一版設計

目前實作邊界：`analysis.py` 產生確定性特徵、五個分數／特徵
payload、五份 deterministic Fact Pack、evidence 與 aggregate；`runtime.py` 以 immutable Core snapshot 執行
 確定性 Mart，`gemini.py` 只提供可選的單一 Gemini 證據限定解說器。
通用 OpenRouter／Gemini／Codex runtime 屬 omniAgent，不是 Janus Mart provider。五個獨立 AI
分析角色已有 Codex CLI wrapper／provider orchestration 與 provider-neutral validator；GCP
完整 target／provider 整合與 auth lifecycle 尚待驗收。CIO 綜合分析、分析設定檔、內容定址重用與
Flutter Admin AI 分析設定工作區仍為**規劃中**。

下一版核准架構為：

`Core immutable snapshot → Evidence Validation → Deterministic Fact Engine →
5 independent Codex CLI Analysts（GCP batch；受控 fallback） → Deterministic AI Output Validator → CIO /
Synthesis AI → Deterministic Synthesis Validator → Governance / Publication Gate →
Immutable Mart artifacts`。

### GCP 批次 Codex 分析師研究路線（Active planning；尚未實作）

參考 [Codex Analyst Architecture](https://docs.google.com/document/d/1wPKndnPMbtVR1nkHEaUgmxTiUbt5_PkdyG-IY-l5Fo4/edit)
的五個獨立分析師、Fact Pack／validator／CIO／publication 分層。Drive 原文仍是
2026-09-25 的 Deferred research note；依使用者 2026-09-30 明確指示，本路線納入 active
WBS 規劃，以 GCP 批次自行執行為目標，不把規劃更新寫成 runtime 已完成。

- 首選 Codex CLI：既有 Mart Cloud Run Job／受控批次在 GCP 容器內啟動
  Fundamental／Valuation／Positioning／Quant／Event Risk 五個獨立 role invocation。
  每個 role 隔離輸入、workspace、輸出與 execution lineage；可先序列化，再依實測設定
  bounded concurrency，不要求五個新 GCP service，也不依賴本機 Codex 桌面或逐次人工操作。
- 本專案的「ChatGPT worker」尚未指定具體可驗證介面。本規劃優先以薄 worker wrapper
  管理 CLI；CLI 的必要協定能力不足且有實測證據時，才評估具體的非互動式 worker bridge。
  Bridge 必須證明 GCP 可達、auth、dispatch、cancel 與結果回收，不以人工貼 prompt／
  ChatGPT 網頁操作充當批次。CLI／bridge 與 OpenAI API 是不同 transport，不自動改用 API。
- Codex 為 primary；Gemini／OpenRouter 只作已核准、profile 明列順序與條件的受控 fallback。
  使用者尚未選定模型前，預設 `gpt-6.1-sol`＋`low`（輕）；之後依使用者選定的 profile 執行。
  Admin 須提供官方重新授權入口與該帳號最新可用模型清單；不得在 Admin 接收原始資格。
  Primary bounded retry 用盡或回 structured unavailable 後才可 fallback；輸出 validation
  失敗不得靠換 provider 繞過 validator。保存每次 attempt、failure、fallback reason 與實際
  provider／transport／model，禁止 silent fallback；沒有合格 fallback 時 fail closed。
- 初始化登入／OAuth／MFA 可由使用者完成，但正常批次須在初始化後自行 dispatch／續期／
  保存結果。Credentials／auth cache 僅放既有核准 secret storage，隔離執行身分並驗證 rotation／
  cold start；不得進 image、argv、log、一般資料表或前端。Auth 過期／revoked／續期失敗時
  留 structured failure／required user action，不用 placeholder。登入方式、GCP headless
  可行性、subscription quota 與可觀察 cost 都待實測，不假定 CLI 免成本或 auth 永久有效。
- CLI version、可用 model／structured-output／sandbox capability、參數、timeout、process-tree
  cancel、退出碼、retry budget、memory／CPU／workspace 清理與冷啟動須有界且可驗證。
  Artifact lineage／reuse identity 須保存實際 transport、CLI／bridge revision 與執行設定，
  不把「研究」當成省略隔離、secret redaction、PIT 或 publication gate 的理由。
  子程序只接收 allowlisted environment／role auth，不繼承 Janus catalog／control／publication
  DB credentials 或完整 runtime secret bundle；只讀已準備的 Fact Packs 與隔離輸出目錄。
- Fundamental／Valuation／Positioning／Quant 關閉 Web Search，只讀 Janus Fact Packs。
  Event Risk 的 controlled Web Search 是獨立 capability／來源 gate，預設關閉；外部發現先留
  research evidence，保存 URL／source／published_at／fetched_at／analysis_as_of／evidence_id，
  通過 source authorization、PIT／provenance／evidence validation 後才可影響分析。
  不直接補寫 Core，不能以這條例外解鎖 Analysis scraper 或無來源推論。
  目前 locked guardrail 禁止外部抓取；解鎖此 capability 前須有系統控制的版本化
  contract／guardrail 調整與來源驗收，不能用 methodology prompt 覆蓋。本次不啟用 Web Search。
- Janus 仍負責收集／清洗／deterministic facts、驗證與 publication。Worker 無 Core／canonical
  number／publication 寫入權；沿用 Gate 3 的 provider-neutral role contracts。CIO 只讀五份
  validated artifacts；任一失敗為 partial／failed。本路線只涵蓋 Mart 研究批次，不重開
  已退役 WBS-4C 通用 Chat／Agent，也不自動建立新資源、啟用付費 API 或部署 Production。

主要驗收是 GCP dev 既有批次的五角色真實 execution、immutable Fact Pack fence、
validator／artifact readback、cold-start auth 與 failure／fallback／cancel evidence。
本機 CLI 成功、人工觸發成功或五個 schema fixtures 都不能替代 GCP 自主批次驗收；
自然每日運行仍由 Gate 6 額外證明。研究可行性以實測判定，本次文件對齊不以官網聲明
作為可行性結論；後續 implementation 仍須模型確認與現有成本／安全 gate。

受控 dev 驗收與未完成 auth lifecycle 的操作限制見 [provider runbook](../runbook-mart-ai-providers.md)。

### 五角色個股批次範圍（Active planning；尚未接線）

使用者 2026-09-30 選定 **active 關注股＋目前有效持股的 symbol 聯集，去重後分析**。
每次批次依 `analysis_as_of` 可見的 membership／持股狀態固定並保存 immutable target
symbols／membership hash；同一 symbol 不因多位使用者關注或同時持有而重複建立五角色工作。
500 檔有效名單是資料網／deterministic screening，不自動產生 500×5 次 AI 分析；
既有 ingestion event 的 market／industry／全部 symbol scopes 也不是 AI admission 名單。
Market／industry AI analysis 須另有明確 scope profile／quota，不隱含於本個股批次。

持股即使離開 500 名單仍在 AI target 聯集；這不自動新增深度來源、抓取頻率或付費資源。
缺資料／PIT／來源資格不合格時保存 missing／insufficient_data／blocked，不用 AI 補值或
宣稱完整成功。取消關注且已無有效持股才退出後續 target；歷史 membership／artifact 不覆寫。
關注股的既有 50 distinct-symbol 護欄仍適用於 watchlist／deep collection，不等同於
關注＋持股 AI 聯集的已核准無界 call quota；AI 批次另做 bounded 子批次、concurrency、
attempt／token／quota／cost preflight，受控 queue 若有 50-symbol 單批限制仍須遵守。
預算／quota 不足時明列未處理 symbol 與 partial／blocked reason，不靜默截斷或擴大付費範圍。

Target membership 只使用已授權的控制／私人讀取邊界產生去識別化 symbols；公開 Mart 與
Codex 只讀公開 canonical Fact Packs，不取得 user-to-symbol 對應、持股數量、成本或私人交易。
私人持股／曝險解釋仍由 authenticated owner 邊界使用公開 analysis reference。
驗收需涵蓋 watch-only／held-only／兩者重疊、多使用者去重、持股離榜、取消關注／清倉、
as-of membership replay、quota／missing-data honesty 與 public／private isolation。

### AI role／CIO contract v1

`intelligence_mart/ai_contract.py` 與 `packages/contracts/mart_ai.v1.json` 提供五個
discriminated role output schema 及 CIO schema；不取代 `mart.v1` deterministic roles。
所有主張使用 `Claim{text,evidence_ids}`；`insufficient_data` 可以沒有 thesis／evidence，
但必須揭露 `missing_information`，不得填 placeholder。格式錯誤回傳 `failed` 與
`invalid_structured_output`；未知角色回傳 `invalid_role`，兩者都不保存原始 provider 文字。
格式通過僅為 `schema_validated / validation_status=pending`，不代表 evidence／numeric／PIT
語意驗證通過、完整研究成功或取得 publication authority。

System guardrail 固定於系統程式，不接受 methodology override。六份 methodology revision
保存於 `prompts/ai_methodology.v1.json`，每份含 version、author、timezone timestamp、
profile reference 與 content hash；Admin editor 留待自身 WBS。新 execution 的 create-only
`artifacts/ai-role-contract.json` 保存 schema、prompt 與 guardrail 全文；舊 manifest 不補寫。
Interpretation artifact 保存 execution／scope／as-of／Core snapshot、Fact Pack／evidence
hash、feature／governance version、provider／model／parameters、profile 與 schema／prompt／
guardrail version／hash，保存於 `interpretations/{artifact_hash}.json`；相同內容可重複保存，
不同內容不得覆寫同一 object。此為不可變保存契約，不代表 rerun/cache orchestration 已完成。
CIO schema 要求五份 validated role artifact hashes；實際資格驗證與 synthesis 執行仍屬後續 WBS。

### 五角色 deterministic output validator

`intelligence_mart/ai_validation.py` 提供 provider-neutral `role-validator-v1`，輸入為
shape artifact 與由 Janus 提供的可信 immutable report；重新核對 schema／prompt／guardrail、
execution／scope／as-of／snapshot／feature／governance、Fact Pack／evidence hash、provenance
集合與 role evidence IDs。沿用原 evidence validator 檢查 URL、授權、單位、重複、衝突與
dataset freshness；另檢查每筆 publication／availability／observation／record time fence。

每個 Claim 的 evidence IDs 須屬於該 role，top-level IDs 必須等於所有 Claim IDs 聯集。
`missing_information` 必須逐項列出 Fact Pack 的 missing fact keys；不得把已驗證的
`insufficient_data` 包裝成完整研究成功。數字主張採保守、fail-closed 的複製契約：只有
以分隔符隔開、逐字引用既有 `fact_key=value` 的數字可接受；自由數字、改值、rounding、
額外單位／百分比或自行計算均拒絕。此規則不自行推算單位，也不宣稱任意自然語言的
數字辨識或 qualitative entailment 已被證明；evidence coverage 不等於推論成立／投資有用。

結果為 create-only `mart_ai_validation_v1` artifact，保存 source artifact hash、合格 lineage
（invalid contract 改用可信 report audit context）、
validator version、sorted error codes 與 `validated`／`blocked`，不複製 rejected output／
exception input；artifact hash 與 source interpretation reference 必須一併供稽核讀回。
只有五個不同角色、同 execution／scope／profile 的完整 validated 結果才形成 complete
validation；任一 missing／blocked／跨 scope 為 partial，insufficient_data 不算 five-role
full success。呼叫者須從可信保存邊界讀取 validator 結果，hash 不替代身分授權。
Validator 永遠沒有 publication authority，既有 deterministic publication path 不變；CIO
qualification／synthesis 與 Codex CLI runtime 分別留待自己的 WBS。

確定性事實引擎的正式定位是「事實包」，分為基本面、估值、籌碼、量化、事件風險五包。
它負責數字、PIT、特徵計算、歷史比較、缺失資料語意、來源追溯、證據引用與基準分數；
基準分數保留作回歸／漂移／結果評估參考，但不等於完整研究分析。

目前 `FactPackV1` 版本為 `1.0.0`，保存 `pack_type`、`analysis_as_of`、
`core_snapshot_id`、`feature_version`、`facts`、`missing_data`、`evidence_ids`、
`provenance_ids`、`evidence_hash`、`baseline` 與 `fact_pack_hash`。
Evidence 先通過 PIT／來源／provenance validation 再進 Fact Pack；同一 immutable
input 可 deterministic replay。Hashes 使用 canonical JSON 的 SHA-256，不包含
analysis execution identity 或 LLM narrative。Baseline 的 score／completeness／
confidence 保留既有 deterministic role 語意，不是 AI analyst output。
五包隨 `mart_scoped_analysis_v1.payload_json` 保存；`mart.v1` contract 的 additive
`1.1.0` 將 `fact_packs` 保留為 optional 欄位，舊 consumer 不必有該欄位。
LLM 關閉不改 facts，缺值不補算；缺資料的 report 仍受原 publication gate 限制。

### mart.v1 additive compatibility

AI interpretation／validation references 保存於獨立 `mart_compat.v1` sidecar，
以 execution／scope／as-of／Core snapshot／deterministic hash 綁定 v1 report；
不新增 strict `MartScopedAnalysisV1` 欄位，不改 publication authority。
舊 consumer 仍讀原 v1 report。future v2 的 shadow／opt-in／cutover／rollback
條件見 [Mart 相容策略](mart-v2-compatibility.md)，不得由 sidecar 存在推定 migration 完成。

## 9. Mart + ML／AI／LLM Job

職責：

- 只讀 versioned Core snapshot；禁止即時補抓。
- 產製特徵、ML 成果物、五角色輸出、證據驗證器、聚合器。
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

AI 分析角色／CIO 只能使用不可變更的事實包與已驗證證據，不能改 canonical
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

- `chips_status` 是受控字彙的顯示文案，必須可回溯 Positioning evidence，不可由 Flutter 自行推斷。
- `ai_whitepaper_analysis` 不得加入 evidence 未出現的數字、客戶或訂單；示例比喻只能建立在已驗證事實上。
- 分數不完整或未通過發布政策時，不得為了 UI 填滿而產生預設健康度或文案。

私人 ledger 的交易類型至少包含 `BUY`、`SELL`、`CASH_DIV`、`STOCK_DIV`；依類型驗證 date、symbol、shares、price、fee、tax 與 currency，金額／股數一律使用固定精度 decimal。私人 Mart 最少包含 `mart_user_positions`、`mart_user_realized_pnl`、`mart_user_unrealized_pnl` 與 `mart_user_annual_pnl`；每筆結果必須帶 `user_id`、ledger version、valuation date、cost-basis method、currency 與 lineage。成本法在 MVP 固定為移動平均法；FIFO 只在完成稅務／會計語意與回歸測試後才能開放。

個人風險與顧問功能排在上述私人 P0 後：

- `user_investment_profile` 保存 risk tolerance、investment horizon、primary goal 與 minimum cash ratio；目前值使用 bounded private index，歷史 revision 進 Private Iceberg，且只在使用者明確授權時提供給外部助理 context。
- `mart_user_exposure` 以現金、持股市值與有效日期的多產業 membership 計算曝險；一檔股票可屬多個產業，分攤方法與 membership snapshot 必須版本化，前端與 LLM 不自行計算。
- `mart_user_annual_performance` 在現金流語意、股利與更正事件通過回歸後提供 XIRR；無根、多根或資料不足時回傳 typed status，不填 0。
- 投資組合 stress test 先由 deterministic scenario 計算資產與現金水位變化；若外部助理解釋結果，只能使用已授權的 bounded context，且不得修改數值、替使用者下單或輸出保證性建議。
- 新聞與情緒沿用公開 Core provenance／`mart_alternative_sentiment`；Gemini Google Search grounding 是對話當下的外部補充，只保存必要 query／citation metadata，不把未授權新聞全文寫入 Private Iceberg 或公開 Core。

五角色：Fundamental、Valuation Risk、Positioning、Quant、Event Risk。

### AI 分析角色、CIO 與提示詞契約（contract 已實作；AI 執行仍規劃中）

五個角色是獨立、以證據為根據的分析階段，可平行執行。每個階段輸入不可變更的事實包、
已驗證證據、`analysis_as_of`、Core snapshot identity、不可變更的系統護欄、版本化角色
方法提示詞，以及模型服務商／模型／參數。輸出至少包含 `stance`、`thesis`、`key_findings`、`positive_evidence`、
`negative_evidence`、`contradictions`、`change_drivers`、`risks`、
`missing_information`、`what_would_change_my_view`、`confidence` 與 `evidence_ids`。

系統護欄不可由 Admin 編輯，至少禁止捏造數字、使用未來資料、隱瞞缺失資訊、提出沒有
證據 ID 的主張、修改確定性事實或決定發布，並明示 confidence 不是獲利機率。角色方法
提示詞（五角色及 CIO）可由唯一 Admin 編輯，但每次修改都建立不可變更版本、內容雜湊、
作者、時間戳記與分析設定檔引用；輸出結構由系統控制。

### 規劃中的 CIO、驗證、重新分析與重用

CIO 只讀確定性事實摘要、五份已驗證的角色分析、基準訊號、證據引用與治理限制，
輸出整體立場／論點、支持／
opposing roles、contradictions、bull／bear、principal risks、watch items 與 change
since previous analysis。CIO 沒有 publication authority；role 與 CIO 都必須通過
確定性驗證器。驗證器至少檢查結構、證據是否存在、數字根據、`analysis_as_of` 時間界線、
未來資料滲漏、缺失資料誠實性、主張／證據覆蓋率、模型服務商／模型／提示詞版本追溯鏈
與不可變更輸入身分。無效角色必須留下結構化失敗，不寫 placeholder；一個角色失敗不得
宣稱五角色全部成功。

正式重新分析語意：事實包未變時，單角色重跑只執行該角色、驗證器、CIO、CIO 驗證器與
治理重算，其他角色成果物重用；Core／相關事實包改變時先重建受影響的事實包；提示詞／
模型改變不重算事實；CIO 提示詞／模型改變只跑 CIO；治理改變只做確定性治理評估；
全部重跑只放在進階功能。

角色成果物的內容定址身分至少包含 `fact_pack_hash`、`evidence_hash`、`role_prompt_hash`、
模型服務商、模型、模型參數、系統護欄版本與相關結構版本。相同身分可重用不可變更成果物，
但每次重用都要留下稽核／版本追溯鏈，不得重複 AI 呼叫。事實與解讀分開保存，例如
`executions/{execution_id}/facts/*`、`executions/{execution_id}/interpretations/*`、
`synthesis/cio.json`、`validation/*` 與 `manifest.json`；實際 storage contract 仍依
既有 GCS／Iceberg boundary 設計。

治理／發布閘門仍是確定性流程：`complete`、`insufficient_data`、
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
