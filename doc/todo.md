# Janus — 唯一 Active TODO

更新：2026-10-20。**只記未完成工程與驗收**；原有結案/部署流水帳完整保留在 [整編前 TODO](archive/todo-before-consolidation-2026-10-19.md)。實際狀態：GitHub main／tests／CI／GCP dev runtime；最高權限與授權依 [PROJECT_RULES](PROJECT_RULES.md)，操作依 [AI 指令](codex-execution-plan.md)。

## 1. 單一執行順序

| 優先 | 工項 | 狀態／責任入口 |
|---|---|---|
| **P0** | **STAGE-48H：48小時 TTL／安全去重／Admin 六桶盤點** | **DEPLOY PASS／LIVE PARTIAL**：[full GHCR #39355867356](https://github.com/tommylin15/janus-omniforge/actions/runs/39355867356)、[四 Jobs #39356643823](https://github.com/tommylin15/janus-omniforge/actions/runs/39356643823)、[獨立 Scheduler／固定 digest 讀回 #39358461946](https://github.com/tommylin15/janus-omniforge/actions/runs/39358461946) PASS；舊 Stage **4,927 件／96,321,204 bytes** 已 generation 實刪、[六桶讀回 #39356190151](https://github.com/tommylin15/janus-omniforge/actions/runs/39356190151) 確認超過7天0；[真實 shared raw/provenance #39358645373](https://github.com/tommylin15/janus-omniforge/actions/runs/39358645373) PASS（測試物件全部清除）；[新版48h dry-run #39359037869](https://github.com/tommylin15/janus-omniforge/actions/runs/39359037869) 候選0。**尚需**當日18:30自然 due/apply 收據與真實登入 Admin 六桶正向 OAuth/IAM；不同 observed_at 的同日 payload 去重效率未驗收，不當 full PASS。D07-PRE 在另一對話。 |
| **P1** | **D07-PRE：GAS→Drive 月檔→Colab；舊研究雲端路線立即退役** | **GitHub 研究入口已退役；GCP 專屬 Jobs/Scheduler／BQ 中介表實機無殘留；共用映像驗收待補**；[唯一新契約](spec/research-collection-gas-drive-colab.md) |
| **P2** | **D07：五角色 ML／OOS 品質及正式介接** | **PLANNED**、待前置評估有合格處置；[唯一 D07 卡](execution-cards/d07-specialist-b9-oos.md) |
| **P3** | **D08：CEO、Admin 模型管理與受控 Owner 報告** | **PLANNED**、有效 Fact Pack 後；[唯一 D08 卡](execution-cards/d08-ceo-admin-owner-report.md) |
| 非阻擋 | **OPS-OBS：自然排程與 GCS 保留量觀察** | 2026-10-20 六桶 current 968,619,706 bytes、Stage 1,457件／318,859,190 bytes，超過7天0；18:30首次新版自然 Stage-only receipt 尚待時點到後核對，與每週 Iceberg 的正式 cadence 分開驗證。 |

**不重開**：D01～D05 `CLOSED/USER_ACCEPTED`、DRL-01 `CLOSED`、FINOPS-AB（已含 D06）`CLOSED`、背景持股/關注股補收 `PASS`、ADMIN-V2 `PASS`。原驗收範圍與缺口不改判；完整實測收據在 [原 TODO](archive/todo-before-consolidation-2026-10-19.md)、[D01～05](archive/d01-d05-relaxed-acceptance-closure-2026-10-17.md)、[DRL](archive/drl01-completed-2026-10-19.md) 和 [Operations](spec/operations-and-testing.md)。歷史工作包的卡片留作維運參考，不能變第二套 active queue。

## 2. STAGE-48H｜最新核准的儲存清理工作（不重開 FINOPS-AB）

**2026-10-20 老 Stage 物件清理補充（使用者明確核准）**：[實機 dry-run #39351045998](https://github.com/tommylin15/janus-omniforge/actions/runs/39351045998) 觀察 61 筆 active control record，其中 4,927 個舊 Stage 物件因 status=running 被 hold；[GCP Stage apply #39351609294](https://github.com/tommylin15/janus-omniforge/actions/runs/39351609294) 已 generation PASS 實刪另外 37 件／38,396 bytes。後續 [控制紀錄稽核 #39352303651](https://github.com/tommylin15/janus-omniforge/actions/runs/39352303651) 確認 24 筆超過 7 天的 running control 紀錄持有該 4,927 件／96,321,204 bytes，**有效未到期的 claimed_until 為 0**；這是控制面 active status 的保守保護，**不是模型訓練引用證據**。使用者已授權移除超過 7 天的這類失效 Stage 舊物件與證實可移除的實體重複副本，目前已透過 [dry-run #39354898619](https://github.com/tommylin15/janus-omniforge/actions/runs/39354898619) 驗證候選 4,927 件／96,321,204 bytes，並由 [GCP apply #39355428497](https://github.com/tommylin15/janus-omniforge/actions/runs/39355428497) **generation PASS 實刪全數 4,927 件／96,321,204 bytes**（Stage 6,384 件／415,180,394 bytes → 1,457 件／318,859,190 bytes；Core/Mart/Private 刪除 0）。MD5 潛在額外 165,308,239 bytes 未核對實體副本／刪除 generation，不得列入已釋放容量。不得影響 Core/Mart/Private 或將未驗證標 PASS。



**10/20 最新 GCS 六桶 metadata-only readback（獨立 CI 身分，非 Admin OAuth）**：[FinOps #39356190151](https://github.com/tommylin15/janus-omniforge/actions/runs/39356190151) OBSERVED_COMPLETE，六桶 current **968,619,706 bytes**、noncurrent **16,877,094 bytes**、soft-deleted 0；Stage current **1,457 objects／318,859,190 bytes**，**超過7天0件**。相同 MD5 潛在重複 **126,687,768 bytes** 不能直接當作刪除資格；需保護未到48h與有效引用。CI 的 GCS metadata 讀權限不等於 API serving identity 或 Admin OAuth 正向按鈕 PASS。

- [x] **48 小時到期資料清理**：dry-run → 受控 generation apply → before/after bytes 讀回；另以 Cloud Logging 確認 2,050 筆的獨立 apply 收據。
- [x] **Stage 相同 observed-at shared raw/provenance 實機**：[Cloud Run canary #39358645373](https://github.com/tommylin15/janus-omniforge/actions/runs/39358645373) 一份 raw、第二 execution reused、兩份不同 provenance、4件 synthetic generation 刪除殘留0 PASS；不同 observed-at 之同日重用及正向 live lease 仍未單獨實機驗證，不能泛稱全情境已去重。
- [ ] **每日自然排程驗收**：新版48h [dry-run #39359037869](https://github.com/tommylin15/janus-omniforge/actions/runs/39359037869) PASS，活躍租約0、過期可刪0件／0bytes；兩次手動 apply [#39359331473](https://github.com/tommylin15/janus-omniforge/actions/runs/39359331473)、[#39359630805](https://github.com/tommylin15/janus-omniforge/actions/runs/39359630805) 因 D07 同時更新 main 被全域 lease 安全拒絕（零刪除），不重試繞過鎖。2026-10-20 18:30 Asia/Taipei 自然 Controller occurrence／Stage-only apply 終態與 generation delta／無重複派送，已安排當日20:00左右一次唯讀驗收；週六 Iceberg 維持不變。
- [ ] **Admin 六桶正向驗收**：UI＋後端 Admin-only POST 已上線，未登入 401 PASS；仍須真的 Admin OAuth 授權按鍵、確認既有 API runtime metadata IAM 與六桶完整/部分/timeout 處理。無新增刪除功能。
- 本工程不變更 Core/Mart/Private/Research 保留政策、不新增付費資源；D07-PRE／Colab 建模另由獨立對話承接，本對話完成 STAGE-48H 收尾後結案。

## 3. D07-PRE｜GAS／Drive 月檔／Colab 與舊雲端研究立即退役

**2026-10-20 定案：[研究資料唯一規格](spec/research-collection-gas-drive-colab.md)。** 新研究資料使用 GAS 直連允許的第三方來源→私有 Drive `資料源/YYYY-MM.zip`→Colab 人工建模；只包含 TWSE／TPEx 普通股、排除 ETF；研究資料每市場×dataset 覆蓋率 ≥70%。第一輪先比較既有持股／觀察股的公開欄位、欄位存在與非空數；暫不以歷史 PIT／兩年完整回補作收集前置。正式 Core 品質與 Owner 行情不改。

- [x] **退役舊排程的 GitHub 定義（待實機驗收）**：已移除 Controller `specialist-retrain` 月度 due、舊 manual workflow/request；舊 Mart `specialist-retrain`、`specialist-baseline`、`ml-oos-data-acceptance` 操作入口亦已自 GitHub main 拆除；歷史 pending 以通用 `schedule_superseded` 處理。**GCP 新映像尚待部署及真實 readback**。
- [ ] **CI 修復**：舊重訓測試刪除後的 2026-10-20 [selective CI #39354033133](https://github.com/tommylin15/janus-omniforge/actions/runs/39354033133) 曾 FAIL（刪除測試仍被本次路由選入、Mart replay 回傳欄位尚未一致）；目前後續文件型 selective CI PASS 不代表完整測試回歸 PASS。須修正 replay contract／選路並重跑 targeted/全相關 tests。
- [x] **GCP 舊研究獨立 Jobs／Scheduler 實機盤點**：2026-10-20 [清理執行 #39359490206](https://github.com/tommylin15/janus-omniforge/actions/runs/39359490206) 及 [精確資源讀回 #39359661801](https://github.com/tommylin15/janus-omniforge/actions/runs/39359661801) PASS。全專案 us-central1 8 Jobs／1 Scheduler；已知舊 `specialist-retrain`／research-big-move 獨立 Job 與專屬 Scheduler 均不存在，實刪 0；唯一 Scheduler 為正式 `janus-ingestion-daily`，不得移除；其餘 Janus 4 支主要 Job、CEO Job 與 3 支 Life Job 均不因研究退役整支刪除。
- [ ] **共用 Controller／Mart 新映像切流驗收**：舊研究程式已在 GitHub main 退役，但本輪 GCP 資源清單不足以證明現役 Controller／Mart 的 digest 已更新、自然排程不再派送舊月度 operation、歷史 pending 標記已生效；需依現役 GHCR rollout、Scheduler occurrence 和 runtime receipt 單獨讀回，未證明前為 `RUNTIME_NOT_VERIFIED`。
- [x] **BigQuery 實體資源盤點／舊中介表退役驗收**：上述 GCP WIF Live 兩輪讀回為 **1 dataset／0 table／0 view**；B5～B8／specialist retrain 舊 BQ 中介實體無殘留候選，實刪 0、無虛構容量節省。唯一 `_4b7fe31e8b2716c2c4242fa47f8ba327c90e9994` 空 dataset 用途尚未查明，保持不刪；歷史 BQ query jobs 及 BQ Data Transfer 排程未在本輪盤點，不能把本證據擴大為所有 BQ 排程皆已移除。
- [ ] **GAS/Drive**：建立分批、續跑、限額、去重／來源版次／SHA256、月 zip、quality/manifest，實抓現有公開資料欄位及全市場 70% 合格率。資料品質不足可 PARTIAL 封存，不補造資料。
- [ ] **Colab**：直接從研究月檔訓練五位分析師；Quant／Risk 優先，其他依欄位可得性與 Event 真人標籤；OOS、模型版本與正式 promotion 獨立驗收。
- [ ] **規格一致性**：GitHub Active SPEC／WBS／runbook／AI 指令及 Drive 五份分析師研究規格同步淘汰舊研究來源與門檻，不重新啟動已結案的 D01～D06/DRL/FinOps。

新流程未驗收標 `NOT_VERIFIED`；從 GitHub 移除排程不等於 GCP 已部署停用或 BigQuery 實刪。

## 4. D07、D08：前置通過後才開始

**D07**（詳情只維護 [D07 卡](execution-cards/d07-specialist-b9-oos.md)）：
- [ ] Quant→Risk 優先，Valuation/Fundamental 待可比較合法歷史，Event 缺已授權人工標籤先維持 deterministic；依同樣本 baseline/ML、成熟 labels、PIT/時間外 fold、成本／regime、來源/版本與不確定性逐角色評估。
- [ ] Colab-only 新模型正式介接：Janus Mart 只負責接受、驗證、註冊、rollback、inference 與 Admin VF-09；不恢復已刪除的舊 Cloud Run fit。
- [ ] 各角色 baseline 與模型品質分級獨立；訓練成功、GCS readback 或 B7 歷史 PASS 不等於 B9／真實 PIT 品質 PASS。

**D08**（詳情只維護 [D08 卡](execution-cards/d08-ceo-admin-owner-report.md)）：
- [ ] 沿用 OmniGateway/Gemini 路由驗證 auth、quota、owner boundary、失敗及回滾；有效 Fact Pack → 手動 request → validator → immutable GCS/PG → User/Owner 授權 history。LLM 不產生 canonical number、不能決定 publication。

## 5. 非阻擋觀察與決策

- **自然 Readiness Ledger**：手動/定向已結案，但 daily/weekly 自然收據仍 `NOT_VERIFIED`，沿現行 Job/Operations 觀察，不新增 DRL 第二施工工單。
- **FINOPS 實刪效果**：候選 Core 6,455／Mart 55 物件不等於實際刪除 objects／bytes，不能從 Job success 推算帳單節省；唯讀查已執行 receipts，**不為填文件再做清理**。使用者取消兩日等量 I/O 比較，狀態為 `CANCELLED_BY_USER`。
- **Dev Pilot**：持續證據見 [Pilot Ledger](pilot-operational-evidence.md)，不另建第二長期監控工單。

**R1 已決定 A（Colab 人工啟動）；R2／R3 要多少資料才足以決策，先依稽核產出分母與來源證據，不能用 88.8% 規劃差額或 UNKNOWN PIT 比率直接批量回補。** 其餘需使用者做的重大選項決定集中於 [專案管理風險 §4](project-management.md#4-重大風險及選項)。未獲付費、IAM、OAuth、無界回補或破壞性操作授權，不以文件代替；非相關的有界工作仍可進行。已接受缺口／未排程構想一律在 [Parking Lot](parking-lot.md)。
