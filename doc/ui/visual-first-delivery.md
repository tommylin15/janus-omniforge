# Janus 四頁視覺優先 — 工程實作清單（B）

更新：2026-10-12
狀態：Active work / PARTIAL acceptance（四頁視覺初版及估值／事件圖表已進固定 dev Preview，完整 GHCR Release／0% 候選／自動 OAuth／公開 serving readback PASS；正式 100% 切流、四頁本人驗收、完整 P0/P1 資料仍缺）。依 [A 正式視覺規格](visual-first-four-pages.md) 與既有 WBS-6、B9 產品＋C／剩餘產品合併授權執行；開發先整套完成再集中驗收。不重做 B0～B8，研究 500 檔母體與五模型 OOS 調參仍後置。

## 2026-10-13 本輪執行邊界

先持股報價／交易試算／成交損益／效能，再 VF 通用圖表與四頁整合；依 [持股優先契約](../spec/holdings-first.md)。VF-05 的健康度／支持風險及 VF-09 研究呈現後置至有效模型階段，不作通用圖表 gate；其他資料合法性與四頁驗收保留。下方 source／Preview 段落是歷史 checkpoint，不是當前實作盤點。

## 1. 歷史實作盤點與缺口（接手須重查 code）

- apps/user_app/lib/final_stock_detail.dart 已取 stock-header、持股／quotes、notes、stock-health、events、analysis；K 線在 Advanced 展開時才請求。
- apps/user_app/lib/final_charts.dart 有 FvKlineChart，現採近 40 根 OHLCV；缺多期間切換與營收／EPS／估值／法人互動圖。部分持股損益繪圖存在，不等於有可信多日資產歷史。
- services/api/app.py 提供 public stock-header、kline、events、health 與 private portfolio/analysis。尚沒有驗證「完整六圖的 public typed series API」；下述新 endpoint 只能視 proposed。
- Iceberg/Core 已有行情、valuation、institutional、MOPS financials、events 來源路徑；資源可查≠每檔各時期的欄位 coverage 已合格。必查季報 period_basis／EPS 股本、事件 observed/published/effective 不一致與資料已發布時間。
- 四張圖片已提交且是 baseline，但 sample 值並非 canonical。此次只做文件／工作拆分，不聲稱新圖表或功能已部署。


### 2026-10-12 使用者新 P0：持股獨立宇宙＋Ledger Final 重構（整合驗收）

1. **持股 membership 即時**：新交易 commit 觸發 owner `current_positions` 重新投影與 ledger version；變更後讀 owner 持股即反映加減碼，含不在 500 檔的股票／ETF。市場價格不是成交回報；未手動記帳或經授權券商同步前不會知道新買賣。
2. **市場覆蓋**：TWSE 與 TPEx 分流，00719B TPEx 債券 ETF 必須能取得官方有效 EOD；不以研究 500 pool 決定行情讀取。盤中 TPEx 只有授權可信 source 才納入；否則顯示最後 EOD 與狀態。原 operational 股數、平均成本永遠可查；單檔缺價只影響當檔與完整 aggregate publication，已計價小計要獨立 typed 明示不得冒充全額。
3. **Private Mart**：市場缺價與 `CloudRunPrivateRecalcTrigger.start` 失敗分開處理；真實 Job dispatch、queue request／ledger checkpoint／worker status 必須可追溯。拒絕要求使用者盲目反覆點「重新嘗試」。
4. **Ledger UI 由圖片還原**：single Hero＋內嵌次級 KPI；每檔卡首列持有成本／**累計未實現**、下一列**當日現價／漲跌／持有股數影響額**，按同義指標排列；響應式桌面／390px、available／missing／stale／withheld／recalc failed，不將 mock 漲跌／Sparkline 入正式頁。以 reference PNG 的卡片資訊密度、比例、留白作可驗收基準。
5. **一次合併驗收**：文件先行、跨層程式全部實作完成後才集中跑 Python/Flutter UI/GCP Release/Live E2E/真實兩尺寸 screenshot，比對資料、source/PIT、成本/股數、owner fence、冷啟動與載入；各階段均須有獨立 PASS evidence 才可整組結案。


## 2. P0/P1/P2 與 acceptance 切片

| ID | 優先 | 實作內容 | 驗收證據 |
|---|---|---|---|
| VF-00 | P0／所有畫圖前置 | Data/Core：建正式 coverage inventory，從官方 source→Core→serving→API→UI，抽持有／未持有／離榜／缺資料代表股票，核行情、估值、三大法人、季財報、月營收、公告、持股估值 | matrix 有期間／符號／缺值／單位／財報期別／來源與授權／PIT／provenance／API readback |
| VF-01 | P0 | API/Mart：優先重用現有 public 與 private read path，僅補 bounded typed chart／Hero projection，首屏不得同步全庫掃 Iceberg 或啟動 Mart/LLM | 正負/缺值/資料日、owner isolation、publication、schema contract tests |
| VF-02 | P0 | Flutter 今日：優先可信 owner-scoped 持股／關注異動 Hero；沒有合格個人重點則切市場 Hero／TAIEX fallback，仍提供真趨勢與最多三件事 | owner／非持股／無關注／無異動、休市／Mart unavailable screenshots；不混時點或造假市場信心 |
| VF-03 | P0 | Flutter 關注：異動、搜尋、主價漲跌、已持有／目標價／追蹤／離榜 chips | watchlist owner、全市場資格／50 quota guard、missing/stale、排序和 drilldown |
| VF-04 | P0 | Flutter 持股：持股市值 Hero、PnL/報酬、損益貢獻 mini bars、次分頁的單一 checkpoint 與 pending | Private Mart/ledger／snapshot consistency，價格日期與 owner readback |
| VF-05 | P0 | Flutter 個股：Hero、短價量圖、快速通用圖表入口、中性資料說明（模型狀態／報告後置），保留來源與進階資訊 | 真實 OHLCV／非持股／圖期間切換；不需要 CEO 才有基本圖 |
| VF-06 | P0 | 四頁設計與 accessibility：字階、台股紅綠＋箭頭、主訊息、loading/stale/null、390×844／字體放大 | targeted/golden/screenshot regression、dev authenticated UI 比對 |
| VF-07 | P1 | Core→Mart→typed API→Flutter：官方月營收/YoY、季 EPS/淨利、PE/PB/殖利率、法人、事件五圖 | 每一圖合法可比序列＋period/PIT/source/readback、互動／缺口狀態 |
| VF-08 | P1 | Private Mart：報表資產與損益歷史、持股貢獻與已未實現分解 | 至少兩個已完成可比歷史估值日、同 owner ledger checkpoint |
| VF-09 | 後置模型階段 | 五 specialist status/drivers/what changed 視覺化 | 真實 persisted artifact、資料不足與研究未驗證分開，無假勝率 |
| VF-10 | P2／有條件 | 同業比較、估值河流／分位、還原股價、現金流與擴充風險圖 | 必須另證來源授權／時間序列／成本；非本輪 release gate |

VF-00/01 與每張圖的資料合法性是**前置**，不放在最後 P2；VF-02～06 可一起實作後集中測試，VF-07～08 依現有核准資料逐圖完成，VF-09 待模型有效後處理，不能畫的標 Partial/Blocked，別用美觀 dummy 充作正式圖。VF-10 僅在 source/time/cost approval 足夠後執行，不能偷擴 500 檔回補。

### 2026-10-11 已提交的第一段資料鏈路

- 公開端點 `GET /api/v1/public/stocks/{symbol}/visual-series?metric=pe|pb|yield|close&limit=120` 只讀正式 `publication.stock_serving_recent`，不回退掃 Iceberg；typed status 與 null/PIT 來源資訊。僅能對已入 serving projection 的資料出圖，不代表全市場／全年都有資料；樣本不足或來源缺時只能 partial／missing／unavailable。
- 此段支援數值序列及時間軸，不提供未驗證 EPS、YoY、月營收或法人趨勢；這幾種仍保持後續資料 engineering gap，不能用訓練／研究暫存補圖。

- 2026-10-11：個股已新增只針對 PE／PB／殖利率的 lazy typed 讀取與歷史點選、圖卡放大。月營收／EPS／法人仍顯示清楚的資料缺口，不以原始公告或不明財報期別生成圖表。

- 新增 owner-scoped `GET /api/v1/me/today-relevant`：只從本人既有 watchlist 一次取得有證據的「待追蹤筆記／距本人設定目標價」提示；不冒充今日漲跌，不增加每檔 MIS request，無合格訊號回 missing，首頁退回市場基準。此路徑屬確定性產品提示，不是第六分析師或模型買賣訊號。

- 2026-10-11：今日首頁接入 owner 追蹤 Hero，獨立 Future；沒有合格本人異動時不阻擋市場快照。關注頁增加真實待追蹤筆記數標籤，尚不宣稱已建通知系統。

- 2026-10-11：持股頁新增加上嚴格相同估值日／幣別檢查的「各持股未實現損益對照」比例條；條長為視覺化比例，不是 Flutter 重算正式報酬或投資貢獻率。checkpoint 不一致就不畫。

- 2026-10-11 路徑核對修正：實際 User App／測試入口是 `final_visual_pages.dart` → `final_today_v2.dart`；先前改 `final_today.dart` 未影響正式頁。已在 **v2 真正入口** 增加 owner 相關 Hero，並保留原 market baseline 獨立載入，避免以未使用頁面假稱完成。

- 2026-10-11：關注列表後端同一次 owner watchlist 查詢新增上一個已發布 OHLCV／昨收參照；行情日期未對齊、缺價或非數值時不提供漲跌。已接 Flutter 漲跌箭頭／百分比，不新增 50 個逐檔行情請求。

補充：2026-10-11 對國巨 2327 與台積電 2330 的小樣本真實 Core 驗證已存於 [資料涵蓋抽樣證據](../archive/visual-first-core-sample-2026-10-11.md)。這是 bounded sample，**不是** VF-00 全市場 coverage PASS，也不是尚未部署新 API 的 serving readback。

### 2026-10-12 第二段跨層正確性與事件視覺化（仍為 PARTIAL）

- `final_stock_detail.dart` 以 request epoch 與每類請求的版本防止 A→B→A 快速切換或同股票舊回應覆蓋新資料；舊請求亦不能結束新股票 loading。
- 公開 `visual-series.v1` 將有效日期但空值／非法值保留成 typed `value: null`，附已發布 source／provenance；Flutter 不跨缺值日期連線。`usable_points` 與 `data_as_of` 僅由合法值決定；PE/PB 非正值不可畫，合法零殖利率可畫；同日重複優先合法值。仍無 request-time Iceberg fallback。
- 個股估值主圖及放大按合法點數而非陣列長度判斷，並能在非末點改變時重繪。公司事件已由既有 published read path 呈現 bounded 中性時間軸，依 `event_id` 去重，明確區分公告與生效日，不猜事件方向。
- Flutter [#38196268477](https://github.com/tommylin15/janus-omniforge/actions/runs/38196268477) PASS；API [#38196525696](https://github.com/tommylin15/janus-omniforge/actions/runs/38196525696) PASS。**最新整合 SHA 的 CI／完整 Release／0% candidate／真實 UI readback 尚須逐項驗證**；尚未正式切流。
- **仍缺**：月營收／季度 EPS、法人合格歷史 serving；持股跨日真實估值趨勢、四頁 Owner 截圖／效能 P95、完整官方 coverage/PIT matrix。此段不代表 VF-07 或整體產品 PASS。

### 2026-10-12 同源 Preview／實際資料驗收 checkpoint

- immutable source：`2ebc875953209875123d4cba04659661e68d1685`。GHCR full [#38197376475](https://github.com/tommylin15/janus-omniforge/actions/runs/38197376475)、0% candidate [#38197718590](https://github.com/tommylin15/janus-omniforge/actions/runs/38197718590)、自動 OAuth/private-negative [#38197849073](https://github.com/tommylin15/janus-omniforge/actions/runs/38197849073)、固定 Preview [#38197920240](https://github.com/tommylin15/janus-omniforge/actions/runs/38197920240)、live readback [#38198005001](https://github.com/tommylin15/janus-omniforge/actions/runs/38198005001) 全 PASS。preview URL：`https://preview---janus-api-2oo7qbkd5q-uc.a.run.app/app/`；正式 API 100% 仍舊版，未切流。
- 真實公開 2327：PE/PB/殖利率各 30 合法點；2330：PE/PB 各 30 合法點，`data_as_of=2026-10-08`，source/provenance 與 build-id SHA 已實際 readback。首個 cold 讀取 4,338 ms、其餘短請求 74–80 ms、同路徑 warmed 83 ms；**非統計 P95、亦非 owner 手機首屏 SLO**。live probes 已更新支援 typed null 樣本，不以 points 陣列長度當全部合法。
- Read-only Core sample 補查 2327 三大法人歷史與 MOPS 2327／2330 官方財報：institutional 已具 TWSE source/provenance 但尚無可信 public typed serving series；financials 的 `period_basis`、`is_single_quarter`、`report_scope`、`share_basis_status`、`publication_time_authoritative` 缺失／不可靠，EPS/淨利/營收跨期不能比較。這是 bounded sample，不能外推 500 檔 coverage，也不以單篇公告湊月營收。
- VF-00～06 尚缺完整四頁本人 390×844 screenshot/實際載入與 owner readback；VF-07 尚缺官方可比財報／法人 typed series；VF-08 缺至少兩筆同 checkpoint 已發布歷史持股估值；VF-09 五角色 persisted 可信狀態仍需獨立 B9 產品驗收。**上述都仍開放，不因 Preview PASS 認定產品交付。**

## 3. Dataset coverage matrix（必要交接表）

每個 dataset_family 都至少有：symbol／market、required_metric、frequency、first/last_period、usable_points／expected_points、missing_rate、unit、period_basis、source_id、source_authorization、published_at／availability_at／observed_at、snapshot／provenance、serving route、API route、UI consumed、freshness、Implemented／Partial／Missing／Unknown／Blocked、blocking_reason、reproducible evidence。

| 圖表／欄位 | 已知方向 | 必查的資料工程問題 |
|---|---|---|
| 價量／K | TWSE/TPEx OHLCV、/kline/{symbol} | UI 40 根限制、區間切換、股數單位、股價是否除權還原、交易日曆 |
| 歷史 PE／PB／殖利率 | 官方 valuation Core | 合法零／null、負 PE、足量歷史、分位窗口與樣本；不可暗用 DCF |
| 外資／投信／自營商 | 官方 institutional Core | 日期對齊、張／股一致、是否可公開 serving、缺角色 partial |
| 季 EPS／淨利 | MOPS financials Core | 單季/累計、合併／個體、比較期、EPS 分母／股本、修正版本與可用時間 |
| 月營收 YoY | MOPS 或官方月營收消息 | 不拿單筆事件文字湊成逐月歷史；需獨立同月份基期與版次 |
| 事件／法說／除權息 | 官方 events | event_id、去重、分類／審核、發布／觀測／生效時間、source jump |
| 持股估值／趨勢 | /api/v1/me/portfolio/snapshot 與 Private Mart | valuation/ledger checkpoint；完整 cash 未證不能叫總資產；沒有歷史不連假線 |
| 同業／產業 | Specialist／Core 各有研究入口 | 有效 cohort、同口徑資料、模型品質未過不可給勝率 |

不可以「有一個 API endpoint」、「一檔有一筆」就宣稱全圖 Implemented。資料異常與缺值必須留下有界錯誤、來源和後續修復 owner；禁止直接用最新月份與不相容財報口徑連成趨勢。

## 4. API／Mart 最小契約（待實作）

先確認 /api/v1/public/stock-header/{symbol}、/kline/{symbol}、/events/{symbol}、authenticated /api/v1/me/portfolio/snapshot 的實際能力；不足才加有界 read-only endpoint。候選 /api/v1/public/stocks/{symbol}/visual-series?metric=...&period=... **只是 proposed 名稱**，不得當成已上線。

Series typed minimum：schema_version、symbol、metric、unit、period、points[{date,value,auxiliary}]、usable_count、coverage、data_as_of、status、freshness、source、provenance_ref、calculation_version、missing_reason、adjustment_basis。financials 另有 fiscal_period／period_basis／report_scope，events 另有 published/observed/effective time。後端計算 YoY、MA、EPS compare、法人累積、合法分位，Flutter 只畫；raw 值不完整不補 0。公開圖僅可引用 published 來源，私人持股／成本／PnL 只能從 owner-scoped /me 取。

首屏沿用 PostgreSQL serving／cache／低成本讀路徑，財務長期 series 按需分段取回。無新增付費 provider／GCP、新 IAM 擴權、未核准回補、BigQuery Storage Read API、隱性外部抓取或自動 CEO／ML retrain。

## 5. 圖卡縮放、有限等待與避免畫面閃爍（2026-10-11 補強）

- 第一屏不等待次要圖卡：Header／持股為 critical，K 線／研究／事件／筆記獨立 async；每個讀取有上限並能個別重試。股票 symbol 改變時必須忽略前一標的延遲回傳，不能讓舊股票資料污染新頁。
- 以既有 API 一次取得最多 200 筆 OHLCV，圖上僅提供「近1月／近3月／近200日」切換；**200 交易日不等於完整 1 年**，待後端可合法提供至少一整交易年資料再改為 1Y。展開/捏合縮放不得為每次手勢重新打 API；切換股票須避免前一股票結果污染。官方原始 K 線未驗證除權息還原前明示此限制。
- 圖卡縮放採「縮圖 → 點擊放大 → InteractiveViewer 捏合縮放／平移 → 關閉」，只針對價格、營收、EPS、估值、法人、資產趨勢等有判讀意義的圖；靜態數字卡不加入無用途手勢動畫。
- loading 小卡使用 inline skeleton／狀態文字，不用整頁 spinner；逾時（暫定前端 read timeout 9 秒）顯示區塊級 error＋重試，已載入清單在 refresh 時 stale-while-revalidate。timeout 不等於後端任務已被取消；必要時 backend 再做 request cancellation／併發與 cache 控制。
- 必須測：單卡卡住、其他卡正常、刷新失敗保留上次 snapshot／日期、retry 成功、10 次快速切換圖卡請求數不增加、低階 Android 390px 畫圖無明顯掉幀、P50/P95 及資料 freshness 可查。長期歷史圖採按需載入、bounded response，暫不自動取整個 500 檔。
- 示意生成圖僅為視覺參考：其中 logo、通知鈴、百分比、健康度與研究文案不得 hardcode；仍沿用既有禁自動推播與未驗證模型限制。

## 6. 測試、集中發布與狀態判定

- Core/Mart targeted：數值單位、null/合法0、不同財報期別、EPS 股本、營收 YoY 基期、公司行動、事件 published 與 observed 反常、PIT leakage 負測、缺樣本不計分位。
- API targeted：schema/pagination/limits、空／單點／缺洞、stale/partial、as_of/source/provenance、authenticated owner/public isolation；今日個人化訊息不得漏出他人持股／關注，沒有個人資料時 bounded fallback，不因一圖 timeout 阻塞首屏。
- Flutter targeted/golden：四頁唯一 Hero，主數字／色彩＋箭頭，價格與 PnL 色彩，圖表軸／單位／期間／tooltip、空資料、非持股、離榜、390×844 和放大字級。
- Integration：GCP dev 已授權 authenticated owner 四頁（不要求每版人工重新 OAuth 登入），真實官方行情＋個股、不同頁同股票價格／估值日一致，Private Mart checkpoint／待更新能解釋，來源與不確定狀態可下鑽。
- Release：同一完整 SHA 必要 CI → GHCR immutable digest → 0% dev candidate → live screenshot／API／Mart readback → 完整 gate PASS 才正式 dev 切流／回滾。沿用現有部署鎖，schema migration 與 Job guard，不額外部署路徑。

**P0 PASS** 需要 VF-00～06 真實實作、CI、dev owner 四頁驗收，個股短價量能互動、每頁有大數字／主訊息、無法用的圖明示原因。**本輪 P1 PASS** 需要 VF-07～08 可比的真實 series／source／PIT／readback；VF-09 留在後置模型階段，不能單靠 mock 圖通過。**本輪持股＋通用圖表交付 PASS** 需新持股契約與適用 VF 驗收；**含分析報告的整體產品 PASS** 才另需有效模型與 C 組；本文件提交只是 docs-only，產品與模型品質目前不自動更動。

## 2026-10-12 P0 合併修復：個人持股不限 500／00719B／視覺落差

狀態：**ACTIVE，集中實作後一次測試與 live Preview 驗收，未通過前不可標 PASS。** 本節由使用者實際 00719B 缺價、未實現總額 withheld、Private Mart 派送失敗與持股畫面明顯不符合 Final Visual Contract 回報觸發。

1. **兩條不同的時鐘**：個人持股池由 owner ledger BUY／SELL／REVERSAL／股票股利的 current_positions 立即投影，無新增 500 membership gate；交易確認後刷新 owner snapshot cache，新增持股立即登記行情需求，減碼立即更新股數與成本，歸零停止需求。行情獨立持久化（quote time、source、received_at、price_date），不可把交易後的新股數與舊版 Private Mart checkpoint 假稱同時點正式損益。不得要求使用者定期手動同步「持股池」。
2. **研究池與估值池分離**：全市場母體供篩選與模型研究；任何真實持股（TWSE／TPEx 股票、ETF 等）仍可依授權官方報價／EOD 提供估值；stock_master 身分與市場需支援持股出池、無入池／短暫未建檔。TPEx 官方 EOD 不可借 TWSE row 或 fake price，未經實證無來源者標 missing；盤中 quote 需測試授權與 timestamp 後才能定義新 TPEx source 為可用，需保障 60s TTL／前景限定／手動 throttle／DB last-success，不產生持續付費 polling。
3. **總額與局部資料隔離**：若任一活躍持股缺可信同時點市價，正式「完整持股總市值／未實現損益」 withheld；但各持股 operational 股數、成本、均價、已實現交易記錄及有價格的個股損益仍可顯示。若提供「已估價部份小計」，必須 backend 明定不完整 coverage（筆數、affected symbols、估值日），不能稱完整總額或偷偷忽略缺價持股。
4. **重算派送獨立查因**：Cloud Run `janus-private-pipeline` dispatch、IAM、queue status、run result 與影像版本各需真實證據；TPEx 缺價≠ Cloud Run Job 無法啟動。未確認不能盲目重送，保留可重試且具狀態診斷。
5. **記帳／持股版型必須收斂**：頁首單一持股市值 Hero，未實現與 YTD 屬 secondary；個股卡**上排是持有以來未實現損益金額＋報酬／股數、下排是即時現價與前收當日每股漲跌、漲幅與依持股數推算的價格變化**，相同時間尺度同一列，避免總損益與日漲跌交錯；桌面需設 maxWidth、手機 390×844 稠密清楚。官方歷史點數與時間語意不合格則不畫 fake sparkline。
6. **合併驗收**：先回寫 doc/UI contract → backend owner positions、TPEx data / resolver、Private Mart trigger、Flutter 卡片與 Hero 一次合併實作 → Python/Flutter targeted & full tests／390px golden、owner missing/stale/unsupported instrument、00719B/live source、owner snapshot/PnL、real Cloud Run Job dispatcher runtime proof → GHCR／0% candidate／自動 OAuth boundary／固定 Preview／authenticated owner screenshot comparison。不可將 mock／CI／公共頁面 readback 代替 Owner 實際持股驗收。先前美術構圖是呈現目標，但當前截圖明顯不符，維持 **VISUAL FAIL**。

## 2026-10-16 資料 → 分析 → UI 一體交付（先求有，再求好）

本節是使用者核准的工作整併與呈現規格，非新待辦或完成證據；唯一授權／狀態仍見 [TODO](../todo.md)。DRL-01 依原指示等 D01～D05 完成及使用者恢復後執行；本次文件修訂不暫停另一條已授權 D01～D05 工作，也不自行啟動 DRL-01。以下「首版」指各既有工作包恢復後的最小交付，不擴大當前 D05 gate。

### 同一功能只做一條鏈

| 既有責任／使用問題 | 資料取得與共用 | 分析／計算 | UI 首版呈現 | 缺資料時先交付 | 共用驗收 |
|---|---|---|---|---|---|
| DRL-01A → D02/D03 VF-02/05；價格是否轉強 | 既有TWSE/TPEx OHLCV與benchmark、日曆；全市場21日、Deep Coverage120日按原範圍 | 重用現有同窗口報酬／RS，ATR依核准窗口計算；不另建排名引擎 | 今日TAIEX唯一主圖；個股短價量＋成交量，點選看日期/價/量；RS與ATR收合為短數字 | 只有短歷史就標實際起訖；一點顯示最新值，不畫趨勢；不足20日不冒充RS20 | 同股票同日期source→Core→serving→API→圖上點值相等；重跑無重複；跨頁一致 |
| DRL-01B → D03 VF-07；營運是否成長 | 先修已存fiscal_month，再補所需同月基期，不重抓已有可靠值 | 月營收、同月YoY；三月合計YoY有足夠配對再算，不等新ML | 個股「營收」Tab：月柱；切換「金額／年增率」避免雙軸；最新月＋同比一行 | 缺去年同月仍畫營收；一月也可單柱；文字「尚缺去年同月」，不整卡空白 | 官方期別/單位與圖值核對，缺月不補0，金額和YoY開關共用同份資料 |
| DRL-01C → D03 VF-07；獲利是否改善 | 中英文EPS concept、單季/YTD、scope、單位與股數；重用財報 | 可比單季EPS／TTM；毛利率等已有可比欄位才顯示 | 個股「獲利」Tab：季度EPS正負柱、最新EPS；有TTM才加小字；財報期別清楚 | 只有累計EPS則顯「上半年／前三季累計」，獨立單值或同口徑柱，不標單季、不強湊TTM | 正負、Q4、股數變動、累計與單季不混；樣本與API單位可重算 |
| D03 VF-07；DRL-01D/VF-10後置；估值處在哪 | 既有官方每日PE/PB先用；五年只後置定向補 | 官方PE/PB與自算口徑分開；短期線先行，歷史分位待窗口符合 | 個股「估值」Tab：PE/PB切換折線＋最新值；後續才加分位區間／情境帶 | 有一點顯單值，有一段畫實際區間；沒有五年不擋短線；虧損PE顯不適用 | 不用今天EPS回畫歷史；短期不標五年；不將倍數低直接標買進 |
| D03 VF-07；籌碼／事件有何變化 | 既有官方法人與公告；不先新增TDCC或新聞來源 | 法人淨買賣按角色／期間；公告去重與時間排序 | 法人正負柱、5/20日切換須資料符合；事件簡短時間軸，可開來源 | 日數不足則顯實際期間合計，不冒稱20日；事件只有一則仍可列 | 股/張/金額正確、子類不重複加總；公告與擷取時間分開 |
| D01/D02/D03 VF-04/08；資產與損益如何變化 | 共用owner snapshot、現金、ledger、Private Mart；不新建帳本 | backend已有市值／PnL／貢獻計算，正式與參考分開 | 保留現金＋總資產主卡與1–2行持股；報表才放資產線／貢獻條 | 延遲價仍顯明示參考總額；真缺價顯已計價小計與涵蓋檔數；只有一期顯當期數字，歷史不回造 | owner/checkpoint與金額正確；既有真人PASS不重做，僅驗本次改動及必要回歸 |
| D07 VF-09 → D08；分析有沒有用、為何判斷 | 重用上述因子／同一份structured artifacts，不另抓另一套資料 | deterministic事實解釋先行；OOS/模型品質各自驗；CEO只解釋 | 圖表旁可有「營收同比上升」等可直接驗算短句；進階才顯研究證據/風險；有效角色後接報告 | 未驗證不顯勝率、買賣建議或綜合健康分；已知事實及圖表照常 | 圖值、規則短句及Fact Pack同源；數值可用不冒稱預測有效 |

因子完整研究候選與公式見 [Drive進階評估](https://docs.google.com/document/d/1SHENmFuR_fdGcuRMRUwKqxRRFEI3MgwdIjelhV9ePrk/edit)。六組因子不是六張新卡或六個新服務；首版只接已核准、可共用資料的項目。供應鏈、TDCC、完整DCF、新策略中心、進階金融/ETF模型不因本節自動進 active queue。

### UI 讀取與視覺層級

沿用底部四入口及個股現有順序：股價 → 本人持股 → 短價量 → 圖表切換 → 中性事實說明／來源 → 後置研究。個股只維持一個主要圖表區，價格／營收／獲利／估值／法人／事件切換；不一次堆六張長卡，不新增第五個底部Tab。
每張圖只回答一個問題，先「最新數字＋單位＋所屬期」，再趨勢；點選顯示日期與值，點擊放大沿用既有元件。日期／延遲小提示就近顯示，完整來源與品質原因下沉展開區；不能把必要的參考／小計語意藏掉。工程hash、snapshot、模型版本留Admin／進階。
關注仍為使用者清單，可顯已有資料的簡短異動標籤並連往對應圖表；不另做推薦榜。今日最多三則事實異動，無可用異動退回既有市場資訊，不呼叫LLM湊內容。持股不塞KD／長文，既有已驗收緊湊列表保持。
Header與持股先顯，歷史圖按需載入；刷新保留上次成功值＋時間，單卡timeout可重試，不全頁spinner。共用一次bounded series讀取，切圖／放大重用資料，不每次手勢打API、不開頁掃Iceberg；沿用D02效能目標，不另創一套SLO。

### 可放寬與不可放寬

| 可先放寬，不擋有用內容 | 仍保留的底線 |
|---|---|
| 不滿五年先顯已有期間；只有一期先顯單值；可解析的現值先供一般閱讀 | 不補假歷史、不補0、不把短窗口標成長窗口；公式缺必要基期時只停該公式 |
| 缺精確首次公布時間／歷史修訂版仍可作一般分析與明示non-strict研究 | 不冒稱嚴格PIT/OOS、不將估計日期寫成官方日期；來源已知禁止與付費限制仍遵守 |
| 已知口徑的累計EPS先展示；不等單季歷史齊備 | 不將累計EPS直接相減當單季；只有可證明同股數口徑或可比單季盈餘及加權股數才能換算 |
| 報價過期仍呈現最近有效參考數字；研究資料尚缺不隱藏現金/成本/價格 | 身分、單位、正確期間、owner隔離及交易金額不放寬；參考／部分小計不冒稱同日完整正式估值 |
| 市場整批coverage尚未達標，單股有真值仍能閱讀；當期描述不等ML有效才顯示 | 上市≤10%／上櫃≤30%仍用於既有整批完成判定；整批PARTIAL不等於逐股禁止展示，也不假稱整批PASS |

不另增五年、40週、252日等「所有畫面共同必備」門檻；它們只在啟用需要該窗口的特定指標時適用。KD初值可標暫定，穩定性不足不發研究訊號；沒有指標亦不影響價量圖。基本數值與安全測試不削減，品質精進不阻擋首版可用內容。

### 工程合併與最小驗收

1. DRL-01負責資料修復與共用計算輸入；D03消費同一輸出，不重抓、不再做另一份公式。D02負責同一serving／快取與首屏，D07才做因子有效性，D08才做報告。
2. DRL-01的資料readback與D03對應圖的數值readback可用同一份證據；記錄symbol／period／value／source及API/UI對照。UI呈現另驗證必要的手機／桌面與缺值狀態，不把資料PASS當視覺PASS。
3. 本次既有D01～D05先照原範圍收尾；DRL-01恢復後，只重驗變動的資料／API／圖表，完成項目不重開，新因子不反向成為本次D05阻塞。
4. 每一功能交付分列「資料可讀／數值可重算／畫面可用／模型是否驗證」。有真資料、正確降級及UI實測可宣稱該功能首版可用；無真資料只完成空狀態不得稱整圖功能完成。未達原coverage與完整acceptance的工作包仍PARTIAL。
5. 不新增pipeline、排程、warehouse、圖表SDK、AI角色或每圖LLM。採既有Controller、Stage/Core、Mart、PostgreSQL serving、typed API及Flutter元件。
