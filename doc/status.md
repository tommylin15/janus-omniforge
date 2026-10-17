# Janus 目前狀態

更新：2026-10-17（Asia/Taipei）。**使用者已授權 D01～D05 快速完成、包含 D04 繞路或必要的最小 IAM；這取代先前「僅 API 100% 切流、其他 P1 暫停」的限制。** 歷史 PASS 只限當次 SHA／環境／scope；下方舊「未切流／尚未真人驗收」段落保留當時 checkpoint，不能倒蓋最新結果。

### DRL-01 最新三項驗收 checkpoint（2026-10-17）

**本輪使用者只授權第①13月營收、②持股／關注120日OHLCV、③合法四季EPS；完成可驗證部分即停止，不往定期Ledger、UI或五年河流施工。整體DRL-01仍PARTIAL。** 以本段真實Core receipt取代舊上櫃缺月／未部署等DRL段落；其他D01～D05已驗收範圍各自保留。

| 子項 | 真實獨立證據與判定 | 剩餘限制 |
|---|---|---|
| ① 13個連續月營收 | **PASS**：[Core Census #38997408284](https://github.com/tommylin15/janus-omniforge/actions/runs/38997408284) 同股票 2025/09～2026/09 TWSE **1,077／1,096（98.27%）**，TPEX **864／896（96.43%）**，分市場超過90%／70%門檻；上櫃最後兩月官方補收[#38990411743](https://github.com/tommylin15/janus-omniforge/actions/runs/38990411743)各有Stage/Core snapshot。 | 來源取得時點非歷史實際公告時點；不可回填PIT。YoY圖UI自然載入另於D03驗收。 |
| ② TWSE持股／關注120日 | **PASS（6檔TWSE）**：[Focus Core readback #38997792145](https://github.com/tommylin15/janus-omniforge/actions/runs/38997792145) 指定六檔各135合法行情日，6／6；無重複Core寫入。上市20／21母體原[#38988025097](https://github.com/tommylin15/janus-omniforge/actions/runs/38988025097)亦達90%。 | 兩檔債券ETF不是股票market master構成；120日獨立部分不可與股票混計。 |
| ② TPEX 兩檔債券ETF | [官方source/schema #38998425476](https://github.com/tommylin15/janus-omniforge/actions/runs/38998425476) 00697B、00719B 兩檔官方當日資料與開高低收／量額具備，read-only PASS；[歷史修復 #38998709152](https://github.com/tommylin15/janus-omniforge/actions/runs/38998709152) 依Core最新真實終態判定。 | 來源可讀不等於120日實際價量已持久化；不得提前勾選。 |
| ③ EPS連續四季 | **PARTIAL**：[官方現有Job＋嚴格Core驗收 #38998082208](https://github.com/tommylin15/janus-omniforge/actions/runs/38998082208)：1513／2382 各9個分散合格單季，但2025Q4缺，0／2具4連季，驗收CI因此FAIL；[官方 Q3/Q4 分母盤點 #38998787882](https://github.com/tommylin15/janus-omniforge/actions/runs/38998787882) 六檔原始財報均有歸母獲利與基本EPS、**卻均無可驗證加權平均股數欄位**，source_failures=0。 | 不得從YTD EPS直接差分或將不可驗證分母當真，Core/圖表維持合法單季值或missing；完整四季尚未達標。 |

**本次工程變更範圍：**只沿用已核准MOPS、TWSE、TPEX、TAIEX官方來源與既有dev Cloud Run Job、GCS Stage/Iceberg Core；不改Owner交易／現金、stock master、正式API traffic、新Scheduler或付費供應商。完成判斷以GitHub／dev runtime receipt，不以commit或Job terminal alone代替。


### D01～D05 合併驗收（2026-10-17）

**整體判定：D01–D05 整合工程驗收 PASS，正式 API 100% promotion 完成。** 完整發布鏈（Release → Candidate → OAuth → Preview → Jobs → API 100%）全部成功，Preview `d739107` 四頁公開 API 驗證通過，使用者三項真人正向驗收維持有效。

| 工作包 | 狀態 | 已取得的直接證據 | 尚缺的獨立驗收 |
|---|---|---|---|
| D01 | **PASS（基本功能）** | 正式 8eb 持股頁、現金交易連動、重算按鈕已有使用者三項 USER_CONFIRMED_PASS；Janus Dev owner read-only MCP 7 positions／ledger v357／估值日 10/15 available | 股利、REVERSAL、更正、競態等進階場景 NOT_VERIFIED。 |
| D02 | **PASS_READ_PATH** | [Dev DB-first snapshot→正式 API #38890365233](https://github.com/tommylin15/janus-omniforge/actions/runs/38890365233) PASS：market-home.v1／10/15 三個 DB 區塊 available | authenticated 手機 P95 效能量測。 |
| D03 | **PASS_READ_PATH_ONLY** | [正式 public typed visual series #38889906057](https://github.com/tommylin15/janus-omniforge/actions/runs/38889906057)：16 available、2 EPS missing（屬 DRL-01C） | 390×844／桌面 authenticated 截圖。 |
| D04 | **PASS** | [安裝 #38991083134](https://github.com/tommylin15/janus-omniforge/actions/runs/38991083134)、[交接 #38991644822](https://github.com/tommylin15/janus-omniforge/actions/runs/38991644822)；隔離 DB restore、owner boundary 通過 | 新 executor timer active 後才停原 timer。 |
| D05 | **PASS（含 API 100%）** | 來源 `d739107` Release #38989576990、candidate #38991849862、OAuth #38991975400、Preview janus-api-00524-tot、Jobs #38992414928、**API 100% promotion [#38996111382](https://github.com/tommylin15/janus-omniforge/actions/runs/38996111382)** 全部 SUCCESS | — |

**本輪安全界線**：未修改 Owner 交易或成本、未手動重算、未切正式 dev API traffic、未停止 VM backup timer；各 PASS 僅限其真正驗收 scope。

### 2026-10-16｜P1 三項真人操作：使用者驗收回報

- **USER_CONFIRMED_PASS（2026-10-16，正式 dev App 8eb）**：使用者在本次對話明確回報：「真人持股畫面、現金交易連動及重算按鈕驗收都完成了。」記錄為使用者親自確認的**正向功能驗收**，不是本輪助手代為登入操作、執行 API write 或擷取新 runtime receipt。
- **範圍**：① 真人持股清單／總額呈現；② 現金部位與股票交易後的現金連動；③ App 的重新計算損益按鈕。既有對應後端 migration 062、真實 Worker queue、GHCR／100% 正式部署的獨立技術證據維持原版本、原 scope，不把它們偽裝為本次新增的交易紀錄。
- **不能外推**：未取得本次測試的每筆精確 BUY／SELL／股利／REVERSAL 明細、金額與 ledger 版本、按鈕 request／Worker execution ID、最新 EOD/PIT valuation、可供稽核的 screenshots、390px／desktop 全量回歸、網路故障／冪等測試或持股端到端 P95。這些若屬仍要求的獨立工程 gate，維持 **NOT_VERIFIED**；不要求使用者為普通發版重做 OAuth／三項基本人工驗收。
- **整體判定**：三項**人工正向 PASS**；P1 其他獨立 D01～D05 工作仍 **PARTIAL**，並未因人工驗收全數結案。本輪只記錄回報與文件同步，未部署、未修改 Owner 資料。

### 2026-10-16｜P1 8eb API 正式 100% 可逆切流與獨立驗收

- **正式 API 可逆切流 PASS**：[GitHub Actions #38865075071](https://github.com/tommylin15/janus-omniforge/actions/runs/38865075071) 同源 release `8eb42dcba28a68d4dee6d30e6a56e7d9e68bb699`，從已核准的 0% GHCR immutable candidate 經驗證後執行新版→前版→新版真實 100% traffic 演練，`result=PASS`；完整 receipt artifact id `12030787184`。
- **獨立 live readback PASS**：[GitHub Actions #38865347217](https://github.com/tommylin15/janus-omniforge/actions/runs/38865347217)；revision `janus-api-00517-ciq` 唯一 canonical 100%，`/app/build-id.txt` 與固定 Preview 皆為本次完整 SHA、健康路徑 200、未登入 Owner 與 cash API 401、immutable image 與 tags 保留、回滾演練 PASS，舊可回滾 revision `janus-api-00512-zal`。只讀驗收報告 `no_mutations=true`，artifact id `12031290847`。
- **當時驗收界線（現已補充新的使用者人工回報）**：發布當下只證明正式 API 與權限邊界，當時尚無真人驗收回報。後續使用者已確認持股畫面、現金交易連動與重算按鈕三項正向功能 **USER_CONFIRMED_PASS**；個別行情缺口、異常／冪等、正式 PIT 和冷暖 P95 仍須另證，不能把發布收據或使用者確認擴充成全量工程 PASS。

### 2026-10-16｜P1 真人截圖回報：參考總額與小計優先顯示（8eb42dcb）

- **觀察／根因**：正式 9f690 真人手機持股截圖顯示 7 檔有行情／股數，卻僅 2 檔價格可納正式報表，其餘「待估值」與主卡「總額暫不發布」，已知操作資訊被合格性 gate 整體隱藏。120 秒 MIS freshness 只能判「即時/延遲」，不能一律抹去 source-authorized 歷史有效成交報價。長錯誤說明擠到列表表頭也是視覺缺陷。
- **修復策略已 commit**：`services/api/intraday_quotes.py` 分離同日正式 `market_value/unrealized_pnl` 與 source/date/positive-price 限定的 `reference_market_value/reference_unrealized_pnl`；跨日／延遲價可做明確標示的**完整參考估值**。若仍有真正缺價，另外提供 `reference_priced_market_value`／已計價損益小計、已計價檔數／總檔數，不冒稱全部持股。已設定現金池時同步提供 `reference_total_asset_value`，或 `reference_partial_asset_value`（現金＋已計價部分）。不為任何缺價虛構價格／數字、不混入正式 PIT 總額。
- **UI 行為**：`apps/user_app/lib/final_ledger.dart` 主視覺優先顯示完整參考總額或可用小計；限制資訊縮為短文字；過時報價保留圖示、日期、個股未實現 PnL。實測截圖的 7 檔股數×顯示現價約為 **TWD 15,210,800**，與畫面現金約 181.1 萬元合計參考資產約 **1,702.2 萬元**；依畫面四捨五入平均成本推算參考未實現損益約 **192.3 萬元**，皆只屬截圖試算、非 runtime 正式 Owner 核定。
- **驗證狀態**：同範圍 Python 與 390px Flutter P1 回歸 tests PASS，`8eb42dcba28a68d4dee6d30e6a56e7d9e68bb699` 完整 GHCR Release [#38856837257](https://github.com/tommylin15/janus-omniforge/actions/runs/38856837257) PASS；0% 候選 [#38857279864](https://github.com/tommylin15/janus-omniforge/actions/runs/38857279864) PASS；自動 OAuth／private boundary [#38857441171](https://github.com/tommylin15/janus-omniforge/actions/runs/38857441171) PASS；固定 Preview [#38857524000](https://github.com/tommylin15/janus-omniforge/actions/runs/38857524000) PASS。原 9f690 四 Jobs 實際回滾基準 [#38856931558](https://github.com/tommylin15/janus-omniforge/actions/runs/38856931558) PASS；新四 Jobs 真實 rollout [#38857643226](https://github.com/tommylin15/janus-omniforge/actions/runs/38857643226) **COMPLETED／SUCCESS**（2026-10-16 06:08:32 UTC；Job logs 明確輸出 `{"result":"PASS","receipt":"ghcr-jobs-rollout.json"}`，receipt artifact id `12028401966`）。部署包含的自動化 canary／rollout 依其正式 receipt 判定，**不能推論 Owner 真實 UI 通過**。**歷史 14:57 暫停時快照**：當時新版 API 尚未升 100%，正式最後驗證為 9f690；**此狀態已被上方較新的 #38865075071（API 100% PASS）及 #38865347217（獨立 live PASS）取代**。真人登入、現金交易／重算按鈕 UI E2E 仍 **NOT_VERIFIED**；本次沒有擅自啟動其它工項。

### 2026-10-16｜P1 現金池／精簡持股 9f690 正式 dev 與獨立驗收

- **DB 062 PASS**：現金 checkpoint 使用 owner-scoped schema／版本與 ledger anchor；migration [#38841287256](https://github.com/tommylin15/janus-omniforge/actions/runs/38841287256) SUCCESS。舊 Broker Profile 的 `declared_cash` 不等於新現金餘額，未設定就保持未設定。後端交易現金淨流入／淨流出採持久化費稅與 reversal，總資產只在全持股合格台幣估值可用時顯示，未實現損益不重複相加。
- **同源部署 PASS**：`9f690363e5517cbe90d837a53a94ae3a4e7ab31e` full Python/Flutter/GHCR [#38841326765](https://github.com/tommylin15/janus-omniforge/actions/runs/38841326765)，API 0% [#38849023963](https://github.com/tommylin15/janus-omniforge/actions/runs/38849023963)，自動 OAuth/private negative boundary [#38849298689](https://github.com/tommylin15/janus-omniforge/actions/runs/38849298689)，固定 Preview [#38849422216](https://github.com/tommylin15/janus-omniforge/actions/runs/38849422216)，四 Jobs reversible rollout [#38849686748](https://github.com/tommylin15/janus-omniforge/actions/runs/38849686748) 均 SUCCESS。初次 API promotion [#38851511933](https://github.com/tommylin15/janus-omniforge/actions/runs/38851511933) 因 inert rollback template 同源 test FAIL、未越過驗證；修復後 [#38851753247](https://github.com/tommylin15/janus-omniforge/actions/runs/38851753247) SUCCESS，舊 7acff baseline 保留。
- **獨立正式 readback PASS**：[commit `7606ccb3812e1fbabddf3e087e19c8f7b7224b27`](https://github.com/tommylin15/janus-omniforge/commit/7606ccb3812e1fbabddf3e087e19c8f7b7224b27) 只更新 readonly request；[#38853614819](https://github.com/tommylin15/janus-omniforge/actions/runs/38853614819) 驗 canonical API 唯一 100% target revision、同源固定 Preview／build-id、immutable image、保留原 tags、health 200、unauth profile/cash 401 及 rollback receipt，無 GCP／traffic／Owner mutation。
- **新版公開暖路徑 PASS（不等於 Owner 效能）**：30 次 Preview public market-home [#38853879877](https://github.com/tommylin15/janus-omniforge/actions/runs/38853879877) 30/30 成功、P50 48.11ms、P95 57.70ms、最大 966.09ms；樣本為 GitHub runner → 公開 API，未涵蓋 authenticated 持股首屏、手機載入、交易保存或手動重算等待。
- **最新正向 Owner 唯讀觀察**：在已授權 Janus private MCP 下讀到 operational ledger v357、目前 7 筆 active positions，valuation／price date 仍為 2026-10-15；10/16 新交易已發生，不能把前一日估值誤稱 10/16 最新收盤/PIT 損益。此次沒有回寫現金或交易，也未證實使用者已設定初始現金。
- **剩餘 hard gate = PARTIAL**：真人 logged-in App 的持股一至二行列表、現金設定後 readback、買賣現金與持股 checkpoint、重新計算損益點擊→enqueue→Worker terminal→UI 更新、390px／desktop 真實截圖與持股 API／UI 冷暖 P95；無登入態正向證據時維持 NOT_VERIFIED，不能用 401／public perf／Worker canary 代替。

### 2026-10-16｜P1 同源 Jobs／固定 Preview 發布與業務驗收

- 四 Jobs 與排程 **PASS**：[rollout #38821199561](https://github.com/tommylin15/janus-omniforge/actions/runs/38821199561) receipt phase=PASS、8/8 實際 canary、同源 immutable digest、rollback baseline 可用。[infra #38826878839](https://github.com/tommylin15/janus-omniforge/actions/runs/38826878839) 確認四 Jobs Ready、Scheduler ENABLED、Controller active。
- 10/15 Owner EOD／損益 **PASS**：[來源與缺口唯讀 #38827197770](https://github.com/tommylin15/janus-omniforge/actions/runs/38827197770) → [官方定日雙 ETF 價與單 Owner Mart 補算 #38827827101](https://github.com/tommylin15/janus-omniforge/actions/runs/38827827101) 終態 PASS_JOB_TERMINAL；8/8 同日價格、8/8 市值與未實現損益、單一 TWD 總結 available，原 ledger v354 不變。獨立授權 MCP 重查 positions 8/8、年度損益與曝險日期均為 2026-10-15。
- 重算後端 Queue **PASS**：[雙 Worker #38828798196](https://github.com/tommylin15/janus-omniforge/actions/runs/38828798196) 1 synthetic request、兩個真實 Worker task，seed／worker／verify／cleanup 全部成功，lease 釋放；不新增真實交易。**Authenticated 按鈕點擊與 UI 顯示仍 NOT_VERIFIED**，不能用技術 canary 代替。
- **正式 dev App API 100% 切流 PASS**：[初次 fail-closed #38830314867](https://github.com/tommylin15/janus-omniforge/actions/runs/38830314867) execution_not_terminal，未切流且 lease 釋放；[五 Jobs 全分頁 readonly #38830554996](https://github.com/tommylin15/janus-omniforge/actions/runs/38830554996) 1174 executions 全終態；[受控 promotion #38830675477](https://github.com/tommylin15/janus-omniforge/actions/runs/38830675477) receipt phase=PASS，舊版 b1bc785…（janus-api-00478-cih）→ 新版 7acff…（janus-api-00507-wez）→ 舊版 → 新版，rollback rehearsal PASS；[獨立正式讀回 #38831003922](https://github.com/tommylin15/janus-omniforge/actions/runs/38831003922) canonical traffic 100%、正式／Preview build-id 一致、immutable image、tags preserved、health 200、unauth owner 401 均 PASS。沒有新付費資源、ledger 交易或 job template 改動。

### P0｜TPEx 官方歷史日期長期能力（2026-10-15 本輪）

- **已落地（程式及資料庫）**：`services/api/tpex_quotes.py` 支援官方 `/www/zh-tw/afterTrading/dailyQuotes?date=YYYY/MM/DD&response=json` 的指定交易日查詢（不限 OpenAPI 七日滾動窗口）；嚴格核對官方回應 `date`、有效收盤價與 14:30 發布門檻。近七日 OpenAPI 仍保留，失敗可走官方定日來源。版本化 migration `061_tpex_official_eod_daily` 使用獨立 PostgreSQL 官方日期／價格／來源 URL／record SHA-256／first-observed，不污染 Core/Iceberg canonical；Private Mart 只用不晚於估值日的已保存官方資料。
- **證據**：官方 `00697B` 10/14 原始 JSON 指定日期與 date response [#38715334637](https://github.com/tommylin15/janus-omniforge/actions/runs/38715334637) PASS；migration [#38714018250](https://github.com/tommylin15/janus-omniforge/actions/runs/38714018250) 真實 dev PASS；17/17 歷史、日期、PIT targeted tests [#38717113572](https://github.com/tommylin15/janus-omniforge/actions/runs/38717113572) PASS；完整來源 `285848e28041bf2fb024bd98bd348641f022a1ed` Release [#38717341300](https://github.com/tommylin15/janus-omniforge/actions/runs/38717341300) SUCCESS；API 0% [#38718006906](https://github.com/tommylin15/janus-omniforge/actions/runs/38718006906) 和自動 OAuth／private boundary [#38718076548](https://github.com/tommylin15/janus-omniforge/actions/runs/38718076548) SUCCESS，**未切 100% 流量**。
- **Owner backend P0 10/14 PASS（與 P1 UI／正式切流分離）**：四 Jobs [#38718355824](https://github.com/tommylin15/janus-omniforge/actions/runs/38718355824) SUCCESS。先前 Owner [#38724207848](https://github.com/tommylin15/janus-omniforge/actions/runs/38724207848) 因雙 ETF 00697B／00719B 缺 Core 日期價 FAILED（#38730256233 精確恢復 lease）；兩檔同日合法官方價格補齊後，Owner [#38730741579](https://github.com/tommylin15/janus-omniforge/actions/runs/38730741579) 完成 derived Mart 寫入但因舊 Private Iceberg schema 不儲存 `stale_price_count`，驗收腳本誤判 aggregate FAILED；#38732315439 安全恢復該次 lease。**真實唯讀** [#38732675488](https://github.com/tommylin15/janus-omniforge/actions/runs/38732675488) 驗 v354／2026-10-14：8/8 有市值、8/8 未實現損益、aggregate_status=available、missing_price_count=0、affected_symbol_count=0、總市值／總未實現損益／報酬欄位非空。最終 immutable receipt gate [#38733406224](https://github.com/tommylin15/janus-omniforge/actions/runs/38733406224) SUCCESS；修正驗收 guard targeted [#38733406111](https://github.com/tommylin15/janus-omniforge/actions/runs/38733406111) SUCCESS。**缺席的舊欄位維持 null，不造假為0；`aggregate_status=available` 由 deterministic Mart 計算的 missing/stale 皆零產生。** 同次記錄的終態 FAILED 不更改歷史判定，也沒有重新發起衍生重算。

**整體 PARTIAL。** 使用者已明確授權 D01～D05 一起開發、以同源整批驗收，取代此前文件-only 暫停；D06 獨立 FinOps、不併入本輪，D07／D08 後置。完整 Release／GHCR digest／0% 候選／自動 OAuth 已 PASS，**正式 API 100% traffic 尚未獲得本產品包的所有真實業務 gate**，不能宣稱產品交付完成。詳見 [TODO](todo.md)、[AI 卡片](execution-cards/README.md) 與 [證據索引](spec/operations-and-testing.md)。

### 2026-10-15｜P1 夜間 Private 派送直接修正（待 live release）

- 使用者要求直接調整，不追舊 execution。修改 `jobs/ingestion-core/ingestion_core/batch_controller.py`：15:30 Private 仍依賴 14:30 ingestion；21:30 Private 設為獨立 EOD slot 並優先於同日待決午後 Private，不能因 ingestion 終態缺失阻止整晚估值；下午 ingestion 真實 `failed` 時，15:30 Private 只記 `skipped/upstream_ingestion_failed`，不偽造成功也不永遠占用 pending queue。
- 官方 TPEx 日價、估值日與 future-leakage／missing／stale／owner publication 約束保持由 Private Mart fail-closed；不因解開排程依賴而推論當日所有股票已具合格價格。
- 相關測試新增獨立 slot、優先序、失敗上游結束、派送只一次的回歸。selective CI [#38755041998](https://github.com/tommylin15/janus-omniforge/actions/runs/38755041998) PASS。完整 SHA `7acff50000644979af3815f00fbd7f1c167e1098` [GHCR Release #38755382061](https://github.com/tommylin15/janus-omniforge/actions/runs/38755382061) Python／Flutter／四 GHCR／匿名 digest **PASS**；[0% candidate #38756170482](https://github.com/tommylin15/janus-omniforge/actions/runs/38756170482) PASS；[自動 OAuth boundary #38756520384](https://github.com/tommylin15/janus-omniforge/actions/runs/38756520384) PASS；四 Jobs reversible controlled [#38756738102](https://github.com/tommylin15/janus-omniforge/actions/runs/38756738102) **FAILED**：Private canary PASS 後，Mart 首輪 canary 卡在 `execution_not_terminal`，自動回復未完成，receipt `RECOVERY_REQUIRED`；當下 Mart/Private 新版、Controller/Ingestion 舊版及 Scheduler `PAUSED`，原部署鎖保留。2026-10-16 專用唯讀 [#38820661165](https://github.com/tommylin15/janus-omniforge/actions/runs/38820661165) PASS，證實混合映像、Scheduler PAUSED、近期 executions 無正在執行的工作；[精確 immutable receipt 回復 #38820889359](https://github.com/tommylin15/janus-omniforge/actions/runs/38820889359) **PASS**，五支受保護 Jobs 的配置／映像回復、Scheduler `ENABLED`、原 annotated GitHub lease 已釋放。新版同一來源再次以共用 fence 受控部署 [#38821199561](https://github.com/tommylin15/janus-omniforge/actions/runs/38821199561) **進行中，尚未取得終態**。另修正 `ghcr_jobs_rollout.recover` 對未終止 canary 不再僅單次 `fence()`，改在既有 bounded execution guard 下重查再恢復；[targeted CI #38821683162](https://github.com/tommylin15/janus-omniforge/actions/runs/38821683162) PASS。此修正 commit 於重試後，不冒稱已套入正在執行的工作流。正式 API 流量未切、Owner ledger 未寫；P1 夜間 Private dispatch／Owner 當日 PIT PnL 與 UI 仍待真實驗收。

### P1｜2026-10-15 Owner 唯讀資料與固定 Preview 接續

- **固定 Preview 同來源 PASS**：[commit `78bf14bb`](https://github.com/tommylin15/janus-omniforge/commit/78bf14bb1665be93ef6f7048d71458632bdbc871) 將 `ops/ghcr-preview-request.json` 目標改為 285848 GHCR API 固定 digest，引用 release #38717341300、candidate #38718006906、OAuth boundary #38718076548；[#38740477232](https://github.com/tommylin15/janus-omniforge/actions/runs/38740477232) 最新 workflow `completed/success`，同次 `Verify fixed preview release and owner-lease safety contracts`、`Update only verified candidate preview tag with rollback protection` 均 success；公開 build-id／tag 校驗由該實際 workflow 執行，且保存 receipt artifact。此結果僅是 Preview，正式流量不變，**Owner UI 尚未驗收**。
- **已授權 Owner MCP 正向唯讀讀回（2026-10-15）**：`positions` 為 `available`、8/8 有效市價／市值，兩檔債券 ETF `00697B`／`00719B` 均有 `price_status=available`，共同 `valuation_date=2026-10-14`、`ledger_version=354`；`annual-pnl` 為 `available`，同日期／版本。此為真實 Owner backend read path，**不是**正式 App UI／手動重算按鈕端到端證明。
- **最新估值仍待獨立驗收**：10/15 約 22:21（台北時間）再次 Owner MCP 唯讀讀回，Private Mart 最後估值仍為 10/14；官方定日來源的歷史價在 PostgreSQL，與一般已發布 Core `ohlcv` 非同一存放路徑。對兩檔 ETF 查 `janus-core/ohlcv` 的 10/14～10/15 區間均回 `missing`，**不能因此倒推已持久化的 TPEx 官方歷史價遺失**，但新交易日 EOD→Private Mart→UI 的完整更新仍 `NOT_VERIFIED`。晚間排程已由 [#38752934496](https://github.com/tommylin15/janus-omniforge/actions/runs/38752934496) 唯讀查核：Controller 模式 `active`、Scheduler `ENABLED` 且 21:30／22:30 controller executions 均 `Completed=True`；但 Private Pipeline 最新僅 20:11 建立、20:12 成功的 `janus-private-pipeline-wnk5x` 唯讀執行，21:30 後無更新的 Private execution。**Controller tick 成功不等於 private occurrence 已派送**；目前尚缺 PostgreSQL `control.batch_occurrences` 依賴／status readback，不能猜是 dependency、busy、skipped 或未建 occurrence。10/15 Owner EOD→Private Mart 最新估值仍 `NOT_VERIFIED`。
- **P1 基礎設施 live PASS**：[#38751648476](https://github.com/tommylin15/janus-omniforge/actions/runs/38751648476) 及 [#38752934496](https://github.com/tommylin15/janus-omniforge/actions/runs/38752934496) 均 `SUCCESS`；實測 Preview `/app/build-id.txt` 等於 285848、`preview` tag 與 0% candidate 指向同 revision；四 Jobs 均 Ready、immutable GHCR；Scheduler ENABLED `30 * * * *`。正式 canonical 仍 100% 舊版 `b1bc785906212b8d2860b1521affb83930d09f04`，本次沒有寫流量／執行 Job／改 Owner 資料。
- **P1 尚缺的硬 gate**：切流當時需重查服務與四 Jobs baseline；authenticated Owner UI（股數、市值、當日漲跌、累計未實現與總損益）；重新計算按鈕→owner enqueue→worker terminal→ledger/checkpoint/PnL；390px／desktop 截圖及適用性能、正式 dev 流量及 rollback 讀回。缺證據就維持 `PARTIAL`，不可拿 P0 成功逕行 API 100% promotion。

## 能確定的現況與限制

| 項目 | 最近可追溯證據／判定 | 下一步 |
|---|---|---|
| 全市場 | 2026-10-13 名冊 1988；Bootstrap、同日 Cached 已有 PASS 收據；不是永久固定分母 | 不重跑該歷史驗收；驗跨 UI／研究／總控剩餘範圍 |
| 費稅／持股 | **P0 backend as-of 2026-10-14 PASS**：00697B／00719B 官方歷史日價、Owner v354，8/8 持股市值及未實現損益都有值，aggregate_status available，缺價／受影響商品 0，總計非空；#38732675488 與 #38733406224 PASS，舊失敗執行保留 FAILED | P1 前端正式持股頁／計算按鈕與新當日估值、正式流量切換另驗；不重做 88 筆費稅事件 |
| 首頁快照 | main 已有正式 caller；057 migration 曾 PASS；最新接線的 runtime 尚待驗收 | 快照產生→API 讀回→冷暖效能 |
| 重算／交易／四頁 | 持股 partial 小計與狀態 Flutter 已修改、完整 Flutter Gate PASS；交易試算與重算舊契約已具實作，**新版本 Owner 交易/重算及四頁 authenticated screenshot 未驗** | 覆蓋同源真實功能、VF-00～08、390px/desktop與可及性 |
| 備份總控 | **D04 PASS**：[安裝 #38991083134](https://github.com/tommylin15/janus-omniforge/actions/runs/38991083134)、[交接 #38991644822](https://github.com/tommylin15/janus-omniforge/actions/runs/38991644822)；新 executor 取得 controller succeeded 收據、不可變備份 SHA256、隔離 DB restore、owner boundary 及原 DB 未變均通過；使用者已補單 VM OS Admin Login、postgres-vm actAs 及 SSH22 IAP | 新 executor timer active 後才停原 timer |
| API／Preview／Jobs | 來源 `d739107` Release #38989576990、candidate #38991849862、OAuth #38991975400、Preview janus-api-00524-tot、Jobs #38992414928、**API 100% promotion [#38996111382](https://github.com/tommylin15/janus-omniforge/actions/runs/38996111382)** 全部 **SUCCESS**；Preview 四頁公開 API **PASS**；**D01–D05 合併驗收 PASS** | 後續 DRL-01 資料修復與 D07/D08 |
| Iceberg／D06 | 2026-10-16 基線 8,343 objects／194,161,764 bytes、8,336 小檔；CI orphan 清理 #38879585601 **PASS**，實刪 477 objects / 2,039,377 bytes。無產品使用者的稽核鏡像停用來源 740e54c2 完整 Release #38873919415 PASS | 完成同源 Jobs rollout／生效讀回；量測 I/O 減量。詳見 [D06證據](archive/d06-finops-2026-10-16.md) |
| Retention fence | 96 Research／495 Private JSON 已完整讀取，8 Core identities皆有manifest；外部／PG全面 fence 未發行 | 使用者明確例外允許保留已知引用、current/named/24h及7日檔齡後清無關聯小檔；不豁免 canonical rows／Core manifest retirement |
| 五角色／CEO | B0～B8 歷史 CLOSED；B9 品質未整體通過；omniAgent P0-V 技術 PASS，正式 Owner publication 未通過 | 產品交付後逐角色評估，再驗真實報告 |

## 本輪直接觀測與阻塞（非永久 runtime 快照）

- [新版本 full Release #38695837708](https://github.com/tommylin15/janus-omniforge/actions/runs/38695837708) 來源 `079cca4f…` 四公開 GHCR、Python/PostgreSQL、Flutter PASS；[#38710296292](https://github.com/tommylin15/janus-omniforge/actions/runs/38710296292) API 0% 與 [#38710582355](https://github.com/tommylin15/janus-omniforge/actions/runs/38710582355) auto OAuth boundary、[#38711150682](https://github.com/tommylin15/janus-omniforge/actions/runs/38711150682) 固定 Preview SUCCESS；Jobs 仍在較舊 SHA，不能做同源正式切流。
- [部署鎖安全恢復 #38709075307](https://github.com/tommylin15/janus-omniforge/actions/runs/38709075307) SUCCESS，原有 GitHub lease ref 已不存在。D04 [唯讀 #38710741325](https://github.com/tommylin15/janus-omniforge/actions/runs/38710741325) 確認唯一 Scheduler 與 3 份 GCS 備份，但 CI VM describe 缺權限；[#38692040229](https://github.com/tommylin15/janus-omniforge/actions/runs/38692040229) install 仍 FAILED，未停原 timer。
- [TPEx 官方來源 #38694634095](https://github.com/tommylin15/janus-omniforge/actions/runs/38694634095) GitHub runner 讀到 00697B、OpenAPI 12,466 rows、正確 2026-10-14 日期；[live readonly #38710480798](https://github.com/tommylin15/janus-omniforge/actions/runs/38710480798) 與 [日志 readback #38711328741](https://github.com/tommylin15/janus-omniforge/actions/runs/38711328741) 則確認 Cloud Run 官方 fetch JSONDecodeError，且 Core valuation 10/14 / saved quote 10/15 不符 PIT。Owner Mart [#38695729369](https://github.com/tommylin15/janus-omniforge/actions/runs/38695729369) `held_etf_official_eod_missing` FAILED，無法宣稱 PnL PASS；本輪均未重送 owner ledger events。
- 舊 D06 [四 Jobs rollout #38686125420](https://github.com/tommylin15/janus-omniforge/actions/runs/38686125420) 現已查到 `completed/success`，但 [audit-cleanup #38686337134](https://github.com/tommylin15/janus-omniforge/actions/runs/38686337134) 為 `completed/failure`，不因 container／rollout 成功就稱 cleanup PASS。D06 後續已由使用者獨立授權續做；最新實清及停用鏡像進度見 [D06證據](archive/d06-finops-2026-10-16.md)，不挪用 D01～D05 授權。
- 本輪尚無 authenticated 手機冷暖 P95／四張真實截圖或完整 Owner 試算/保存/重算 terminal/checkpoint 新版驗收；不以 GitHub mock、公開 API 或上版 build 替代。

- [公開效能 #38695300866](https://github.com/tommylin15/janus-omniforge/actions/runs/38695300866) 固定 Preview 先前來源 536598 30/30 公開 API，P50 47.43ms／P95 51.42ms；[圖表 #38696030009](https://github.com/tommylin15/janus-omniforge/actions/runs/38696030009) 18 指標有 16 available、2 EPS missing。不可外推為新版 079cca authenticated UI 或手機冷暖 P95。
- GCP_MCP Google OAuth `redirect_uri_mismatch` 屬連接器授權，工程改以已驗證 GitHub Actions → GCP WIF 執行，不調整 Janus OAuth Client 或任意擴 IAM。

## 文件整理結果與下一入口

- [盤點／風險與修正](documentation-review-2026-10-15.md)：文件與程式差異、範圍及驗證。
- [系統建置與驗收補強](spec/system-development-contract.md)：UI、持股操作、模型驗證及 FinOps 的工程契約。
- 未完成工作只在 [TODO](todo.md) 排隊；本頁不維護第二份 checkbox。
- 舊逐次狀態完整保留於 [整編前快照](archive/documentation-baseline-2026-10-15-status.md)，不得用其中過期 PAUSED／IN_PROGRESS 覆蓋本頁。
