# Janus — 唯一開發待辦

更新：2026-10-16。只保存尚未完成的交付與驗收；真實終態證據見 [status](status.md) 與 [operations](spec/operations-and-testing.md)。

## 執行範圍

**2026-10-16 本次授權的新版 API 正式 100% 切流已完成；其他 P1 工作沒有自動恢復**。P1 總額優先 `8eb42dcb` 的完整 GHCR Release #38856837257、0% candidate #38857279864、自動 OAuth #38857441171、固定 Preview #38857524000、四 Jobs 真實 rollout #38857643226 均 PASS；新版 8eb API 可逆 100% promotion #38865075071 與獨立 live 100% readback #38865347217 均 **PASS**（正式 revision `janus-api-00517-ciq`；回滾基準 `janus-api-00512-zal`）；不以 CI／部署取代真人操作驗收。Owner 10/15 backend 估值與雙 Worker queue PASS，但新版真人持股頁、現金交易連動、按鈕重算 E2E 仍 PARTIAL；D04 VM IAM／備份交接 BLOCKED。** 本次僅核准 8eb API 切流；其餘工作等下一次明確接續指示。

A 組及 B0～B8 已結案的範圍不重開；有實質變更才回歸受影響路徑。全市場 Bootstrap／同日 Cached、費稅88筆更正、00719B 身分／估值既有成功證據不重送。研究範圍採各歷史日期全上市櫃；50 關注 quota 仍保留。

以下 `D01～D08` 是本次文件工作包代碼，不取代既有 WBS ID。新增設計補強見 [契約](spec/system-development-contract.md)，不是已實作聲明。

D01～D08 各有一張獨立可供 AI 執行的 [標準任務卡](execution-cards/README.md)；操作程序不代替本 TODO 唯一狀態與當次授權。

| 工作包 | 狀態／次序 | 既有 WBS 責任 | 依賴與退出條件 |
|---|---|---|---|
| [D01 持股交易／完整估值](execution-cards/d01-holdings-trading-valuation.md) | PARTIAL；產品第1項 | WBS 4J／6 | 新版正式商品報價、共用費稅與試算、交易版本／冪等、完整估值及 Owner 重算 E2E |
| [D02 快照／首屏](execution-cards/d02-full-market-snapshot-performance.md) | PARTIAL；產品第2項 | WBS 3／6 | D01資料契約；首頁與持股 snapshot 真實生成／readback、冷暖效能 |
| [D03 圖表／四頁](execution-cards/d03-four-page-charts-visual.md) | PARTIAL；產品第3項 | WBS-6-USER-FINAL-VISUAL-CONVERGENCE 非 AI 範圍 | D01／D02；VF-00～08、真實資料／四頁截圖、可及性 |
| [D04 總控／備份交接](execution-cards/d04-controller-backup-handoff.md) | BLOCKED_VM_IAM；可整合前3項 | WBS 3／7 | 無重複排程、同源總控；新備份與隔離還原後才停舊 timer |
| [D05 產品集中發布](execution-cards/d05-integrated-release-dev.md) | PARTIAL；第5項 | WBS 8／CI-CD | D01～04適用條件通過；完整SHA release、candidate、自動auth、Jobs fence、Preview、功能證據、正式dev切流讀回 |
| [D06 Iceberg／I/O](execution-cards/d06-iceberg-retention-io.md) | PARTIAL；獨立已授權 | WBS 7／retention | 既有 Jobs／cleanup 終態、完整引用保護、真實 objects／bytes／等量 I/O 驗收 |
| [D07 五角色資料與品質](execution-cards/d07-specialist-b9-oos.md) | 後置；產品交付後 | WBS-5-MART-SPECIALIST-ENGINES／RERUN-CACHE（B9） | 全市場歷史母體、逐角色 baseline／OOS；B7 PASS 不代替B9 |
| [D08 CEO／Admin／報告](execution-cards/d08-ceo-admin-owner-report.md) | 後置；有效角色後 | WBS-5-MART-AI-PROVIDERS／CIO-SYNTHESIS、WBS-6-ADMIN-ANALYSIS-PROFILE、User AI整合 | P0-V技術已PASS；真實 Fact Pack／capability／immutable report／Owner history另驗 |

## D01｜持股交易與正式損益

- [x] **P0 Owner 2026-10-14 backend 全持股估值／總未實現損益**：TPEx dailyQuotes、migration 061、SHA 285848 Release／API 0%／OAuth／四 Jobs rollout PASS；00697B + 00719B 同日官方資料已持久化。MCP readonly 8/8 市價、市值可用，Private Mart readonly #38732675488 驗 8/8 未實現 PnL、單一總計 aggregate_status=available、missing=0、affected=0、總市值／總 PnL／報酬非空，ledger v354 未變；最終 gate #38733406224 PASS。原 #38730741579 FAILED 是舊 schema 缺 `stale_price_count` 使驗收腳本誤判，修正後不再次重算、不編造欄位。後續新日期、UI、交易按鈕／queue、正式 App 屬 P1。
- [ ] **現金池 Owner 正向驗收**：新 owner-scoped cash checkpoint API／migration 062 與 1～2 行持股列表已在 `9f690363` 發布，#38841287256、#38841326765、#38849686748、#38851753247、#38853614819 PASS。仍缺 authenticated「我的 → 現金部位」設定→精確 readback→交易 BUY／SELL／股利／REVERSAL 後現金變化、同 owner ledger checkpoint 與總資產非重複計入的真人 E2E；沒有初始現金不可顯示假總資產。不得新增測試真實交易或代替使用者設定現金。
- [ ] backend 唯讀試算及正式保存共用 MOVING_AVERAGE／Decimal／商品費稅，券商折扣與規則快照可追溯；表單自動費稅／一字搜尋及ETF／Enter／競態拒絕均有新版驗收。
- [ ] 買入、加減碼、部分／全部賣出、零股、股利、更正、作廢、歷史補登、超額賣出拒絕、未知保存結果與冪等；不同 owner／ledger／broker version 不混用。既有費稅 apply 不重送。
- [ ] **重算功能使用者 E2E**：後端真實雙 Worker 佇列 seed／worker／verify／cleanup #38828798196 PASS；仍需登入正式 App，按「重新計算損益」→ authenticated enqueue → SUCCEEDED／同 ledger checkpoint → UI PnL 更新與 idle，並驗證失敗／重試視覺。不得向真實帳本新增測試交易或將 canary 冒充按鈕 PASS。
- [ ] operational股數／成本／該筆損益可即時呈現；行情更新、帳本保存、正式報表重算互不阻塞。首次完整估值不以市場10%／30%容忍代替。

## D02｜全市場、快照與效能

- [ ] 完成全市場跨搜尋／關注／screening／研究入口的剩餘驗收；固定官方當日分母、TWSE≤10%／TPEx≤30%逐資料集判定；舊500 artifacts不重標全市場。
- [ ] 首頁快照批次caller、migration057初始補建、serializer、freshness／版本與持股DB-first snapshot真實readback；無N+1／首屏Iceberg掃描。
- [ ] 暖首屏P95≤2秒、冷主資訊P95≤5秒、暖試算≤500ms、保存至新版股數／成本可見≤2秒；每暖情境≥30樣本，冷樣本不足明示，timeout計入失敗。端到端與API分開。
  - 最新 9f690 固定 Preview 公開 market-home 暖路徑 #38853879877：30/30、P50 48.11ms、P95 57.70ms，**只算 public API 子項 PASS**；authenticated holdings snapshot／recalc／手機視覺效能仍未驗，不得外推。


## D03｜四頁與通用圖表

- [ ] VF-00～01：source→Core→serving→API→UI coverage matrix，財報期別／available-at、事件時間、typed owner read path。
- [ ] VF-02～06：今日個人相關異動／TAIEX fallback、關注價格與異動、持股單一市值Hero及同時點貢獻、個股短價量與圖表捷徑；模型未驗證不占主畫面。
- [ ] VF-07～08：官方營收／單季EPS／PE-PB／法人／事件及可比Private Mart歷史趨勢；六類資料逐類驗收，不以全missing或假線結案。
- [ ] 390×844與desktop authenticated截圖、文字放大／鍵盤／讀屏、loading／empty／gap／stale／partial、當日行情與累計損益分列；新語意見系統補強契約。

VF-10高階同業／估值河流／還原價仍屬有條件後續構想，不是本次產品必過gate。

## D04｜總控與備份

- [ ] Cloud Scheduler總控唯一業務排程；Actions只保留既有備份清理schedule。研究前瞻留存、dirty owner、snapshot／dispatch lag／重試冪等真實驗收。
- [ ] D04：GitHub Actions → WIF #38710741325 已唯讀確認 Scheduler ENABLED、GCS daily 3 份（最新 10/14）。既有 VM `compute.instances.get` DENIED_OR_UNAVAILABLE；只有在合法現有 VM access 或使用者額外核准最小 IAM 後，才可進行 executor install→controller 備份→isolated restore→讀回→交接／停舊 timer；不得因存在 3 份備份稱 restore PASS。

## D05｜整合發布

- [x] **P1 8eb API 正式可逆 100% 切流及獨立讀回**：同源完整 Release #38856837257、0% #38857279864、auto OAuth #38857441171、Preview #38857524000、四 Jobs #38857643226 PASS；[正式可逆 promotion #38865075071](https://github.com/tommylin15/janus-omniforge/actions/runs/38865075071) PASS、[獨立 live readback #38865347217](https://github.com/tommylin15/janus-omniforge/actions/runs/38865347217) PASS；唯一 canonical 100% revision `janus-api-00517-ciq`、完整 build SHA、Preview、健康及負向 Owner/cash auth、immutable image/tags 全部確認，9f690 revision `janus-api-00512-zal` 保留回滾。此項僅 API 發布驗收，不表示使用者功能 E2E PASS。
- [ ] **真實持股操作與參考總額主卡驗收**：驗持股 7 檔個股價格／成本／損益和延遲提示、完整參考總市值、真缺價小計與 `已計價檔數／全部檔數`、現金＋已計價部分，確認無錯誤長句遮擋表頭。帳本、現金修改、重算按鈕的真人正向 E2E 及 390px／桌面截圖、冷暖 P95 另行驗證；不得以 GHCR／Preview／Jobs PASS 當作真實操作 PASS。截圖試算 TWD 15,210,800 持股與約 1,702.2 萬參考資產僅是當時畫面推估，非官方現時數字。
- [ ] **P1 剩餘：8eb 正式 App 真人操作與視覺 E2E**。**8eb 正式 API 100% 切流 #38865075071 和獨立讀回 #38865347217 已 PASS，以下沿革為之前已驗證基礎，不是新的阻塞。** 前版 7acff 的 10/15 Owner Mart／雙 Worker queue backend PASS、正式 100% rollback/readback 均保留；新版 9f690 DB 062 #38841287256、full Release #38841326765、API candidate #38849023963、auto OAuth #38849298689、四 Jobs #38849686748、fixed Preview #38849422216、受控正式 API promotion #38851753247 及獨立 100% immutable SHA/build-id/auth 401 #38853614819 均 PASS。初次 promo #38851511933因 template test FAIL 在 GCP 修改前停下，修正後 retry 成功；舊 7acff rollback baseline 保留。最新 Owner private MCP operational ledger v357／7 active positions、報價/估值仍 10/15，屬 10/16 交易後但尚未完成當日正式 EOD。**仍缺** authenticated cash-set／交易後 cash 差額與總資產、持股 1～2 行圖卡、實際重算按鈕→Owner queue terminal→UI PnL、交易保存及 390px/desktop screenshot／持股冷暖 P95。10/16 自動夜間 Private Mart 必須另觀察，不以一次補算或公開效能冒充。
- [ ] 無需每版人工OAuth登入；自動auth與owner隔離仍驗。metadata／401不代表正向PnL或UI PASS。不要以舊來源的API／Jobs證據交叉替代。

## D06｜Iceberg、引用及I/O

- [ ] 讀回 #38686125420／#38686337134 的真實終態、四Jobs digest及Scheduler；unknown不重送、不把container成功當清理成功。
- [ ] 完整核對Core／Mart／Research／private／PG publication引用及19份oversized內容；缺資料fail closed。90天以上manifest當時為0，不能為追求刪除量降低門檻。
- [ ] compact dry-run／compact／snapshot expiry／orphan cleanup分開記錄；保存protected refs、generation、刪除清單與bytes。audit-only不代表一般retention解封。
- [ ] 同等工作量、同長度時間窗比較ReadObject／GetObjectMetadata、objects／bytes／RSS／耗時；控制一次性compact干擾。未量測不報節省百分比；夜批依既有總控及引用fence。

## D07｜五角色及模型品質

- [ ] 前瞻留存membership／公告版本／publication／first-observed；全市場歷史研究保留退出股票，不用今天名冊回填。無法重建區間標blocked_source_history。
- [ ] VF-09角色狀態視覺化、五角色structured artifacts／繁中規則說明、missing／provenance／隔離、dirty/reuse與真實artifact/API讀回；正常0 LLM token。可靠baseline與ML品質分開。
- [ ] Quant→Risk優先；基本面／估值先修資料，Event先合法training-use及真實人審標籤。預登記時間切分、成熟標籤／purge、baseline、成本情境、主要指標與不確定性；逐角色升級，無優勢維持baseline。
- [ ] 明確分離財報strict_pit=false研究比較與嚴格PIT publication；核對舊B9診斷硬編碼blockers，不能刪掉guard或把歷史診斷當永久無法研究。
- [ ] 月度成熟資料skip/reuse、model/evaluation版本／回復／漂移；specialist變更只標CEO stale，不自動呼叫LLM。

## D08｜CEO及分析產品

- [ ] 接續既有OmniGatewayGeminiProvider與已通過P0-V技術鏈，不重建串接；部署前核對Janus實際endpoint／audience／allowlisted model。上游專案成功不代表Janus已切正式route。
- [ ] Admin模型／profile／evaluation／immutable history／rollback／capability、provider health／quota／cooldown／usage及安全audit；核對052與每日50／300秒實際readback。
- [ ] 真實有效五角色Fact Pack→新手動request→Gateway→Gemini→完整validator→immutable GCS／PG→authenticated Owner history；timeout／cancel／未知終態不得盲重送或擅自fallback。
- [ ] CEO只解釋validated numbers，無canonical／publication決策權；thesis／衝突／情境／失效條件／unknowns有來源。User顯示freshness、歷史及permission-aware操作，五角色有效後才整合報告。

## 完成與歷史

每項交付列implementation、tests／CI、deployment、migration、workload／business readback及剩餘gap。沒有適用證據維持PARTIAL／NOT VERIFIED。
原重複工作、舊授權及收據完整保存於 [整編前TODO](archive/documentation-baseline-2026-10-15-todo.md)；歷史不再形成另一份執行佇列。未排程構想統一見 [Parking Lot](parking-lot.md)。
