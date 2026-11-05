# 今日盤中進度圖 V3｜2026-11-05

狀態：使用者核准規格，程式正依 CI／固定映像／Dev 遷移與 Runtime 驗收；提交程式不是已上線。

## 需求
- 個股及 TAIEX 分鐘點**統一保留 3 天／72 小時**；有新盤中有效寫入時順便刪除超期分鐘點，不新增排程、常駐 Job 或高頻抓取。未有新寫入時過期資料可能暫留資料庫，不假稱定時清理。
- 大盤與個股共用固定的 09:00–13:30 台北交易時段 X 軸。新樣本按真實分鐘映射到起點及終點間的實際位置，尚未取樣的未來留白，不因只收集 3 分鐘就把全日壓成這 3 分鐘。
- 前一正式收盤價為 0% 灰色水平虛線；上漲紅色、下跌綠色；跨越 0% 的線段在交點分色。沒有合法前收則顯示缺值，不能用第一筆分鐘報價推估。
- 圖下方顯示「觀測最高／觀測最低／最新觀測」的時間 HH:mm、價格、相對昨收漲跌幅；顯示最新觀測時間距 13:30 的時段進度。
- 中間任何缺少一個完整分鐘即斷線，不跨空缺或插補 0 點；排除非當日與 09:00–13:30 外的樣本。高低只指已收集點，不代表整日成交真正高低。

## 實作
- Flutter 增加 FvIntradayProgressChart 專用元件；採用 fvGain 台股紅及 fvLoss 台股綠，與既有日線、融資圖分離。
- TAIEX 以 market-home 官方 benchmark history_points 最新早於交易日且在 7 天內的有效正式收盤價作為前收，沒有來源不能計算幅度。
- Owner 股票 /api/v1/me/portfolio/intraday 按既有持股授權，回傳當日已保存的分鐘點及單檔官方 previous_close、previous_close_date、previous_close_source；不因新圖新增上游行情要求或觸發下單。
- 新增 PostgreSQL migration 077_index_minutes_three_day_retention.sql，只給 janus_private_api 對既有大盤分鐘表的 DELETE 權限；在 QuoteRouter 成功寫入 TAIEX 時以 minute_at < now() - interval 3 days 清理。若 migration 尚未套用，暫跳過清理不阻擋原本行情寫入。
- 既有個股分鐘表三天清理、Owner ACL 與每日只讀今天的 API 限制維持。

## 驗收
- Flutter：固定 09:00/13:30、漲紅跌綠、零線、跨零分段、缺分鐘斷線、前收缺值、單點空資料、最高最低時間與正負幅度；原 5/20/30 日圖不可受影響。
- Python：077 表權限與新 index cleanup、缺權限容錯、Owner 未登入與非持有拒絕、官方前收缺值不造假。
- 部署：完整 Flutter/Python CI → GHCR full Release → Dev 077 migration → 0% Candidate → OAuth/Owner boundary + 真實盤中比較 → reversible API-only 100% promotion → Runtime／Owner UAT。現有 V2 Candidate 曾因 2330 intraday/stale 不一致失敗，未處理前不能宣稱 Dev 上線。
- KBars 缺口回補屬獨立需求，本版不開新付費 API、持續背景收集或延長三天保留期。
