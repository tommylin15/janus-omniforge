# 方案 A｜個股變化判讀、盤前與盤後
更新：2026-10-24。**A1–A4 原定有界工作包已 USER_ACCEPTED／CLOSED。** Python／Flutter、GHCR、dev API 100% 與獨立 live readback 已 PASS；2026-10-24 使用者回覆「核對完成」屬 Owner UI 使用者驗收，並非額外的 OAuth／跨 Owner trace／截圖機器收據。詳 [Operations](operations-and-testing.md)。下列 §2 保留 2026-10-21 開工前問題基準，不能再當尚未實作或 Active TODO；後續 04 RV 功能另見 [Valuation 規格](valuation-range.md)。

## 1. 目標與範圍
讓小白 30 秒內回答「現在狀態、最新變化、下一個觀察點」。先用現有正式資料與規則產出事實解讀，再接 D07 合格預測。保留原四頁、持股金額與圖表，不重開 D01～D06/DRL/FINOPS。
本輪規劃持股∪關注股站內盤前/盤後、跨日觀察；全市場沿用 screening。沒有推播、盤中 tick、新供應商、新服務、自動 LLM、自動下單或個人現金反推公開股票評價。
公開個股判讀與私人清單/成本/現金隔離。同股票同 cutoff 的公開判讀相同；個人曝險另作 overlay。

## 2. 有界查證與改善清單
查證基準 main d7083890738a8660786110d0c73d58d8fe183c15；這是程式盤點，不是登入後畫面或新版部署證據。
| 切片 | 已見問題／需要增加 | 交付與驗收 |
|---|---|---|
| A1 事實解讀 | specialists.py 的 plain_language 串接指標；個股摘要/支持風險被 validated gate 包住，且只取第一可用角色 | 事實解讀獨立於模型 gate；營運/價格/風險/估值/事件只用有效證據；每句可定位比較值、期間和來源；無假因果 |
| A2 變化追蹤 | 現有 future-market-alerts 是 deferred；缺有界前後判斷閉環 | 保存前次觀察、當次比較、新增/持續/增強/減弱/解除/失效；同事件修訂不冒充新事件；無資料不等於解除 |
| A3 盤前盤後 | 首頁目前市場→個人→模型簡報；尚需專用截止時間及摘要 | 同一批公開 facts 組成兩種 view；盤前列可觀察條件，盤後回核原條件；明示資料截止與未更新區塊 |
| A4 UI/集中驗收 | 既有三行重點與程式呈現有落差 | 首頁優先重要變化；個股狀態/證據/下一觀察點→一個主圖→深入資料；390px/桌面真實讀回，30秒理解測試 |
這四切片屬一個 A-CHANGE 工作包，開工後整包集中驗收；已驗過的記帳/現金流程只做受影響回歸。

## 3. 解讀契約
每條 observation 最少含 symbol、kind、state、headline、meaning、evidence_refs、metric/value/comparison_value/unit/period、analysis_as_of、cutoff_at、source_available_at、rule_version、input_hash、previous_observation_id、next_check、invalidation_condition、status。
將 confirmed_fact、conditional_scenario、scheduled_event、validated_prediction 分開。規則門檻版本化，不把規則強弱當上漲機率。
- 比較：同口徑/同單位/明確期間；價格趨勢必考慮公司行動；同比基期為負/零時用轉虧轉盈或差額，不能亂算成長率。
- 關係：價量同時變化可說「同時」，不能無證據說公告造成上漲；法人買超不是知道主力意圖。
- 支持與疑點各最多兩項；未驗證 ML 不輸出機率/買賣分數；有合格當期事實則正常顯示，不等五角色齊全。
- 缺失只影響相依結論。資料不足、來源過期、確認無異動三種狀態分開。
- 若條件用到未來量能/價格，必須有可驗證門檻、有效期間與失效條件；未校準門檻只能標觀察規則。
- 同一事件以 symbol+kind+period+source_event/version 建身份；重跑同 input_hash 冪等，來源修訂形成 revision，不改寫舊報告。

## 4. 盤前／盤後與變化狀態
採 Asia/Taipei，實際 batch 由現有 Controller 路由；具體時間由既有來源完成時間決定，不在文件虛構已部署 cron。
- 盤後：等當日 EOD 及可用資料完成後組成 snapshot；未到資料保留上次結果及日期，不宣稱完整收盤分析。
- 盤前：最近完整交易日價量＋本次 cutoff 前新增公告/已知事件；沒有隔夜來源則明寫依昨日收盤資料。股價窗口不因跨午夜自動前移。
- 休市：不製造新交易日；若有新公告，可更新事件區並保持價量日期。盤中 quote 只供行情，不混進 EOD 模型特徵。
- 首次出現→新增；仍成立→持續；可量測條件更強/弱→增強/減弱；觀察原因消失→解除；原假設被反證→失效；超過有效期→過期。缺資料→待更新，不能自動解除。
- 保存小型 facts/observation/預測/結果紀錄，擬定 365 日熱讀上限；未成熟預測及現役觀察保留至成熟/終態，模型回饋明細另按[模型生命週期](model-lifecycle.md)保存36月；現役/回退模型與必要研究輸入保護，不以365日熱讀期限提前清掉成熟評估證據。這是新產物政策，不改 Stage48h/Core current-only，也不授權刪除既有資料。

## 5. UI 唯一呈現補充
本節只定義方案 A 增量語意，視覺 tokens/尺寸仍由 [四頁 UI](../ui/visual-first-four-pages.md) 維護。
- 今日：緊湊資產摘要→最多三則重要變化→市場位置；盤前/盤後標籤及 cutoff 就近顯示。個人清單只決定選取與排序。
- 個股：報價/持股→一張「目前狀態、最新變化、下一觀察、失效條件」卡→既有單一主圖→支持疑點/筆記→來源/五角色/CEO 收合。
- 標題用「近期轉強」「營運改善但價格偏高」「變動加大」等白話；不得只丟 CVaR、Beta、供給區等名詞。若要顯示術語，旁邊給一句解釋。
- 保留數字與圖表可下鑽，主卡不要堆缺值清單、hash、model_version 或五個重複分析師段落。
- 沒持股則不放空持股大卡；無事實不補空健康分。資料日期與必要參考/部分語意不能藏起來。

## 6. 工程界線與交付
重用 specialists.py、market_screening.py、packages/analysis_product.py、既有 Mart projection/API、final_stock_detail.dart、final_today_v2.dart。具體 migration/route 名稱開工先查，不在此假稱存在。
新增計算放既有批次及 dirty symbol 路徑，Web GET 只讀 persisted serving；不開頁掃 Iceberg/抓外網/跑 ML 或 LLM。公開分析一次產出，多 owner 共用，私人 membership 在授權 API 過濾。
A-CHANGE 的模板摘要不依賴 D07；D07 只增加已驗證預測，D08 手動 CEO 沿原品質/權限 gate，不因 A 取消治理。

## 7. 驗收
規則數字重算、source/time/單位、缺值/修訂/休市/重跑、跨股/跨 owner、未驗證模型隱藏而事實可見、狀態轉移與過期、前後報告對照。先以資料齊/缺財報/公司行動或停牌的代表案例，再真實 dev API/UI readback；不足案例用 fixture 補邊界，不冒充 live。
手機30秒可說出三要點；同一數字在圖/摘要/Fact Pack 一致。成功、失敗保留上版與回退驗證。以本界線結案，不做無限全市場/全歷史追查。

