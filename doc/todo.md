# Janus — 唯一開發待辦

更新：2026-10-15。只保存尚未完成的交付／驗收；方法見 [AI 指示](codex-execution-plan.md)，證據見 [status](status.md)。

## 執行範圍

**2026-10-15 本輪：P0（00697B／00719B 官方 as-of 10/14 Owner backend）已取得 real Mart 8/8 全部估值／聚合 PnL PASS；P1（正式 App 顯示、Owner 互動／重算、Preview 同版與流量驗收）仍 OPEN；D04（VM IAM／備份交接）仍 BLOCKED。** 本次只執行 P0 救援，D06 FinOps／後置 B9 不重新啟動；正式 100% traffic 未切，不能說整體產品完成。

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
- [ ] backend 唯讀試算及正式保存共用 MOVING_AVERAGE／Decimal／商品費稅，券商折扣與規則快照可追溯；表單自動費稅／一字搜尋及ETF／Enter／競態拒絕均有新版驗收。
- [ ] 買入、加減碼、部分／全部賣出、零股、股利、更正、作廢、歷史補登、超額賣出拒絕、未知保存結果與冪等；不同 owner／ledger／broker version 不混用。既有費稅 apply 不重送。
- [ ] 重算按鈕→authenticated API enqueue→Private Worker→terminal／exact ledger checkpoint→PnL／queue idle／cleanup讀回；有界輪詢及失敗重試。不向本人帳本新增測試交易。
- [ ] operational股數／成本／該筆損益可即時呈現；行情更新、帳本保存、正式報表重算互不阻塞。首次完整估值不以市場10%／30%容忍代替。

## D02｜全市場、快照與效能

- [ ] 完成全市場跨搜尋／關注／screening／研究入口的剩餘驗收；固定官方當日分母、TWSE≤10%／TPEx≤30%逐資料集判定；舊500 artifacts不重標全市場。
- [ ] 首頁快照批次caller、migration057初始補建、serializer、freshness／版本與持股DB-first snapshot真實readback；無N+1／首屏Iceberg掃描。
- [ ] 暖首屏P95≤2秒、冷主資訊P95≤5秒、暖試算≤500ms、保存至新版股數／成本可見≤2秒；每暖情境≥30樣本，冷樣本不足明示，timeout計入失敗。端到端與API分開。

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

- [ ] P1：P0 backend 10/14 real Mart aggregate PASS **不代表**正式 App／重算 E2E、當日來源時效 PASS；API 0% 與四 Jobs 已同 SHA 285848。固定 Preview 285848 更新請求 [commit 78bf14bb](https://github.com/tommylin15/janus-omniforge/commit/78bf14bb1665be93ef6f7048d71458632bdbc871) + [實際工作流 #38740477232](https://github.com/tommylin15/janus-omniforge/actions/runs/38740477232) **SUCCESS（tag 更新與 build/lease 驗證步驟 PASS）**，正式 100% 未切。Owner MCP 正向唯讀 8/8 positions／年度已實現損益已證 10/14、ledger v354；10/15 22:21 MCP 重讀仍為 10/14 估值日；live [#38752934496](https://github.com/tommylin15/janus-omniforge/actions/runs/38752934496) 證實 Preview build-id 285848、四 Job Ready、Controller active，21:30／22:30 controller tick SUCCESS，但 21:30 後沒有新的 Private Pipeline execution，須再查 `control.batch_occurrences` 中 private 的 dependency／status 及確切未派送原因，不等於 10/15 新批次、正式 UI 或重新計算按鈕端到端。仍須 authenticated Owner UI/API、最新估值日、重算請求→terminal→PnL、固定 Preview UI/效能、SHA/rollback 與 100% 切流讀回。
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
