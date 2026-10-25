# 單一路線：逐項 AI 執行指示

更新：2026-10-25。工作順序與狀態只看 [TODO](../todo.md)，本檔只保存操作指示。SEQ-01 已完成文件、程式及完整離線 CI（Python217／Flutter7／Controller99 PASS；[收據 #40148605544](https://github.com/tommylin15/janus-omniforge/actions/runs/40148605544)）；集中部署與真實Dev驗收仍交SEQ-04。唯一下一入口為SEQ-02文件設計，SEQ-02…08依使用者後續指定及前置條件開始。

## 建議模型

這是依任務分工的建議，沿用本工作環境模型名稱，不宣稱外部產品排行或另購訂閱要求。

| 階段 | 預設建議 | 使用方式 |
|---|---|---|
| 文件設計 | GPT-6 Astra（高推理） | 跨資料／模型／Owner／備份契約與缺口判斷 |
| 程式開發 | GPT-6.1 Sol（高推理） | repository實作、schema、測試來源與修正 |
| 測試驗收 | GPT-6.1 Sol（高推理） | 執行targeted／Release／真實讀回；數值或模型契約爭議才交Astra覆核 |
| 部署 | GPT-6.1 Sol（高推理） | 既有runbook、固定SHA/digest、lease、回復與收據 |

只使用目前帳戶可選模型；若介面無上述名稱，選已可用且具讀碼／工具執行能力的模型，不新增付費API。沒有模型切換工具時由使用者選擇，不宣稱已替你切換。

## 可直接貼給下一個 AI 的共同指令

```text
你是 Janus／OmniForge 接手工程 AI。
任務：使用者指定的 SEQ-ID；階段：使用者指定的文件設計／程式開發／測試驗收／部署。
1. 讀 AGENTS.md、doc/PROJECT_RULES.md、doc/todo.md、本檔對應 SEQ 卡，以及該卡最少必要來源。
2. 先核對 main HEAD 與現有改動／相關程式／真實證據。不要覆蓋其他AI提交、重做已完成工作或從舊卡復活取消項。
3. 本卡各階段段落都是必須執行的具體指示；只做指定階段，未指定階段則按四階段完成本任務可做範圍。跨任務集中部署依卡片延後，停止時交代唯一下一入口。
4. 依文件設計→程式開發→部署前測試→部署→部署後live驗收執行；四個欄位是管理分類，不能顛倒live驗收的物理依賴。
5. 唯一業務定時入口為既有Cloud Scheduler兩小時總控；GitHub只作版本管理／CI／Release，無備份、清理或任何日常業務cron。
6. 正式角色只有Quant／Risk／Fundamental／Valuation，全部本版正式上線；採現有可發布artifact，不新增研究調校、重訓或第五模型。必要feature一致性與真實推論不可省略。
7. 不碰sources/；不新增付費資源／IAM、真實交易、production環境或不可逆擴大刪除。研究稽核精簡、Stage48h、current-files、Owner隔離與有效lease規則維持。
8. tests／Release以同SHA必要範圍為準，不能拿舊PASS替新版背書。若只剩遠端長任務等待，回報run連結後停止，按專案規則等待使用者接續。
9. 任何commit前依PROJECT_RULES做可用review；提交main，不另建branch/PR。更新TODO階段狀態及Operations必要收據，失敗保留事實；完成當前授權範圍後停止，不自動跨任務。
回報：SEQ-ID、階段、SHA、變更、實測結果／未驗點、deployment digest／migration（適用時）、rollback、下一個唯一入口。
```

使用例：`請執行 SEQ-01 的文件設計，依 doc/execution-cards/sequential-delivery.md，完成該階段並提交後停下。`
也可指定整項；若指定 SEQ-04／08，必須先具備卡內前置證據。文件存在不是啟動部署授權。

## 集中部署與驗收規則

SEQ-01→02→03 依序完成設計／開發／離線測試後交SEQ-04集中部署與live；SEQ-05→06→07依序完成前置後交SEQ-08集中部署與live。每項仍有完整四階段，部署欄明確指定執行者；不為形式重複發版。SEQ-04不因尚未完成四模型整合而假稱全產品已驗，SEQ-08不重跑仍有效的備份證據。

<a id="seq-01"></a>

## SEQ-01｜收取、清理與市場分析總控

整併來源：UB-01。負責角色：資料工程。
前置：使用者指定開工；本次文件提交不自動開工。
必讀：[spec/unified-batch-flow.md](../spec/unified-batch-flow.md)、[runbook-unified-batch-ai.md](../runbook-unified-batch-ai.md)、[runbook-batch-controller-dev.md](../runbook-batch-controller-dev.md)。程式入口從上述SPEC／WI的已確認路徑定位，勿猜不存在的命令。

| 階段 | 建議 AI | 直接執行指示／交付 |
|---|---|---|
| 文件設計 | GPT-6 Astra | 核對兩小時 tick、各業務 due、交易日／跨日、補缺→正常收取→Core ready→market-cycle 的依賴。確認 Stage 48h 與週維護不互相替代，TWSE／TPEx／FinMind 沿已核准 adapter、快取與限流收取，僅補實際缺口。 交付：更新對應SPEC的契約、輸入輸出、接受條件與回復界線。 |
| 程式開發 | GPT-6.1 Sol | 檢查並補完 batch_controller.py、unified_collection.py、runtime_entrypoint 與 market_cycle.py；處理來源真失敗、重複事件、五天 queue、有效租約、退役 pending 與 Admin freshness。重用現有工作，不新增逐股 Job 或業務 cron。 交付：最小程式差異、必要migration／測試來源與操作文件。 |
| 測試驗收 | GPT-6.1 Sol；模型／數值爭議用Astra | 依統一 WI A 執行相關 Python／Admin targeted tests；覆蓋台北換日、週末、重複觸發、ambiguous、部分失敗、8 次 claim／900 秒上限及 Stage 有效租約。live 條件留待 SEQ-04。 交付：真實指令、SHA、結果、未驗點；不得省略失敗。 |
| 部署 | GPT-6.1 Sol | 併 SEQ-04 一次部署既有 Controller／ingestion／Mart／API；本任務不單獨改 Scheduler。記為 DEFERRED_TO_SEQ-04，不能標已部署。 交付：實際image／版本與讀回，或指定集中部署的待辦引用。 |

退出條件：設計／程式／離線測試完成；部署與 live 由 SEQ-04 收據結清。
失敗處理：只修本項具體失敗；涉及金額／Owner／清理安全不得降低assert。部署失敗沿既有runbook恢復已知可用版本，保留失敗與回復證據。缺權限／artifact標明BLOCKED及所需輸入，不造PASS。

<a id="seq-02"></a>

## SEQ-02｜持股、買賣與觀察設定快照

整併來源：UB-03、4J／4R 的本次增量。負責角色：後端／產品工程。
前置：SEQ-01 的可交接階段完成；集中部署項須其前置任務的離線／Release證據齊備。
必讀：[spec/unified-batch-flow.md](../spec/unified-batch-flow.md)、[runbook-unified-batch-ai.md](../runbook-unified-batch-ai.md)、[ui/user-app.md](../ui/user-app.md)、[ui/reference/user-app-final/README.md](../ui/reference/user-app-final/README.md)。程式入口從上述SPEC／WI的已確認路徑定位，勿猜不存在的命令。

| 階段 | 建議 AI | 直接執行指示／交付 |
|---|---|---|
| 文件設計 | GPT-6 Astra | 明定原始交易／沖銷／修正／現金與 watchlist/profile 版本是權威；快照保存計算輸入與 ledger_version，不複製完整交易史。定義即時記帳、背景重算、快照時點、舊值提示、Owner 存取及私人快照保存／重建邊界。 交付：更新對應SPEC的契約、輸入輸出、接受條件與回復界線。 |
| 程式開發 | GPT-6.1 Sol | 補齊 PrivatePipeline、workspace_snapshots store、owner-scoped API 與必要 UI 接線；買賣／修正／沖銷／觀察設定異動後可對應新版本；內容去重不得吞掉需區分的時間／版本。先檢查現有實作再補差，不新增券商下單。 交付：最小程式差異、必要migration／測試來源與操作文件。 |
| 測試驗收 | GPT-6.1 Sol；模型／數值爭議用Astra | 測同 Owner 重跑冪等、A/B 隔離、未登入拒絕、日期與查詢上限、版本改動重算、缺行情／舊值顯示、刪帳號相容；使用 fixture，不新增使用者真實買賣。live 讀回併 SEQ-04。 交付：真實指令、SHA、結果、未驗點；不得省略失敗。 |
| 部署 | GPT-6.1 Sol | 併 SEQ-04 同版 Private／API／必要前端；保存舊 reader 相容與可回復 image。Iceberg 新表建立能力需驗證，不自動擴權。 交付：實際image／版本與讀回，或指定集中部署的待辦引用。 |

退出條件：離線測試通過；SEQ-04 證明既有 Owner 快照／API／必要 UI 一致後才整項 CLOSED。
失敗處理：只修本項具體失敗；涉及金額／Owner／清理安全不得降低assert。部署失敗沿既有runbook恢復已知可用版本，保留失敗與回復證據。缺權限／artifact標明BLOCKED及所需輸入，不造PASS。

<a id="seq-03"></a>

## SEQ-03｜日週月備份、保留清理與回復範圍

整併來源：UB-04（不是重開 OPS-P0-1）。負責角色：資料維運。
前置：SEQ-02 的可交接階段完成；集中部署項須其前置任務的離線／Release證據齊備。
必讀：[spec/unified-batch-flow.md](../spec/unified-batch-flow.md)、[spec/retention-governance.md](../spec/retention-governance.md)、[runbook-unified-batch-ai.md](../runbook-unified-batch-ai.md)。程式入口從上述SPEC／WI的已確認路徑定位，勿猜不存在的命令。

| 階段 | 建議 AI | 直接執行指示／交付 |
|---|---|---|
| 文件設計 | GPT-6 Astra | 逐類定義 PG 帳本／現金／觀察設定、GCS 私人快照、公開 Core/Mart、模型 artifact／報告的備份或重建方式。PG dump 不含 Iceberg data files；補清必要持久資料回復缺口，不承諾全歷史湖倉備份。維持 daily7／weekly4／monthly6、Stage48h、current-only／7日 orphan。 交付：更新對應SPEC的契約、輸入輸出、接受條件與回復界線。 |
| 程式開發 | GPT-6.1 Sol | 檢查 migration069、VM executor、ledger-durability、retention 與 Controller 分離狀態；補必要回復依賴／manifest 或既有路徑缺口。單次 dump 複用日週月副本，period 副本不覆寫；不得重新加入 GitHub 備份清理 cron。新付費備份／不可逆擴大刪除停在具體阻擋。 交付：最小程式差異、必要migration／測試來源與操作文件。 |
| 測試驗收 | GPT-6.1 Sol；模型／數值爭議用Astra | 依 WI 測跨週跨年跨月、副本碰撞、最新備份36h、generation drift、未知檔名、刪除上限3/1/1、備份成功清理失敗、migration重跑；列出隔離還原查核欄位。實際 restore／apply 留 SEQ-04。 交付：真實指令、SHA、結果、未驗點；不得省略失敗。 |
| 部署 | GPT-6.1 Sol | SEQ-04 先套 migration069，再以同 SHA 更新既有 PG VM executor/policy，再部署新版 Controller；停用衝突舊 timer。禁止覆寫 live DB、刪 current files 或 Owner 原始帳本。 交付：實際image／版本與讀回，或指定集中部署的待辦引用。 |

退出條件：測試及回復清單可執行；SEQ-04 完成新備份隔離回復／有界清理收據後結清。
失敗處理：只修本項具體失敗；涉及金額／Owner／清理安全不得降低assert。部署失敗沿既有runbook恢復已知可用版本，保留失敗與回復證據。缺權限／artifact標明BLOCKED及所需輸入，不造PASS。

<a id="seq-04"></a>

## SEQ-04｜基礎批次集中部署與兩小時切換

整併來源：UB-05：UB-01／03／04 合流。負責角色：發版／維運。
前置：SEQ-03 的可交接階段完成；集中部署項須其前置任務的離線／Release證據齊備。
必讀：[runbook-unified-batch-ai.md](../runbook-unified-batch-ai.md)、[runbook-dev-deploy.md](../runbook-dev-deploy.md)、[spec/cicd-v2.md](../spec/cicd-v2.md)。程式入口從上述SPEC／WI的已確認路徑定位，勿猜不存在的命令。

| 階段 | 建議 AI | 直接執行指示／交付 |
|---|---|---|
| 文件設計 | GPT-6 Astra | 彙總 SEQ-01…03 同一來源 SHA、變更／migration／VM／Job／API／前端清單，按 WI 定義回復基準及一次有界 live 範圍；不重做已通過且仍適用的離線測試。 交付：更新對應SPEC的契約、輸入輸出、接受條件與回復界線。 |
| 程式開發 | GPT-6.1 Sol | 只修合流發現的具體問題與部署腳本缺口，不在發版途中加入新功能；同版 source／digest 與 schema 前後相容。 交付：最小程式差異、必要migration／測試來源與操作文件。 |
| 測試驗收 | GPT-6.1 Sol；模型／數值爭議用Astra | 部署前取得同 SHA 必要 Release／auth gates；部署後一次驗證收取→Core→市場產物、Owner快照、日週月備份與隔離還原、清理保護、Admin，以及一個新 Scheduler occurrence。四模型／完整新報告尚由 SEQ-05…08 完成，不冒稱此處已驗全產品。 交付：真實指令、SHA、結果、未驗點；不得省略失敗。 |
| 部署 | GPT-6.1 Sol | 按 WI B 執行既有 Dev：保存舊設定→暫停單一 Scheduler／在途作業正常終態→migration069→VM→四 Jobs／API／必要前端→cron 30 */2 * * *、Asia/Taipei→讀回並恢復。失敗依 WI D 回復。GitHub 僅 CI／Release，無日常業務批次。 交付：實際image／版本與讀回，或指定集中部署的待辦引用。 |

退出條件：SEQ-01…04 原定有界條件 PASS；排程真實讀回，無需數週自然觀察。
失敗處理：只修本項具體失敗；涉及金額／Owner／清理安全不得降低assert。部署失敗沿既有runbook恢復已知可用版本，保留失敗與回復證據。缺權限／artifact標明BLOCKED及所需輸入，不造PASS。

<a id="seq-05"></a>

## SEQ-05｜Valuation 真資料、唯一估值卡契約

整併來源：RV-01…06、UB-02 的 Valuation 子功能。負責角色：估值／後端工程。
前置：SEQ-04 的可交接階段完成；集中部署項須其前置任務的離線／Release證據齊備。
必讀：[spec/valuation-range.md](../spec/valuation-range.md)、[research/valuation-rv01-serving-readers-2026-10-24.md](../research/valuation-rv01-serving-readers-2026-10-24.md)。程式入口從上述SPEC／WI的已確認路徑定位，勿猜不存在的命令。

| 階段 | 建議 AI | 直接執行指示／交付 |
|---|---|---|
| 文件設計 | GPT-6 Astra | 沿既有 RV reader／純函式，確認2330與2882現有資料可用性；定義四季同口徑 EPS／金融 BVPS、60月窗口至少24有效月、唯一價帶及缺值狀態；取消的歷史 PIT 稽核不復活。 交付：更新對應SPEC的契約、輸入輸出、接受條件與回復界線。 |
| 程式開發 | GPT-6.1 Sol | 補 RV-03 真實讀取所需接線與 RV-04 Mart／Fact Pack／API、RV-05 唯一估值卡及 A-CHANGE 整合；缺資料只補已確認必要範圍，ETF not_applicable。保留 event 舊 reader 相容，不新增第五 Registry role。 交付：最小程式差異、必要migration／測試來源與操作文件。 |
| 測試驗收 | GPT-6.1 Sol；模型／數值爭議用Astra | 重用有效 RV-02／03 測試，對改動補數值／單位／截止日／缺月／虧損／金融／ETF／API相容測試；真實2330／2882讀回若缺分母不得造價帶；UI 真實驗收併 SEQ-08。 交付：真實指令、SHA、結果、未驗點；不得省略失敗。 |
| 部署 | GPT-6.1 Sol | 功能程式併 SEQ-08 集中部署；只需讀取現有 Dev 的樣本不算新部署。RV-06 的完整發布證據由 SEQ-08 引用。 交付：實際image／版本與讀回，或指定集中部署的待辦引用。 |

退出條件：唯一估值值／狀態可由後端重算，離線測試與現有真資料讀回有證據；發布仍待 SEQ-08。
失敗處理：只修本項具體失敗；涉及金額／Owner／清理安全不得降低assert。部署失敗沿既有runbook恢復已知可用版本，保留失敗與回復證據。缺權限／artifact標明BLOCKED及所需輸入，不造PASS。

<a id="seq-06"></a>

## SEQ-06｜四模型正式上線模式、版本與共用快取

整併來源：UB-02、D07 serving、Risk API/UI、D07-CROSS-JOB-MODEL-CACHE；FACTOR-FACTORY／X/Y 僅必要 serving 一致性。負責角色：模型／推論工程。
前置：SEQ-05 的可交接階段完成；集中部署項須其前置任務的離線／Release證據齊備。
必讀：[spec/specialist-engines.md](../spec/specialist-engines.md)、[spec/model-lifecycle.md](../spec/model-lifecycle.md)、[spec/model-feature-time-contract.md](../spec/model-feature-time-contract.md)。程式入口從上述SPEC／WI的已確認路徑定位，勿猜不存在的命令。

| 階段 | 建議 AI | 直接執行指示／交付 |
|---|---|---|
| 文件設計 | GPT-6 Astra | 列 Quant／Risk／Fundamental／Valuation 四角色輸入、feature順序、artifact／schema／輸出與版本契約；以既有可發布模型接線，不把研究改善變前置。CEO不是第五模型，event僅相容事實。 四角色均以正式服務模式為交付，不留research-only或baseline作結案替代。只盤點並補本次推論所需的特徵與既有X/Y公式一致性，研究資料全面重整及調校留2027年第一季。 交付：更新對應SPEC的契約、輸入輸出、接受條件與回復界線。 |
| 程式開發 | GPT-6.1 Sol | 補既有 loader、GCS單次下載與execution內快取、批量推論、Mart／Fact Pack／Registry相容與Risk讀取；跨 Job 不假設共用RAM，不新增常駐服務／每股Job。模型 artifact 缺失須列角色與位置，不拿baseline假冒ML。 接手時逐角色定位既有可發布artifact並接正式loader／狀態；缺artifact是具體交付缺口，回報給使用者，不擅自啟動第二版研究。 交付：最小程式差異、必要migration／測試來源與操作文件。 |
| 測試驗收 | GPT-6.1 Sol；模型／數值爭議用Astra | 逐角色驗真artifact載入、train/serving特徵順序單位、輸出shape／缺值／版本、快取失效／回退；測非授權Owner資訊不進公開X。只有具體 artifact 缺口才 BLOCKED，不等待新20日cohort／全歷史PIT／重新訓練。 交付：真實指令、SHA、結果、未驗點；不得省略失敗。 |
| 部署 | GPT-6.1 Sol | 併 SEQ-08 固定 artifact／image 版本受控部署；Registry 狀態變更依實際 gate，保留上一可用版本，不能由「可發布規劃」直接改ACTIVE。 交付：實際image／版本與讀回，或指定集中部署的待辦引用。 |

退出條件：四角色真實推論與版本／快取測試有證據；runtime與UI驗收交SEQ-08結清。
失敗處理：只修本項具體失敗；涉及金額／Owner／清理安全不得降低assert。部署失敗沿既有runbook恢復已知可用版本，保留失敗與回復證據。缺權限／artifact標明BLOCKED及所需輸入，不造PASS。

<a id="seq-07"></a>

## SEQ-07｜分析報告、Owner history 與 UI 完整接線

整併來源：UB-02、D08、RV-05 合流。負責角色：全端／產品工程。
前置：SEQ-06 的可交接階段完成；集中部署項須其前置任務的離線／Release證據齊備。
必讀：[execution-cards/d08-ceo-admin-owner-report.md](../execution-cards/d08-ceo-admin-owner-report.md)、[spec/unified-batch-flow.md](../spec/unified-batch-flow.md)、[ui/user-app.md](../ui/user-app.md)、[ui/reference/user-app-final/README.md](../ui/reference/user-app-final/README.md)。程式入口從上述SPEC／WI的已確認路徑定位，勿猜不存在的命令。

| 階段 | 建議 AI | 直接執行指示／交付 |
|---|---|---|
| 文件設計 | GPT-6 Astra | 定義 Stage/Core日期→Mart／四角色→Fact Pack→站內事實報告／按需CEO→Owner history→今日／個股／持股／觀察頁資料契約。唯一估值卡由SEQ-05提供，數字由後端產出；顯示partial、版本、資料日期與上次成功。 交付：更新對應SPEC的契約、輸入輸出、接受條件與回復界線。 |
| 程式開發 | GPT-6.1 Sol | 補報告生成／保存／查詢、Owner history、Gateway按需摘要與UI；接SEQ-02快照、SEQ-05估值、SEQ-06四角色。修移動版必要呈現與重試／快取，不重開已結案全產品視覺工程，不加每日全市場LLM。 交付：最小程式差異、必要migration／測試來源與操作文件。 |
| 測試驗收 | GPT-6.1 Sol；模型／數值爭議用Astra | 對Fact Pack到報告API與UI做targeted／契約／必要widget測試；涵蓋單角色失敗、舊資料、缺行情、Owner隔離、重複請求、Gateway失敗退回事實報告；不得用LLM改canonical值。 交付：真實指令、SHA、結果、未驗點；不得省略失敗。 |
| 部署 | GPT-6.1 Sol | 併 SEQ-08 一次部署 Mart／Private／API／前端；按需CEO實測限既有授權Gateway，不新增供應商或付費模型。 交付：實際image／版本與讀回，或指定集中部署的待辦引用。 |

退出條件：產品鏈離線測試通過；真實資料／登入後UI與報告一致由SEQ-08結清。
失敗處理：只修本項具體失敗；涉及金額／Owner／清理安全不得降低assert。部署失敗沿既有runbook恢復已知可用版本，保留失敗與回復證據。缺權限／artifact標明BLOCKED及所需輸入，不造PASS。

<a id="seq-08"></a>

## SEQ-08｜四分析師到報告 UI 集中發布驗收

整併來源：UB-02 完成 gate、RV-06、D08 發布。負責角色：整合驗收／發版。
前置：SEQ-07 的可交接階段完成；集中部署項須其前置任務的離線／Release證據齊備。
必讀：[runbook-unified-batch-ai.md](../runbook-unified-batch-ai.md)、[runbook-dev-deploy.md](../runbook-dev-deploy.md)、[spec/cicd-v2.md](../spec/cicd-v2.md)、[ui/user-app.md](../ui/user-app.md)、[ui/reference/user-app-final/README.md](../ui/reference/user-app-final/README.md)。程式入口從上述SPEC／WI的已確認路徑定位，勿猜不存在的命令。

| 階段 | 建議 AI | 直接執行指示／交付 |
|---|---|---|
| 文件設計 | GPT-6 Astra | 鎖定SEQ-05…07來源SHA、四artifact、API/schema、前端與rollback；列2330、2882、既有Owner持股／觀察股的一次有界產品驗收，重用SEQ-04仍有效的排程／備份證據。 交付：更新對應SPEC的契約、輸入輸出、接受條件與回復界線。 |
| 程式開發 | GPT-6.1 Sol | 僅修整合與發布失敗；若改程式，重跑受影響測試與所需Release gate，不新增獨立workflow／排程。 交付：最小程式差異、必要migration／測試來源與操作文件。 |
| 測試驗收 | GPT-6.1 Sol；模型／數值爭議用Astra | 部署前同SHA必要Release／auth gate；部署後讀真四模型→Fact Pack→唯一估值卡→報告→Ownerhistory／快照→UI。驗證缺值／partial與版本對應，CEO按需一次。必要真人畫面無可用session時列精確待驗，不用負向401冒充成功登入。 正式發布四角色各有真實artifact版本、正式serving狀態與非fixture輸出；任一仍research-only／baseline替代即不算四模型上線完成。 交付：真實指令、SHA、結果、未驗點；不得省略失敗。 |
| 部署 | GPT-6.1 Sol | 既有Dev固定digest候選→受控Jobs→API一次100%→固定前端，保留上一可用版本；實際失敗才rollback。四模型發布與Risk狀態只按本次授權／證據變更，不藉研究線暗改。 交付：實際image／版本與讀回，或指定集中部署的待辦引用。 |

退出條件：SEQ-05…08原定條件PASS，產品整條路線可用；不等待後面研究改善。
失敗處理：只修本項具體失敗；涉及金額／Owner／清理安全不得降低assert。部署失敗沿既有runbook恢復已知可用版本，保留失敗與回復證據。缺權限／artifact標明BLOCKED及所需輸入，不造PASS。


## 分析Mart／報告增量的共同必讀

SEQ-01、05、06、07、08加讀[分析Mart規格](../spec/analyst-input-mart.md)與[四階段AI WI](../runbook-analyst-input-mart-ai.md)。沿上方原順序與模型建議，不另開分線。程式已加入15月補收、分析artifact與週期事實報告；四個真模型schema／Valuation mapping／UI接線仍按各卡完成，不能誤當已上線。每日行情／風險資料照常，完整事實報告週期＋異動，CEO按需。
