# Janus — TODO

版本：3.0
用途：**只保留確定要做的工作**。不確定、暫不做、純 observation、Production 才需要、已接受缺口與研究構想一律不放 active TODO；統一保存在 [`parking-lot.md`](parking-lot.md)，且不計入目前專案未完成度。

## 規則：只有「做／不做」

- 在本文件：**做**。代表 Janus 已確認最後需要完成，必須有明確 implementation／acceptance，依順序執行。
- 不在本文件而在 [`parking-lot.md`](parking-lot.md)：**不做**。保留資料供未來翻找，但不得自行開工，也不得把它當成目前欠著沒做。
- 已接受的 source-level missing、coverage threshold 內缺值、自然 observation 沒有新 evidence，都不建立 TODO checkbox。
- Active WBS 可以因外部核准或 runtime evidence 暫時呈 `partial`／`blocked`；這是執行狀態，不是第三種工作分類。
- 完成證據與歷史 checkpoint 移入 `archive/` 或 `spec/operations-and-testing.md`，不讓 TODO 永久累積歷史流水帳。

歷史／決策入口：

- [WBS-3 補資料第一版完成（2026-10-03）](archive/wbs-3-data-supplement-v1-completed-2026-10-03.md)

- [2026-10-02 Admin／User／Routing／Provider 決策總結](decision-2026-10-02-admin-user-routing-and-provider-plan.md)
- [2026-10-02 Legacy Static Admin 退役／backup 座標](archive/legacy-static-admin-retired-2026-10-02.md)
- [Parking Lot／暫不做](parking-lot.md)
- [2026-09-26 Product Completeness reprioritization 與 TODO cleanup](archive/todo-cleanup-and-product-completeness-priority-2026-09-26.md)
- [WBS-3 Liquid-500 rotation completed](archive/wbs-3-liquid-500-rotation-completed-2026-09-27.md)
- [WBS-3 TWSE 500 base coverage completed](archive/wbs-3-full-market-base-coverage-completed-2026-09-29.md)
- [WBS-5 Mart Fact Packs completed](archive/wbs-5-mart-fact-packs-2026-09-30.md)
- [WBS-5 Mart v1 additive compatibility completed](archive/wbs-5-mart-v2-compat-2026-10-01.md)
- [WBS-6 MIS 持股報價 completed](archive/wbs-6-portfolio-intraday-quote-2026-10-01.md)
- 其他已完成證據保留於 `archive/`；完整 runtime／deployment evidence 見 `spec/operations-and-testing.md`。

六個月 Dev Pilot 的自然 evidence 只寫入 [`pilot-operational-evidence.md`](pilot-operational-evidence.md)；它不是 active engineering TODO，也不因沒有新事件而製造待辦。

## 模型確認規則

- 每次只取下列順序中的一個可執行 WBS／工作組。正式執行前，AI 先提醒建議模型與目標 WBS／工作組；使用者明確確認後開始。
- 一旦開始，以整體 acceptance scope 結案，不在內部 dataset／adapter／單一畫面之間反覆停等。
- 新付費 API／model／subscription、新付費 GCP 資源、重大權限擴張、不可逆大量刪除、MFA／OAuth consent／付款仍需使用者明確授權。

# 執行順序

## 1. `WBS-5-MART-AI-PROVIDERS` — 【Sol】— **partial；依使用者決策暫停前景執行**

- [ ] GCP Mart 自主啟動五個獨立 Codex CLI workers；完成 headless dispatch、cold-start auth／續期、role workspace 隔離、capability／參數、timeout／process-tree cancel／退出碼／bounded retry。
- [ ] Provider route 預設 **Codex CLI → OpenRouter → Gemini**；只有 approved／authorized 且符合 free-or-explicitly-approved-paid gate 的 profile 進 effective route。每個 execution 固定 route version/hash/profile snapshot，保存 attempt／fallback reason／transport／model／parameters／latency／可觀察 usage/cost。
- [ ] Fallback 只限 timeout／transport／rate-limit／provider unavailable／auth-capacity unavailable 等核准 failure class；schema／validator／grounding／PIT／missing-data failure 不得藉由換 provider 繞過。
- [ ] 完成 watch-only／held-only／重疊去重、多使用者、持股離榜、取消關注／清倉、as-of replay、quota／missing-data honesty 與 private isolation 的 same-execution acceptance。
- [ ] 完成 GCP dev 真實五角色 execution、validator、artifact readback、auth lifecycle、structured failure 與 zero-secret-leakage acceptance；本機 router code、credential probe、CI 或 deploy 單獨不構成 completion。
- 2026-10-01 evidence：GCP `gpt-6.1-sol`＋`low` 五次真實 CLI 輸出、17-object readback 與九類 DB 投影驗收通過；validator 3 validated／insufficient_data、2 blocked。
- 2026-10-02 credential evidence：Fugle quote HTTP 200；Gemini models HTTP 200；OpenRouter key HTTP 200 但 `is_free_tier=false`。OpenRouter 尚需 `$0`/free-only actual model request；Gemini 尚需 Free Tier／billing confirmation。Fugle credential 可用，但行情 source approval／runtime 接線在後續 Quote Router 工作完成。
- 2026-10-02 bounded runtime checkpoint：第二個 GCP cold-start execution 五角色均 `validated/insufficient_data`，19-object readback／單股 same-execution Core／target lineage 通過；effective route 僅 Codex。兩批共用完十次核准 invocation，auth version 1→1、rotation 未觀察。OpenRouter 免費請求與 Gemini billing probe 被自動審核擋下，兩者維持 blocked；WBS 仍 partial。逐角色缺資料與未完成 gate 見 [checkpoint](archive/wbs-5-mart-ai-providers-checkpoint-2026-10-02.md)。

## 2. `WBS-5-MART-CIO-SYNTHESIS` — 【Sol】

- [ ] CIO 只讀 validated role outputs；建立 synthesis／validator／immutable lineage。
- [ ] CIO 無 publication authority；publication 仍由 deterministic governance 決定。
- [ ] 任一 input／validator failure 保持 structured partial／blocked，不包裝成完整研究成功。

## 3. `WBS-5-MART-RERUN-CACHE` — 【Sol】

- [ ] single-role rerun、dependency invalidation、content-addressed reuse、immutable artifact lineage。
- [ ] prompt/model 改變不重算 deterministic facts；governance-only change 不呼叫 LLM。
- [ ] 相同 identity reuse 可稽核，且舊 artifact immutable。

## 4. `WBS-6-ADMIN-ANALYSIS-PROFILE` — 【Sol】

- [ ] Production Profile versioning、direct new Production、rollback、role／CIO prompt editor、locked guardrail、model picker、per-role override、固定 test symbols 與 compare。
- [ ] Provider global default `Codex CLI → OpenRouter → Gemini`；Admin 只可 reorder 已核准 provider，execution 固定 route version/hash snapshot。
- [ ] 顯示 provider approval／auth／health、官方重新授權入口與最新可用 model list；Admin 不接收或顯示原始 token。

## 5. Admin operational convergence — 【Sol】

- [ ] **Actionable exceptions**：首頁「需要處理的事項」由被動 count 改成可點入 filtered 明細，至少顯示哪一筆、reason、last update、retryability 與安全 action；正常 execution 不佔主要空間。
- [ ] **Job Control Center**：master／batch controller＋child jobs、effective schedule／trigger、latest state／last update／latest success、最近 3 天 timeline＋更早歷史選取、安全 manual rerun、dependency／duplicate／exclusive guard 與 audit。
- [ ] **Storage／Private Operations**：Stage／Core／Mart／Private Mart live objects／active bytes、snapshot／manifest、report references、retention／maintenance／anomaly；Private Pipeline checkpoint／backlog／last execution／valuation lag；live bytes 與 billable storage 分開，未知顯示 `unknown`。
- [ ] **Routing controls**：versioned reorder／audit／optimistic lock；AI route 如上；行情 target default 盤中 `Yahoo → Fugle realtime → TWSE MIS`、盤後 `TWSE EOD → Fugle → Yahoo`。effective route 只包含 approved／authorized source；Yahoo 未授權前必須跳過。

## 6. User operational convergence — 【Sol／Luna】

- [ ] 【Sol】 **Performance profiling + fix**：先量測 auth、DB connect/query、Iceberg、endpoint fan-out、p50/p95；再處理已證實的 Flutter page recreation／Future-in-build、section loading、request cache／SWR、PostgreSQL pool、interactive Iceberg read model。不得無 evidence 宣稱 CPU／RAM／index／bloat root cause。
- [ ] 【Sol】 **Quote Router＋persisted last quote**：先完成免費可核准來源審查；DB-first → async refresh → success persist；保存 source／quote_at／received_at／session／freshness。盤中 operational quote 不覆寫 canonical Core OHLCV／Private Mart EOD。Fugle 走免費範圍核准；Yahoo 在未取得明確授權前不進 executable route。
- [ ] 【Sol】 **Transaction synchronous position projection**：ledger commit 後由 backend deterministic projection 立即更新 shares／average cost／cash impact；Flutter 不自算 authoritative holdings；Private Mart 保留 canonical valuation／PnL／risk／reconciliation。
- [ ] 【Luna】 **Journal／Watchlist／Stock Detail UX**：記帳預設第一頁為「持股」；Watchlist 與 Trade form 共用中文股票名稱＋代號 autocomplete；Stock Detail 在既有 health／AI plain-language／why-risk hierarchy 整合研究資訊，不另建重複頁。
- [ ] 【Sol】 **操作池／Broker Profile**：current cash／可稽核 cash-ledger strategy、fee discount multiplier、minimum broker fee、server-side fee/tax rule version；交易表單不要求每次手填 fee/tax，歷史重現與 audit 保留。
- [ ] 【Luna】 **Typed numeric formatter**：price semantics 2 decimals；amount／shares／ratio 依契約整數＋comma、negative parentheses；股票代號／日期／交易輸入維持原語意。

## 7. `WBS-6-USER-FINAL-VISUAL-CONVERGENCE` — 【Luna／Sol】

- [ ] 依 `ui/user-app.md` 與 `ui/reference/user-app-final/README.md` 完成 Today／Watchlist／Ledger／Stock Detail 四頁 final presentation convergence。
- [ ] 四張 final PNG binary、Flutter targeted／golden／screenshot regression 與 GCP dev 真實 authenticated browser acceptance 完整；sample/mock data 不得進 canonical runtime。
- [ ] loading／empty／error／partial／stale／missing 狀態一致且不得 permanent spinner；Flutter 不自行計算 canonical PnL／研究數字。

## 完成證據

每個 TODO 至少需有與範圍相稱的 implementation、tests／CI、deployment、migration（如適用）、live runtime／integration acceptance；文件勾選、commit、build 或單次 bounded success 本身都不等於完成。
