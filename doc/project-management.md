# Janus｜專案管理與文件治理

> **2026-10-24 研究精簡決策優先**：本文涉及獨立資料稽核、逐來源補證、全歷史 PIT／精確時間校準、例行週月稽核及自然驗收等待的要求已取消，不再是待辦或發布前置。依 [研究精簡政策](spec/research-simplification.md)，保留必要日期／單位、基本防洩漏與操作安全；歷史證據不改判 PASS。


更新：2026-10-24（多線依賴管理補正）。此文件管理**唯一待辦、文件責任、驗收與重大風險決策**，不取代 [PROJECT_RULES](PROJECT_RULES.md)，也不建立第二份 TODO。Dev 是現有真實 parallel-live；本次文件作業沒有直接執行 Cloud Run、Scheduler、migration 或訓練。

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

## 2. 唯一 Active TODO、多線排序與研究資料責任（2026-10-24）

- **執行佇列唯一**：[TODO §1](todo.md)；**責任與先後/平行路由唯一**：[WBS 工作線矩陣](wbs.md)；**事實證據**：[Operations](spec/operations-and-testing.md)。本頁不保存第二份逐項進度。
- P0 是 P0-2 57 筆無有效 lease 逐筆安全收斂及 P0-1 自然排程驗證；不以此全面凍結獨立 research。P1 A-CHANGE 既有工程驗收／Janus 2.0 改良、RV-01…06 Valuation Range、研究資料包 preflight/C1-A reader 盤點 **可分線**。P2 Quant/Risk/Fundamental/Valuation 依凍結資料獨立做 OOS，P3 D08 事實報告可先做，不必等五模型一起可部署。
- **嚴格合流**：Controller/lease/retention apply 串行變更；frozen release/hash、canonical writer 和 migration 需一致；Risk §1.12 未達 gate 維持 DETERMINISTIC；公開 Fact Pack/Owner API 及 RV-05 合流測真實 UI。第五角色由 [新 SPEC](spec/valuation-range.md) 取代 Event 模型，但 event 原始事實/公告提醒保留。
- D07-PRE 原有 21 月 OHLCV / Drive 收據與新 v3.8.4 research release 是不同版本，不互相冒充 full pass；Colab 人工啟動、可追溯增量，X/Y 與評估於現行 ChatGPT 研究流程；舊 GCP/BQ retrain 已退休，不能重啟。資料與模型 research-only 不可替代正式 PIT/source/promotion。
- D01～D06、DRL-01、FINOPS-AB 依原有有界收據結案，不把 2.0 重新定義成其遺漏驗收；資料治理 C1-B 未取得許可不得刪表欄或自行觸發 destructive apply。

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
| **R1 免費 Colab 不保證每月無人值守** | **【使用者已選 A｜2026-10-19】人工啟動／留 hash 與 execution receipt，Janus 僅於受控模型匯入／驗證記錄新結果；舊月度 Controller 不再建立 pending fit** | **暫不執行、不列現階段驗收門檻**。日後若使用者另提需求才評估官方受控託管／排程及費用／OAuth/IAM | 決策已結；Colab 實跑、receipt 對接仍須 D07-PRE/D07 工程驗證，免費版 auto retrain 不需實作 |
| **R2 全市場 24 月研究 vs Core 一般365天** | **用 Colab／Drive 研究月檔與合格版次累積，缺月份明示；不依賴Core365天保存** | 有界擴充合法歷史回補／研究保存，但先核成本、來源及回復路徑 | 24 月是模型窗口目標，不是已實收 |
| **R3 Current-only snapshots 與歷史 as-known PIT** | **`strict_pit=false` 限研究，保留 hash/source/time availability；沒有證據不對外說嚴格 PIT** | 額外引入歷史版次/first-observed 有憑據的來源與 frozen PIT replay，先核授權／成本 | 嚴格 PIT／publication 與研究品質 gate 分開 |
| **R4 資料帶往 Colab 的 training-use／Owner 安全** | **只允許合規公開研究特徵、短效／最小權限，不帶 Owner/secret** | 新來源/第三方外部訓練授權不足時評估合約或替代合法來源 | 缺授權就不送 Colab，不補造 |
| **R5 FINOPS 實際刪除和成本節省未清楚核實** | **唯讀原已執行 Job receipts 算 objects/bytes，不能拿候選數當實刪** | 真實 I/O／費用仍過高時另決定有界優化／必要 BQ 前處理 | 已結案 scope 不重跑 destructive cleanup |

**R1 已定案 A（人工執行 Colab）**，本階段不追求免費版無人值守能力，不把它當 D07-PRE 阻擋；只要求可人工操作且有不可變結果及 Janus 驗收收據。**R2／R3 尚未選定擴大資料取得或歷史版次建置**；先按現有資料做有界、合法研究並精確盤點，再由使用者選擇是否補全，不能自動批准新增付費、不可逆資料操作或 IAM 擴張。嚴格 PIT 模型 promotion 的未通過條件仍不放寬。

## 5. 封存與防止文件重新膨脹

已結案 release/事故、日期快照、舊 Admin 六頁規格、當時的資料/批次盤點移入 `archive/`，保留原始證據與當時 FAIL，不用舊狀態當現在工作。仍會被程式、CI、active SPEC／Runbook 使用的文件先查連結再搬；本次不隨意刪源碼、Migration、附件或其他專案 Drive。正式治理修改須同步最小入口，而不是每個 WBS、README、UI 都複寫一份 TODO。


## 6. 歷史研究缺口（不再是收集前置）

舊 B5/B8 Core census、24月 PIT 缺口與完整 frozen Parquet 的估算僅為歷史研究證據，可由 Git 版本查詢；**不能作 D07-PRE Colab 來源、月份或開工 gate**。新的第一批欄位清單、研究70%分母與 Colab OOS 分別按 [新契約](spec/research-collection-gas-drive-colab.md)／[TODO](todo.md) 建立真實證據。
