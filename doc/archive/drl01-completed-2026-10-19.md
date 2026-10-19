# DRL-01 工程結案（2026-10-19）

狀態：**PASS，依使用者已核准範圍結案**。自然daily／weekly新版收據依2026-10-18決策改列後續觀察，仍NOT_VERIFIED；不以等待時間阻擋工程結案。歷史PIT、跨期每股基準與TTM不因此取得認證。新持股／關注股自動背景補收是另一條已記錄但尚未實作、目前暫停的需求。

## 合併驗收

| 項目 | 真實證據與判定 |
|---|---|
| 正式兩年PE／PB | 六股×2共12/12 ready、25月；2026-10-19正式修正版再讀回12/12。5876手機／桌面PE/PB四畫面於2026-10-18 PASS，不外推為六股逐頁矩陣 |
| Readiness Ledger | Admin `data_readiness_ledger` key、值及獨立重算PASS；[#39121917976](https://github.com/tommylin15/janus-omniforge/actions/runs/39121917976)，狀態`PRICE_AND_FOCUS_READY_ONLY`，不是全資料無缺口 |
| 市場覆蓋／營收／持股歷史 | 全市場20/21日、13月營收與指定8檔120日沿既有Core證據；六股135日、二檔債券ETF125日，ETF不進股票市場分母。詳細原證據見下方歷史範圍連結 |
| Market Volume | 四slices既有PASS，本次沒有重送；market-volume、market-activity與指數不混用 |
| 六股2025Q4 EPS | Yahoo直接補收，Stage→Core→serving六股全部成功；正式／Preview API各6/6讀回；5876桌面1440×1000、手機390×844實際圖表與2025Q4明細PASS |

六股2026Q1／Q2先前已PASS；2025Q4這次採供應者明示單季值，不用累計差分，不要求重建官方股數分母。長期第三方直接補收核准見[PROJECT_RULES §1.7](../PROJECT_RULES.md)。

## EPS 真實補收與讀回

[補收 #39205780588](https://github.com/tommylin15/janus-omniforge/actions/runs/39205780588) SUCCESS，execution `janus-ingestion-core-8lj4b`，receipt `status=PASS`、`owner_mutation=false`；每股inserted=1、published=1。Stage保留原頁／hash／實際取得時間，Core保留來源與provenance，API日期皆2025-12-31，source_id皆`yahoo-finance`。

| 股號 | EPS（元／股） | 各次Core提交snapshot |
|---|---:|---|
| 1513 | 2.08 | 8033705836514087391 |
| 2327 | 3.29 | 6394577521718913864 |
| 2382 | 5.76 | 1830941233246179401 |
| 3231 | 2.69 | 5965813818332916637 |
| 3711 | 3.39 | 670336218476474700 |
| 5876 | 0.50 | 896803124588164820 |

Snapshot為當次提交證據；依current-only retention政策不保證舊snapshot長期可重播。2327等每股基準依Yahoo供應者口徑，未知基準不認證歷史TTM或跨期可比。

正式API驗收`/api/v1/public/stocks/{symbol}/visual-series?metric=eps&limit=20`：六股2025-12-31點的值、日期、來源與非空provenance全部符合；`calculation_version=eps-provider-reported-single-quarter-v3`。既有2026Q1／Q2點仍保留MOPS來源。

實際已登入App：5876 EPS圖顯示3期、2025-12-31～2026-06-30；季度明細顯示`2025 Q4 0.50 元／股`及日期；來源顯示`mops、yahoo-finance`，TTM尚未驗證文字保留。手機無水平overflow。只驗這個代表股的兩尺寸畫面，不宣稱六股真人逐頁矩陣。

## 發布、失敗與修復

- 映像來源完整SHA：`e3e0098399846eb337dd2ed1f8b636240bc88c20`。
- [完整Release #39126918277](https://github.com/tommylin15/janus-omniforge/actions/runs/39126918277)、[0%候選 #39127304288](https://github.com/tommylin15/janus-omniforge/actions/runs/39127304288)、[同源auth #39127497388](https://github.com/tommylin15/janus-omniforge/actions/runs/39127497388)全部SUCCESS。
- [Jobs #39127659349](https://github.com/tommylin15/janus-omniforge/actions/runs/39127659349) PASS、8個不同execution canary；[#39205643115](https://github.com/tommylin15/janus-omniforge/actions/runs/39205643115)再確認現役固定digest及無active executions。
- [Preview #39205683042](https://github.com/tommylin15/janus-omniforge/actions/runs/39205683042) PASS、`janus-api-00558-xon`，鎖已釋放；先前取得lease前失敗未改流量，歷史不改判。
- 首次正式promotion [#39206290652](https://github.com/tommylin15/janus-omniforge/actions/runs/39206290652)在PREFLIGHT拒絕`jobs_snapshot_coverage_incomplete`，`gcp_traffic_write=false`。既有rollout已支援研究Job退役，promotion仍要求5份快照；修正腳本`3cca4709`保留四現役Job必備、禁止未知Job、8次canary、即時Job名單與快照一致、映像／設定與回滾檢查。137項相關回歸與真實收據檢查PASS；只改發布腳本，未重建或替換已驗證映像。
- [正式promotion #39206641641](https://github.com/tommylin15/janus-omniforge/actions/runs/39206641641) PASS，正式`janus-api-00558-xon`唯一100%；新版→前版`janus-api-00553-col`→新版的回滾演練PASS，保留tags與前版。流量前現役Jobs／Scheduler ENABLED fence通過，最後部署lease安全釋放。
- API固定image：`ghcr.io/tommylin15/janus-api@sha256:5cf4121aabb60e8196f1542674ad2ac48264fc403210051fe2e98a2fa4e75365`；ingestion/controller：`ghcr.io/tommylin15/janus-ingestion-core@sha256:59fbf1b58196df048f90e63fb78f761787095ce8ab16555931a3ca84c1287506`。

首次Yahoo HTML被Stage MOPS-only guard拒絕的失敗與34項Stage回歸見[停止checkpoint](drl01-yahoo-stage-checkpoint-2026-10-18.md)；原先MOPS12份報表0/6可重建不是第三方無資料的證據。

## 證據保存與邊界

正式／Preview API、Core收據與兩張真實畫面存本機忽略目錄`.tmp/drl01-yahoo/`；`ui-final/desktop-eps.jpg`與`mobile-eps.jpg`已實際檢視。原始頁面、私人畫面不推GitHub。GitHub Actions保存受控發布與補收收據。

本輪沒有Owner交易寫入、新付費來源、額外Scheduler／常駐worker或模型呼叫。全市場EPS、所有歷史PIT、TTM、即時新增持股／關注股補收、自然daily／weekly收據均未假稱完成。DRL-01歷史範圍／已取代gate保留於[前次停止checkpoint](drl01-yahoo-stage-checkpoint-2026-10-18.md)及[2026-10-18 readback](drl01-pre-readback-2026-10-18.md)，不再保留於active TODO。


## 2026-10-18 歷史證據摘要（原判定保留，不是目前狀態）

### 2026-10-18｜DRL-01 Yahoo Stage修復／停止checkpoint（PARTIAL）

第三方直接補收已由[正式規則§1.7](../PROJECT_RULES.md)核准。六股2025Q4 Yahoo數值已取得，但首次真實執行`janus-ingestion-core-6fc7l`在Stage舊MOPS-only HTML guard失敗，0項發布；不是來源資料不存在。修正來源`e3e0098399846eb337dd2ed1f8b636240bc88c20`、34項Stage／EPS回歸PASS；[完整Release #39126918277](https://github.com/tommylin15/janus-omniforge/actions/runs/39126918277)、[0%候選 #39127304288](https://github.com/tommylin15/janus-omniforge/actions/runs/39127304288)、[自動auth #39127497388](https://github.com/tommylin15/janus-omniforge/actions/runs/39127497388)均SUCCESS。Preview更新在取得lease前BLOCKED且未變更；Jobs更新已送出、最後讀回IN_PROGRESS；精確終態、固定digest與續行入口見[checkpoint](../archive/drl01-yahoo-stage-checkpoint-2026-10-18.md)。

使用者要求更新完停止、先回寫文件與同步GitHub；不再啟動EPS重跑或新功能。自然daily／weekly Ledger改列後續觀察，NOT_VERIFIED不冒充PASS，也不再作本次DRL-01結案gate。剩六股修正版Stage→Core→serving、正式API與畫面讀回；新持股／關注股自動補收另案契約未實作。

### 2026-10-18｜DRL-01 整批續行：Ledger 落地、兩年 API／UI PASS；自然週期及 EPS 歷史仍 PARTIAL

- **授權／範圍**：使用者「一次執行下去」解除 DRL-01 暫停，合併驗收既有尾項。只更新既有 EPS 唯讀請求與證據文件；本輪未改業務程式、部署、Scheduler、Owner 資料或新增來源。先前「API 無 profile／Ledger 無鍵」為歷史結果，見 [舊 checkpoint](../archive/drl01-pre-readback-2026-10-18.md)。
- **可追溯版本**：獨立 continuity [#39121917976](https://github.com/tommylin15/janus-omniforge/actions/runs/39121917976) 與 API [#39121953691](https://github.com/tommylin15/janus-omniforge/actions/runs/39121953691) 均 SUCCESS，workflow source `68b353943b3d7f0aee6c228983c4b9b90cb0364d`。正式與 Preview 的 `/app/build-id.txt` 均為 `b5df7e30bc02676a41d0d3300325b9ca5d6fb553`；這是實際 serving build，不能用 workflow source 或 Jobs `252db8c` 冒充同源。
- **P0-2 Admin Ledger 落地 PASS**：execution `janus-ingestion-core-rpxzr` 經既有 control-plane 讀回 `data_readiness_ledger`，`found=true`、`as_of=2026-10-18`、`checked_at=2026-10-18T10:54:20.309919+00:00`、`status=PRICE_AND_FOCUS_READY_ONLY`。固定快照 ohlcv/focus `9152198946506568330`、benchmark `4002887643851730668`、financials `2963097382187259653`；寫入攔截的獨立重算 `PASS_READ_ONLY`。TWSE 1058/1096（96.53%）、TPEx 767/893（85.89%）符合 20/21 日門檻；13 月營收 1077/1096、864/893 均 PASS，focus 為當次配置的 4/4，不能外推成指定八檔歷史驗收。
- **P0-2 自然週期仍 NOT_VERIFIED**：Controller 最近五天有 5 次 data-supplement succeeded，最近 occurrence 對應 `janus-ingestion-core-bk8xc`；可讀摘要的 `data_readiness_status` 為 null，不能證明新版自然發布。使用者手動 `janus-ingestion-core-szlxm` 成功及上述設定落地不代替自然增量。下一次自然 daily／weekly 需關聯 occurrence、execution、Ledger checked_at、source cursor／snapshot／watermark；尚未取得這組收據，整個 P0-2 不標 CLOSED。
- **P0-1 正式兩年 API PASS（12/12）**：六股 `1513,2327,2382,3231,3711,5876` × `pe,pb` 全部 HTTP200、`data_status=available`、`two_year_profile.status=ready`、`window_years=2`、25 個月。2327 各 480 有效日，其餘各 487；Core valuation snapshot `4660132369949617208`。現有 API 經 publication 單列讀回，無需本輪重新發布。
- **P0-1 真實 UI PASS（限定 5876、PE/PB × 兩尺寸 4/4）**：正式登入後從既有持股進個股，1440×1000 與 390×844 檢視 PE/PB 兩年區間、分位與 25 期月中位數圖；期間 2024-10-16～2026-10-16、來源與非 PIT 提示可見，手機未見橫向溢位。PE 最新 15.34／分位59.2%，PB 最新1.23／分位99.9%；月中位圖與最新日值分開。截圖僅保存本機忽略目錄 `.tmp/drl01-20261018/ui/`，未上傳本人持股資料；未宣稱其餘五股逐頁視覺矩陣或全站 visual convergence PASS。測試後還原 viewport。
- **P0-3 沿用 PASS，不重送補收**：本次僅獨立抽讀 market-volume snapshot `7109808353202011087`，指定樣本 7/8/9/10 月日期22/21/20/11，至10/16；抽樣不是全市場覆蓋率。market-activity 仍是另一 dataset，不據此新增回補 scope 或偽稱完整。
- **P1-4 官方來源核查完成，修復 BLOCKED_SOURCE_EVIDENCE**：請求 commit `0ba6b7a5008226fff0128e77718874efeda4632f`，selective CI [#39122275345](https://github.com/tommylin15/janus-omniforge/actions/runs/39122275345) SUCCESS；官方核查 [#39122275355](https://github.com/tommylin15/janus-omniforge/actions/runs/39122275355) SUCCESS，execution `janus-ingestion-core-v6jdx`，六股 Q3/Q4 共12份 `FETCHED_VALIDATED`、`source_failures=0`，均有 basic EPS／歸母盈餘，但核查的 YTD context 無加權平均股數，`eligible_numerator_denominator=0`、`NO_SAFE_Q4_DENOMINATORS`。這只證明既有 MOPS 入口的核查結果，不宣稱所有官方資料皆不可能取得。Core 2025Q4 合格單季仍0/6；2026Q1/Q2 六股公開 API 仍6/6。不以 EPS 差分、猜股數、填零寫入，未新增財報資料，四季／TTM 維持 NOT_CERTIFIED／WAIVED_FOR_MVP。
- **替代官方入口核對**：另查 [財務比較E點通官方說明 §三.3](https://mopsfin.twse.com.tw/terms)，該站明示第四季單季資料由累計金額相減產生。這不符合本專案「不得以累計EPS差分充數」契約，不能只因網站官方就把該衍生值當作公司直接申報單季EPS；本輪未將其加入來源或寫入資料。
- **整體**：DRL-01 維持 PARTIAL；目前剩自然 daily／weekly publication 證據及可核實的2025Q4單季來源。既有 D01～D05 不重開。收據見上述 Actions artifacts；本輪適用檢查為請求 JSON、probe 編譯、文件連結與 diff review，無業務程式改動，不以舊 CI 冒充新 Release gate。
