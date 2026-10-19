# Janus｜專案管理與文件治理

更新：2026-10-19。此文件管理**唯一待辦、文件責任、驗收與重大風險決策**，不取代 [PROJECT_RULES](PROJECT_RULES.md)，也不建立第二份 TODO。Dev 是現有真實 parallel-live；本次文件作業沒有直接執行 Cloud Run、Scheduler、migration 或訓練。

## 1. 各文件只做一件事

| 文件 | 唯一責任 | 不應保存 |
|---|---|---|
| [PROJECT_RULES](PROJECT_RULES.md) | 授權、成本、安全、canonical/LLM/source/PIT、Dev 工程與完成規則 | 每輪 execution、暫時工項 |
| [README](README.md) | 最短導覽／領域文件地圖 | 待辦與版本流水帳 |
| [status](status.md) | 最新有證據的結案與仍未驗狀態 | 多輪歷史部署／舊進度 |
| [TODO](todo.md) | **唯一 active queue、順序、scope、acceptance** | 已完成項詳細 checklist、過去 run ID |
| [WBS](wbs.md) | 工作責任與相依；what | 同任務第二份待辦 |
| [SPEC](spec.md)／[UI](ui.md) | 合法資料、API、source/PIT/retention、產品與畫面；correct | 當前進度與逐次 release |
| [AI 指令](codex-execution-plan.md)／[任務卡](execution-cards/README.md) | 如何執行、tests/CI、deploy、失敗復原；how | 自動執行授權或另一組優先序 |
| [Runbook](runbook-batch-controller-dev.md) | 現有 Job／Scheduler／資料修復安全操作 | 歷史 Cron 當最新設定 |
| [Operations](spec/operations-and-testing.md)／[Pilot](pilot-operational-evidence.md) | 時間戳、SHA、真實證據及未驗點 | 設計與執行佇列 |
| [Archive](archive/README.md) | 舊版、已結案與被取代的完整原文 | 目前需執行的命令 |
| [Parking Lot](parking-lot.md) | 暫緩、未核准、production-only／構想 | 當前必做任務 |

入口：`AGENTS.md → PROJECT_RULES → status → TODO → 指定任務卡 → 最少相關 SPEC/code/tests`。最新 runtime/code 優先於舊文件。Drive 只主動在白名單 `janusChatGPT` 內查原始設計，不能用 Drive 研究文件替換目前 GitHub/runtime 真相。

## 2. 接下來的唯一施工順序

**D07-PRE → D07 → D08**。D01–D05、DRL-01、FINOPS-AB＋D06、Admin v2 與持股／關注背景補收，按既有 evidence 完成範圍已閉環，**不能把其舊卡／WBS 歷史 blocker 又變新 TODO**。原 FINOPS-C 的資料／成本評估與 Colab 研究現在只屬**D07-PRE 一個工作包**，不另建立 BigQuery 工程前置或第二 Scheduler。

D07 資料/模型的唯一目標為：Core 合格資料固定匯出 → **Colab 做研究資料 Join/feature/labels、rolling 24 月訓練與 OOS** → 版本化模型/評估 → Janus Mart 驗收/正式推論。只有 Colab 大資料瓶頸有實測與授權才加入 BQ SQL 前置縮減；不使用 BQML 或 Cloud Run 替代訓練。現行 Mart retrain 程式未改，不能因文件承諾而稱已遷移。

## 3. AI 作業與完成分層

收到一個工項：核對 TODO 授權、GitHub `main` 最新 SHA 和現有 runtime → 查該工項最少必要 SPEC／code → 使用原工具最小變更 → targeted tests／CI → 若工程範圍要求，dev deployment/migration/Job/自然 workload 及真實 readback → 失敗修復或安全回退 → evidence 入 Operations、狀態只入 TODO。多 AI 同在 main 要核對 HEAD／deployment lease，不能覆蓋彼此工作。無付費／重大擴權／破壞性資料修改的新授權不得自行進行。

| 層級 | 只能宣稱 |
|---|---|
| 文件／決策 | `DOC_UPDATED/DESIGN_DECIDED`，非工程 |
| Implementation + tests | `IMPLEMENTED/TARGETED_PASS`，不能當上線 |
| CI／Release／migration | 指定 SHA、digest、run、migration 之證據 |
| 自然排程／資料 | Worker terminal、schema/來源、Core/Mart/PG/API／source 時點讀回 |
| 模型 | 成熟樣本、baseline vs OOS、PIT/leakage/來源授權；fit≠quality |
| 產品 | Auth/Owner、UI、真實報告和 rollback；部分成功必標 `PARTIAL` |

## 4. 重大風險及選項

以下 **A 是未決前可維持的保守工作邊界，不是代替你做永久決策**。涉及費用／付費 API、IAM 擴張、Source 授權、不可逆操作，須取得使用者明確同意。

| 風險 | A：保守方案 | B：必要時升級 | 目前影響 |
|---|---|---|---|
| **R1 免費 Colab 不保證每月無人值守** | **【使用者已選 A｜2026-10-19】人工啟動／留 hash 與 execution receipt，Janus 原月度 Controller 只登記／驗回；沒跑就 pending** | **暫不執行、不列現階段驗收門檻**。日後若使用者另提需求才評估官方受控託管／排程及費用／OAuth/IAM | 決策已結；Colab 實跑、receipt 對接仍須 D07-PRE/D07 工程驗證，免費版 auto retrain 不需實作 |
| **R2 全市場 24 月研究 vs Core 一般365天** | **用實際有效資料及合規 frozen Parquet 累積，缺的月份標 insufficient** | 有界擴充合法歷史回補／研究保存，但先核成本、來源及回復路徑 | 24 月是模型窗口目標，不是已實收 |
| **R3 Current-only snapshots 與歷史 as-known PIT** | **`strict_pit=false` 限研究，保留 hash/source/time availability；沒有證據不對外說嚴格 PIT** | 額外引入歷史版次/first-observed 有憑據的來源與 frozen PIT replay，先核授權／成本 | 嚴格 PIT／publication 與研究品質 gate 分開 |
| **R4 資料帶往 Colab 的 training-use／Owner 安全** | **只允許合規公開研究特徵、短效／最小權限，不帶 Owner/secret** | 新來源/第三方外部訓練授權不足時評估合約或替代合法來源 | 缺授權就不送 Colab，不補造 |
| **R5 FINOPS 實際刪除和成本節省未清楚核實** | **唯讀原已執行 Job receipts 算 objects/bytes，不能拿候選數當實刪** | 真實 I/O／費用仍過高時另決定有界優化／必要 BQ 前處理 | 已結案 scope 不重跑 destructive cleanup |

**R1 已定案 A（人工執行 Colab）**，本階段不追求免費版無人值守能力，不把它當 D07-PRE 阻擋；只要求可人工操作且有不可變結果及 Janus 驗收收據。**R2／R3 尚未選定擴大資料取得或歷史版次建置**；先按現有資料做有界、合法研究並精確盤點，再由使用者選擇是否補全，不能自動批准新增付費、不可逆資料操作或 IAM 擴張。嚴格 PIT 模型 promotion 的未通過條件仍不放寬。

## 5. 封存與防止文件重新膨脹

已結案 release/事故、日期快照、舊 Admin 六頁規格、當時的資料/批次盤點移入 `archive/`，保留原始證據與當時 FAIL，不用舊狀態當現在工作。仍會被程式、CI、active SPEC／Runbook 使用的文件先查連結再搬；本次不隨意刪源碼、Migration、附件或其他專案 Drive。正式治理修改須同步最小入口，而不是每個 WBS、README、UI 都複寫一份 TODO。


## 6. 2026-10-19 R2／R3 可量化缺口之證據界線

- **R2（24 月全市場 OHLCV 規模）**：按 [因子容量矩陣](spec/factor-coverage-retention-ledger.md) 之規劃情境，1,992 股×每年約250日×兩年＝**996,000 股日組合**；[2026-10-18 Core census #39083283620](https://github.com/tommylin15/janus-omniforge/actions/runs/39083283620) OHLCV 為 **111,929 筆**。**884,071／88.76% 是兩個不同母體及口徑的規劃算術差額，不是實際去重後缺口率，不授權按該差額盲抓。** 缺少 historical membership/退市、dataset/date/market/symbol 去重、上市停牌、fresh 10/19 全量 COUNT、eligible feature/label/PIT 排除後分母。B5 固定 Parquet 499 股、10,978 row、2026-03-19～09-03，僅約5.5個曆月日期跨度，不能當作全市場24月。一般 Core OHLCV row TTL 365 天，亦不等於實際每股已有滿一年。
- **R2（六股重點 OHLCV 的局部量化）**：2026-10-19 背景補收範圍的 1513／2382／3231／3711 各158日、2327／5876 各200日，**1,032股日**；與兩年近似 6×500＝3,000 相比，**帳面差1,968股日（65.6%）**，不扣停牌／生效資格／日期缺口，僅供 sizing。這六股的 25月 PE/PB已 ready，**不可用 OHLCV 差額推論估值亦缺 65.6%**。證據：[舊 TODO 的 10/19 8檔讀回](archive/todo-before-consolidation-2026-10-19.md)。
- **R3（嚴格 PIT 缺口）**：當前**沒有可驗證的全市場分母、通過筆數、缺少歷史 original-published／first-observed/version 的分項 COUNT**，所以 `unknown`，不能聲稱 PIT 缺 100% 或 0%。2026-10-19 Janus 公開 MCP bounded readback 中 5876 財報樣本具有 `observed_at`／`availability_at`、部分 `published_at`，但 `publication_time_authoritative=false`、`numeric_revision_verified=null` 等未證明歷史原版數值；樣本不能推論全體。已核准財報 `strict_pit=false` 僅 research-only，Core/Mart current-only Iceberg snapshot 不可用文字 ID 重建歷史 as-seen。
- **R3（舊模型逐筆 provenance 確知缺口）**：[B9 實測](b9-quality-evidence.md) 明列歷史 **1,536筆 v4 prediction records** 無逐筆 source authorization／sample provenance，故該**固定舊版本的 1,536／1,536 需視為逐筆證據未驗**；新 v5 schema 只適用未來新資料，不能補造舊歷史 as-known。此 1,536 不等於全市場 PIT 原始資料缺筆總數，真正全體分母仍 UNKNOWN。
- **D07-PRE 唯一精查產物**：按 `dataset × market × symbol × calendar_month × horizon × source` 輸出預期/有效/缺失股日與 coverage%，再按 `available_at_evidence (official_timestamp / verified_first_observed / assumption / unknown) × revision_trace × training_use_authorization` 輸出嚴格 PIT 合格與不合格／UNKNOWN 分子分母。24 月 window 與 5/20/60/120日成熟 label、purged OOS/holdout 分開計；未有稽核無法給具體回補清單或每個角色之缺口百分比。不另建 R2／R3 WBS。
