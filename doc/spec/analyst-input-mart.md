# 四模型分析輸入 Mart 與個股報告頻率

更新：2026-10-25。靜態程式查核；不是線上資料覆蓋、模型已上線或測試PASS。此增量併SEQ-01／05／06／07／08，不開第二條工作線，調校仍延至2027 Q1。

## 1. 結論與證據

**不能認定現有Mart足夠。** storage.py列11個歷史Iceberg Mart名稱，不代表每表有現役writer或模型因子。market_screening.py主要產報酬／相對強弱／成交金額／波動／PE/PB摘要；specialists.py仍是規則輸出，product_runtime.py只有Risk正式預測的獨立overlay。research/chatgpt/janus_precision.py有34個模型席位（非34個不重複因子）：Quant11、Risk8、Fundamental10、Valuation5；正式模型自己的feature schema仍是最終依據，不能自動拿此清單取代12／14／15等候選版本。

| 角色 | 現有資料／計算 | 已證實缺口與處置 |
|---|---|---|
| Quant | Core OHLCV；研究公式11席位 | Screening未提供完整同版X；重用研究因子公式只輸出當期X，保留未知／缺窗口 |
| Risk | risk_inputs.py＋risk_pilot／risk_v1八因子 | 既有獨立讀取保留；RMS波動與screening去均值std不可互換，使用現役Risk公式 |
| Fundamental | financials月營收；研究10席位 | stock_supplement只補13月，但三月合計YoY需15月；改目標15完整月／550曆日取回範圍；統一TWD／千元，不反覆補已有另一合法單位資料 |
| Valuation | Core估值／財務；RV reader／純函式 | 缺模型會計口徑mapping；不拿debt_to_equity當debt_ratio、不拿PE當X；模型X缺值明列。RV的EPS/BVPS／24有效月仍由SEQ-05接線，不能由新Mart捏造 |

本輪不跑live查詢／測試，真實逐股可用比例未知；下一AI在SEQ-08按2330、2882、既有持股／觀察股抽樣讀回，不做全歷史稽核。

## 2. 兩方案與選擇

| 面向 | A：既有Mart execution內物化分析輸入 | B：新Iceberg寬表與獨立刷新工作 |
|---|---|---|
| 業務價值 | 一次計算供分析／報告共讀 | 多讀者大規模SQL查詢較方便 |
| 架構／複雜度／速度 | 原Job、GCS execution artifact、既有PG product；改動較小 | 新schema／writer／maintenance與遷移較多 |
| Cloud Run／DB／網路／成本 | 只讀持股∪觀察股公開資料，不新增服務或IAM；既有界限 | 額外寫入／compaction／查詢及維護 |
| 安全／失敗隔離／回復 | 無owner欄位；缺角色不造數字，保留舊產品；回復image | 要管理表schema與舊reader相容 |
| 維護／適配 | 適合目前小範圍深度分析 | 多消費者／大查詢量才值得 |

採A，P1：建立邏輯分析Mart executions/<id>/analyst-inputs.json，不是新增Iceberg表或新bucket。資料來源仍Stage→Core，持股／觀察股僅提供去識別化股票聯集，公開artifact不含owner、成本、數量或現金。報告由Private層結合個人曝險。未來有實際SQL需求才評估B。

## 3. 資料流與契約

- Stage沿現有adapter／idempotency／48h清理；增量補收只補必要缺月，無新爬蟲或全市場歷史重抓。
- Core保留原始合法單位；分析adapter把月營收TWD_thousands乘1000轉TWD，重複相同值合併、衝突維持missing。收取期間與計算期間分開。
- 全市場screening仍原每日一次；深度specialist reader改只讀target聯集，市場benchmark共用不得被股票symbol filter漏掉。
- 分析Mart保存四角色feature_order、values、missing_features、feature_version、input_as_of、source日期／缺口；只保留X，不儲存Y、未來報酬或Owner資訊。每天新資料可更新事實；不宣稱模型已適配此版本。
- Quant／Fundamental重用現有研究公式；Risk重用現役八因子公式。未知market不可猜；缺交易日不能前補；財務口徑未知不得硬湊。Valuation新增X前必須同模型schema完成會計mapping（SEQ-06），本輪顯示缺口，不擅自改公式。
- 新artifact連到specialist manifest及既有product，供分析師／報告讀取；讀回驗hash、symbol／as_of，沿現有execution保留清理，不新增備份排程。
- feature_ready只表示該參考schema的必要值齊，model_compatible仍需SEQ-06對實際發布artifact驗證；不等於可發布／模型有效。

## 4. 頻率決策（工程預設，可由後續實測調整）

| 工作 | 執行頻率 | 理由 |
|---|---|---|
| 原始行情／EOD、損益與快照 | 保留既有每日／異動更新 | 不能因報告減頻而讓持股價格與損益過期 |
| Quant／Risk輸入與推論 | 有新交易日資料時最多每日一次；同輸入重用 | 新價格可能改變風險，無需每兩小時重推論 |
| Fundamental | 新月營收／財報或更正時 | 相同財務內容無需每日重算 |
| Valuation模型／估值基礎 | 財務或模型版本變更；既有價差欄隨收盤更新 | 價格位置與估值基礎分開，不能每天重跑同財報模型 |
| 持股／觀察股完整事實報告 | 首次、距上次7日且有新資料、財務變更、版本變更，或相對上次報告收盤價變動≥5% | 週期＋異動；5%僅報告更新門檻，不是交易訊號 |
| 手動重產報告／CEO長文 | 按需，沿既有權限／quota／Gateway | 不新增每日自動LLM支出 |
| 個人買賣／觀察設定變更 | 快照立即／既有背景更新；新標的首次分析 | 成本與數量不觸發全市場公開模型重訓 |

報告以資料日計7日，不因假日tick製造新版本；同資料不重新蓋今天日期。每天產品可以帶較舊完整報告，保留report_as_of／inputs_as_of與reuse狀態；不能用舊報告日期代替最新價格日期。失敗／partial保留明確缺值，不假稱四ML齊備。此自動報告是可重算事實摘要，CEO仍按需。

## 5. 交付與驗收責任

本輪：文件＋程式與測試來源，未執行測試／CI／migration／部署／驗收。SEQ-01驗15月補收／單位及target讀取，SEQ-05驗RV，SEQ-06核對四個真模型schema與mapping，SEQ-07驗報告重用及Owner接線，SEQ-08集中實機驗收。詳細指示見[WI](../runbook-analyst-input-mart-ai.md)。

風險：資料缺口仍可能存在、模型schema可能不同、舊五角色API尚相容；用missing／model_compatible未驗狀態表達。沒有新資源或IAM；原部署限制不變。回復固定舊image即可，新增payload欄位可由舊reader忽略；不得刪Owner資料。

實作界限：本輪已接分析X artifact、15月補收及deterministic stock_report週期；四模型正式推論、Valuation會計mapping、各模型dirty-input推論快取與UI呈現仍歸SEQ-06／07。頻率表是這些任務的契約，不表示所有ML執行節奏已上線。新報告保留每角色原model_status，不用規則報告冒充四ML報告。
