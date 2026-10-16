# Janus — 唯一開發待辦

更新：2026-10-16。只保存尚未完成的交付與驗收；真實終態證據見 [status](status.md) 與 [operations](spec/operations-and-testing.md)。

## 執行範圍

**2026-10-16 本次授權的新版 API 正式 100% 切流已完成；其他 P1 工作沒有自動恢復**。P1 總額優先 `8eb42dcb` 的完整 GHCR Release #38856837257、0% candidate #38857279864、自動 OAuth #38857441171、固定 Preview #38857524000、四 Jobs 真實 rollout #38857643226 均 PASS；新版 8eb API 可逆 100% promotion #38865075071 與獨立 live 100% readback #38865347217 均 **PASS**（正式 revision `janus-api-00517-ciq`；回滾基準 `janus-api-00512-zal`）；不以 CI／部署取代真人操作驗收。Owner 10/15 backend 估值及雙 Worker queue PASS；**2026-10-16 使用者確認新版持股畫面、現金買賣交易連動、重算按鈕三項人工正向驗收均完成（USER_CONFIRMED_PASS）**，不再以「真人尚未操作」列為阻塞。剩餘異常場景、可追溯 runtime 細節與效能仍分別驗收；D04 VM IAM／備份交接 BLOCKED。** 本輪只回寫驗收，不自行啟動新部署／重算。

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
- [x] **現金交易連動真人正向驗收**：使用者 2026-10-16 回報「現金交易連動驗收完成」，記為 `USER_CONFIRMED_PASS`（8eb 正式 dev）。owner-scoped cash／migration 062 工程與正式部署原證據維持；本次沒有測試新增交易，也沒有新的逐筆資料或金額收據。
- [ ] **現金進階一致性／失敗場景（獨立工程 gate）**：若仍列在 D01 acceptance，需提供股利、REVERSAL、更正、不同 Owner、idempotency／版本競態與 ledger checkpoint 的可稽核讀回；不因一般買賣現金連動人工 PASS 自動推定全部邊界 PASS。未配置初始現金不得製造總資產。
- [ ] backend 唯讀試算及正式保存共用 MOVING_AVERAGE／Decimal／商品費稅，券商折扣與規則快照可追溯；表單自動費稅／一字搜尋及ETF／Enter／競態拒絕均有新版驗收。
- [ ] 買入、加減碼、部分／全部賣出、零股、股利、更正、作廢、歷史補登、超額賣出拒絕、未知保存結果與冪等；不同 owner／ledger／broker version 不混用。既有費稅 apply 不重送。
- [x] **重新計算損益按鈕真人正向驗收**：使用者 2026-10-16 已明確回報驗收完成（`USER_CONFIRMED_PASS`）。後端雙 Worker 佇列 #38828798196 的 synthetic 技術驗收另有 PASS；不聲稱這次回報附有 enqueue／Worker terminal／checkpoint 的新 run ID。
- [ ] **重算操作稽核與異常路徑（獨立）**：如後續需要，補齊本人實際點擊 request ID→Worker terminal→同 ledger checkpoint／UI PnL 的可查收據，以及失敗／重送／timeout 狀態及冷暖等待時間；沒有資料就維持 NOT_VERIFIED，不重跑真人正向驗收。
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
- [x] **真人持股畫面正向驗收**：使用者 2026-10-16 明確回報「真人持股畫面驗收完成」，以 `USER_CONFIRMED_PASS` 接受新版持股畫面的基本真人操作流程；與 8eb 發布 #38865075071、獨立 runtime #38865347217 的技術驗收分開存證。
- [ ] **持股視覺特殊場景與效能（獨立）**：真缺價小計／涵蓋檔數、延遲與跨日參考市值、手機 390px／桌面 authenticated 截圖、文字可及性及 P95 均需其各自受控證據；使用者人工正向確認不等於這些量測完成。舊截圖推算 TWD 15,210,800、約 1,702.2 萬元屬歷史估算，不是現時合格值。
- [ ] **P1 尚需的獨立工程驗收**：新版 8eb 已在正式 App 100% 發布並獨立讀回 PASS；使用者 2026-10-16 確認持股畫面、現金交易連動、重算按鈕三項真人正向 **USER_CONFIRMED_PASS**，不再重列未操作。餘下只保留確有要求的特殊缺價／stale／partial 呈現、trade/owner/refund/reversal 安全與冪等、回溯到 ledger／Worker terminal 的機器可稽核證據、390px/desktop 截圖與冷暖 P95、10/16 夜批 Private Mart 最新 EOD／PIT readback；缺證據維持各自 PARTIAL／NOT_VERIFIED，**不得反向推翻已完成的基本人工驗收**。
- [ ] 無需每版人工OAuth登入；自動auth與owner隔離仍驗。metadata／401不代表正向PnL或UI PASS。不要以舊來源的API／Jobs證據交叉替代。

## D06｜Iceberg、引用及I/O

- [x] 真實縮減 Core 小檔：基線 8,343 objects／194,161,764 bytes、其中 <1 MiB 8,336；CI orphan 清理 [#38879585601](https://github.com/tommylin15/janus-omniforge/actions/runs/38879585601) **PASS**，實刪 477 objects / 2,039,377 bytes，剩餘 7,866 objects / 192,122,387 bytes / 7,859 小檔。
- [ ] 停用無產品查詢使用者的 Iceberg 稽核鏡像（使用者最新決策取代每日／每週），保留 PostgreSQL 事件；來源 `740e54c2…` 已提交，完整 Release／受控 Jobs rollout／runtime 生效待驗。
- [ ] 已完成 GCS JSON 引用掃描（62 Core、71 Mart、96 Research、495 Private，無略過）；仍須補 PG publication／active 引用證據。此次依使用者 2026-10-16 明確例外，已知引用＋current/named/24h snapshot＋7日檔齡保護後可清無關聯小檔，不造假完整 deletion fence、不淘汰 Core manifests 或 canonical rows。
- [ ] 記錄實際／預期 I/O 與 Core 小檔減量；稽核匯出路徑停用預期消除 100% 專用匯出掃描／寫入，整體 Core ReadObject／GetObjectMetadata 降幅須等量時間窗量測，未量測不報節省百分比。詳見 [本輪證據](archive/d06-finops-2026-10-16.md)。

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
