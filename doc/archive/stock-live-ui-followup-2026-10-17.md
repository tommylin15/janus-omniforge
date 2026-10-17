# 個股真人補驗、首次載入追查與日期列表調整（2026-10-17）

## 授權與同步

使用者要求先同步 GitHub，再補真人截圖矩陣與價格圖首次載入調查；其後追加日期表格／列表最新在上、月季資料近兩年、交錯底色及適用季度折疊。日資料另按用途縮短，不強制列滿兩年。工作開始已 fetch／fast-forward 至 `501e8f9de400b92a2450dcb000c12492e8fd2f64`；保留使用者既有 `token-savior/` 未追蹤目錄。

## 正式真人畫面矩陣：8／8 正向 PASS

驗收來源為當時正式 `becb6a15496959c1f5d3d4985d7b523b652bd3ee`／`janus-api-00533-yah`，不是尚未發布的新日期列表。使用者本人恢復 Google 登入後，沿既有正式網址與真實 Owner／persisted 資料逐頁查看，不寫交易／現金／筆記，不按重算。

| 頁面 | 390×844 手機 | 1440×1000 桌面 |
|---|---|---|
| 今日 | PASS：正式收盤／真實指數線與市場區塊 | PASS |
| 關注 | PASS：本人清單、正式名稱／行情日／狀態 | PASS |
| 記帳／持股 | PASS：真實持股／估值日／緊湊列表 | PASS |
| 個股 5876 | PASS：報價「可用」、實際行情日、「報價估值」、66日價量 | PASS：折線／日K切換 |

另驗手機 EPS：2026 Q1／Q2 兩期、MOPS、明示TTM未認證；桌面另一檔2327首次進入亦成功顯示66日價格圖。對照四張正式PNG及最新UI順序，沒有水平溢出或假數字填圖；本次不聲稱所有字體／主題／可及性／異常狀態的全量矩陣。

原始截圖含個人財務資料，僅存本機 `.tmp/stock-live-acceptance/`，不提交 GitHub。最初 viewport 擷取曾縮放不符；已重設後重拍，只有符合上述像素尺寸的 `.jpg` 納入證據，錯誤裁切不計PASS。

## 原首次載入事件：實際追查結果

窄查舊事件 UTC 08:21～08:27 Cloud Run request logs，5876 kline 在08:23:25、08:23:50、08:24:53均為HTTP200，latency分別26.15、22.52、21.46ms；未找到同期kline 4xx／5xx。同時段公開錯誤僅daily-brief 404，不能當作價格圖失敗原因。舊初始截圖為載入中，後續截圖已有有效圖表；沒有保存足以唯一辨識Timeout／網路／回應解碼原因的原始客戶端記錄。

本次真人新建個股頁三次（手機5876、桌面5876、桌面2327）皆首次完成，不按重試；對應新版request均HTTP200，伺服器耗時74.10、42.61、39.06ms。這排除這些已觀測請求的後端HTTP失敗／慢查，但不能捏造舊事件唯一根因，也不能把先前可重現的共用鎖阻塞直接等同該事件。

新增Flutter回歸：首請求停滯超過9秒→顯示有界錯誤但有效報價仍可讀→重試真實typed `rows`結構成功→較晚的舊回應不蓋新圖。並在真正kline失敗時記公開股號、錯誤類型、耗時，不輸出token、回應內容或Owner資料，填補原診斷缺口。

## 日期列表修改

- 圖表維持時間正序及既有窗口，五年圖不因表格兩年預設被裁掉。
- 通用圖表資料表依最新季度／最新日期倒序，季度可折疊，逐列交錯底色；月季近24個月，日資料最近20期（含缺值位置）。
- 營收／法人用「表列合計」、估值用「表列平均」、EPS只列單季原值／最新值；有缺值不彙總。明示只對本表觀測作閱讀輔助，不是完整季度報表，不替代或回寫canonical數字。
- 交易明細、事件、筆記按合法日期倒序，未知日期置後。公告日與生效日分開；交易更早年度仍可明確選取，帳本不刪。股票為主軸的持股／本人關注排序保留。

## 新日期 UI 真人驗收（同源固定 Preview）

完整來源 `7f3e5621d39a99cdb6be622c80636da10f9a391e`；[完整 Release #39031856247](https://github.com/tommylin15/janus-omniforge/actions/runs/39031856247) Python 1415 passed／2 deselected、Flutter 及四個公開 GHCR 固定 digest PASS；[0%候選 #39032329887](https://github.com/tommylin15/janus-omniforge/actions/runs/39032329887)、[自動 auth #39032620084](https://github.com/tommylin15/janus-omniforge/actions/runs/39032620084)、[固定 Preview #39032747389](https://github.com/tommylin15/janus-omniforge/actions/runs/39032747389) SUCCESS。候選與 Preview 的 build-id、六股 EPS／營收12／12、報價與66日價量讀回 PASS。

使用者本人登入新版固定 Preview 後，手機390×844與桌面1440×1000各完成今日／關注／持股／5876個股四頁，**新版本8／8正向真人截圖 PASS**；首次進入5876價格圖手機、桌面皆成功，未按重試。原圖逐張實際檢視，無水平溢出；桌面DOM寬度1440與body寬度一致。這是本次指定畫面／資料狀態驗收，不擴充成所有主題／可及性／異常狀態全量矩陣。

- 每日TAIEX表：最近20期，2026-10-16、10-15、10-14、10-13倒序；季度可展開／收合、交錯底色。
- 月營收表：2026Q3最新在上，9月4,382,814、8月4,547,978、7月5,216,480千元；表列合計14,147,272千元，圖表仍依時間正序。
- EPS：2026Q2最新1.04、Q1為1.05元／股，未誤加總，四季／TTM未認證說明仍在。
- 本益比：圖保留120期，表限最近20期；Q4表列11期平均14.27倍，Q3表列9期平均13.94倍，日期倒序、逐列交錯底色，明示非完整季度報表。
- 真人交易明細：月份10月→9月，10月內10/16→10/15→10/14倒序，交錯底色；未點交易新增／更正／刪除／重新計算。

新版私有截圖與像素尺寸／SHA256 manifest 僅存本機 `.tmp/stock-live-acceptance/dated-ui/`，不提交 GitHub。舊正式矩陣與新 Preview 矩陣分開記錄。

[四 Jobs #39032863146](https://github.com/tommylin15/janus-omniforge/actions/runs/39032863146) **SUCCESS**，收據 `phase=PASS`、8次不同執行均PASS、`rollback_available=true`／`rollback_baseline_verified=true`，既有becb公開固定digest及設定回滾基準保留；未宣稱實際執行舊Job映像回滾。Scheduler `janus-ingestion-daily`唯讀確認`ENABLED`。

## 正式可逆切流：PASS／100%

[API promotion #39034273922](https://github.com/tommylin15/janus-omniforge/actions/runs/39034273922) **SUCCESS**，收據 `phase=PASS`／`rollback_rehearsal=PASS`；映像來源仍為上述完整7f3 SHA，請求提交與後續文件提交不是映像來源。最終 `janus-api-00538-sox` 唯一100%，固定Preview同revision；API映像為 `ghcr.io/tommylin15/janus-api@sha256:77a1529d2b5dfe43864c62c83aa4e797f8b2de33608bdb48b023197591b99e5c`。

實際新版→前版`janus-api-00533-yah`（becb）→新版100%演練完成，前版公開固定映像 `ghcr.io/tommylin15/janus-api@sha256:a745346a1e1910024ed8b52e98d0b2a6e6959d5ffb400fe2604bc3cbb73d20e4`保留；health／未登入private401／traffic／tags／完整build-id護欄PASS。切流後獨立讀正式與Preview：完整SHA精確匹配，六股EPS／營收兩邊均12／12 available、5876報價available／54.30／2026-10-16、價格圖66筆available。這些單次讀取不是登入後P95。部署lease ref唯讀無結果，已釋放。

本次新增邏輯本機Flutter37項、公開runtime10項及發布護欄93項通過；完整Release另涵蓋Python1415項與Flutter。舊事件唯一客戶端原因無法補造，診斷／回歸與當前正向鏈路已完成；不宣稱全量異常／可及性矩陣PASS。D01～D05仍依使用者接受的範圍CLOSED，不建立後續補驗。DRL其它scope仍各依原證據，未額外跑五年歷史回填或Owner重算。

使用者最後明確要求「正式100%之後就停下，先回寫文件和同步GitHub」；本輪回寫與同步後停止，不啟動其他任務。
