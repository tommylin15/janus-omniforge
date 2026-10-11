# 四頁視覺資料涵蓋 — 真實 Core 小樣本證據

觀察日：2026-10-11；來源：現有 Janus Dev Read-only v2 / janus_market_context（唯讀）。
狀態：**SAMPLE ONLY／VF-00 PARTIAL**。本檔不保存私人持股、token、原始 payload 或帳戶資訊。

| Dataset | 抽樣 symbol／筆數 | 觀察到的資料與最新期 | UI 可用性判定 |
|---|---|---|---|
| OHLCV | 2327／5 | TWSE 官方、2026-10-08、close 635.00、OHLC/volume/source/provenance | Core **confirmed**；價格圖已有 App 程式，實際 serving/preview 仍待同 SHA readback |
| Valuation | 2327／4、2330／5 | TWSE PE/PB/殖利率，2026-10-08：2327 PE 42.76、PB 7.38、yield 0.94%；2330 PE 29.56、PB 10.28 | Core **confirmed**；新 typed public valuation-series 僅已發布 serving projection，若缺投影回 missing/unavailable 而不掃 Iceberg |
| Institutional | 2327／4 | TWSE trade_date、investor_type、net_shares，可見 10/08 各角色和 10/07 部分 | Core **partial sample**；尚無合格 bounded institution-series/public serving，不能在 App 自行拼成完整法人趨勢 |
| Financials | 2327／4、2330／3 | MOPS fiscal year/quarter/metric/value/official source；樣本 period_basis、is_single_quarter、report_scope、share_basis_status 為 null | **BLOCKED for comparable EPS/revenue chart**；需官方 period normalization、股本可比性、比較期／available-at；不能據此判 EPS 趨勢 |
| Events | 2327／6 | 官方 event_id、event_type、published_at、observed_at、effective_date、provenance | Core **partial sample**；可以列表/時間軸，但時間異常與更正版次要檢查，未知方向不標利多利空 |

抽樣限制：每次只取 3～6 筆，回傳狀態皆為 `partial`（主要反映 bounded/truncated 查詢），不代表整體 dataset 缺值率，也不能推論 500 檔歷史覆蓋。以上日期與數值是樣本事實，不可當現行即時行情。未取得全市場日期區間、每日可用點數、serving projection rows、登入後 Flutter/Cloud Run 真實回讀；`VF-00`、`VF-07` 仍開放。

接續驗收：
1. 對代表性持有/關注/未持有/離榜/缺價股票，記 source→Core→serving→API→UI 的日期、點數、status、missing_reason、unit、provenance。
2. 對公開 `visual-series` 的 2327／2330 分別驗證 PE/PB/yield 的有界點數、last data_as_of、無 cache miss Iceberg fallback。
3. Institutional 與 financials 先建立 authorized structured serving 與期別正規化，再考慮補正式互動圖；不可為達 6 張圖假造時間序列。
4. 資產走勢需要真正連續 Private Mart owner valuation snapshots；單日多次報價不構成歷史資產曲線。
5. 以正式 dev candidate 相同 SHA、API data/provenance、OAuth owner four-page screenshot、P50/P95 和圖卡 click count 作 acceptance；文件與示意 PNG 不等於 pass。
