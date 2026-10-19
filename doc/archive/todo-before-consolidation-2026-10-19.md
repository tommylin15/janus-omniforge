# Janus — 唯一開發待辦


更新：2026-10-19。只保存尚未完成的交付與驗收；真實終態證據見 [status](../status.md) 與 [operations](../spec/operations-and-testing.md)。

## 執行範圍

**2026-10-17 最新決策：D01～D05 全部 PASS／CLOSED（使用者核准寬鬆驗收）**。既有真人正向驗收、資料讀取、備份與正式發布證據已接受；其餘嚴格量測、獨立補驗及原 D03 後續增補均不再要求，不另留支線或後續待辦。缺少證據的部分記為 USER_ACCEPTED／WAIVED，不偽稱實測通過。結案依據、已接受限制及原始清單見 [結案紀錄](d01-d05-relaxed-acceptance-closure-2026-10-17.md)。

**2026-10-18 最新範圍決策：D06 取消獨立收尾，將其剩餘引用保護／Retention／Orphan／Core・Mart Cleanup 整併 FINOPS-AB；D06 原兩天或長時間等量 I/O 量測由使用者取消，不作交付條件。FINOPS-AB（A 快速節流＋B Ingestion／Iceberg 原地優化＋D06 安全收尾）列最高優先，立即推進；DRL-01已於2026-10-19依核准範圍結案，見[證據](drl01-completed-2026-10-19.md)；共用main／runtime仍不得競爭部署。**D07-PRE（資料、模型與運算器整合前置評估）** 合併原 FINOPS-C preflight 與現有兩年資料/Colab 評估，作為 D07/D08 前唯一前置工作包。須完成資料覆蓋、補收/PIT/OOS、**唯一 Colab 資料整理與模型訓練**的可行性、成本／安全和原 Janus 串接評估；**BigQuery 只作大型資料前置縮減**，不列為並行訓練選項。記錄同一份 GO/NO-GO/DEFER/BLOCKED 決議，BQ 不需先實施。既有 ADMIN-V2 正在進行，不因本次排列改動已授權範圍；不重開 D01～D05 及 D06 歷史 gate。唯一 AI 執行指令見 [FINOPS-AB／C 卡](../execution-cards/finops-ingestion-iceberg-ab-and-c-gate.md)。

A 組及 B0～B8 已結案的範圍不重開；有實質變更才回歸受影響路徑。全市場 Bootstrap／同日 Cached、費稅88筆更正、00719B 身分／估值既有成功證據不重送。研究範圍採各歷史日期全上市櫃；50 關注 quota 仍保留。

以下 `D01～D08` 是本次文件工作包代碼，不取代既有 WBS ID。新增設計補強見 [契約](../spec/system-development-contract.md)，不是已實作聲明。

D01～D05 已結案；D01～D08 各有一張供查閱的 [標準任務卡](../execution-cards/README.md)；操作程序不代替本 TODO 唯一狀態與當次授權。

| 工作包 | 狀態／次序 | 既有 WBS 責任 | 依賴與退出條件 |
|---|---|---|---|
| [FINOPS-AB CPU／GCS I/O 優先優化](../execution-cards/finops-ingestion-iceberg-ab-and-c-gate.md) | **P0／PASS（2026-10-18 完成）** | WBS-3／WBS-7（A＋B） | Jobs rollout、Core retention、Mart retention、週維護啟用全部 SUCCESS |
| [D06 Iceberg／I/O 歷史證據](../execution-cards/d06-iceberg-retention-io.md) | **不再獨立排程；剩餘全部併 FINOPS-AB** | WBS-7／retention（於 AB 驗收） | 477 objects 清理／audit mirror 停用 PASS 沿用；兩天 I/O 比較 `CANCELLED_BY_USER`，不作另一次驗收 |
| [ADMIN-V2 Admin 四頁主要重構](../decision-2026-10-17-admin-v2.md) | **PASS（2026-10-19 完成）** | WBS-6-ADMIN-OPERATIONAL-CONVERGENCE | 四頁重構＋總覽使用分析／單一使用者追蹤；A1～A5 全部完成，Flutter/Python tests PASS |
| [D07-PRE Colab 單一建模資料流程（含 FINOPS-C）](../colab-d07-modeling-feasibility-2026-10-19.md) | **IN_PROGRESS／設計已定案、live 尚 PARTIAL；D07/D08 唯一前置** | WBS-5／WBS-7（原 C-preflight） | 資料／特徵／標籤／OOS＋模型訓練統一在 Colab；Janus Core 唯讀合格資料出口，Mart 只做驗證／推論；僅大資料實測瓶頸才用 BigQuery 前置縮減。查 24月 coverage、來源/PIT、安全/成本與月度人工／自動化阻塞 |
| [D07 五角色資料與品質](../execution-cards/d07-specialist-b9-oos.md) | 後置；D07-PRE 整合評估與處置決議完成後 | WBS-5-MART-SPECIALIST-ENGINES／RERUN-CACHE（B9） | 全市場歷史母體、逐角色 baseline／OOS；B7 PASS 不代替B9 |
| [D08 CEO／Admin／報告](../execution-cards/d08-ceo-admin-owner-report.md) | 後置；D07-PRE 整合評估與處置決議及有效角色後 | WBS-5-MART-AI-PROVIDERS／CIO-SYNTHESIS、WBS-6-ADMIN-ANALYSIS-PROFILE、User AI整合 | P0-V技術已PASS；真實 Fact Pack／capability／immutable report／Owner history另驗 |

## FINOPS-AB｜CPU／GCS I/O 優化（P0／PASS，2026-10-18 完成）

**2026-10-18 完成摘要：**

| 步驟 | Run ID | 狀態 |
|------|--------|------|
| 新四 Jobs rollout (252db8c) | [#39101646737](https://github.com/tommylin15/janus-omniforge/actions/runs/39101646737) | ✅ SUCCESS |
| Core retention | [#39103394210](https://github.com/tommylin15/janus-omniforge/actions/runs/39103394210) | ✅ SUCCESS |
| Mart retention | [#39105091080](https://github.com/tommylin15/janus-omniforge/actions/runs/39105091080) | ✅ SUCCESS |
| 週維護啟用 | [#39106307549](https://github.com/tommylin15/janus-omniforge/actions/runs/39106307549) | ✅ SUCCESS |

**已完成：**
- [x] 新版本 `252db8c` 四 Jobs 部署（精確 generation 實刪）
- [x] Core snapshot 過期 + orphan 清理
- [x] Mart snapshot 過期 + orphan 清理  
- [x] `FINOPS_WEEKLY_MAINTENANCE=true` 已設定
- [x] 清理前候選：Core 6,455 檔／~100 MiB、Mart 55 檔／~370 KiB，合計約 580 個舊 snapshot

**使用者決策：**只留每表 current snapshot，其餘可清理。取消24小時、舊 named refs 與研究／模型／報告／publication 引用保留。詳見[正式決策](../decision-2026-10-18-current-only-snapshots.md)。

**原 D06 兩天／長時間等量 I/O 量測：CANCELLED_BY_USER**，不執行、不阻擋結案。實際清理統計待補。

## 持股／關注股背景補收（PASS，2026-10-19 完成）

**持股／關注股補收接線（使用者2026-10-18新增授權）**：新增時立即排入背景補收，重用每日08:30增量作兜底；涵蓋價量、13月營收、已發布單季EPS與兩年估值，不限EPS。缺口可直接使用Yahoo／FinMind等第三方，不以官方查找為前置。範圍及驗收見[補收契約](../runbook-data-supplement.md#新持股關注股補收契約2026-10-18-使用者新增需求)。不變更Owner交易內容，不新增付費資源或獨立Scheduler。

**2026-10-19 驗收完成：**

| 步驟 | Run ID | 狀態 |
|------|--------|------|
| Migration 066 | [#39211319189](https://github.com/tommylin15/janus-omniforge/actions/runs/39211319189) | ✅ PASS |
| Run（8檔補收） | [#39218676440](https://github.com/tommylin15/janus-omniforge/actions/runs/39218676440) | ✅ 8/8 ready |
| Readback（API驗證） | [#39219930372](https://github.com/tommylin15/janus-omniforge/actions/runs/39219930372) | ✅ 8/8 PASS |

**驗收結果：**

| 股號 | 類型 | 價量 | 營收 | EPS | PE/PB |
|---|---|---|---|---|---|
| 00697B | 債券ETF | 125日 ✅ | N/A | N/A | N/A |
| 00719B | 債券ETF | 125日 ✅ | N/A | N/A | N/A |
| 1513 | 股票 | 158日 ✅ | 13月 ✅ | 12季 ✅ | 2年 ✅ |
| 2327 | 股票 | 200日 ✅ | 13月 ✅ | 12季 ✅ | 2年 ✅ |
| 2382 | 股票 | 158日 ✅ | 13月 ✅ | 12季 ✅ | 2年 ✅ |
| 3231 | 股票 | 158日 ✅ | 13月 ✅ | 12季 ✅ | 2年 ✅ |
| 3711 | 股票 | 158日 ✅ | 13月 ✅ | 12季 ✅ | 2年 ✅ |
| 5876 | 股票 | 200日 ✅ | 13月 ✅ | 12季 ✅ | 2年 ✅ |

**已完成：**
- [x] Migration `066_stock_supplement_queue`（PostgreSQL 佇列與 lease）
- [x] 按股號共用佇列、去重、失敗重試（24hr）、取消需求
- [x] API 異動喚醒（記帳／關注後觸發）
- [x] 既有 daily 08:30 補漏兜底
- [x] FinMind 價量／營收／估值接線
- [x] Yahoo 12 季 EPS 接線
- [x] Stage→Core→serving→API 完整鏈路讀回驗證



## D06｜歷史結果（剩餘工項併 FINOPS-AB，不獨立施工）

- [x] 真實 orphan 清理：原 8,343 objects／194,161,764 bytes，已刪 477 objects／2,039,377 bytes，剩餘 7,866 objects／192,122,387 bytes；[#38879585601](https://github.com/tommylin15/janus-omniforge/actions/runs/38879585601) PASS。
- [x] 停用 `ops.batch_events_v1` audit mirror：Jobs rollout [#38875865395](https://github.com/tommylin15/janus-omniforge/actions/runs/38875865395) 8/8 PASS，runtime [#38881471078](https://github.com/tommylin15/janus-omniforge/actions/runs/38881471078) PASS。
- [x] GCS 引用掃描 62 Core／71 Mart／96 Research／495 Private 已有證據，PG publication 共138筆；`core_snapshot_id` 欄位仍有 privilege 缺口，未完成全引用授權刪除。
- [ ] 引用保護、Retention fence、合法 Orphan／Snapshot 清理及讀回：**已轉入 FINOPS-AB 的 D06-R1/R2/唯一驗收**，不另發佈或重複計算。
- [x] 兩天／長時間等量 I/O 比較：**CANCELLED_BY_USER（需求取消，不是量測 PASS）**；不執行、不阻擋 FINOPS-AB 結案。

## ADMIN-V2｜主要重構（PASS，2026-10-19 完成）

**單一執行入口：**[Admin v2 架構與逐步順序](../decision-2026-10-17-admin-v2.md) → [Admin UI](../ui/admin.md) → [WBS-6](../wbs/wbs-6-api-and-apps.md)。

**2026-10-19 完成摘要：**
- 四頁 shell（總覽／批次／資料品質／系統設定）已實作並通過 Flutter 測試
- Controller 營運整合（AdminBatchPage, AdminEffectiveBatches）已完成
- 資料品質頁面（AdminReadinessPage, AdminStockWorkbench, AdminSourceHealthPage）已完成
- 營運治理（AdminGovernancePage）已完成
- 使用分析（A4-U）完整實作：Flutter UI、Python API、PostgreSQL migration 064
- AI 模型與 Gateway（AdminAnalysisPage）已完成
- 響應式設計：390px mobile drawer / desktop NavigationRail 已驗證

**已完成：**
- [x] **A0 規格整併（文件）**：六頁→四頁的目標、舊頁功能歸位、A1～A5 工程順序、D07／D08 消費位置及驗收邊界已寫入本 TODO／WBS／UI／兩張卡片。
- [x] **A1 四頁 shell 與功能遷移**：總覽／批次／資料品質／系統設定；保留必要搜尋、details、history、Admin authorization。Flutter `admin.dart` 實作 `AdminWorkspace` 四頁導覽。
- [x] **A2 Controller 營運整合（D01、D02、D04、D05 的影響）**：Private Mart、Snapshot、effective batch/backup/job terminal、受控 retry、已驗證 deployed SHA/digest 的唯讀顯示。`AdminBatchPage`、`AdminEffectiveBatches` 已實作。
- [x] **A3 DRL-01 資料品質（含 D02／D03 影響）**：TWSE／TPEx、OHLCV／營收／EPS 合法期間、stock／market 缺口、來源及安全修復；2026 單季 EPS 與歷史 TTM 未認證區別顯示。`AdminReadinessPage`、`AdminStockWorkbench`、`AdminSourceHealthPage` 已實作。
- [x] **A4 D06／D04 營運治理**：Iceberg objects/bytes、maintenance、cleanup/protected refs、可比負載 I/O、備份與 worker 設定。`AdminGovernancePage` 已實作。
- [x] **A4-U 全站＋單一使用者行為分析**：`admin_usage.dart`、`usage.py`、`064_usage_analytics.sql` 完整實作。Flutter allowlist 事件非同步批次、PostgreSQL 每日 user-feature 彙總、短期事件保留、Admin 授權與存取稽核。
- [x] **A5 Admin 專屬完整驗收**：
  - Flutter targeted tests：`admin_shell_test.dart`、`admin_overview_batch_test.dart`、`admin_stock_workbench_test.dart`、`usage_test.dart`
  - Python tests：`test_usage_analytics.py`、`test_admin_v2_acceptance.py`
  - 權限與 owner 隔離：User/Admin audience 分離、feature allowlist 驗證
  - 響應式：390px mobile drawer / 1280px desktop NavigationRail 測試通過
  - GCP 驗收腳本：`admin_v2_acceptance.py`、`admin-v2-acceptance.yml` workflow

**禁止擴張：**D01～D06 的 TODO 列、任務卡、完成與驗收條件**保持原樣**；新增 A4-U 只隸屬 ADMIN-V2，User App 只增加共用非阻塞埋點，不更動既有交易、估值或專案資料契約；相關工作只列在此處，亦不建立另一個 DRL、Scheduler、Admin 重算或發布系統。D07 的 VF-09 接「系統設定／AI 模型」；D08 的 CEO/Gateway 接同一容器且正式報告回 User，兩者維持既有模型／業務 gates。

## D07-PRE｜Colab 唯一資料與模型訓練流程（合併 FINOPS-C）

**狀態：目標流程 DECIDED／工程與真實資料驗收 PARTIAL。** 執行契約：[Colab 單一流程與 24月資料評估](../colab-d07-modeling-feasibility-2026-10-19.md)；AI 操作卡：[FINOPS §4](../execution-cards/finops-ingestion-iceberg-ab-and-c-gate.md)。**沒有獨立 Colab、C-preflight、BQ 模型訓練或第二月度排程工單。**

- [ ] **D07-PRE 同一組完整驗收**：① 實際 24 個月各 dataset × market × date × symbol × horizon coverage、歷史成分、來源 training-use、成熟 labels、OOS／holdout、PIT 缺口及既有有界補收；② 既有 Core→合格、固定版本 Parquet→**Colab 唯一完成資料驗證／特徵／標籤與 Quant CPU baseline/LightGBM PoC**，驗輸入輸出 hash/provenance、成本、RAM、耗時、安全及上傳回 Janus 的 Artifacts；③ 既有月度第一個週六10:30 Controller 仍唯一調度面，Colab 模型工作先走**可稽核人工操作與回傳**（free runtime 不保證無人值守），盤點未來要可靠自動化的授權/成本/做法，**不得隱藏未自動化的 blocker，也不得 fallback 至 GCP 再訓練**；④ BigQuery 預設 DEFER，不跑 BQML；**僅 Colab 大量 Join/運算有實測瓶頸**才評估 BQ 前置縮減的 bytes/cost、IAM、parity 與回退，仍讓 Colab 負責訓練；⑤ 單一文件記錄日期/SHA/數據、GO/NO-GO/BLOCKED（BQ 前置可 DEFER）、是否可開 D07，並同步 WBS/治理/TODO。
- **現有 API／canonical Iceberg／daily Screening／Owner 與既有月度 GCP Job 不因文件提交而改動**。將舊 Mart 模型訓練遷移到 Colab 必須在 D07 工程實作與真實測試驗證，且切換前保留既有安全功能；不能宣稱新流程已部署或月度自動訓練可用。
- **品質分離**：完成 Colab 資料/模型路徑 ≠ 五角色 OOS 有效 ≠ Champion 升級／D08 發布；每個門檻依 D07 任務卡驗收。

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
原重複工作、舊授權及收據完整保存於 [整編前TODO](documentation-baseline-2026-10-15-todo.md)；歷史不再形成另一份執行佇列。未排程構想統一見 [Parking Lot](../parking-lot.md)。
