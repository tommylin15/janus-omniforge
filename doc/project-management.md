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
| **R1 免費 Colab 不保證每月無人值守** | **人工啟動／留 hash 與 execution receipt，Janus 每月 Controller 只登記／驗回；沒跑就 pending** | 評估官方受控託管／排程、費用與 OAuth/IAM，授權後才自動化 | 新 Colab auto retrain 未驗證；不在 GCP 暗中再 fit |
| **R2 全市場 24 月研究 vs Core 一般365天** | **用實際有效資料及合規 frozen Parquet 累積，缺的月份標 insufficient** | 有界擴充合法歷史回補／研究保存，但先核成本、來源及回復路徑 | 24 月是模型窗口目標，不是已實收 |
| **R3 Current-only snapshots 與歷史 as-known PIT** | **`strict_pit=false` 限研究，保留 hash/source/time availability；沒有證據不對外說嚴格 PIT** | 額外引入歷史版次/first-observed 有憑據的來源與 frozen PIT replay，先核授權／成本 | 嚴格 PIT／publication 與研究品質 gate 分開 |
| **R4 資料帶往 Colab 的 training-use／Owner 安全** | **只允許合規公開研究特徵、短效／最小權限，不帶 Owner/secret** | 新來源/第三方外部訓練授權不足時評估合約或替代合法來源 | 缺授權就不送 Colab，不補造 |
| **R5 FINOPS 實際刪除和成本節省未清楚核實** | **唯讀原已執行 Job receipts 算 objects/bytes，不能拿候選數當實刪** | 真實 I/O／費用仍過高時另決定有界優化／必要 BQ 前處理 | 已結案 scope 不重跑 destructive cleanup |

**需優先由使用者選定**：R1（人工或另外取得可自動的 Colab 方案）、R2（接受分段／稀疏歷史還是另擴充回補）、R3（維持研究級 PIT 還是投資更完整歷史版次）；決定前只做保守、合法、有界研究，受影響正式模型 promotion／自動化維持 `BLOCKED/NOT_VERIFIED`。不要自動選新增付費、破壞性資料刪除或 IAM 擴權。

## 5. 封存與防止文件重新膨脹

已結案 release/事故、日期快照、舊 Admin 六頁規格、當時的資料/批次盤點移入 `archive/`，保留原始證據與當時 FAIL，不用舊狀態當現在工作。仍會被程式、CI、active SPEC／Runbook 使用的文件先查連結再搬；本次不隨意刪源碼、Migration、附件或其他專案 Drive。正式治理修改須同步最小入口，而不是每個 WBS、README、UI 都複寫一份 TODO。
