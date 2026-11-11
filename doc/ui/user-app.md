# Janus UI — User App 頁面

## 2026-11-11｜記帳「已實現損益 待更新」與紀錄頁反應慢（已發布 Dev／Live PASS）

- **根因**：過去 `/journal/monthly-summary`、`/journal/symbol-summary` 從 Private Mart 讀取舊的 ledger_version，發現版本落後就清空整個摘要，導致即使有真實交易仍顯示許多「待更新」。紀錄頁四支 Owner GET 併發加上 9 秒吞錯逾時；持股首屏又提前取一份未使用的歷史交易資料，增添等待。
- **實作**：Owner ledger 每版用既有移動平均成本、手續費、稅、股利與沖銷規則一次衍生年度／月份／個股已實現損益；以 owner/year/ledger_version 有界快取、更新版本即重新計算、不讀過期 Mart、缺值不補假數字。新增單一 Owner `GET /api/v1/me/journal/records?year=...` 合併交易歷史＋月份／個股／年度資料；Flutter 紀錄頁只請求一次且將 409、失敗或逾時明確顯示，未載入成功不稱待更新。持股首屏移除不使用的歷史 GET，只按需讀年度損益與重算狀態。
- **工程／部署收據**：第一輪 [fixed GHCR #42968898297](https://github.com/tommylin15/janus-omniforge/actions/runs/42968898297)、[0% #42969885414](https://github.com/tommylin15/janus-omniforge/actions/runs/42969885414)、[Auth/行情 #42970039084](https://github.com/tommylin15/janus-omniforge/actions/runs/42970039084)、[100% #42970187286](https://github.com/tommylin15/janus-omniforge/actions/runs/42970187286)、[Live #42970356061](https://github.com/tommylin15/janus-omniforge/actions/runs/42970356061) 全 PASS。第二輪移除首屏重複讀取 [Flutter #42970622783](https://github.com/tommylin15/janus-omniforge/actions/runs/42970622783)、[fixed GHCR #42970929789](https://github.com/tommylin15/janus-omniforge/actions/runs/42970929789)、[0% #42971563776](https://github.com/tommylin15/janus-omniforge/actions/runs/42971563776)、[Auth/行情 #42971772461](https://github.com/tommylin15/janus-omniforge/actions/runs/42971772461)、[100% #42971889927](https://github.com/tommylin15/janus-omniforge/actions/runs/42971889927)、[獨立 Live #42972065939](https://github.com/tommylin15/janus-omniforge/actions/runs/42972065939) 全 PASS；現役 immutable source `0fab0e9c43fe59a18e1f39cf02112959c7e61ab3`，Ready、100% flow、Owner 匿名 401/403 防護及公開行情讀回成功，保留前版 rollback。
- **驗收範圍**：本輪修復使用原有 Dev，不更動 Owner 帳本、PG、Jobs、Scheduler、IAM 或付費資源；Flutter 和公開 Runtime **PASS**。Owner 實際登入後的月份／個股金額、手機畫面是否仍顯示「待更新」與實測耗時 **NOT_VERIFIED**（無 Owner OAuth session）；不將匿名安全讀回冒充實際損益數值驗收。

## 2026-11-11｜今日／關注分鐘圖修復（Dev API 100%／獨立公共 Live PASS；Owner UAT 已回報完成）

- **原始異常**：Owner 截圖中 5876 在 09:28 僅有約 09:05 的一個分鐘觀測；3231 有真實現價但正式前收缺值，使圖表完全不畫。圖表改為即使前收缺值也繪出真實原始價格／高低最新值；只有日期與來源核准的前收才顯示百分比及 0% 虛線，缺分鐘不連假線、09:00–13:30 軸固定。今日頁區分載入／讀取失敗；關注頁顯示歷史 Kbar 回補狀態並提供使用者按需「重查缺口」，仍受 PG 每檔每 30 分鐘／每日 3 次與 Owner 授權限制。
- **後端故障證據與修復**：先前公開 API 有 503／12–30 秒逾時，有限 Cloud Run 日誌含 `QueryCanceled`、`ConnectionTimeout`（[#42942841400](https://github.com/tommylin15/janus-omniforge/actions/runs/42942841400)）。現版讀取避免個股首屏觸發 Iceberg 冷查詢、盤中有效當日成交免重複 EOD 掃描、market-home 不等待同步 broker refresh，改成按頁面需求回應後有界刷新。Shioaji simulation-only Proxy 的回呼需同時核對成交時間與接收時間，過期成交不當新行情，改交既有 TWSE MIS 備援；Proxy 原址 Dev 部署 [#42945494536](https://github.com/tommylin15/janus-omniforge/actions/runs/42945494536) PASS。未擴張 IAM 或新增排程；私人 Proxy CI 測試身分沒有直接 mint token 權限，未繞過。
- **固定發布與實際生效**：修正版不可變 GHCR full Release 固定 source `775fdc5343a46d26e1922063c59bc60ed283fe03`，[#42943952618](https://github.com/tommylin15/janus-omniforge/actions/runs/42943952618) Python＋Flutter＋四映像 PASS → 0% Candidate [#42944621819](https://github.com/tommylin15/janus-omniforge/actions/runs/42944621819) PASS → OAuth／Owner／Admin／MCP 負測及當日 TAIEX/2330 公開行情正測 [#42944864987](https://github.com/tommylin15/janus-omniforge/actions/runs/42944864987) 第三次 PASS → GHCR API-only 100% [#42946507915](https://github.com/tommylin15/janus-omniforge/actions/runs/42946507915) PASS → 獨立現役 [#42946704452](https://github.com/tommylin15/janus-omniforge/actions/runs/42946704452) `API_LIVE_READBACK_PASS`。單一現役 Ready 100%、build ID 與 digest 對應、Owner/Admin 匿名拒絕；原版 `ac9e0309302248eabcc8d7a6553d479cacf2f828` 保留 rollback，不變更其他 Jobs／Scheduler／PG／IAM／Owner 內容。
- **市場資料實證**：獨立三檔 [#42946245806](https://github.com/tommylin15/janus-omniforge/actions/runs/42946245806) 確認 2330／3231／5876 於 2026-11-11 盤中皆 HTTP 200、`intraday`、有前收與漲跌，候選查詢約 1.83–2.77 秒；獨立 100% 現役 [#42946704452](https://github.com/tommylin15/janus-omniforge/actions/runs/42946704452) 亦 PASS 3231／5876 來源日、盤中狀態與前收正向斷言。加權指數 EOD 30 期，融資 10 期、法人 3 類均 available。
- **Owner 實際操作回報**：使用者於 2026-11-11 在要求查核「今日 3231」與「關注 5876」之後回覆「完成」，此為兩張圖的 Owner 本人正向操作驗收回報，範圍依使用者回報記錄為 PASS。公開 API/Full Release 證據另見上方；獨立 Kbar PG row count、缺口完整率與兩輪 60 秒刷新原始收據未提供，仍 UNKNOWN，不以 UI UAT 冒充資料完整性核證。

## 2026-11-10｜盤中缺口與長期市場資訊首屏修復（Dev 工程與獨立 Live PASS）

- 盤中圖維持實際相鄰分鐘才連線，缺值不造假；後端回補資格由實際時間槽檢查開頭、中段與末段缺口，避免整日覆蓋達85%便忽略局部缺口。保留共享PG限流：30分鐘、每日3次，不由60秒行情輪詢抓歷史K棒。Shioaji維持simulation=True。
- 持股與大盤既有補收狀態提供「重查缺口」按需操作，前端有5分鐘防重按，不繞過後端限制；未回補成功時保留斷線與缺值提示。
- 長期觀察最上方顯示「加權指數最新正式收盤、相較前一有效正式收盤點差／漲跌幅、比較日期及來源」，僅取已發布日行情，不混盤中報價或估測。下方5／20／30日趨勢、融資兩週、法人買賣超、本人追蹤／研究狀態均保留，正常上下捲動。
- **已發布補充**：每日行情內嵌大明細表改為「查看收盤明細」底層面板，不占用長期首頁空間；新增「更新資料」重試當次盤後研究來源；個人追蹤 API 無資料時保留可見缺值狀態，不直接隱藏整區。全量 Release [#42794861330](https://github.com/tommylin15/janus-omniforge/actions/runs/42794861330)、0% [#42795775968](https://github.com/tommylin15/janus-omniforge/actions/runs/42795775968)、auth parity [#42796075164](https://github.com/tommylin15/janus-omniforge/actions/runs/42796075164)、Dev 100% [#42796276597](https://github.com/tommylin15/janus-omniforge/actions/runs/42796276597)、獨立 Live [#42796710267](https://github.com/tommylin15/janus-omniforge/actions/runs/42796710267) 全 PASS。固定 source `ac9e0309302248eabcc8d7a6553d479cacf2f828`，公開 EOD 30 期、融資 10 期、法人 3 類；Owner 真人 UI 與下次真盤中缺口覆蓋尚未驗證，不虛報 PASS。

## 2026-11-10｜手機閱讀與單檔主視圖（覆蓋舊版高密度佈局）

本輪目標是**減少不必要捲動**，並非禁用垂直捲動。不同手機高度、系統文字放大或長資料時可正常捲動；核心數字和主圖優先，次要資訊向下移動、可展開或切換，不裁切資料。

- **首頁與關注分鐘圖（2026-11-10 新版覆蓋）**：盤中紅／綠線寬約 1.7 logical px（原 2.7），淡色區域陰影與細網格只標示**已觀測的連續分鐘段**，未來空白不延伸，缺分鐘不連假線。最新點只在新的資料分鐘進入時短暫柔和強調（約 320ms），不可常駐假動畫或觸發額外報價。原先圖下方的最新／最高／最低觀測價、百分比與實際時間直接上移到圖上方同列；手指可點擊／拖曳選取真實分鐘點，保留 09:00–13:30 固定 X 軸與可信前收 0% 虛線。券商真實成交量繼續有條件顯示（高度精簡），缺值與缺口直接提示，長篇資料注意事項改由「資料說明」展開；正常可縱向捲動。不得因視覺優化把分鐘最高當成逐筆最高，也不得改 canonical price 或新增輪詢。
- **今日（2026-11-10 大盤摘要修正）**：預設「盤中變化」大盤摘要必須直接顯示**加權指數現值／當日漲跌點數／當日漲跌幅 %**（漲紅、跌綠）及「盤中實際觀測時間／非即時／資料日」，不能要求先點入完整圖表或下捲才能看漲跌。點開後仍以下方彈層看完整大盤分鐘圖。即時漲跌以同筆 TWSE MIS／Shioaji 合法 TAIEX 報價及交易所前收為準，無該欄時可讀同日之前合法 Core TAIEX 收盤歷史（需日期及來源），不得用第一筆分鐘點、過時日期、缺值或來源不明的 return_percent 假設前收；無有效可比前收顯示「漲跌待可比前收」，不可造零。盤中標示只給當日且新鮮的實際觀測，其他資料顯示非即時。持股只使用一組「前一檔／目前股票下拉／下一檔」選擇器（含 ETF）；不再同時存在橫向股票 chips、ETF 展開列和第二組上下檔導覽。現價為大字，漲跌及新鮮度明確標示；「今日走勢／買賣五檔」共用同一內容區、不得上下同時堆疊。五檔僅於切入該視圖或手動刷新時按需讀取，不加入 60 秒輪詢。盤中／長期兩大 Tab 仍互斥載入並保留選股。
- **觀察**：與今日一致，採單一股票下拉及左右切換，保留盤中／長期分頁、A／B／C 池及 S 持股。現價與當日變化優先於分鐘圖，觀察池標籤、目標價、鎖定與編輯放到圖表下方可展開區；清單搜尋／新增／管理往後放。缺值、停牌與名冊退出提示仍在主摘要保留。
- **持股清單實際間距修正（2026-11-10 最新畫面覆蓋）**：依 Owner 手機實際截圖，「成本」與「每股當日增減（%）」曾在兩欄交界幾乎黏在一起。本版不再讓四個 Expanded 各自決定兩行高度，改為**共用的四欄網格**：表頭／主數值列／次要數值列都採同一 25:23:25:27 比例，主數值與次要資訊在全清單分別對齊；欄位左右內容各留 3px（相鄰欄實際內容至少約 6px 間距），不新增橫向捲動。股票名稱 16.5、現價 19、損益金額 18、股數 12、成本 11.5、每股當日漲跌數（%）12，總損益 % 仍 18；若超出單欄才由 FittedBox 縮放，成本與股數數值不能用省略號遮住。主數值同列、補充文字同列，縮放文字不得侵入鄰欄；維持紅漲綠跌、下方每股當日增減數及百分比不加正負號、總損益 % 不加「參考」，缺值及非即時提示仍在。390px、320px 與放大字級 widget tests 必須覆蓋多檔大額、成本／漲跌組合及同列對齊；這是 presentation 層修正，不修改 API／行情數字或 Owner 帳本。
- **持股／記帳（2026-11-10 最新覆蓋）**：總資產、持股市值與損益字級不縮回小字；每檔持股改成**單一橫向四欄列**「股票／現價／當日損益／總損益」，欄位標題在表頭只列一次，主數字保持大字並對齊，股數、成本、漲跌百分比／報酬率各放在本欄主數字下方；**當日損益金額保留 18px 粗體**，下方改為較小的 **12px 每股當日增減數（漲跌幅 %）**，格式例如 `1.50（1.25%）`，增減數與百分比均不顯示正負號，僅依台股慣例**紅漲、綠跌、平盤中性**分辨方向；這個增減數是每股現價相對前收的價差，不是整筆持股的當日損益，缺少實際價差不能只用百分比反推；**總損益金額與總報酬率維持 18px 粗體**；總損益百分比後方**不附加「參考」字樣**，非即時報價狀態仍由股票名稱旁的時鐘提示／完整詳情保留，欄位太窄時各自等比縮放避免換行；股票欄次要資訊**僅顯示股數**（例如 `30,000 股`），不重複顯示股票代號，極長股數限於該欄寬等比縮小、不可用省略號截斷，不把每檔卡片分成上下兩大區。極端長數字只在自己的欄寬中縮放，原始精確數字仍顯示並可點個股看詳情；保留漲跌停柔和反底、缺值／stale 與縱向捲動，不增加橫向捲動。
- **文字層級**：關鍵報價、損益約 26～30 logical px；股票名稱 18～22；一般資訊 15～17；標籤、日期與新鮮度 13～14；導覽標籤 14。尊重使用者系統字體縮放及 390px 手機寬度，不用固定高度裁切文字；色彩繼續遵循台股紅漲綠跌及柔和漲跌停底色。
- **驗收**：真實 dev Owner 登入下，檢查 390px、窄幅與系統放大字體，首頁首屏主圖優先、選股單一、ETF 可選、切換不多抓 API／不重置、按需五檔、觀察移動次要資訊、持股數值不溢出；離頁／背景輪詢仍依既有 contract 停止。CI／Release／runtime 各自核對，不因本文件寫完即判 live PASS。

## 2026-10-31 個人策略與觀察池最新呈現契約

依[個人策略SPEC](../spec/personal-strategy-briefings.md)覆蓋下文及舊PNG中相反的筆記入口／平面觀察設計；本輪已撰寫Flutter程式，未做視覺驗收。
- 個人設定：先選操作策略（股市或其他樣板／自訂），再選風險，預覽後按「產出個人策略」，每ISO週成功保存一次。
- 獨立「個人策略」入口與頁面：生效策略＋盤前／盤中／盤後／週六報告，唯讀MD rich卡片，無編輯／筆記按鈕；每類最近3份，最多12份。
- 持股頁移除筆記區塊及入口，不刪既有筆記，不變更記帳／交易功能。
- 觀察頁A/B/C分組，允許手動調池／鎖定；S為帳本持股標籤。週六執行前明確選擇同步／不同步，結果在週報呈現。
- 四種報告仍手動每日每類一次，週報僅週六；page load不生成。設定週鎖、名單同步與報告日額度各自獨立。

> 2026-10-24 批次與快照改以 [統一流程](../spec/unified-batch-flow.md) 為準。四模型按可發布規劃，既有artifact/Registry真實狀態不改判；訓練仍外部執行、無週月例行模型稽核、無GitHub業務cron。本輪未測試／部署。

> **2026-10-24 研究精簡決策優先**：本文涉及獨立資料稽核、逐來源補證、全歷史 PIT／精確時間校準、例行週月稽核及自然驗收等待的要求已取消，不再是待辦或發布前置。依 [研究精簡政策](../spec/research-simplification.md)，保留必要日期／單位、基本防洩漏與操作安全；歷史證據不改判 PASS。


更新：2026-10-13（四頁視覺優先＋Ledger 手動重算可操作契約）

## 5. User App 頁面

本文件只保存目前有效的 User App 資訊架構與狀態語意。被取代的「五個生成式 role／CIO」UI 不再是 active contract；現行研究架構為 persisted 五 specialist + authorized manual On-demand CEO。

**2026-10-11 新的四頁視覺契約：**[A 正式 UI 規格](visual-first-four-pages.md)／[B 工程工作單](visual-first-delivery.md)。舊四 PNG 是最低基礎值、非圖表上限。各頁唯一 Hero，先圖與大數字後文字；當本次新順序與舊 PNG 不一致，以新規格為準，原資料治理不變。

**2026-10-13 最新順序：**先完整持股／報價／交易損益與首屏，再個股通用圖表及四頁整合，五分析師有效後才建立整合分析報告。依 [持股優先契約](../spec/holdings-first.md) 執行；實際驗收見 [status](../status.md)，當次授權／暫停範圍只見TODO，不由UI規格決定。

## 5.0 Final Visual Contract

手機版最終 presentation target 由 [`reference/user-app-final/README.md`](reference/user-app-final/README.md) 定義，固定四張圖：

- `reference/user-app-final/today.png` — 今日
- `reference/user-app-final/watchlist.png` — 關注
- `reference/user-app-final/ledger.png` — 記帳／筆記
- `reference/user-app-final/stock-detail.png` — 個股詳情

圖片規範資訊架構、section order、card hierarchy、手機資訊密度與視覺語言；sample price、PnL、法人金額、日期、AI prose、健康度、logo、sparkline、mock chart 只作 illustrative，不得 hard-code 或當 canonical data。

資料正確性、missing／stale／partial／blocked、auth／owner isolation、PIT／provenance、source authorization、canonical number、publication 與 LLM boundary 以 active SPEC／WBS／runtime contract 為準。PNG 未 commit 或 live acceptance 未完成時不得宣稱 final visual convergence 完成。

對 A 組而言，Final Visual Contract 不是後續 cosmetic polish。Today／Watchlist／Ledger／Stock Detail 的**非 AI 主體 UI**必須在既有 GCP dev、真實登入、真實 owner、真實資料與真實 API/runtime 下先明顯收斂；至少包含 section order、card hierarchy、資訊密度、spacing、主要色彩、mobile layout、390px 級版面，以及 loading／empty／error／partial／stale／missing 不破壞主要 hierarchy。若真實畫面仍明顯像 legacy UI，即為 A 組 acceptance failure／implementation gap。

Specialist／CEO 等 AI-only 區塊未就緒時，可以 bounded unavailable／hidden／partial；不得因 AI 尚未完成而保留舊版非 AI layout。A 組的真實驗收發現 UI/data-state/functional gap 後，需回到 implementation 修正並重新部署／重驗，不能只留下報告。

## 5.1 今日

**2026-11-09 新增漲跌停柔和反底（首頁／持股）**：共用可用行情、正數前收及交易所價位升降單位計算精確漲跌停，不能用漲跌幅接近 ±10% 直接判定（例如 374 元前收之漲停價為 411 元，即 +9.89%）。首頁選股列淡紅／淡綠提示，選中個股另顯示反底現價；持股頁只將現價格反底，日損益與未實現損益色彩不變。過時、缺價、缺前收或無法確認 10% 限幅規則時不推測。國內成分 ETF 0050 已有明確規則；其餘 ETF（可能無漲跌幅限制）待權威價位欄位／分類後再啟用。只改 UI，不改報價輪詢、Owner 隔離與 canonical 數字。

**2026-11-06 V7 核定首頁雙 Tab（覆蓋下方舊頁面順序）**：預設「盤中變化」，只顯示大盤當日、單張持股當日分鐘圖、選股與五檔；「長期觀察」獨立顯示大盤正式 5／20／30 日收盤、融資近兩週、法人金流、個人追蹤與已驗證研究。不再把盤中與長期表串成同一條長頁面。兩 Tab 切換不重置持股選擇與研究期間；只有盤中 Tab 可見／前景時才每 60 秒讀市場。大盤與個股分鐘圖 Y 軸跟隨實際觀測高低＋已驗證昨收（0%），非對稱固定 ±10%；X 軸固定 09:00–13:30，缺點仍斷線。當券商真 `shioaji_kbars.Volume` 存在時下方獨立畫量柱，否則明示缺值，不虛構。正式資料契約見 [V7 SPEC](../spec/today-live-home-2026-11-04.md#v7首頁盤中變化長期觀察與動態分時軸2026-11-06)。


**2026-11-06 五檔新增：**「持股今日走勢」單張個股分鐘圖下方，增加 Shioaji BidAsk 五檔按需面板。只有選股或手動刷新讀取，原每分鐘 Quote Timer 不查五檔；顯示買／賣五檔價量、張數比、來源與實際資料時間，缺值／過時不可顯示假五檔。Shioaji Snapshot 官方只有最佳一檔，不能把它當完整五檔。細節見 [今日首頁 V5](../spec/today-live-home-2026-11-04.md#v5買賣五檔按需面板2026-11-06)。


**2026-11-05 最新核定｜今日持股走勢去重：**本節下文若仍要求「資產短摘要」、多檔持股大張即時卡或重複損益，均以本段覆蓋：今日主體是 TAIEX 及一張選定個股分鐘圖，上方只有橫向精簡選股列（普通股先、ETF 預設收合、左右切換），選定後有「詳情」到個股頁；多檔現價、日損益、現金、資產、成本和報表只放「持股／記帳」。模型研究留在個股詳情。來源日期、真實缺值與 Owner 隔離不能移除。規格見 [今日首頁 V4](../spec/today-live-home-2026-11-04.md)。


頁面順序與互動唯一採 [四頁正式UI規格的「今日」節](visual-first-four-pages.md)：資產短摘要 → 最多三則本人相關事實 → TAIEX背景 → 後續收合追蹤／候選。資產卡不是另一張大Hero，無個人異動則TAIEX作主訊息。owner資料與公共市場分開讀取；任一timeout不阻擋其他區。
首版只顯「最近更新」，不新增已讀／推播；事件去重、空狀態與資料錯誤分開。金額、日期與參考／正式語意沿本文件持股契約；市場仍只用TAIEX。可核對的事實描述不需要ML／CEO，預測與整合研究結論仍受原gate。

## 5.2 關注

**2026-11-09 關注雙 Tab（最新需求）**：關注頁比照首頁持股精簡呈現，預設「盤中變化」，橫向選股列切換 A／B／C 本人關注標的，僅繪製選定個股 09:00–13:30 的真實分鐘資料並以正式前收設 0% 基準；「長期觀察」讀取已發布的原始日收盤，提供近 5／20／60／120 日選擇。選股及期間在兩個 Tab 間保留；長期行情按需取一次，不與分鐘行情混算。
**安全與使用限制**：新增 Owner 限定 GET /api/v1/me/watchlist/intraday?symbol=，只可查本人 active watchlist，仍不放寬原持股專用 GET /api/v1/me/portfolio/intraday；Shioaji 歷史 1 分 K 補收僅在初次選股／重入盤中按需，涵蓋本人已持有或已關注的標的，受 PostgreSQL 每檔每日 3 次、30 分鐘冷卻節流，60 秒 Timer 不調用歷史補收。盤中輪詢只在 Watchlist 前景、盤中變化 Tab 且台股交易時段內進行，重用後端 QuoteRouter 分散式單飛。無有效前收、缺價與 stale 狀態均明示，不造假補點、不把觀看股票視為持股或計算持股損益。
**清單操作**：A／B／C 分類與 S 持股、目標價、鎖定、加入／移除、原長按排序完整保留於預設收合的「管理關注清單」。已退出名冊而仍有效關注的標的仍保留並顯示缺值及狀態；不要求先持有才能查看走勢。是否正式上線以 GitHub CI、Release 與 Live readback 證據判定。

以 authenticated owner 的 active watchlist 為中心，不顯示平台推薦榜，也不因搜尋／page load 觸發 scraper、Agent 或 LLM。

- 搜尋支援股票代號與中文名稱，使用 canonical stock-master search contract；第一層輸入 dialog 的主要動作明確標示「搜尋」，選定股票後才在設定／確認步驟使用「儲存」。
- 新加入股票資格為官方有效的全上市／上櫃個股，取消原 500 範圍；最多 50 active distinct symbols guard 保留。
- 既有關注遇停牌／下市或名冊變更仍保留並標明狀態，不自動刪除。
- 顯示 canonical name＋symbol、latest-price resolver 的 price／date／source／state、held state、target price、pending note／follow-up、bounded missing／stale。盤中只有此頁可見且 App 在前景時才每分鐘 revalidate；沒有 App demand 時不呼叫 MIS。
- add／remove／reorder、target price／note 都走 backend contract；Flutter 不自行建立 owner mapping 或 admission 規則。
- 點擊股票進 Stock Detail。

## 5.3 個股詳情

**2026-10-28 使用者最新決策：**整頁改為總覽／技術／營運／估值／籌碼／研究六區，四模型以各自任務的歷史預測與實際對照為研究主內容；公告與筆記從個股頁移除且不再讀取，不刪資料或其他頁面功能。此呈現決策覆蓋下方及舊參考圖的相反版序，細節見[圖資 v2 整頁重構](stock-detail-charts-v2.md#0-整頁重構決策2026-10-28使用者覆蓋)。資料／Owner 授權與正式發布 gate 不變。

**2026-10-27 最新呈現契約：**[個股圖解與白話資訊](stock-detail-readable.md) 覆蓋下方舊五 specialist／進階資料呈現；四個白話面向、公告內容與閱讀提示、預設收合技術明細。資料與模型 gate 不變，本輪僅需求／文件／程式。

Primary content 依 [四頁正式UI規格的「個股」節](visual-first-four-pages.md)：股價／本人持股 → 營運、估值、風險三行事實 → 同一價量／通用主圖 → 支持與疑點 → 既有筆記／驗證點 → 收合深入研究。點三行中的任一行直接切對應圖表與期間；可驗算事實不等模型，但預測結論須依D07/D08。

`StockHeader` 顯示 latest-price resolver 的現價／正式收盤價與行情日；backend bounded 讀最近兩筆 canonical OHLCV，回傳 `previous_close/change/change_percent`。正值紅、負值綠、0／未知中性；Flutter 不另抓行情重算漲跌。

「我的持股」首屏優先讀 owner-scoped `/api/v1/me/portfolio/snapshot` 的 DB-only 持股與持久化報價；失敗才沿 `/portfolio/quotes`／`/journal/positions` 相容備援，前景行情更新仍走 quotes。成功的快照不受較慢備援請求失敗覆蓋；尚未讀回前顯示載入中，不能先稱無持股。未實現損益與百分比同樣採獲利紅、虧損綠。

短價量圖與圖表總覽入口屬 primary，不得僅在 Advanced 展開後才看得到。完整 K 線、Fact Pack、五 specialist 完整 artifacts、CEO report、參數及 provenance 可按需留 Advanced；未成熟 series 顯示具體資料缺口。

### 5.3.0 Risk 分析師的可理解訊號與更新小字（2026-10-22）

- 正式個股頁優先提供**「波動風險升高／相對緩和／接近近期／尚待驗證／資料過期」**等使用者能採取風控注意的訊號，不得以MAE/RMSE/回測排名替代個股訊號；XGBoost輸出是未來20個交易日**年化波動**，不是漲跌方向/報酬機率或買賣建議。
- 必須從持久化、同一模型版本且經 OOS promotion 的artifact讀出預測及最近年化波動。只有 `model_status=oos_validated`、`model_version=risk-xgboost...`、`baseline_status=available`、`freshness=current` 且兩個數值均有效時，才給橘色警示（pred/recent≥1.20）、青綠色相對緩和（≤0.80）、其他中性色；這是第一版呈現差異門檻，非校準買賣策略。未驗證/缺值/過期一律灰色不顯ML數值，不將未驗證研究資料偷偷帶進User。
- 目前 Flutter `risk_signal_ui.dart` + `final_stock_detail.dart` 已做以上**顯示契約**；後端當前仍是 `deterministic-unpromoted-v1`，故必須看到中性「模型尚待驗證」，直到正式模型promotion和真實API讀回完成。
- 小字至少包含真正 `analysis_as_of` 行情資料日、`更新頻率：交易日盤後`、模型版本與「每月模型評估／每季重訓檢討」。若真正完成時間可追溯則增加 completed_at，**不能以App開啟時鐘假造**。市場休市不顯示當日已更新；資料過期明示。
- 正式批次使用既有 Scheduler→Controller→Mart，每個交易日 EOD入庫後推論；不每天fit、週健康/月OOS/季重訓按 [Risk生命週期](../spec/risk-model-training-retraining-runbook.md)。投資盈虧紅綠不等於風險顏色，低波動不等於買進。

### 5.3.1 五 specialist

五 specialist 是 persisted Python／SQL／ML production outputs：

- Fundamental
- Valuation
- Quant
- Risk／Regime
- Event／Catalyst

User 只讀已持久化／validated artifact；plain-language 來自 structured output + SHAP／rules／templates，正常 path 不需要 LLM API。

每個 specialist 顯示與產品有關的：

- analysis/data as-of；
- status／freshness；
- 主要 metrics／drivers；
- missing／stale／partial；
- evidence／provenance；
- what changed（如有）。

模型版本、input hash、snapshot、完整 feature contribution 等工程資訊放 Advanced detail，不搶 primary UX。

### 5.3.2 On-demand CEO

CEO report 是 symbol-level persisted research artifact，不是 page-load narrator。

- 沒有有效 CEO report：顯示「尚無 CEO 分析」或 bounded unavailable；不得自動呼叫 LLM。
- 有 report：顯示 report as-of、產生時間、specialist freshness/material delta、status、主要 thesis／risks／unknowns。
- 只有 backend capability（例如 `ceo_analysis.request`）允許的使用者才顯示 `分析`／`重新分析`。
- 點擊後建立新的 immutable execution；舊 report 保留，不原地覆寫。
- request 需受 in-flight、quota／cooldown、profile／provider approval 等 backend guard；Flutter visibility 不代表 authorization。
- CEO 不計算或覆寫 canonical number，validator failure 顯示 structured partial／blocked。

### 5.3.3 歷史

歷史可依 `analysis_as_of`／execution／artifact version 檢視：

- facts／Fact Pack；
- specialist outputs；
- CEO reports；
- provenance／source references。

歷史 artifact immutable；不得借用最新資料回填舊 artifact 的 null／unknown。

未知／停用股票顯示 404；已啟用但資料或 specialist 尚未產生時顯示 bounded waiting／unavailable，不以 placeholder 冒充完成。

## 2026-11-05 持股「報表」改為持股變化（本次使用者提供兩張券商圖為參考）

- 「持股／記帳 → 報表」只提供兩個直覺分頁：**持股市值占比**與**持股市值走勢**。既有「持股」摘要、交易「紀錄」與年度已實現損益的可用 API 不因版面更換而刪除。
- 市值占比：依**本人**最新已持久化行情估值，圓餅圖＋名稱與占比，依市值排序；可切個股／ETF，逐檔勾選、全選。完整 owner-scoped 總額由既有 `/portfolio/snapshot` backend 提供；選股後只標示**所選已計價市值**，不得冒充正式全持股總額。價格缺失、過期或幣別不符時標出未計價與排除範圍，不填造零值。
- 走勢：實際已保存的 Owner Private Mart `workspace_snapshots` 日期／ledger version／持股部位估值，按**每月最後實際估值日**畫市場市值（青色）與持有成本（橘色）兩條線；預設近一年，可看已保存的最多五年。預設只分析目前仍有持股的股票，明確勾選「含已出清」才包含歷史已清倉股票；個股／ETF 與逐檔切換共通。觸碰圖點查看該月市值／持有成本，**成本線不是累計入金，市值增加不等於報酬**。
- `GET /api/v1/me/portfolio/value-history?days=365..1825` 必須依 authenticated owner 範圍只讀歷史，禁止開報表時叫用行情來源、LLM 或批次重算，禁止以**當前**股數／價／成本倒填過去的月資料；當歷史不足兩個可比月份／月資料不足／price status 非 available／valuation date 不匹配／不同幣別時，清楚顯示 insufficient／partial 或斷線，不能畫虛構走勢。限 TWD，不混外幣。最多返回上限需標明 truncated，不能稱完整。
- 本次 screenshots 只提供畫面層次與互動參考；色彩沿用 Janus App 既有主題，而非強制改為券商深色。圖表等價文字、手機 390px 與字級放大需驗收。
- 此項功能修改的 GitHub implementation／CI／Dev 已部署狀態依實際收據分開判定，勿將程式已 commit 視為完成。

## 5.4 個人記帳與筆記

本頁是 P0 主功能，不依賴公開 Mart／LLM。使用 segmented control 切換「記帳／筆記」；進入記帳預設次導航為 **持股**，Ledger 次導航至少包含 **持股／紀錄／報表**。

### 5.4.1 Ledger／operational projection

- 交易與更正使用 append-only ledger／correction semantics。
- mutation 成功表示 ledger 已持久化；backend 同步更新 deterministic operational position projection，讓 shares／average cost／cash impact 可立即反映。
- Flutter 不計算 authoritative holdings、PnL、exposure、performance。
- Private Mart 仍擁有 canonical valuation／PnL／exposure／performance／reconciliation；若尚未追上，UI 明示 valuation date／checkpoint／pending。
- 正式 aggregate 若因 missing／stale／valuation-date mismatch 不可靠，backend withheld 並回 bounded diagnosis；Flutter 不忽略缺值自行加總。
- 「持股／紀錄／報表／筆記」次導覽固定在本頁上方；四格 holdings summary **只於持股**顯示。其他次頁不重複顯示，但仍共享 canonical position／valuation semantics、ledger version／as-of 與 freshness checkpoint。

Ledger／Holdings 一致性至少涵蓋 shares、cost／average cost、market value、unrealized PnL、realized PnL、YTD realized PnL、valuation date、as-of／data freshness、pending transaction／pending Private Mart。若不同 subview 的數值不同，UI 必須能表達其正式 freshness／as-of 差異；不能讓使用者看到無解釋的互相矛盾摘要。


**2026-10-12 持股獨立估值／視覺收斂（使用者核准，P0）：**
- **Personal Holdings Universe 由 owner ledger 決定，研究母體已擴為全上市櫃**。以 owner 的 append-only ledger／`private.current_positions` 做持股池唯一 membership；買進、賣出、股票股利、更正、作廢交易 commit 後同步重建 operational positions／ledger version，新增、加碼、減碼即進出持股池（0 股從 active 移往歷史，歷史交易不刪除），不需要等每日全市場 screening。持股行情 service 每次讀取 owner 最新 holdings symbols，且交易修改時使 quote/valuation cache invalidated；已授權外部券商資料**未同步交易前不能推知成交**。
- 股數與成本取同 owner operational checkpoint；價格讀來源授權且具日期與 provenance 的上市 TWSE／上櫃 TPEx 股票、ETF 正式收盤／可授權盤中行情；不因離開 500 檔而拒絕。00719B 為 TPEx 債券 ETF，不得套用 TWSE MIS 股票通道。先補合法 TPEx source/identity、held-symbol serving projection/持久化 latest-price，正式 Mart 再以同 checkpoint 計算損益。來源與交易不同步需顯示狀態；無可信價格不能推估價格／PnL，亦不得阻塞 operational shares/cost、已實現交易明細。
- **兩種更新**：交易 membership 隨 ledger 寫入即時變更；價格只在頁面前景交易時段按需 revalidate／手動更新，收盤後走官方 EOD 交接。避免使用每分鐘排程掃所有持股或逐檔 Iceberg/HTTP；TPEx 無已核准盤中來源時明示 EOD-only，不宣稱即時。
- **卡片同欄同指標**：第一視覺列左為個股＋股數＋價／成本，右為「未實現總損益（NT$）＋持有報酬％」；第二列集中「當日最新現價、每股漲跌／漲跌幅、現有股數的當日變動額」，日期／來源尾註。永不把「當日股價變動」與「持有至今累計損益」在同一水平列左右對稱。缺價時維持精簡卡、簡短原因，不能讓錯誤報錯巨幅擠掉 Hero。
- 對照 `reference/user-app-final/ledger.png` 與真實桌面截圖作 responsive convergence：只有一張市場持股市值主 Hero（未實現、報酬、年度已實現在內嵌次級欄），完整無價時保留精簡 Hero 並明示 missing symbols；下方緊湊股票列、近期紀錄；桌面主欄合理 max width，手機 390px 無 overflow；只有官方可追溯收盤序列才畫 mini sparkline，否則不畫假線。保持台股紅獲利／綠虧損與負號／狀態文字。

此處只定義契約；歷史00719B缺價與dispatch failure不當作永久現況。最新資料／畫面驗收見status，資料fallback與queue故障各自驗證。

### 5.4.2 持股

第一屏資料可用時，僅「持股」次頁優先顯示**持股市值主 Hero**、可驗證損益貢獻圖及下列四項有主次的摘要：

- aggregate market value；
- unrealized PnL／return；
- YTD realized PnL；
- valuation date／status。

**2026-10-16 使用者定版（覆蓋舊大卡視覺）：**持股頁每檔縮至 1～2 行四欄：名稱／代碼與股數、現價／成本、當日持股價格變動與百分比、持有未實現總損益與報酬率。預設將可驗證的當日損益絕對值較大者置頂；來源時間、交易明細、缺價原因都放到個股詳情，主畫面只用細小圖示與 —，不重複大面積「資料不足」。不能把缺價當零，也不能混合日期或 owner 造出完整總損益。

頂端「總資產」增加兩個數字：①現在現金部位 ②現金＋持股當前市值；萬元、小數一位呈現，後端保留精度。未實現損益已含在市值中，不得再加一次。缺價／非台幣未換匯／現金未設定時，總資產不得假裝完整。現金資料由新的本人現金池提供，不引用歷史 Broker Profile 宣告現金。
未驗證 cash／其他資產完整性前，不能把持股市值稱為總資產，也不能用即時 quote 畫假歷史資產線。手機持股用較大字、紅漲綠跌的可掃描 card：canonical name／symbol、shares、market price／average cost、前一交易日官方收盤價、當日每股漲跌／百分比／以現持股數估算的價格變動額、unrealized PnL／return、price／valuation status。每檔都直接顯示未實現損益與百分比，正值紅、負值綠、0／未知中性；價格與未實現估值使用 latest-price resolver 回傳的 owner holdings valuation。operational shares／cost 與 canonical valuation／PnL 的資料時間仍須可判讀。

**2026-10-16 P1 盤中延遲報價修正：**MIS 的 60 秒刷新與 120 秒 freshness 只決定「即時／延遲」標籤及何時重抓，不是股票市值與參考損益的刪除條件。具有合法來源、有效正價格、可信不晚於讀取時間之報價日期的 last-known observation，即使 quote state=stale，仍可顯示「參考市值／參考未實現損益／參考總資產」；現金池＋所有持股的最近有效報價可形成**明示跨日期的參考總額**，但不得稱為單日正式估值或把 stale 標成即時。若只有部分持股取得合法參考價，**必須第一時間顯示已計價市值與未實現損益小計，以及已計價檔數／總持股檔數**，不把小計誤稱「總額」；若現金可用，再顯示「現金＋已計價部分」，註明未計價持股不包括在內。把交易決策可用的數字放在主卡，完整性檢查縮為旁邊小提示，不可讓全頁只剩「總額暫不發布」。完整同日正式總額仍受原 PIT／source／same-date／owner guard 控制；單檔無合法參考價格時參考總額也不得偽造。UI 主要數字與每檔損益正常顯示，延遲只以時鐘小圖示／來源時間表示；完整缺口說明下沉個股詳情，禁止把冗長工程訊息擠到持股列表標頭。發版與實測證據另依 status、operations 判定，不因規格寫入宣稱真人驗收成功。

首屏優先呼叫 owner-scoped `/api/v1/me/portfolio/snapshot`：只從既有 PostgreSQL current_positions、latest-price resolver 的 last-success persistent state 及官方已發布 OHLCV serving projection 讀取，禁止 request-time MIS network／Private Mart 掃描；舊 API 僅供相容性／明確失敗備援。年度 PnL、交易歷史及重算狀態於首屏後另外載入。昨收以 PostgreSQL 已發布 OHLCV serving projection 批次讀取，不每檔逐一查 Iceberg。無有效昨收、報價 stale、參考日不合法或 checkpoint 不一致時，當日漲跌維持缺值；持股價格變動額不代表包含交易、費稅及除權息的實際當日交易損益。

持股分頁使用 latest-price resolver：盤中且 App 位於前景／持股分頁時每 1 分鐘 revalidate；13:30 後停止每分鐘輪詢，14:30 EOD handoff 時間到後只需成功讀取一次 persistent latest state，同一頁面生命週期內的 tab re-entry 不得重複自動抓取。13:30–14:30 若頁面已開啟，可保留最後 persistent state，並在 14:30 安排一次 handoff read；使用者明確按 refresh／交易異動後的必要同步不受此「tab re-entry 不重抓」限制。保留可見的「更新股價」手動入口，backend 僅對 authenticated owner 的目前 TWSE 持股執行 MIS refresh；手動刷新略過 60 秒 TTL，但仍有 10 秒 hard throttle。離開持股、App 進背景或市場關閉後停止輪詢；沒有 App demand 時不執行每分鐘行情工作。更新失敗保留 PostgreSQL last-success 並明示報價狀態，不以失敗回應覆寫 canonical EOD／Private Mart。

YTD realized PnL 必須有明確 display semantics：

- 當年度確定沒有已實現交易，且 canonical aggregate 可確認零值時，顯示 `0`；
- 資料不足、projection／Private Mart 尚待刷新、valuation/as-of 不一致時，顯示 bounded empty／unavailable／pending，而不是用假 `0` 補值；
- 已有已實現交易且 authoritative aggregate 可用時，不得長期缺值或完全不顯示。
- **2026-10-13 使用者最新要求（取代舊版條件）**：Authenticated Owner 在持股次頁**永遠看得到「重新計算損益」入口**，包括 YTD confirmed `0`、`available`、`pending/stale`；顯示入口≠可重複派送。手動重算只建立**目前登入 owner** 的 queue request，Flutter／User API request thread 不直接寫 canonical Private Mart。同 owner 的 `QUEUED/RUNNING/CANCEL_REQUESTED` 期間按鈕 disabled、提示進度且重複點擊不得建立第二筆；`FAILED/CANCELLED` 時顯示安全的錯誤原因與「重新嘗試」；`SUCCEEDED` 後重新讀回 PnL／ledger checkpoint。狀態輪詢一次最多一筆、單次 9 秒 bounded timeout，頁面不因後端慢回永久 spinner。未驗證 Private Worker 真實 E2E 前，只能標 UI implementation／Flutter regression PASS，**不得宣稱手動損益重算可正式使用**。
- User UI 的 realized／unrealized PnL 與其報酬百分比統一採台股語意：獲利紅、虧損綠、0／未知中性；負值以減號顯示，不使用會計括號。

### 5.4.3 紀錄

資訊架構：`年度 selector → 按月份／按個股 → 可收合群組 → 單筆交易`。

- 年度 selector 至少涵蓋目前年度與前五年，並在同區直接顯示該年度 authoritative 已實現損益；多幣別、pending、資料不足不得硬湊單一數字。
- 「按月份」與「按個股」的每個群組預設收合；群組標題只顯示分類名稱與 **已實現損益**，不再堆買進支出、賣出回收、股利收入、交易筆數等摘要。
- 已清倉、目前不在持股清單中的股票仍可從歷史年度「按個股」查看。
- 月份／個股／年度已實現損益都必須由 backend／Private Mart 使用同一 moving-average、fee／tax 與 correction semantics 產生；Flutter 不從畫面交易自行加總 authoritative PnL。
- 展開群組後，單筆主視圖保持精簡：日期、event type、canonical name／symbol、適用時的 shares × price；完整 metadata 與 correction workflow 由 detail／「建立更正」承接，並提供「刪除交易」。刪除採 append-only reversal-only semantics：原始事件不做 SQL DELETE，新增 REVERSAL 後立即刷新 operational positions，並觸發 Private Mart 重算；若作廢買進／股票股利會使任一後續賣出失去足夠股數，backend 必須拒絕。

cash flow 與 PnL 不得混為同義。交易類型目前為買進、賣出、現金股利、股票股利；backend 負責 fee／tax rule 與 persisted rule/profile version。

切換到「紀錄」時不再顯示持股專屬四格摘要；Records 本身顯示 ledger transactions 與其 own as-of。若 transaction mutation 已成功而 aggregate 尚未刷新，需明示 pending／checkpoint，不得默默顯示舊摘要。

### 5.4.4 報表／refresh semantics

- 報表／圖表只讀 canonical backend／Private Mart aggregate，不由 Flutter 從局部交易或目前畫面資料自行重算正式 PnL／performance。
- 報表頁不顯示持股四格摘要，但使用相同 canonical／ledger version checkpoint；不得因 tab 切換維持不同版本的舊數值。
- 報表需顯示可判讀的 valuation date／as-of／freshness／pending／stale 狀態。若 aggregation 尚未追上 transaction／position projection，應顯示 bounded pending，而不是把舊數值當最新。
- 交易新增、修改、同步或 position projection 更新後，Holdings summary、Ledger summary、Records、Reports、YTD realized PnL 都必須進入一致的 refresh／invalidation 流程；舊 cache 不得長時間殘留而沒有 freshness 說明。
- Ledger mutation commit 後先由 ledger version mismatch 自動形成 stale/pending fence，API 只 enqueue authenticated owner，並由既有 `janus-private-pipeline` Cloud Run Job 的 owner-queue mode 處理；不呼叫會 revalue 全體 owner 的 `PrivatePipeline.run()`。不同 owner 可由 2–8 個 Cloud Run task 平行計算，同 owner concurrency 固定 1；shared Iceberg write 先用 advisory lock 序列化。scheduled full pipeline 保留為 durability／reconciliation fallback。
- 真正更新機制以 backend/runtime contract 為準。若採 batch，正式 evidence 應能指出 Job、Scheduler／trigger、頻率、source table、target projection、freshness SLA 與 failure 行為；若非 batch，應能追溯 event-driven／synchronous／materialization 的實際鏈路。UI 不得在 root cause 未查明前把 stale report 解釋成「正常等待批次」。
- Reports acceptance 必須追查並對齊 report API、transaction source、position projection、report aggregation source、DB table/view/materialized projection、cache TTL/invalidation 與 transaction 入帳後更新鏈路；最後以 evidence 判定 `implemented`／`partial`／`missing`／`blocked`。

### 5.4.5 Broker Profile／cash

現金池新契約：舊版 Broker Profile 的 declared_cash 與 cash_as_of 只是歷史申報快照，不代表即時可用現金。新版 private.cash_balance_snapshots 由本人隨時直接設定絕對 TWD 餘額；不用輸入入金／提款原因、銀行明細或先做大量查核，僅使用 owner 隔離、idempotency、防競態 cash version 與原始不可變設定歷史；首次未設定回 not_configured，不預設為零。
每次手動覆寫時保存目前 ledger anchor，之後持久化 BUY 扣除價金與費稅、SELL 增加賣出淨額、CASH_DIV 加入股利淨額；STOCK_DIV 不改現金。作廢／更正反向沖回原始淨現金流再加新交易。重算不重扣、冪等交易不重扣，現金手動調整不修改交易與券商費稅版本。現金可因交易呈現負值，不強制阻擋正常帳本流程。

私人 Broker Profile 可保存 current cash／cash strategy、fee discount multiplier、minimum fee 與 rule/profile version。2026-10-15 起 Admin「資料治理」沿用同一 owner 的券商設定（本人折扣 0.4）；交易新增／更正不提供手續費與證交稅輸入，兩項統一由 backend 自動計算。交易股票欄位支援代號／名稱第一字下拉搜尋，使用已登記股票主檔並包含 ETF；可點選或按 Enter 選取，僅送出選定的標準代號。修改文字後必須重新選取；舊搜尋較晚回傳不得蓋過新輸入，沒有結果或搜尋失敗時保留輸入並允許修改重試。現金優先由可稽核 cash ledger（opening/deposit/withdrawal/trade/dividend）推導；任何 CASH_IN／CASH_OUT／adjustment 仍須 append-only／audit。

目前 canonical cost method 維持移動平均法；未核准 FIFO 前不提供任意切換。scenario／預計交易不得直接寫正式 ledger／PnL。

### 5.4.6 Notes

一般筆記使用 revision model，可獨立存在或連結股票／交易；支援文字、股票、年份與 pending follow-up filter。修改保留歷史版本。

## 5.5 行情 read path

行情採 persistent DB-first latest-price resolver。2026-10-13 使用者核准官方 EOD 覆蓋 **TWSE + TPEx 全部個股**，沿用既有 ingestion 保存 Core／serving；不以排名或目前持股縮限。TAIEX 仍是首頁指數。TPEx EOD 不冒充盤中 tick；研究／新關注亦取消 500 股票資格限制，50 quota 保留。

- regular session（09:00–13:30 Asia/Taipei）：可見的 Today／Watchlist／Holdings／Stock Detail 每分鐘最多 revalidate；backend 只有 persistent quote 超過 60 秒 TTL 才打 MIS。
- 13:30 後若同日正式 EOD 尚未到位：保留最後 MIS，狀態 `closing_pending_eod`。
- 14:30 EOD ingestion 成功並更新 serving projection：同日 `core_ohlcv`／TAIEX EOD 優先，狀態 `eod_final`。
- App 未使用、頁面不可見或 App 在背景：不因「每分鐘」規則產生 MIS request。
- Holdings 手動「更新股價」只刷新 owner 當前 TWSE 持股；不接受 caller 指定 owner，且有 10 秒 hard throttle。
- MIS 只寫 long-lived operational PostgreSQL last-success；正式 EOD serving 由 canonical Core projection 重建。MIS 絕不寫 canonical Core OHLCV。
- source、quote time、receive time、price date、state、final flag 必須可判讀；missing／stale 不補 0、不拿掛單價冒充成交。

## 2026-11-02「我的」投資組合區塊移除

依使用者截圖要求，移除「我的」中的投資組合摘要（含現金資料不足提示）、產業曝險、年度 XIRR、壓力測試及其說明；同時停止該元件的四個 portfolio 讀取。投資屬性表單仍使用 investment-profile 讀寫。此決策覆蓋下方要求在「我的」呈現該組區塊的舊契約；其他頁面的既有資料用途依原契約。

發布驗收（2026-11-02）：[Release 41415772781](https://github.com/tommylin15/janus-omniforge/actions/runs/41415772781)、[0% 候選 41416582647](https://github.com/tommylin15/janus-omniforge/actions/runs/41416582647)、[OAuth 41416960217](https://github.com/tommylin15/janus-omniforge/actions/runs/41416960217)、[API-only 100% 41417151859](https://github.com/tommylin15/janus-omniforge/actions/runs/41417151859)、[入口同步 41417527735](https://github.com/tommylin15/janus-omniforge/actions/runs/41417527735) 全 PASS。程式來源 `9b5a5c9021f20e511aaa23f637b2ef499c8d6a46`，revision `janus-api-00653-xod`，digest `sha256:9633b57b56033ffc4c24341d593897ddbf5d57874af55f784a74e376cbddc67c`。

Flutter 完整 147 項／定向 21 項 PASS，分析無 error／warning；回歸測試確認只讀 investment-profile 且仍可儲存。已登入正式頁重載後，摘要、三個區塊及說明皆不存在，設定表單正常載入。獨立安全 HTTP 讀回 PASS；四 Jobs 映像與完整設定 hash 不變，Scheduler ENABLED／排程不變，19 個入口均指向新版。未做 migration 或重跑模型／Jobs workload，API-only receipt 的 Jobs／Scheduler／storage／IAM mutated 均為 false。


## 5.6 資產與風險

- 顯示總資產、現金水位、持股、估值日期與缺價狀態；正式數值只讀 Private Mart。
- exposure 先以可讀比例／列表呈現；跨產業 membership 需版本化分攤說明。
- 年度績效顯示 realized PnL、dividend、fees/tax、trade count、XIRR status；無根、多根或資料不足不得顯示 0%。
- stress test 顯示 deterministic scenario 與 data as-of；Janus UI 不提供模型 runtime selector。

## 5.7 我的

- theme：light／dark／system；字體縮放跟隨系統。
- 投資屬性可含 risk tolerance、horizon、primary goal、minimum cash ratio；提供給外部 AI 前需明確 opt-in。
- 提供 Janus 私人資料匯出與可稽核刪除；`CLEANUP_PENDING` 不得顯示完成。
- 不放方案定價、公開績效排行榜、預測戰績或券商同步控制。

## 5.8 Research Context（Planned）

在既有資訊架構中增量呈現：

- market regime／deterministic signal summary；
- research thesis supporting／invalidating evidence；
- candidate／strategy state；
- 可用時的 supply-chain exposure／signal；
- portfolio impact；
- provenance／freshness／missing data。

不另建聊天面板；Janus ResearchContext 由 bounded API／MCP 提供。private section 仍受 owner auth 與明確授權。

## 5.9 Loading／效能

- 主 navigation 頁保持 persistent state；切頁不無條件重送全部 API。
- 不在 widget `build()` 內建立會因 rebuild 重送的 request future。
- composite screen 使用 section-level loading／partial；已持久化資料可先顯示再 revalidate。
- Ledger 首屏不得等待未啟用分頁：持股只載必要 core state 與 latest-price；紀錄／報表／筆記依切換 lazy load，頁內相同 GET 重用 request future，避免最慢 fan-out request 阻塞整頁。
- backend latency root cause 必須先量測 auth、DB、Iceberg、fan-out、p50／p95；沒有 evidence 不預設 CPU／RAM／index 是原因。
- high-frequency read 優先 bounded DB read model／cache／connection pool；GET 不做與讀取無關的 retirement write。

## 5.10 數值顯示

**2026-10-17 使用者新增日期列表規則：**圖表維持時間正序及原圖選定範圍；日期為主軸的表格／交易／事件／筆記列表一律最新在上，未知日期置後，不拿事件生效日冒充公告日。月／季表預設近24個月；日資料依用途縮短，通用圖表資料表先列最近20個有效日期位置（含缺值），不硬列兩年每日資料。股票為主軸的持股／關注保留原股票／本人排序，不因行情日期破壞其順序。

資料列使用交錯淡色，表格按年度／季度折疊，季度最新在上。營收／法人顯示「表列合計」、估值顯示「表列平均」、EPS只顯原始單季／最新值，不推算TTM；任何缺值都不彙總。這些只對本表已列觀測作閱讀輔助，明示不等於完整季度報表，不回寫或替代backend canonical數字。原始資料／五年圖不刪減；交易仍可透過原年度選擇查看更早年度，不刪除歷史帳本。

- 使用共用 typed formatter，不讓各 widget raw interpolation。
- 股價語意固定 2 位小數。
- 金額、股數、比例依產品契約四捨五入整數、comma 千分位；User損益與漲跌負值用減號，與台股紅漲綠跌語意一致。
- symbol、日期、version、hash、decimal trade input 保留原語意。
- targeted／golden regression 覆蓋主要格式。

## 5.11 跨專案邊界

Janus User App 不提供 Chat／Ask Janus／provider／runtime／MCP／Skills／approval 產品入口。generic conversation UI 由 omniAgent 持有；Janus 透過 authenticated bounded API／MCP 提供投資 context。

任何 UI completion 都必須依真實 backend capability 呈現；missing／stale／partial／unavailable／blocked 不得用 sample／placeholder 補成成功。


## 2026-10-16 資料與分析的可用呈現補充

依 [資料→分析→UI對照](visual-first-delivery.md) 接續既有DRL-01／D03，不新建頁面或待辦。一般事實短句與通用圖表不必等待五模型有效；整合研究結論與CEO仍依原gate。
個股採四頁正式UI規格的最新順序，三行事實置於共用主圖前；一個主圖切換價格／營收／獲利／估值／法人／事件。最新值、單位、期間先呈現，來源詳情收合；圖點可查值、可放大，持股列表不塞研究指標。
有一期顯一期，有短歷史畫實際期間；缺同比仍顯營收、累計EPS明標累計、缺五年仍顯已有PE/PB；不補零、不畫假線、不冒稱長窗口。已驗證數值描述可直接顯示，不能升格為買進機率或健康總分。
市場批次未達coverage不阻擋有合格值的單股閱讀，整批仍PARTIAL。未證明歷史首次可得時間不阻擋當期閱讀，non-strict研究如實標示；owner、數字、單位、期別與參考／正式語意不能放寬。
本次只修文件，未完成實機截圖或新的視覺驗收；既有PNG與本節文字一起作後續驗收依據。唯一工作狀態見TODO。

## 方案 A 路由（2026-10-21）
基本事實、盤前/盤後及站內跨日觀察按[變化判讀](../spec/change-analysis.md)獨立提供，版面依[四頁UI第6節](visual-first-four-pages.md#6-方案-a-現行增量2026-10-21)。模型未驗證不能阻擋有效事實，也不能讓模板產生未驗證機率。保留既有Owner、日期、參考價及效能規則。

## 2026-10-22｜持股摘要／盤中 ETF 與非普通股（使用者核准）

- 持股市值、當日損益、未實現損益及本年已實現損益：僅 TWD 在 UI 改用「萬元、小數一位」；API 原值與 Decimal 精度不改。非 TWD 不可誤標。
- 「當日損益」依後端最新實際持股股數 × 當前報價相對前一交易日收盤的變化直接加總，當日有買賣以最新持股為準，不是當日已實現交易損益。缺部分報價時不得將小計包裝為全部；顯示覆蓋率與行情日。
- TWSE MIS 對應上市 `tse_`／上櫃 `otc_`，依回傳 exchange＋symbol 核實；TPEx ETF 亦支援盤中行情。前收盤先查官方價歷史，缺少時只容許同交易日 MIS 原始 `y`，不推造前一日期。官方 TPEx OpenAPI 仍僅盤後 EOD。
- 個股頁依正式 `instrument_kind` 判定非普通股，隱藏公司財報、法人、公司事件及專屬模型卡入口；對未升級 API 的典型 0 開頭 ETF 股票代碼採保守備援。價格、本人持股與筆記保留。

## 2026-10-22｜持股卡同行 YTD 與 TPEx 日內修正

- 本年已實現損益應在持股參考市值的數值同行（右側次要欄）；次列僅當日損益與未實現損益。保留萬元／小數一位與狀態語意。
- 對正式核實的 00719B、00697B 等 TPEx 債券 ETF，QuoteRouter._due 不可再限制 TWSE-only，須允許 TPEX／OTC／TPEX_UNVERIFIED 候選交由 MIS 嚴格核實回應之 exact `otc_` exchange+symbol；unknown／disabled 不可嘗試。當日無成交價或有效前收盤仍維持待行情，不造假。

## SEQ-07 分析區增量（2026-10-25）

個股 Advanced 維持原有主畫面與四頁順序。新增「週期／異動事實報告」閱讀卡：`report_as_of`、`checked_as_of`、各角色 `input_as_of`、`serving_roles` 版本／狀態／缺值與 `stock_report_refresh.generated` 明示新產或沿用。單一估值卡只顯示後端已發布數值，不由 Flutter 估算。本人持股／啟用觀察股歷史報告可展開；無授權／API 錯誤不隱藏已可讀最新 Fact Pack；CEO history／手動 Request 保持不自動觸發。事件是相容事實，不是第五模型。SEQ-08 前不得稱登入後的實機呈現已驗收。
