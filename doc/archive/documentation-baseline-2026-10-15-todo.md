> 歷史快照：2026-10-15 文件整編前。不是 active queue；相對連結已隨搬移校正。

# Janus — TODO

## 2026-10-15 使用者要求暫停（PAUSED）

後續開發、部署、Job 派送及驗收均暫停；本次只保存既有程式進度、更新文件並同步 GitHub。正式 API 100% 流量保持原版本，固定 Preview／四 Jobs 已驗證來源為 `4d058c47ac62ad7328f9f7c0e9fcd4ef4f1ac7b1`。

費稅回補已 PASS：88 筆 append-only 更正，ledger 176→352，折扣0.4／profile3，8 筆持股股數不變。00697B 身分已補齊但仍缺價，完整持股損益仍 PARTIAL。TPEx 缺價修正、057 初始快照補建及 VM 隔離還原工具已保存原始碼及 targeted tests，尚未部署／執行。原備份 timer 仍 active，新 executor 尚未安裝。

恢復後仍依 1～5 順序接續；不啟動後置模型研究。本次不變更 Release 請求；費稅操作請求回到 ledger352 的唯讀 preview。詳細證據、測試與接手入口見 [暫停交接](pause-checkpoint-2026-10-15.md)。

**2026-10-15 最新授權：依序完成持股交易／損益 → 首頁與快照效能 → 通用圖表／四頁 → 總控／備份 → 集中測試及正式 dev 切流（1～5）。** 本輪不啟動後置模型研究。

- [ ] **自動費稅與歷史更正**：費用使用本人券商設定的折扣倍率 **0.4** 及既有最低費用；證交稅依商品／交易日的預設規則計算，交易新增／更正表單不再輸入兩項。所有歷史有效交易先有界核對，以 append-only reversal／replacement 更正費稅，保留原始交易、成交內容與 audit，重算持股及正式損益並驗證 readback；不影響其他 owner。059、完整 CI 與 dev 88 筆更正／Mart352已通過；仍待00697B缺價根因的新版本部署及完整估值 readback，不勾選整體驗收。

**2026-10-15 接續：01 全市場 Bootstrap 與 02 Cached 真實 PASS，03～05 仍 PARTIAL／NOT STARTED。** 最新逐 Run／數值收據見 [status.md](../status.md) 首段。原 2026-10-14 暫停為歷史 checkpoint，已由使用者後續 01～05 合併工程指示解除相應暫停；其他未授權 production／IAM／破壞性操作限制不變。後置五模型研究／CEO publication 不併入本輪。

- [x] **01 官方全市場＋必要 dataset coverage**：交易日 2026-10-13、固定官方 TWSE 1095／TPEx 893，全部必要 dataset 依各市場 10%／30% 門檻 PASS，stage/core/serving 與不可變 provenance 收據 [#38575674367](https://github.com/tommylin15/janus-omniforge/actions/runs/38575674367)。
- [x] **02 同日 Cached**：從已通過 Bootstrap 收據強制鎖定 2026-10-13，必要 17／17 cache_hit、`staged=0`／`serving_published=0`，[#38651225144](https://github.com/tommylin15/janus-omniforge/actions/runs/38651225144) PASS；不得因成功日期往後推而重抓新資料。
- [ ] **03 Owner 持股與正式損益（PARTIAL）**：00719B 官方商品身分已透過 source-audited migration 058 [#38652846263](https://github.com/tommylin15/janus-omniforge/actions/runs/38652846263)＋單一 Owner 真實 Private Mart [#38653250200](https://github.com/tommylin15/janus-omniforge/actions/runs/38653250200) PASS，MCP 讀回名稱、身份、價格、ledger version 170 一致，不再有 `stock_master_not_found`。舊兩Task canary原workflow因cleanup缺收據而FAIL；exact request已確認SUCCEEDED／attempt1／worker相符／verify標記存在、active queue0／dispatch=false，不新seed、不將原run改為PASS。仍需交易存檔、加減碼、賣出／股利／更正／作廢、缺價隔離及使用者按鈕→API enqueue 的真實端到端，不往本人帳本新增測試交易。
- [ ] **04 四頁視覺與效能**：固定 Preview public market-home API 30／30、P50 65.1ms／P95 72.1ms，但單筆最慢 6.67s（新來源4d058c47）；仍需 authenticated 四頁 390×844／desktop 以及 Owner 首屏冷暖、試算／保存 P50／P95 與錯誤率，不以 30 筆公開 API 暖讀取代完整體驗驗收。
- [ ] **05 受控正式 dev API 切流**：03／04 仍未足夠，不得提前從 0% Preview 改正式 100%；待各 gate PASS，再以 exact SHA／共用部署鎖／既有 rollback 做 live cutover 與 readback。

**2026-10-14 使用者要求暫停並同步 GitHub。** 此為歷史 PAUSED／PARTIAL checkpoint，後續繼續指示已恢復本工作包；已提交與未完成驗收見 [checkpoint](full-market-pause-2026-10-14.md)；不得將程式或 unit tests 完成當成 live acceptance。

**2026-10-13 最新合併開發授權：P0-1 至 P1-2 一次完成相依開發，再整合測試／真實驗收。** 本指示取代之前「只更新文件後停止」。先掃全文件，將有效500個股任務與資料收集改全上市櫃；歷史證據／識別字保留且不冒充全市場PASS。P2模型研究與P3報告不由本次自動啟動。

## 最高優先新增：全上市櫃＋單一批次總控（2026-10-13）

本段取代下方所有舊「維持研究500／500 admission／下一個先B9」敘述。最新授權已恢復 P0-1 至 P1-2 合併開發，以下為本輪尚未完成的待辦。

- [ ] 全市場 membership／SQL migration／ingestion／screening／研究／搜尋／watchlist／Admin／UI／fixtures 一次移除股票母體500限制；50 quota、分頁／batch size 等非母體限制保留。
- [ ] 各市場／必要資料集／期間按 TWSE 上市缺失率 ≤10%、TPEx 上櫃 ≤30%（均含邊界）分開通過 coverage gate；固定官方適用名冊分母、未知值／超標與個人完整估值分開。**固定 1988 名冊的 Bootstrap／同日 Cached 已有 PASS 證據，見首段 01／02；跨 UI／研究／總控整體 acceptance 仍未全部完成。**
- [x] **工作流與批次入口治理收斂**：完成 89 份歷史探測、診斷與前 500 研究排程歸檔至 `.github/workflows/archive/`，移除所有舊研究 Actions schedule，僅保留備份清理定時工作；建立統一運維診斷工具 `ops/diagnose.py`（2026-10-14）。
- [ ] 備份產生納入總控；先驗證既有VM路徑與還原再停timer。研究前瞻留存若保留也走總控，不重播歷史500 request。
- [ ] 即時入帳／試算／股數成本、報價snapshot、首頁／圖表serving、dirty owner報表快照，沿 [全市場／快照契約](../spec/full-market-batch-policy.md)；其中 **首頁快照 helper／讀取路徑已提交且單元測試通過，Migration 057 已有部署 PASS；本輪已補批次接線及共用 API serializer，尚待新來源部署／快照收據；不能把公開 API 暖讀觀測當成快照自動生成或冷啟動驗收**。
- [ ] 全市場分片資源／總控dispatch lag／備份不中斷／無雙重派送與P0/P1同源集中驗收。

順序：全市場與總控必要底層＋持股／交易／效能 → 通用圖表／四頁 → 全市場模型研究 → 有效後報告。

版本：3.30（2026-10-13：恢復三項優先整合；上市／上櫃全市場官方報價）
用途：**只保留確定要做的 active work 與未完成 acceptance**。Deferred、Candidate、Observation、Production-only、已接受缺口與研究構想統一放 [`parking-lot.md`](../parking-lot.md)；已完成／被取代內容放 `archive/`。

## 規則

- **2026-10-11 使用者合併授權**：B9 產品功能、C 組、剩餘持股頁／首屏及產品整合（順序 1／2／3）先整套開發，再一併驗收及發布至正式 dev；不在各組內部完成後停等，不提前逐項切換正式流量。必要安全／migration／targeted tests 保留；全市場模型研究仍後置。執行細節見 `codex-execution-plan.md`。

- 在本文件：**做**。必須有 implementation／acceptance，依下列順序執行。
- 不在本文件而在 `parking-lot.md`：目前**不做**，不得自行開工或計入未完成度。
- active work 可因外部核准或 runtime evidence 呈 `partial`／`blocked`；partial 不等於完成。
- 完成證據移至 `archive/` 或 `spec/operations-and-testing.md`，TODO 不保存歷史流水帳。

### P0-V｜Janus CEO → omniAgent Gateway → Gemini Flash-Lite（獨立任務）

**技術整合 PASS／真實 Owner CEO publication PARTIAL；與下方持股／重算 PAUSED BY USER 完全獨立。** 詳見 [CEO P0-V 整合驗收](../ceo-omniagent-p0v-integration.md)。不解除原持股重算暫停、不切正式流量。

- [x] 以 opt-in Gemini-only `OmniGatewayGeminiProvider` 串通既有 CEO router；只接受既有 market-mart SA audience-bound ID token、匹配 project／owner／request／model，拒絕超量 Fact Pack、格式錯誤、未知結果與任何 fallback／盲重試。保留原來的五角色 hash、schema validator、immutable report 與 PostgreSQL 寫入範圍；程式已提交。
- [x] Exact-SHA 完整 GitHub Release [#38363636133](https://github.com/tommylin15/janus-omniforge/actions/runs/38363636133) **PASS**：來源 `b63bf350213fa7c3933724fa38006d8ab7b8033f`，Python／Flutter＋四 GHCR 映像＋CEO image public digest。API 0% 候選 [#38364240675](https://github.com/tommylin15/janus-omniforge/actions/runs/38364240675) **PASS**，舊正式流量 100% 不變；CEO Job 之後另於 #38367279461 受控更新完成。
- [x] 專用 market-mart 身分實際 runtime impersonation **PASS**：[本 Job 原身分讀回 #38366833454](https://github.com/tommylin15/janus-omniforge/actions/runs/38366833454)；原 CI SA 無 `getIamPolicy` 屬唯讀觀察限制，不能覆蓋真實 Cloud Run 身分成功證據；沒有新增專案級 IAM。
- [x] **CEO Job**（Cloud Run Job 無 0%）digest/配置可回復 rollout＋新版真實 signed canary **PASS**：[同來源 #38367279461](https://github.com/tommylin15/janus-omniforge/actions/runs/38367279461)；只更新專用 CEO Job，四排程 Jobs、Janus API 正式流量、omniAgent Gateway 正式流量不變。Gateway 繼續走 0% pilot tag。
- [x] **真實 Gemini JSON 最小回路 PASS**：[已部署 Worker 單回合合成非個人測試 #38367878942](https://github.com/tommylin15/janus-omniforge/actions/runs/38367878942)；Janus Router 收到 Gemini Flash-Lite 回覆並通過 CEO Pydantic JSON／hash 欄位檢查。此測試**沒有產生或持久化正式 CEO report**。
- [x] **P0-V 隔離技術契約與實際持久層 smoke PASS**：[ #38372494501](https://github.com/tommylin15/janus-omniforge/actions/runs/38372494501)：73 Python tests 包含五份 synthetic Specialist hashes、完整 `validate_ceo_output`、evidence／numeric／missing／fence 負測、CI 隔離 PostgreSQL 的真實 Worker report write → Owner API history／hash readback／跨 Owner denied／不可變終態。另由已部署原 CEO Job 執行真實 GCS acceptance 專用前綴 create→immutable readback→delete，以及真實 PG JSONB 讀回（**PG dev 不新增 TEMP grant、不寫正式資料表**）；共用 lease release PASS。先前真實 Gemini 一次性回覆證據仍為 #38367878942，這一輪本身 0 模型呼叫。
- [x] **P0-V 完整五角色 Prompt → Gemini → CEO JSON 真實技術驗收 PASS**：[Janus #38490887562](https://github.com/tommylin15/janus-omniforge/actions/runs/38490887562) SUCCESS；在 [離線 CI #38490691563](https://github.com/tommylin15/janus-omniforge/actions/runs/38490691563) PASS、omniAgent [新版 0% 候選 #38488277144](https://github.com/tommylin15/omniAgent/actions/runs/38488277144) PASS、[Gemini 恢復短呼叫 #38488547115](https://github.com/tommylin15/omniAgent/actions/runs/38488547115) PASS 後，以一次性 Job env override 指向 `p0v-market2048-00d45861`，維持 canonical audience，使用原生 29.5–32 KiB 合成五角色 Fact Pack 完成實際 Gemini Flash-Lite → Janus `execute_ceo`／Schema／hash／evidence/numeric validator；**1 模型呼叫、0 正式報告、0 永久 Job 更新、global lease 安全釋放**。先前 HTTP 503 歷史維持 FAIL 記錄，不當作現況阻塞。
- [ ] **真實 Owner CEO 分析的獨立業務驗收**：等五角色真實來源與 capability 就緒後，用**新**手動 request 完成真實 Fact Pack → Gateway → Gemini → `validate_ceo_output` → immutable GCS／PostgreSQL report/hash → authenticated Owner API history readback；若缺任何 live evidence 仍 PARTIAL，絕不拿本次合成技術 PASS 充當正式分析／publication PASS，不重送舊 request 或建立假持股測試帳本。


**2026-10-13 最新產品順序取代下列舊 B9／C 優先敘述：**先持股完整與快速報價／交易損益，再通用圖表和四頁整合；五分析師有效後才建完整報告。B9／C 留作後置責任索引，不阻塞本輪前兩項。詳細 [需求與驗收](../spec/holdings-first.md)。

- [ ] 交易前唯讀 backend 試算：費稅／成本法／版本一致，未知值與正式成交分開。
- [ ] 成交後快速回傳新版股數／成本／該筆已實現；重送／衝突／歷史更正正確；正式報表 pending 獨立。
- [ ] 持股／首屏／試算／保存的冷暖 P50／P95、失敗率與 quote age，依新契約實測。
- [ ] 個股先簡圖及中性說明；未驗證健康度／整合報告退出 primary，不等待模型完成才交付。

### P0｜全市場官方報價、持股重算、首屏效能與四頁整合（2026-10-13 恢復）

**ACTIVE／PARTIAL。** 使用者已恢復並指定三項優先：① P0 持股／手動損益重算與上市、上櫃全部個股官方報價；② 持股頁與首屏效能；③ 四頁視覺整合。先一次完成跨層程式、migration、UI 與測試，再集中驗收／發布；開發所需唯讀根因調查可先執行。CEO provider 與 全上市櫃模型研究不在本次優先工作包。原暫停證據保留：[歷史交接](../p0-holdings-recalc-pause-handoff-2026-10-13.md)。

- [ ] **Owner 持股運作**：authenticated 新增交易／買入／加減碼／賣出／股利／更正／作廢後 `current_positions` 與 membership／shares／cost／ledger version 即時一致，500 檔研究池外亦可保留及正確操作；不得自行推定未同步的券商成交。以真實 owner readback 和隔離驗收。
- [ ] **全市場官方報價**：上市／上櫃全部個股整批擷取，不以成交排名或現有持股篩選；保存官方日期、source、provenance、Core／serving 與全市場 coverage。沿用既有 14:30 ingestion，盤中 MIS 僅可見需求刷新，不在首屏逐檔抓全市場。
- [ ] **報價、估值與缺價隔離**：TWSE／TPEx 官方來源、商品身分及 EOD/PIT/provenance，00719B 既有單 owner 估值 PASS 不需盲目重做；補齊其他 500 外持股、單檔無價不清空整頁、shares／cost 保留、aggregate coverage 與 `partial/stale/missing` 語意的 live readback。
- [ ] **P0 阻塞／Private Recalc queue E2E**：先在唯讀、受限、不洩露 owner 內容的路徑取得原先一筆 Worker `failed=1` 的實際 `error_code`、請求 terminal、ledger checkpoint／dispatch 和測試紀錄殘留；確認根因並最小修復，補上失敗／重試／parallel worker／owner 隔離 tests。受控重跑一筆 synthetic queue 需觀察 `SUCCEEDED`、exact execution／checkpoint、fence 釋放、可稽核 cleanup。**Cloud Run container SUCCESS 不算業務重算 PASS**；未知終態不得重送。
- [ ] **Ledger 真實互動**：持股頁任何合法 YTD（包括 confirmed 0 與 available）都能看到「重新計算損益」；`QUEUED/RUNNING/CANCEL_REQUESTED` disabled、`FAILED/CANCELLED` 可安全重試、輪詢併發受限且 bounded。驗收 owner 按鈕→ API enqueue → Private Worker → PnL readback；不得用 Flutter fixture 取代真實結案。
- [ ] **視覺／載入效能**：持股卡上排同為持有總損益／報酬，下排同為當日行情變化，台股漲紅跌綠；Hero、缺值／加減碼／多檔狀態、390×844 與 desktop authenticated 截圖對照 Final Visual Contract，無永久 spinner。資料首次冷請求已有 timeout／19s 樣本，仍須量測並修復 P50／P95，不用單次暖讀冒充達標。
- [ ] **最終同源發布／上線驗收**：先確認現在 GitHub `main`、live API/Jobs/Preview 真實基準；完成受影響 tests／完整 GHCR Release／0% candidate／**自動** OAuth & private negative／四 Jobs 受控同源 rollback canary／固定 Preview／實際 owner 操作與 quote/PnL/queue readback，全部 PASS 後才將正式 API 100% 切至新版本並驗收 traffic readback／rollback。每次發版無須人工 OAuth consent；上線仍不豁免 owner/功能證據。


## 現行架構決策

### Token-first specialists + On-demand CEO

權威文件：

- [`decision-2026-10-03-token-first-specialist-and-on-demand-ceo.md`](../decision-2026-10-03-token-first-specialist-and-on-demand-ceo.md)
- [`wbs/wbs-5-specialist-engines.md`](../wbs/wbs-5-specialist-engines.md)
- [`spec/specialist-engines.md`](../spec/specialist-engines.md)

目前產品契約：

- 五 specialist production 主路徑為 Python／SQL／ML，正常 path 不使用生成式 LLM。
- 全上市櫃個股在每個交易日 EOD canonical data ready 後做低成本 market screening／cross-sectional discovery；預設 PyIceberg，BigQuery 不自動切流，不做 全市場×5 深度 specialist。
- 完整五 specialist 只做 `active watchlist ∪ effective holdings`，依 dirty dependency／input change 更新；無變更 reuse，不固定每日全重算。
- retraining／calibration／OOS evaluation／cache reconciliation 第一版固定 **每月第一個週六 10:30（Asia/Taipei）** 執行；不另設每週六 全市場×5 全量深算排程。
- plain-language output 由 structured output + SHAP／rules／templates 產生，正常 0 API token。
- Codex CLI／OpenRouter／Gemini 只用於 authorized manual On-demand CEO／approved rare escalation。
- CEO report immutable；重新分析建立新 execution/report，不覆寫舊報告。
- Admin 管 specialist model/evaluation、CEO provider/profile、DB-backed user capability、quota/cooldown、usage/cost/audit。

### Iceberg canonical + BigQuery analytics hybrid

權威文件：

- [`decision-2026-10-06-bigquery-analytics-over-iceberg.md`](../decision-2026-10-06-bigquery-analytics-over-iceberg.md)
- [`spec/specialist-engines.md`](../spec/specialist-engines.md)
- [`wbs/wbs-5-specialist-engines.md`](../wbs/wbs-5-specialist-engines.md)

目前 B 組資料／運算契約：

- Core Iceberg V2／GCS 繼續是 canonical／PIT／provenance/history；BigQuery 不取代 canonical store。
- PostgreSQL serving projection 與 User／Admin request-time hot path 保持不變。
- 每日 screening／一般 specialist 預設 PyIceberg；BigQuery 僅 ML/OOS 前處理與 training dataset preparation 明確 opt-in，不自動 cutover。
- 禁止 BigQuery Storage Read API；小結果走一般 query/result API，大型 training data 走 versioned GCS Parquet export artifact。
- 不預設複製整套 Core 到 BigQuery native storage；temporary/TTL derived data 可用但不可升格 canonical。
- 資料角色固定：Iceberg/GCS 保存 canonical/PIT/history；BigQuery intermediate 是可重建 compute；大型 training/evaluation dataset 以 versioned GCS Parquet 保存；model/evaluation/specialist 成果依 Mart contract 保存。BigQuery 中間結果不要求再回寫一份 Iceberg。
- 先抽出 exact-snapshot analytics reader，再做 BigQuery compatibility/canary；無法證明與固定 Core snapshot 一致時保留 PyIceberg path。
- 本架構方向已核准；若 implementation 需啟用新付費 API／建立 BigLake/Lakehouse/BigQuery 計費資源或擴大 IAM，仍需另有明確授權。

### Admin UI scope

權威文件：

- [`decision-2026-10-03-admin-ui-scope-and-governance.md`](../decision-2026-10-03-admin-ui-scope-and-governance.md)
- [`ui/admin.md`](../ui/admin.md)

Admin operational convergence **不重做整個 Admin**。保留 `總覽 / 批次 / 個股 / 市場資訊 / AI 分析`，原 placeholder 收斂為 `資料治理`。第一版優先使用 Flutter Material，不導入第二套 metadata／orchestration control plane，也不要求大型 DAG／lineage graph／dashboard。

## 模型確認規則

- 每次只取下列順序中的一個可執行 WBS／工作組。
- 正式執行前依該項標示的【Sol】／【Luna】完成模型 gate；開始後以整體 acceptance scope 結案，不在內部 dataset／adapter／單一畫面反覆停等。
- 新付費 API／model／subscription、新付費 GCP 資源、重大權限擴張、不可逆大量刪除、MFA／OAuth consent／付款仍需使用者明確授權。

# 執行順序：持股完整／效能 → 通用圖表／四頁整合 → 模型驗證 → 有效後報告

依使用者 2026-10-05 指示，先完成上班族操作體驗／效能／Admin，再整合原 specialist 與 CEO 工作。執行細節與可貼給 Codex 的指令見 [Codex 執行指令](../codex-execution-plan.md)。以下產品組與後置研究切片是執行順序；後面的 1～8 是原 WBS acceptance 索引，不再代表先後順序，也不重複計工。

| 工作組 | 範圍與原待辦對應 | 主要模型 | 集中驗收 |
|---|---|---|---|
| A：操作體驗／效能／資料營運 | §6 Admin；§7 非 CEO 功能；§8 非 AI 相依版型；下列新增補強 | Sol | 一組 API／Flutter／資料營運回歸與一輪 dev browser/readback |
| B：B9 產品功能 | §1 可靠基準 + §2 cache；Admin 真實狀態 | Sol | 真實基準分析、缺值／來源／增量／persist/readback；不要求 ML 勝出 |
| C：CEO／權限／最終整合 | §3 provider + §4 CEO + §5 Admin profile；§7 AI 整合；§8 剩餘驗收 | Sol | 一組端到端安全／UI 測試與最少已授權 provider live calls |
| 後置研究：B9 模型品質切片 | 產品交付後，全上市櫃歷史研究池與五角色評估 | Sol | 各日期母體／資料／OOS／基準比較，逐模型決定升級 |

同組先完成相關程式、migration、UI、tests、文件再集中驗收，不逐檔／逐 API／逐股票獨立部署。失敗僅補跑受影響範圍；原 acceptance、必要安全檢查及真實 dev 證據保留。A 不因尚無 CEO 而延後基本 UI；§8 整體結案仍須所有條件成立。跨組連續執行須使用者明確指定全部組，依 PROJECT_RULES 的本次例外處理。

預警／推播／警訊 outcome 增補已移至 [Parking Lot](../parking-lot.md) 與其獨立未來文件，不是本次 active scope；既有 Event specialist 與 OOS 照原契約。

## A 組結案

A 組 implementation／CI／dev runtime 與兩項人工 gate 已於 2026-10-06 全部驗收完成。完成證據已移至：

- [非佇列結案紀錄](group-a-nonqueue-live-closure-2026-10-06.md)
- [latest-price／Ledger UI 驗收紀錄](latest-price-ledger-ui-acceptance-2026-10-06.md)

A 組既有範圍不重開；下一個開發入口依上方全市場／持股與總控工作包。
## 2026-10-12 發版 OAuth 人工驗收已取消

使用者明確取消「每次 GitHub Actions 發布前要求 Owner 手動登入 Google／重做 OAuth consent／A→B→A」的關卡，**不是取消 OAuth 驗證**。同來源 SHA 成功的自動 candidate OAuth metadata、PKCE／redirect、未登入 User/Admin／MCP 授權負測與可自動執行的 token／refresh／owner-scope 測試保留；Jobs／API promotion 的 `auth_boundary_run` 必須通過。詳見 [PROJECT_RULES §12.2](../PROJECT_RULES.md)、[CI/CD SPEC](../spec/cicd-v2.md)、[OAuth runbook](../runbook-user-oauth-dev.md)。真人登入證據未做仍為 `NOT_VERIFIED`，其餘必要發布 gate 不豁免。這是已確定政策／已改 gate，不另把人工登入列待辦。

## 2026-10-11 四頁視覺優先（併入既有 B9＋C＋剩餘產品工作包）

使用者指定四張已核准 PNG 只是最低基礎值，每頁需唯一 Hero、圖表／大數字／顏色先行。 [A 正式 UI 契約](../ui/visual-first-four-pages.md) 和 [B 工程工作單](../ui/visual-first-delivery.md) 定義詳盡責任與 acceptance；不重開 A 組／B0～B8，不提前做 全上市櫃模型研究。

- [ ] VF-00～01 P0：資料 coverage matrix（source→Core→serving→API→UI）、MOPS 財報期別與事件時間、缺值／PIT、owner-scoped typed read path。
- [ ] VF-02～04 P0：今日以本人持股／關注可信異動優先、無資料退回市場判讀／TAIEX；關注異動與價格、持股市值 Hero／有證據的損益貢獻；四頁不再用無重點的數字牆。
- [ ] VF-05～06 P0：個股真實短價量及圖表入口、五角色可信狀態、390×844／字級放大／partial/stale/empty golden 與可及性。2026-10-11 第一批 Flutter 主圖／期間切換／捏合縮放、bounded fetch、關注 stale-while-revalidate 已提交待 CI／真實 dev readback；不得因此勾選整項。
- [ ] VF-07～09 P1：真實官方營收／EPS／PE/PB／法人／事件圖、Private Mart 報表歷史趨勢與角色狀態；缺口不得補假值。
- [ ] 同 SHA 集中 CI／GHCR dev／真實 owner 四頁 screenshot／數值／來源 readback；P0/P1 不得只憑文件／fixture 標 PASS。

VF-10 高階同業／估值河流／還原價為需另證來源／成本的有條件 P2，不列本輪必過驗收。

## 2026-10-08 持股頁 UX／首屏加速（獨立於已結案 A 組及已完成的 B7）

- [ ] 「持股／紀錄／報表／筆記」固定頁首、四格只顯示持股、字體放大，台股漲紅跌綠。
- [ ] 官方昨收／當日每股漲跌／幅度與現持股價格變動有缺值、stale／日期與 owner-scoped guard；migration 050 真實驗收。
- [ ] 首屏不等待年度交易歷史、PnL、重算狀態；版本、報價日期與狀態一致；量測 API latency P50／P95。
- [ ] Flutter／Python targeted CI、dev deployment/migration、真實 User UI／Owner 一致性驗收。未通過維持 ACTIVE，不更動原 A 組 CLOSED 判定。

## B 組：後置執行入口（B7／B8 CLOSED → B9）

**B0～B8 CLOSED／PASS，不重跑；B9 為持股／圖表交付後的 gate。** B0～B6 歷史驗收入口： [B0](group-b-b0-baseline-closure-2026-10-07.md)、[B1](group-b-b1-reader-acceptance-2026-10-07.md)、[B2](group-b-b2-closure-2026-10-07.md)、[B3](group-b-b3-closure-2026-10-07.md)、[B4](group-b-b4-deep-coverage-closure-2026-10-07.md)、[B5](group-b-b5-ml-oos-data-closure-2026-10-08.md)、[B6](group-b-b6-ml-oos-cache-closure-2026-10-08.md)。B7 月度機制、B7 derived-cache freshness 與 B8 均已通過各自核准的 dev 驗收；B9 仍待執行。B7 freshness 完整證據見 [結案](group-b-b7-derived-cache-freshness-closure-2026-10-10.md)，B8 完整證據見 [B8 結案](group-b-b8-closure-2026-10-10.md)。執行方法見 [B 組指令](../codex-execution-plan.md)。

- [ ] **B9 產品功能驗收（後置入口）**：完成五角色可靠計算／規則基準、產品必要資料修復、structured／繁中白話產物、缺值／來源／PIT 時間政策、dirty/reuse、public/private isolation、CI／dev 發布／真實 workload／artifact/API readback。正常 path 0 LLM token；未驗證機率不發布。模型品質未過不阻擋可靠基準服務，純研究 OOS 不作此切片 gate。
- [ ] **前瞻證據留存**：先盤點既有 daily membership、公告版本、publication／first-observed time 與 source receipts，沿用授權來源／retention 補必要缺口；不假造歷史、不提前啟動 全市場大量回補。

2026-10-13 順序更新：本輪持股／首屏及通用圖表整合開發後集中驗收；B9 模型與 C 整合報告後置，不能當成本輪產品發布的前置。只有適用真實驗收完成才能判定本輪交付。B9 模型品質保留獨立 NOT VERIFIED／PARTIAL，不寫「B9 全部 PASS」。

- [ ] **B 組跨階段安全底線**：PostgreSQL serving 與 A 組已驗證 read path 不回歸；BigQuery failure audit/fallback 不修改 canonical Iceberg；不使用 BigQuery Storage Read API；不自動呼叫 CEO；維持現有 1 CPU／1 GiB Mart 限制。新付費 API／資源、IAM 擴權或 catalog migration 需另取得授權，未授權部分單獨 `BLOCKED`，其餘可行項繼續。

## 產品交付後：B9 模型研究切片（已排程，依賴產品交付）

- [ ] 建立目標全上市櫃個股的各日期歷史研究母體與 coverage matrix：上市／下市、納入／排除、來源授權、當時可用時間；不得以今日名單冒充歷史。無可信來源的期間標 blocked_source_history。
- [ ] 按角色建置歷史行情／公司行動／benchmark／財報／估值／事件資料；固定 snapshot、版本、provenance、缺漏及時間政策；研究與 canonical／每日服務分離。
- [ ] 預先固定 baseline、目標期限、主要指標、成熟標籤／purge、walk-forward、最終未調參時段、成本情境與不確定性評估，再調校模型；不以 train success 或股票數達母體數 當 PASS。
- [ ] Quant 優先、Risk 次之；基本面／估值先修資料與規則基準；Event 先取得合法 training-use 與人工審核標籤。五角色具體目標／交付物見 [Codex 作業指示](../codex-execution-plan.md)。
- [ ] 逐模型完成 OOS／校準／分環境穩定性及真實 artifact readback；無優勢保留基準，不自動 promotion。新增費用／資源／IAM 依 PROJECT_RULES。

# 原 WBS acceptance（依上方工作組整合執行）

## 1. `WBS-5-MART-SPECIALIST-ENGINES` — 【Sol】

目前進度：`partial`。

先核對 [`spec/operations-and-testing.md`](../spec/operations-and-testing.md) 已記錄的公開資料清理 apply/readback 與最新 runtime；依 [`spec/retention-governance.md`](../spec/retention-governance.md) 只補尚缺的整合／排程證據，不為舊待辦重跑已完成刪除。其他治理／成本收斂併 A；不以文件過期阻擋 B。

- [x] 約 500 檔**每日盤後**低成本 market screening 已由 B3 CLOSED；Deep Coverage universe／selective execution／no-change reuse 已由 B4 CLOSED。兩者未混成 500×5 全量深算。
- [ ] Fundamental：官方財務比較及 deterministic 基準可用；LightGBM 品質轉後置研究。
- [ ] Valuation：relative valuation 可用；DCF／reverse-DCF 缺完整輸入／核准假設則 unavailable；LightGBM／CatBoost 轉後置研究。
- [ ] Quant：動能／相對強弱／市場排名基準可用；Linear／LightGBM／CatBoost／Qlib 品質轉後置研究。
- [ ] Risk：波動／CVaR／beta／drawdown 基準可用；Markov regime 品質轉後置研究。
- [ ] Event：官方事件 parser／rules 可用；人審標籤與本機 classifier OOS 轉後置研究。
- [ ] 五 specialist 產出 structured artifact、適用的 feature contribution／SHAP、deterministic plain-language report；正常 path 0 LLM API token。
- [x] Deep Coverage 使用 `active watchlist ∪ effective holdings`；持股離開 500 仍保留，清倉且不在 watchlist 才退出。B4 live acceptance 已驗 5 symbols × 5 roles。
- [ ] 完成 PIT／provenance／missing-data／public-private isolation、tests、dev deployment、live execution、artifact persist/readback；OOS 模型品質獨立依後置研究驗收。

目前各必要資料集上市缺失率 ≤10%、上櫃 ≤30% 為使用者接受範圍（分市場／期間且含邊界）；超過先討論，不直接判整體失敗或自行擴張補資料。Mart 資源維持使用者指定 1 CPU／1 GiB；需要提高時先提出 evidence，不自行升級。

使用者最新核准：歷史財報有資料就做 OOS，不再要求原始數值版次／當時公開時間已證明。採最新官方數值版本、優先官方公開／上傳時間，缺少時明示期末後 90 天假設；正式模型作法及結果標示見 specialist SPEC。價格標籤成熟與來源／品質／隔離檢查保留。

## 2. `WBS-5-MART-RERUN-CACHE` — 【Sol】

- [x] 建立 dirty dependency graph：依 accepted/rejected PIT dependency state、feature/engine/model version 只 invalidate 受影響 symbol/specialist；B4 已有 regression + live evidence。
- [x] monthly revenue／financials、EOD price、event 依 specialist dependency mapping 選擇性 invalidation；event-only regression 已驗 1 computed / 4 reused。
- [x] 無 input change 直接 reuse，保留可稽核 cache identity；B4 live 第二輪 0 computed / 25 reused。
- [x] 每月第一個週六 10:30（Asia/Taipei）的 retrain／calibration／OOS evaluation／reconciliation 首輪實際執行與本次 derived cache freshness 已通過；下次自然排程尚未到期，見 B7 archive。
- [ ] specialist change 只標記 CEO report freshness／material delta，**不得自動觸發 CEO LLM**。

## 3. `WBS-5-MART-AI-PROVIDERS` — 【Sol】

有效產品範圍只有 On-demand CEO／approved rare escalation provider runtime。

- [ ] 重用既有 Codex CLI／OpenRouter／Gemini adapter、routing、auth、free/billing gate、fallback/audit 能力。
- [ ] 目前先以既有 runtime bundle 的 Gemini key、已確認 Free tier 與 `gemini-3.5-flash-lite` 完成 CEO 上線；實際執行只走 Gemini，既有三 provider profile／歷史保留。omniAgent 統一 AI 入口待此階段完成後再接。
- [ ] 完成 manual CEO request 的 headless dispatch、cold-start auth／續期、timeout／cancel／retry、route snapshot/version/hash、attempt/fallback、usage/cost audit、zero-secret-leakage。
- [ ] 不新增未核准付費 provider／model／resource。

## 4. `WBS-5-MART-CIO-SYNTHESIS`（legacy tracking ID）— CEO Analysis — 【Sol】

產品名稱與語意一律使用 **CEO Analysis**；上述舊 ID 只為既有 WBS／artifact traceability 保留。

- [ ] CEO 只讀最新 validated specialist outputs／Fact Pack／provenance；不得計算或覆寫 canonical numbers，無 publication authority。
- [ ] 只由具 capability 的使用者明確 request；Scheduler、行情或 specialist dirty event 不自動觸發。
- [ ] 產出 thesis、cross-specialist conflict resolution、bull/base/bear、risks、invalidation conditions、unknowns；validator failure 保持 structured partial／blocked。
- [ ] 每次分析／重新分析建立新 immutable execution/report；保存 requester／trigger audit metadata。

## 5. `WBS-6-ADMIN-ANALYSIS-PROFILE` — 【Sol】

- [ ] 管 specialist champion／model／version／evaluation 與 CEO provider／model／profile；保留 immutable version history、rollback、audit、test symbols／compare。
- [ ] 加入 DB-backed Google user capability 管理，例如 `ceo_analysis.request`；backend enforce，Flutter visibility 不可代替 authorization。
- [ ] Admin 顯示 CEO provider approval／auth／health、model list、quota/cooldown、usage/cost；不得接收或顯示 raw token。
- [ ] 依最新授權保存本人每日 CEO 額度 50、冷卻 300 秒；先完成 migration 052／API 上限及 Admin readback，不能把程式修改當作已套用。
- [ ] CEO 提示詞明列必填 JSON 格式與範例，再以真實 Gemini 回應驗證有效報告與 immutable history；格式失敗保留原紀錄。

## 6. Admin operational convergence — 已完成 A 組範圍

已移入 [A 組結案證據](group-a-nonqueue-live-closure-2026-10-06.md)；B／C 的模型與 CEO 接線保留於其對應待辦。

## 7. User operational convergence — 【Sol／Luna】

- [ ] 【Sol】Stock Detail backend 增加 bounded CEO command/status/history API；驗證 authenticated user、`ceo_analysis.request` capability、symbol/profile、in-flight、quota/cooldown。
- [ ] 【Luna】Stock Detail 顯示五 specialist persisted plain-language outputs、最新 CEO report、analysis/data as-of、dirty/freshness/material-change、immutable history，以及有權限帳號的 `分析／重新分析`。

非 AI Journal／Watchlist／Stock Detail UX、typed formatter 與四頁 390px browser gate 已完成 A 組驗證；交易驗收交接見上文。

## 8. `WBS-6-USER-FINAL-VISUAL-CONVERGENCE` — 【Luna／Sol】

四頁非 AI presentation／PNG references／Flutter regression／authenticated dev browser 已完成 A 組驗證；本 WBS 整體仍保留 B／C 的 AI 整合驗收。

- [ ] Stock Detail persisted-first、manual CEO only、permission-aware、history immutable、freshness/material-change visible。
- [ ] specialist／CEO 接線後再驗四頁 AI-dependent state；不得把 A 組非 AI 結案當作此 WBS 全部完成。

## 完成證據

每個 TODO 至少需有與範圍相稱的 implementation、tests／CI、deployment、migration（如適用）、live runtime／integration acceptance。文件勾選、commit、build、upstream benchmark 或單次 bounded success 本身都不等於完成。

## 歷史／決策入口

- [2026-10-03 Token-first 五 specialist 與 On-demand CEO](../decision-2026-10-03-token-first-specialist-and-on-demand-ceo.md)
- [2026-10-03 Admin UI 範圍與資料治理呈現](../decision-2026-10-03-admin-ui-scope-and-governance.md)
- [WBS-3 補資料第一版完成（2026-10-03）](wbs-3-data-supplement-v1-completed-2026-10-03.md)
- [2026-10-02 Admin／User／Routing／Provider 歷史決策](decision-2026-10-02-admin-user-routing-and-provider-plan.md)
- [Parking Lot／暫不做](../parking-lot.md)

其他已完成／被取代證據保留於 `archive/`；完整 runtime／deployment evidence 見 `spec/operations-and-testing.md`。


- 交易股票選取：支援代號／名稱，輸入一字即顯示下拉選項，涵蓋已登記 ETF；修改搜尋後須重新選取，避免錯誤代號入帳。已接線，待新來源 dev 驗收。
