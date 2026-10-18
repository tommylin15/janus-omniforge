# DRL-01 2026-10-18 本輪讀回前歷史 checkpoint

以下保留當時結果；暫停已由使用者「一次執行下去」解除，現況見 [最新證據](../spec/operations-and-testing.md)。

### 2026-10-18｜DRL-01 暫停／文件同步（PAUSED_BY_USER；不構成 runtime 驗收）

- **指令／範圍**：使用者已確認「正式 dev API 新版 100% 切流、驗收完成」，後要求完成 DRL-01 四個尾項，隨即明確「暫停作業」，本輪僅允許 GitHub 文件回寫。只暫停 DRL-01 後續工程；不變更其它工項／既有 Scheduler、Jobs、已核准 ops request。
- **兩年河流**：官方 25 月三片補收 [#39051869951](https://github.com/tommylin15/janus-omniforge/actions/runs/39051869951) PASS；曾有 PG 六股 × PE/PB = 12 組 `ready/window_years=2`。但前次正式 API 唯讀 [#39083839390](https://github.com/tommylin15/janus-omniforge/actions/runs/39083839390) 12 路 PE/PB 無 `two_year_profile`；正式 API／Flutter 個股頁分位河流 **NOT_VERIFIED**，不可由使用者確認 100% traffic 外推。
- **Readiness／自然增量**：既有 Controller 有 data-supplement 自然成功記錄；此前 `control.data_readiness_ledger` Admin 設定查無鍵。程式修正／targeted CI 與正式 Jobs rollout、下一次自然增量之固定 Core snapshot／Ledger 寫入讀回必須分開驗收；當下 **NOT_VERIFIED**。
- **Market Volume 缺口與真實前置**：[Core 逐月 #39083573483](https://github.com/tommylin15/janus-omniforge/actions/runs/39083573483) 指定股票抽樣 2026-07／08／09／10（至16日）= 0／0／19／11 個日期，不能推論為全市場筆數；TAIEX 指數日期連續亦不代表 volume/activity 完整。當前 `ops/drl01-market-volume-replay-request.json` **`approved=true`**，但該 request 提及的 Jobs rollout [#39089399302](https://github.com/tommylin15/janus-omniforge/actions/runs/39089399302) **FAILED**；近期 workflow [#39098854896](https://github.com/tommylin15/janus-omniforge/actions/runs/39098854896) **SKIPPED**，不能聲稱回補或 TWSE 10%／TPEx 30% 門檻已通過。
- **EPS**：2026Q1/Q2 指定六股 6/6 合格；2025Q4 原始資料存在但未有合格單季／可證股數分母，歷史四季／TTM 保留 `NOT_CERTIFIED/WAIVED_FOR_MVP`；禁止將 YTD EPS 直接相減、推估分母或缺值補零。
- **本次變更與復工條件**：GitHub 僅 status／TODO／operations 文字 commit，**無新的 code、migration、CI 人工觸發、deployment、runtime query、真實資料改寫、Owner 操作**。GitHub push 如由既有 workflow 自動派發一般 CI，不能視為 DRL-01 acceptance。復工時先核對最新 `main`／active image digest／deploy lease／自然排程與 FINOPS-AB 並行，再依四項順序執行及留存實際 receipt。

### 2026-10-18｜DRL-01 正式 dev 收尾：Core 逐月缺口與 serving 分離（PARTIAL）

- **使用者驗收**：新版 dev API 已切流至 100% 且本人完成正式驗收；這項回報不直接涵蓋兩年 PE/PB 新欄位。必須分別核對 Core → PG publication → public API → UI。
- **官方 Core 唯讀總帳**：[Core metadata census #39083283620](https://github.com/tommylin15/janus-omniforge/actions/runs/39083283620) PASS：`benchmark` 759、`market-volume` 39,699、`ohlcv` 111,929、`market-activity` 135,050、`valuation` 16,595、`financials` 88,131。Snapshot: benchmark `16811576102780075`、ohlcv `4001332868550575344`、financials `5736520631016782502`。這些是當次數量，不等於連續歷史與嚴格 PIT。
- **逐月唯讀**：[continuity #39083573483](https://github.com/tommylin15/janus-omniforge/actions/runs/39083573483) PASS。合併 benchmark 有效交易日期 2026-07/08/09/10（截至16日）=22/21/21/11，但 TAIEX 75 日、TPEx 指數僅39日；六檔指定股票 OHLCV 日期 22/21/20/11；market-volume 抽樣 0/0/19/11，market-activity 抽樣 0/3/14/11。**這是指定股票抽樣，非全市場逐日 coverage。** July～September 的指數、全市場價量與市場活動不能視為同一資料集。
- **EPS**：六檔股票 2026 Q1/Q2 合格單季 6/6；2025 Q4 皆有原始 EPS 期間，但六檔均沒有可證明的合法單季值，四連季仍 `NOT_CERTIFIED/WAIVED_FOR_MVP`，禁止以累計 EPS 直接相減或填零。當前 financials Core snapshot 同上；全市場連續四季單季驗證 0/1992，非「沒有任何財報」。
- **河流／API**：既有 [25月官方補收 #39051869951](https://github.com/tommylin15/janus-omniforge/actions/runs/39051869951) 最終 `PASS_TWO_YEAR_PUBLISHED`。2026-10-18 PG 唯讀證實6股×PE/PB共12筆 `status=ready,window_years=2`；但 [正式 API #39083839390](https://github.com/tommylin15/janus-omniforge/actions/runs/39083839390) 18個public visual-series皆 HTTP200，其中12個PE/PB**未返回 two_year_profile**，要比對正式 build-id／serving及UI後才能標「河流呈現」PASS。
- **Ledger／自然排程**：過去五天 Controller 記錄 4 次 data-supplement succeeded、1 次 running，data-quality 1次 succeeded；但當次 control `data_readiness_ledger` 查無鍵，故 **週期性 Readiness 發布 NOT VERIFIED**。待讀回指定自然 execution 日誌、修正 `data_readiness_status=UNKNOWN` 根因，並在至少一次自然增量、下一次讀回確認。
- **修復／發布**：`market_history.py` 先前錯把上櫃30%門檻當10%，已改 TWSE≤10%、TPEx≤30%，補邊界案例測試。通過 tests／build 不代表市場歷史回補已實際完成；應先對真正缺日、來源、會員母體與既有 Job image 做幂等、有界、有 receipt 的回補，再核讀 Core 與 serving。
- **狀態**：DRL-01 仍 `PARTIAL`；不重開 D01–D05 已結案豁免、不新增資料來源／排程、不操作 Owner、不按 TTL 直接刪 Core 歷史。


