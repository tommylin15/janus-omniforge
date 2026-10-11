# Janus 四頁視覺優先 — 工程實作清單（B）

更新：2026-10-11
狀態：Active work / PARTIAL implementation（2026-10-11 第一批價量主圖、縮放、bounded loading 程式已提交；CI／live 仍待驗）。依 [A 正式視覺規格](visual-first-four-pages.md) 與既有 WBS-6、B9 產品＋C／剩餘產品合併授權執行；開發先整套完成再集中驗收。不重做 B0～B8，研究 500 檔母體與五模型 OOS 調參仍後置。

## 1. 已查 main 的現況與缺口（不是 live PASS）

- apps/user_app/lib/final_stock_detail.dart 已取 stock-header、持股／quotes、notes、stock-health、events、analysis；K 線在 Advanced 展開時才請求。
- apps/user_app/lib/final_charts.dart 有 FvKlineChart，現採近 40 根 OHLCV；缺多期間切換與營收／EPS／估值／法人互動圖。部分持股損益繪圖存在，不等於有可信多日資產歷史。
- services/api/app.py 提供 public stock-header、kline、events、health 與 private portfolio/analysis。尚沒有驗證「完整六圖的 public typed series API」；下述新 endpoint 只能視 proposed。
- Iceberg/Core 已有行情、valuation、institutional、MOPS financials、events 來源路徑；資源可查≠每檔各時期的欄位 coverage 已合格。必查季報 period_basis／EPS 股本、事件 observed/published/effective 不一致與資料已發布時間。
- 四張圖片已提交且是 baseline，但 sample 值並非 canonical。此次只做文件／工作拆分，不聲稱新圖表或功能已部署。

## 2. P0/P1/P2 與 acceptance 切片

| ID | 優先 | 實作內容 | 驗收證據 |
|---|---|---|---|
| VF-00 | P0／所有畫圖前置 | Data/Core：建正式 coverage inventory，從官方 source→Core→serving→API→UI，抽持有／未持有／離榜／缺資料代表股票，核行情、估值、三大法人、季財報、月營收、公告、持股估值 | matrix 有期間／符號／缺值／單位／財報期別／來源與授權／PIT／provenance／API readback |
| VF-01 | P0 | API/Mart：優先重用現有 public 與 private read path，僅補 bounded typed chart／Hero projection，首屏不得同步全庫掃 Iceberg 或啟動 Mart/LLM | 正負/缺值/資料日、owner isolation、publication、schema contract tests |
| VF-02 | P0 | Flutter 今日：優先可信 owner-scoped 持股／關注異動 Hero；沒有合格個人重點則切市場 Hero／TAIEX fallback，仍提供真趨勢與最多三件事 | owner／非持股／無關注／無異動、休市／Mart unavailable screenshots；不混時點或造假市場信心 |
| VF-03 | P0 | Flutter 關注：異動、搜尋、主價漲跌、已持有／目標價／追蹤／離榜 chips | watchlist owner、500/50 guard、missing/stale、排序和 drilldown |
| VF-04 | P0 | Flutter 持股：持股市值 Hero、PnL/報酬、損益貢獻 mini bars、次分頁的單一 checkpoint 與 pending | Private Mart/ledger／snapshot consistency，價格日期與 owner readback |
| VF-05 | P0 | Flutter 個股：Hero、短價量圖、快速圖表總覽入口、五角色可信狀態、三支持／風險，保留來源與進階資訊 | 真實 OHLCV／非持股／圖期間切換；不需要 CEO 才有基本圖 |
| VF-06 | P0 | 四頁設計與 accessibility：字階、台股紅綠＋箭頭、主訊息、loading/stale/null、390×844／字體放大 | targeted/golden/screenshot regression、dev authenticated UI 比對 |
| VF-07 | P1 | Core→Mart→typed API→Flutter：官方月營收/YoY、季 EPS/淨利、PE/PB/殖利率、法人、事件五圖 | 每一圖合法可比序列＋period/PIT/source/readback、互動／缺口狀態 |
| VF-08 | P1 | Private Mart：報表資產與損益歷史、持股貢獻與已未實現分解 | 至少兩個已完成可比歷史估值日、同 owner ledger checkpoint |
| VF-09 | P1 | 五 specialist status/drivers/what changed 視覺化 | 真實 persisted artifact、資料不足與研究未驗證分開，無假勝率 |
| VF-10 | P2／有條件 | 同業比較、估值河流／分位、還原股價、現金流與擴充風險圖 | 必須另證來源授權／時間序列／成本；非本輪 release gate |

VF-00/01 與每張圖的資料合法性是**前置**，不放在最後 P2；VF-02～06 可一起實作後集中測試，VF-07～09 依現有核准資料逐圖完成，不能畫的標 Partial/Blocked，別用美觀 dummy 充作正式圖。VF-10 僅在 source/time/cost approval 足夠後執行，不能偷擴 500 檔回補。

### 2026-10-11 已提交的第一段資料鏈路

- 公開端點 `GET /api/v1/public/stocks/{symbol}/visual-series?metric=pe|pb|yield|close&limit=120` 只讀正式 `publication.stock_serving_recent`，不回退掃 Iceberg；typed status 與 null/PIT 來源資訊。僅能對已入 serving projection 的資料出圖，不代表全市場／全年都有資料；樣本不足或來源缺時只能 partial／missing／unavailable。
- 此段支援數值序列及時間軸，不提供未驗證 EPS、YoY、月營收或法人趨勢；這幾種仍保持後續資料 engineering gap，不能用訓練／研究暫存補圖。

- 2026-10-11：個股已新增只針對 PE／PB／殖利率的 lazy typed 讀取與歷史點選、圖卡放大。月營收／EPS／法人仍顯示清楚的資料缺口，不以原始公告或不明財報期別生成圖表。

- 新增 owner-scoped `GET /api/v1/me/today-relevant`：只從本人既有 watchlist 一次取得有證據的「待追蹤筆記／距本人設定目標價」提示；不冒充今日漲跌，不增加每檔 MIS request，無合格訊號回 missing，首頁退回市場基準。此路徑屬確定性產品提示，不是第六分析師或模型買賣訊號。

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
- Integration：GCP dev 真實登入 owner 四頁，真實官方行情＋個股、不同頁同股票價格／估值日一致，Private Mart checkpoint／待更新能解釋，來源與不確定狀態可下鑽。
- Release：同一完整 SHA 必要 CI → GHCR immutable digest → 0% dev candidate → live screenshot／API／Mart readback → 完整 gate PASS 才正式 dev 切流／回滾。沿用現有部署鎖，schema migration 與 Job guard，不額外部署路徑。

**P0 PASS** 需要 VF-00～06 真實實作、CI、dev owner 四頁驗收，個股短價量能互動、每頁有大數字／主訊息、無法用的圖明示原因。**P1 PASS** 需要 VF-07～09 可比的真實 series／source／PIT／readback，不能單靠 mock 圖通過。**整體產品 PASS** 仍需原 B9 產品、C 組、持股頁及既定驗收全部達成；本文件提交只是 docs-only，產品與模型品質目前不自動更動。
