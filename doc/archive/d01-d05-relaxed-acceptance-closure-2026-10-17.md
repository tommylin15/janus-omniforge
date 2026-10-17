# D01～D05 結案：使用者核准寬鬆驗收

日期：2026-10-17（Asia/Taipei）。狀態：**D01、D02、D03、D04、D05 全部 PASS／CLOSED（使用者核准範圍）**。

## 結案依據

使用者本次明確指示：「d01-d05請採取寛鬆驗證,能過關就pass ,也不用後面再補做什麼項目」。本決策取代這五包尚未完成的嚴格驗收與後續增補要求；採既有功能、真人正向驗收、CI、正式 dev 發布及本次唯讀觀察結案。未量測或未實作部分屬 **USER_ACCEPTED／WAIVED，不是實測 PASS**，不再形成 TODO、支線或補驗義務。

| 工作包 | 可沿用的真實證據 | 結案 |
|---|---|---|
| D01 | 持股、現金交易連動、重算按鈕 USER_CONFIRMED_PASS；進階場景測試及本次 targeted Python 32 passed；手機持股可讀 ledger v357、2026-10-16 估值 | PASS／CLOSED |
| D02 | [DB-first snapshot #38890365233](https://github.com/tommylin15/janus-omniforge/actions/runs/38890365233)；既有全市場 Bootstrap／cached／coverage；真實手機快照讀回 | PASS／CLOSED |
| D03 | [公開 typed 圖表 #38889906057](https://github.com/tommylin15/janus-omniforge/actions/runs/38889906057)；本次正式 App 390×844 持股、關注、個股價量唯讀觀察 | PASS／CLOSED |
| D04 | [安裝 #38991083134](https://github.com/tommylin15/janus-omniforge/actions/runs/38991083134)、[交接 #38991644822](https://github.com/tommylin15/janus-omniforge/actions/runs/38991644822)；隔離還原、owner boundary、Controller 清理及保留 VM executor timer 的既有證據 | PASS／CLOSED |
| D05 | 來源 `d739107aa26ae4641d6f3e1b9c80f2e9aa1a57b6` 的 Release #38989576990、candidate #38991849862、OAuth #38991975400、Preview、Jobs #38992414928、[API 100% #38996111382](https://github.com/tommylin15/janus-omniforge/actions/runs/38996111382)；本次正式 build-id 讀回一致 | PASS／CLOSED |

## 已接受限制：不補做、不另列待辦

- 不要求額外本人點擊 request ID→Worker terminal→checkpoint 收據、故障注入、交易保存與即時股數成本的額外端到端量測；既有真人 PASS 與安全／冪等測試保留。
- 不要求登入後各情境30筆、冷暖 P95、試算500ms／保存2秒的完整性能認證。本次持股刷新只觀察到6個暖樣本（845、1378、973、777、1251、943ms）及一次初始2070ms；不足以宣稱正式 P95 PASS。721ms 為今日 core 單次值。量測工具另有一次額外 UI locator 等待失敗，不冒充 API failure 或消除其紀錄。
- 不要求桌面四頁、完整手機截圖矩陣、200%文字、鍵盤／讀屏與全部 loading／gap／stale／partial 特殊場景的完整現場認證。已有 widget 回歸與本次手機觀察照其 scope 保留，不宣稱完整 Final Visual Convergence 實測認證。
- 個股有效價格仍可能伴隨研究區的「尚未就緒」或缺估值日期提示；價格圖首請求曾不可用、重試後可讀。接受此版本既有呈現／有界重試；不新增修正待辦。此次試作的顯示修正已撤回，沒有未發布程式被算入交付。
- 原 D03 首頁資產摘要／事實異動、個股三行事實／單一主圖／支持疑點等尚未交付增補，不再作這五包或後續補做義務。既有 DRL-01 自己的資料／消費端驗收範圍另依原 TODO，不把這些取消項目暗中轉入 DRL-01。
- 不要求新增日期 EOD／PIT、全市場入口與逐資料集的重複驗收；不更改資料的實際日期、缺值、source／PIT／owner／金額規則，不偽造缺少證據。

本次只有文件結案，沒有新增交易、重算、migration、部署、切流、權限、付費資源或 runtime guard 變更。DRL-01、D06～D08 的既有工作不因本次放寬而關閉或擴大。

本次 targeted Flutter 40 passed 包含一項後來撤回的顯示修正測試，僅作過程證據，不當作正式部署版的同 SHA 完整 Release。

## 結案前原始清單（歷史快照，不是待辦）

以下未勾選符號只保存結案前狀態；全部依上方決策完成接受或豁免，不得重新啟動。

## D01｜持股交易與正式損益

- [x] **P0 Owner 2026-10-14 backend 全持股估值／總未實現損益**：TPEx dailyQuotes、migration 061、SHA 285848 Release／API 0%／OAuth／四 Jobs rollout PASS；00697B + 00719B 同日官方資料已持久化。MCP readonly 8/8 市價、市值可用，Private Mart readonly #38732675488 驗 8/8 未實現 PnL、單一總計 aggregate_status=available、missing=0、affected=0、總市值／總 PnL／報酬非空，ledger v354 未變；最終 gate #38733406224 PASS。原 #38730741579 FAILED 是舊 schema 缺 `stale_price_count` 使驗收腳本誤判，修正後不再次重算、不編造欄位。後續新日期、UI、交易按鈕／queue、正式 App 屬 P1。
- [x] **現金交易連動真人正向驗收**：使用者 2026-10-16 回報「現金交易連動驗收完成」，記為 `USER_CONFIRMED_PASS`（8eb 正式 dev）。owner-scoped cash／migration 062 工程與正式部署原證據維持；本次沒有測試新增交易，也沒有新的逐筆資料或金額收據。
- [x] **現金進階一致性／失敗場景**：D01 進階場景測試 25 tests 全部 PASS（local 2026-10-17）。包含股利處理（4 tests）、REVERSAL（4 tests）、更正交易（4 tests）、競態/冪等（4 tests）、Owner 隔離（4 tests）、邊界案例（5 tests）。工程入口：`services/api/trade_calculation.py`、`services/api/trade_fees.py`、`services/api/private_recalc_queue.py`、`tests/test_d01_advanced_scenarios.py`。
- [x] backend 唯讀試算及正式保存共用 MOVING_AVERAGE／Decimal／商品費稅，券商折扣與規則快照可追溯；表單自動費稅／一字搜尋及ETF／Enter／競態拒絕均有新版驗收。
- [x] 買入、加減碼、部分／全部賣出、零股、股利、更正、作廢、歷史補登、超額賣出拒絕、未知保存結果與冪等；不同 owner／ledger／broker version 不混用。既有費稅 apply 不重送。
- [x] **重新計算損益按鈕真人正向驗收**：使用者 2026-10-16 已明確回報驗收完成（`USER_CONFIRMED_PASS`）。後端雙 Worker 佇列 #38828798196 的 synthetic 技術驗收另有 PASS；不聲稱這次回報附有 enqueue／Worker terminal／checkpoint 的新 run ID。
- [ ] **重算操作稽核與異常路徑（獨立）**：如後續需要，補齊本人實際點擊 request ID→Worker terminal→同 ledger checkpoint／UI PnL 的可查收據，以及失敗／重送／timeout 狀態及冷暖等待時間；沒有資料就維持 NOT_VERIFIED，不重跑真人正向驗收。
- [ ] operational股數／成本／該筆損益可即時呈現；行情更新、帳本保存、正式報表重算互不阻塞。首次完整估值不以市場10%／30%容忍代替。

## D02｜全市場、快照與效能

**AI入口：**[D02卡](../execution-cards/d02-full-market-snapshot-performance.md)／[總指令路由](../codex-execution-plan.md)。首頁增補沿此工項共用snapshot，版型見[A第5節](../ui/visual-first-four-pages.md)。

- [ ] 完成全市場跨搜尋／關注／screening／研究入口的剩餘驗收；固定官方當日分母、TWSE≤10%／TPEx≤30%逐資料集判定；舊500 artifacts不重標全市場。
- [ ] 首頁快照批次caller、migration057初始補建、serializer、freshness／版本與持股DB-first snapshot真實readback；無N+1／首屏Iceberg掃描。
- [ ] 暖首屏P95≤2秒、冷主資訊P95≤5秒、暖試算≤500ms、保存至新版股數／成本可見≤2秒；每暖情境≥30樣本，冷樣本不足明示，timeout計入失敗。端到端與API分開。
  - 最新 9f690 固定 Preview 公開 market-home 暖路徑 #38853879877：30/30、P50 48.11ms、P95 57.70ms，**只算 public API 子項 PASS**；authenticated holdings snapshot／recalc／手機視覺效能仍未驗，不得外推。


## D03｜四頁與通用圖表

**AI入口：**[D03卡](../execution-cards/d03-four-page-charts-visual.md) → [A具體版面第5節](../ui/visual-first-four-pages.md) → [B三層交付](../ui/visual-first-delivery.md)。不得只讀工項名稱自由設計。

- [ ] **D03後續增補（等DRL-01恢復，不擴當前D05 gate）**：首頁資產短摘要／三則事實異動／TAIEX；個股三行事實→對應圖表、單一主圖、支持疑點、既有筆記延續。沿VF-02/05/06/07與D02，不新建工作包；手機／桌面位置、尺寸、字級、按鈕與狀態依A第5節，資料依DRL-01，模型依D07。已存在部分只補差距。

- [ ] VF-00～01：source→Core→serving→API→UI coverage matrix，財報期別／available-at、事件時間、typed owner read path。
- [ ] VF-02～06：今日個人相關異動／TAIEX fallback、關注價格與異動、持股單一市值Hero及同時點貢獻、個股短價量與圖表捷徑；模型未驗證不占主畫面。
- [ ] VF-07～08：官方營收／單季EPS／PE-PB／法人／事件及可比Private Mart歷史趨勢；六類資料逐類驗收，不以全missing或假線結案。
- [ ] 390×844與desktop authenticated截圖、文字放大／鍵盤／讀屏、loading／empty／gap／stale／partial、當日行情與累計損益分列；新語意見系統補強契約。

VF-10高階同業／估值河流／還原價仍屬有條件後續構想，不是本次產品必過gate。

## D04｜總控與備份

- [x] Cloud Scheduler總控唯一業務排程；Actions只保留既有備份清理schedule。研究前瞻留存、dirty owner、snapshot／dispatch lag／重試冪等真實驗收。
- [x] D04：備份清理已從 GitHub Actions 移至 Batch Controller（`ledger_backup.py` cleanup_old_backups()），保留政策 7 天（至少保留 3 個）。GitHub Actions `private-ledger-backup-retention.yml` 已停用排程。VM timer `janus-ledger-backup-executor.timer` 已恢復啟用（ENABLED）。新增 4 個清理邏輯單元測試。

## D05｜整合發布

- [x] **P1 8eb API 正式可逆 100% 切流及獨立讀回**：同源完整 Release #38856837257、0% #38857279864、auto OAuth #38857441171、Preview #38857524000、四 Jobs #38857643226 PASS；[正式可逆 promotion #38865075071](https://github.com/tommylin15/janus-omniforge/actions/runs/38865075071) PASS、[獨立 live readback #38865347217](https://github.com/tommylin15/janus-omniforge/actions/runs/38865347217) PASS；唯一 canonical 100% revision `janus-api-00517-ciq`、完整 build SHA、Preview、健康及負向 Owner/cash auth、immutable image/tags 全部確認，9f690 revision `janus-api-00512-zal` 保留回滾。此項僅 API 發布驗收，不表示使用者功能 E2E PASS。
- [x] **真人持股畫面正向驗收**：使用者 2026-10-16 明確回報「真人持股畫面驗收完成」，以 `USER_CONFIRMED_PASS` 接受新版持股畫面的基本真人操作流程；與 8eb 發布 #38865075071、獨立 runtime #38865347217 的技術驗收分開存證。
- [ ] **持股視覺特殊場景與效能（獨立）**：真缺價小計／涵蓋檔數、延遲與跨日參考市值、手機 390px／桌面 authenticated 截圖、文字可及性及 P95 均需其各自受控證據；使用者人工正向確認不等於這些量測完成。舊截圖推算 TWD 15,210,800、約 1,702.2 萬元屬歷史估算，不是現時合格值。
- [ ] **P1 尚需的獨立工程驗收**：新版 8eb 已在正式 App 100% 發布並獨立讀回 PASS；使用者 2026-10-16 確認持股畫面、現金交易連動、重算按鈕三項真人正向 **USER_CONFIRMED_PASS**，不再重列未操作。餘下只保留確有要求的特殊缺價／stale／partial 呈現、trade/owner/refund/reversal 安全與冪等、回溯到 ledger／Worker terminal 的機器可稽核證據、390px/desktop 截圖與冷暖 P95、10/16 夜批 Private Mart 最新 EOD／PIT readback；缺證據維持各自 PARTIAL／NOT_VERIFIED，**不得反向推翻已完成的基本人工驗收**。
- [ ] 無需每版人工OAuth登入；自動auth與owner隔離仍驗。metadata／401不代表正向PnL或UI PASS。不要以舊來源的API／Jobs證據交叉替代。

