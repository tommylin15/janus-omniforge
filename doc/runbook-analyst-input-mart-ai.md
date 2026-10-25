# 分析輸入Mart／個股報告：AI驗測交接

本輪只交付程式／文件／測試來源，以下尚未執行。依[SEQ順序](todo.md)逐項開工，不另外觸發日常GitHub批次或重訓。

## 1. 文件設計（建議GPT-6 Astra）

讀PROJECT_RULES、[新SPEC](spec/analyst-input-mart.md)、[四階段卡](execution-cards/sequential-delivery.md)，固定實際main SHA。逐角色列模型artifact的feature_order、公式／單位、窗口與對應Core欄位。參考34席位不是模型最終schema；任何差異只能補必要serving接線，不調參。
Valuation的ROE／debt_ratio／assets／revenue_yoy尚無已確認會計mapping，不能以現有debt_to_equity代替；連同RV的EPS／BVPS／24有效月缺口歸SEQ-05／06。真正缺資料才用現有Stage→Core補收，不要求歷史全面齊備。

## 2. 程式開發（建議GPT-6.1 Sol）

- SEQ-01：核對stock_supplement十五月／550天、TWD及千元重用，含更正／衝突資料；補收仍先缺口後provider，不新增來源／每股Job。
- SEQ-06：analyst_inputs.py重用現有Quant／Fundamental公式、現役Risk八因子；對各實際artifact完成schema／前處理版本接線，補Valuation會計mapping。現在model_compatible=NOT_VERIFIED是誠實缺口，不可直接改PASS。必要時修套件打包，保留Colab獨立執行。
- specialist_runtime已加入execution分析artifact；全市場screening交既有market_screening，deep reader只掃持股∪觀察股，benchmark仍共用。核對超過50持股聯集時既有Risk讀取限制，使用有界分頁而非剔除持股或無限放大row_limit。
- SEQ-07：product_runtime將分析輸入與週期報告接既有PG product。四ML正式輸出／API／Owner history與UI仍須按SEQ-06／07接完；目前規則輸出／Risk candidate不等於四ML報告。UI分別顯示最新行情日期、各角色輸入日期、report_as_of、重用原因。必要時依現有UI契約檢視binary。
- 手動CEO繼續既有權限／quota／Gateway；不把週報改成自動LLM。新增force參數僅是純函式能力，公開API按需入口仍應沿既有驗權接線，不能視為已新增API。

## 3. 測試驗收（建議GPT-6.1 Sol；模型數值由Astra覆核）

部署前在既有依賴環境執行：
```bash
bash scripts/test-unified-batch.sh
```
新增tests/test_analyst_input_mart.py已寫但未跑。另依變更補／執行既有stock supplement、specialist runtime、analytics reader、product projection、artifact retention與API測試；不要以舊預期全市場deep掃描或13月fixture反向覆蓋新契約。

必要案例：
1. 15個完整月份跨年、缺1月、元／千元相等或衝突、已有Core資料不重抓；數值無NaN外洩。
2. 對相同輸入比較新X與實際訓練／serving test_vectors；特別RMS vs std、volume_ratio20的前20日、log_turnover20、月營收YoY百分點。驗61/121日窗口／15月窗口、停牌缺日、同日修訂與金融／ETF適用性。
3. 只有target聯集進deep掃描；空target不掃全市場；benchmark symbol不被濾掉；依日期與row_limit fail closed，不能截斷後說完整。
4. 新artifact被manifest引用、hash／symbol／date一致；首次／retry／投影重跑不重算報告，不誤刪活躍execution；退役artifact與孤兒7日清理可dry-run讀回。
5. 週報：首次、7日新資料、相同資料不更新、財務／model版本變更、價格5%門檻、手動force；partial不能改ready，reuse保留原日期／hash；每日行情與PnL不隨報告減頻。
6. 同版四ML輸出能進報告與UI，Owner A不可讀B，不新增真實交易；暫缺模型欄位要見missing reason，不顯示假機率。

## 4. 部署（建議GPT-6.1 Sol）

不新建表／migration／bucket／Scheduler。SEQ-04先部署基礎批次；本增量的Mart模型／報告完整發版合流SEQ-08，必要ingestion修正可併SEQ-04。依現有Release同SHA/digest與Job lease／回復程序，不使用main動態tag。
部署後一次有界2330、2882、既有Owner持股／觀察股：讀Core→analyst-inputs→四ML→product／stock_report→API／UI。記每角色有效／缺值欄位、資料日、實際掃描筆數和是否重用；不將文件欄位數當真實覆蓋。週期案例可離線fixture驗，不為等7日新增自然觀察門檻；live只驗一次真實鏈。
回復舊image，新增payload欄位可保留；不刪Owner資料或舊模型artifact。完成收據入Operations，進度只更新原SEQ項。
