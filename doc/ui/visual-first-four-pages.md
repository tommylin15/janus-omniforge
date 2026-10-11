# Janus — 四頁視覺優先正式 UI 規格（A）

更新：2026-10-11
狀態：Active requirement，**尚未實作／部署／live 驗收**。
範圍：今日、關注、記帳／筆記、個股詳情。執行切片及資料盤點請看 [B 工程工作單](visual-first-delivery.md)。

## 1. 使用者目標與權威

四張 [Final Visual Contract PNG](reference/user-app-final/README.md) 是最低視覺基礎，不是圖表或資訊架構的上限。2026-10-11 使用者重新確認：**每頁唯一主訊息，先看圖、顏色、關鍵大數字，再看白話解釋和進階數據**；若舊圖片／舊版 UI 文字排列牴觸本次補強，以本文件與同步修訂的 [User App 契約](user-app.md) 為準。原四張 PNG 保持 bytes 不變，圖片中的股票、價格、PnL、日期、圖線、logo、研究文案皆為示意，不能當成真實已部署資料。

任何 UI 順序不得凌駕官方資料、source authorization、PIT／available-at、provenance、public/private owner 隔離、canonical number、partial／stale／missing／blocked 或模型 publication gate。未驗證的 ML 機率、研究分數、分類可信度不能包裝成獲利勝率；頁面載入不自動呼叫 CEO／LLM。

## 2. 四頁定位及資訊層級

| 頁 | 主要問題 | 主 Hero／強調數字 | 次級視覺與下鑽 |
|---|---|---|---|
| 今日 | 今天市場最值得知道什麼？ | 有正式證據的市場一句話判讀；否則以 TAIEX 快照作主 Hero | 真實短趨勢、最多三件事、產業／候選入口 |
| 關注 | 我追的哪些股票現在有異動？ | 每檔最新價與漲跌，已持有／目標價／待追蹤狀態 | 有證據才顯示異動摘要、短趨勢；直達個股 |
| 記帳／持股 | 我的持股市值和賺賠怎麼變？ | **持股市值**、未實現損益及報酬、估值日期 | 損益貢獻 mini bars；歷史趨勢放報表 |
| 個股 | 這檔價格、成長、估值與風險在哪？ | 現價／漲跌、本人持股、短價量圖、五角色可信狀態 | 三項支持／風險、六圖捷徑、籌碼／事件 |

### 今日：重要訊息不是數字牆

主順序：**可信 MarketVerdictHero → TAIEX MarketSnapshot（可驗證的小趨勢）→ 今日三件事 → 市場活動／法人短卡 → 產業輪動／熱門話題／候選股**。若尚無相同 analysis_as_of 的已發布市場判讀，Hero 退化成 deterministic TAIEX 快照，註明「完整市場判讀尚未就緒」，不假稱偏多／偏空與高信心。三件事有資料才顯示，最多三則；Mart 無法使用不得讓 TAIEX 首屏消失。只保留當前 active TAIEX，不因舊示意圖而恢復 TPEx。

### 關注：動態狀態不是靜態報價清單

搜尋名稱／代號及關注數／50、有效約 500 新增限制仍可見。股票卡先大字現價／漲跌，次要名稱代號、日期、已持有／未持有、目標價、待追蹤筆記與「離榜保留」；依合法 persisted 價格／事件做異動摘要，沒有可靠規則時不造異動排名。目標價屬使用者設定，不是模型推薦。待追蹤 chip 不代表已啟用通知。stale／missing 股票不因空值從清單消失，owner isolation 與加入／刪除仍由 backend 決定。

### 記帳／持股：資產變化先於記帳細項

次導航固定 **持股／紀錄／報表／筆記**，四格摘要只在持股；視覺上唯一 Hero 是持股市值，其餘未實現損益／報酬、本年已實現、估值日／freshness 分主次排列。未驗證涵蓋現金與其他資產前，不能稱為「總資產」。持股卡突出每檔損益金額／比例、股數、現價／均價；依同一 authenticated owner、同一 Private Mart checkpoint 的貢獻額畫正負條，不能 Flutter 重算正式損益。

報表以歷史市值／損益趨勢為主圖，但必須存在至少兩筆真正可比的已發布歷史估值；不能用短時間內多次即時報價畫假歷史資產曲線。紀錄以已實現損益為重點，現金流≠損益；新增／更正／作廢仍走 ledger append-only，待 Private Mart 更新時清楚顯示 pending／checkpoint mismatch。

### 個股：看圖、位置、風險，不先看長文字

主順序：
1. 股價 Hero：現價、大漲跌／百分比、行情日期及 source。
2. 本人持股卡（若有）和估值日；未持有者不顯示假成本／PnL。
3. **短價量趨勢**：有資料就畫簡圖，無資料顯示原因，不能永久 spinner。
4. 五 Specialist 的「基準可用／資料不足／研究品質未驗證」狀態＋一句白話摘要。
5. 最多三項支持、三項風險。
6. **圖表總覽**：一個操作內可看價格量、月營收、季度 EPS／淨利、PE／PB／殖利率、法人買賣超、事件時間軸。
7. 筆記與追蹤、籌碼／事件、可展開證據／provenance、進階完整 K 線／Fact Pack／五角色／On-demand CEO、免責說明。

簡圖及圖表入口屬 primary，不只藏在 Advanced。「籌碼與定位」是 supporting evidence，不是第六個 specialist。五角色仍為 Fundamental、Valuation、Quant、Risk／Regime、Event／Catalyst；可信狀態不得畫成未校準上漲機率。CEO 只有明確授權且使用者主動要求才執行。

## 3. 圖表語意／視覺元件規範

- 首屏只能有一個主 Hero。主 KPI 明顯大於次級數字；台股紅漲／紅獲利、綠跌／綠虧損，同時加箭頭、正負號／文字，不用單純顏色作含義。未知與 0 用中性色。teal/cyan 是品牌與選擇，不表示績效。
- 每張圖要有**名稱、單位、橫軸日期、期間選擇、可點觸提示、最後資料日、來源／狀態**；無足夠點數、不同期間／不連續缺口不可畫連續趨勢或估值分位。空值不得補 0、不得改用非授權來源隱性補圖。
- 價量：OHLCV／量／MA5/20/60 的計算版本，交易日和公司行動；未還原與還原價不混線。
- 月營收：正式逐月序列、YoY 比較基期；不能直接把重大訊息內單筆敘述湊成完整圖。
- 季 EPS／淨利：同一季／合併口徑、單季與累季、股本基礎、歷史更正與 available-at 可比較才畫。
- PE／PB／殖利率：合法 null、虧損 PE 不造值、0 殖利率有效；歷史分位必標期間與有效樣本數，不等於 DCF。
- 法人：外資／投信／自營商按日同單位買賣超、累積圖，某類缺失明示 partial。
- 事件：event ID 去重、公告發布／首次觀測／生效日期、版本；事件方向不明不塗成利多或利空。
- 資產：持股市值與真正「總資產」分名，貢獻分布／歷史走勢皆由同一 owner 的 backend／Private Mart aggregation 提供。
- 390×844 級手機、放大文字、鍵盤／讀屏、觸控圖點仍不 overflow。各區塊獨立 loading／empty／error／partial／stale，主資訊不因深度分析失敗而消失。

## 4. 完成驗收（不可被圖稿或 smoke test 取代）

四頁真實 owner 在 390×844 手機能於 **3 秒指出每頁主訊息與主數字**、30 秒找到一張可理解的圖／支持證據／下鑽入口；這是驗收時要實測記錄的目標。個股實際價量圖可切期間且一鍵進圖表總覽，其他尚無合規歷史的指標顯示明確資料缺口。持股數字、損益日期跨分頁一致或能說明 checkpoint 差異。

必做 Flutter targeted／golden／screenshot regression，empty/single-point/gap/stale／partial 負測，對應 API／Mart tests，GCP dev 真實 authenticated owner 四頁 screenshot/readback 與正式 Release gate。只存 PNG、改文件、寫 UI、使用 fixture 或 build PASS 均不代表產品結案。
