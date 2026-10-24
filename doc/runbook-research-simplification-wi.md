# WI｜研究精簡版本驗證與部署交接

日期：2026-10-24。原清理輪次僅修改文件與程式；**後續離線測試已 PASS，dev 部署與 runtime 驗收尚未執行**。本文件保留可重跑操作指示，不建立另一份 TODO。

## 已改內容

| 對象 | 變更 | 部署前現況 |
|---|---|---|
| Controller `BATCHES` | 移除週六 `data-quality`；舊 pending 由現有 `schedule_superseded` 跳過 | 新程式未上線 |
| `data_quality.run_quality` | 移除重抓財報／12月營收、Core掃描、Stage寫入、品質帳本；回 skipped | 舊映像仍可能執行舊邏輯 |
| `data_supplement` | 不再讀舊品質 issues 觸發歷史重抓；正常缺期增量保留 | 同上 |
| Mart `specialist_runtime` | 刪除重複 Risk 品質運算／GCS risk-quality 寫入；相容欄位為 null | 正常預測輸入驗證保留 |
| Admin | 移除品質批次、未實作月度模型檢查占位、週六品質卡與該卡資料請求 | API／Flutter 待發布 |
| 研究貼標 | 歷史產業檢查預設 NOT_REQUESTED；明確 `--require-industry` 才啟用 | 既有產業因子不自動新增 |
| Risk promotion | 移除全歷史／新cohort的無條件 exit 1；仍需提供實際技術檢查值 | 不自動 ACTIVE；沒有改 ops activation request |
| 獨立 Risk preflight CLI | 不再連 GCS 列舉／下載歷史 shadow；回 NOT_REQUESTED | 工具不代表模型認證 |
| 5 個獨立稽核 Workflow | 移至 `.github/workflows/archive/*.yml.disabled` | main 更新後無新觸發入口；既有進行中 run 不由本次取消 |

五個入口：`governance-metadata-readonly`、`feature-readiness-metadata-census`、`drl01-live-continuity-audit`、`full-market-inventory-readback`、`p02-readiness-diagnostic`。

## 保留與未刪的範圍

保留日期／單位／必要欄位與數值、模型基本 cutoff/X-Y 防洩漏、訓練與推論一致、auth／owner、lease／防重派、current snapshot／generation 刪除保護、備份與36h清理保護。這些直接避免錯算或誤刪。

不刪任何真實 table、column、GCS object、研究 frozen input；schema 中現有 provenance/hash/time 欄位保持相容。既有正常資料入庫仍可能保存 manifest/hash，屬既有 writer/reader 契約，並非新增獨立稽核。本次沒有逐一移除所有資料路徑的 metadata 檢查。

`monthly_reconciliation.py` 為目前無日常 caller 的歷史工具，未新增排程；研究評估函式、純資料檢查函式保留按需用途。週維護的 EOD/current snapshot 安全邊界保留，不以「時間校準」名義拔掉刪除保護。

## 1. 取得本次程式

讀最新 main 的 `AGENTS.md`、`doc/PROJECT_RULES.md` §0、本 WI、`doc/todo.md`。確認沒有其他 AI 覆蓋本次變更。不要把取消的稽核重新列成門檻；不要還原退役 Workflow。

原始程式清理 commit 使用 `[skip ci]`；後續於 Git SHA `6e1de4f010b29eb347e5a3785f3b5846dc580b8f` 執行 CI 與離線測試並取得 PASS。`/ponytail-review` 在執行環境不可用，改採 diff／契約／CI 結果審查；不偽稱執行該命令。

## 2. 有界離線測試（2026-10-24 PASS）

測試來源與結果（均為 2026-10-24 GitHub Actions 日誌，非 runtime acceptance）：

- [Selective CI #40080225057](https://github.com/tommylin15/janus-omniforge/actions/runs/40080225057)：`controller` 99 passed，成功。
- [離線測試 #40080225060](https://github.com/tommylin15/janus-omniforge/actions/runs/40080225060)：`ingestion-and-admin` 64 passed（1 warning）；`risk-and-mart` 77 passed（7 warnings）；`research` 19 passed；`flutter-admin` 5 passed；5 個已退役 Workflow 均無現役 `.yml` 入口。
- Python 累計 259 test executions passed；Flutter 5 passed；無測試失敗。警告不代表 test failure，仍須以真實功能異常為修復依據。
- 一次性離線測試 Workflow 在成功後自 `main` 刪除；保留 Actions Run 日誌作驗證依據。**下一步僅第 3 節 dev 部署與第 4 節一次功能驗收，不能提前標 PASS。**

重跑時先安裝 repository 現有必要依賴，再執行：

```bash
PYTHONPATH=jobs/ingestion-core:jobs/intelligence-mart:. python -m pytest -q \
  tests/test_batch_controller.py tests/test_data_quality.py \
  tests/test_data_supplement.py tests/test_admin_batch_dashboard.py \
  tests/test_industry_membership_preflight.py \
  tests/test_risk_inputs.py tests/test_risk_active.py tests/test_risk_shadow.py \
  tests/test_risk_feature_parity.py tests/test_risk_registry_cas.py \
  tests/test_risk_promotion_preflight.py
```

在 `apps/user_app` 執行：

```bash
flutter test test/admin_overview_batch_test.dart
```

針對 Mart 修改另找實際 `specialist_runtime` 整合測試並跑受影響集合。舊測試若只要求週品質／月度占位／預設產業稽核，改驗退役行為；不得把模型錯算、權限或資料刪除安全的失敗直接豁免。

必驗行為：

1. 週六及平日均不建立 data-quality；既有 pending 不派送、Admin 不允許 start。
2. 直接呼叫 quality 入口無 HTTP／PG／GCS，回 skipped 而非 passed；舊 quality issues 不驅動補收。
3. 正常增量、私人損益、每日備份、Stage 48h、週 Iceberg 的排程與防重派未壞。
4. 貼標預設不呼叫 industry checker；明確 require 選項仍檢查；X/Y 不互相污染。
5. Risk 不寫新 risk-quality artifact，但有效模型預測與拒絕壞輸入仍正常；舊 manifest 可讀。
6. activation 缺真正技術檢查仍被拒絕；不以政策更新產生全 PASS。這次驗收不必啟用 Risk。
7. Admin 無已退役品質卡／月度假工作，其他卡片資料索引仍正確。

Workflow YAML 及變更路徑做一次靜態檢查即可，不觸發已退役稽核。失敗只修受影響範圍，不重跑全市場來源稽核。

## 3. 發布既有 dev

使用 `doc/runbook-dev-deploy.md` 的既有 GHCR release／Jobs rollout／API／Flutter 路徑。不要建立新 Cloud Build、Scheduler、Job、bucket 或付費服務。部署前留現用映像／設定以便恢復；Controller 與 ingestion 必須都換新版，否則移除排程但手動入口仍可能跑舊品質程式。

部署時檢查是否有正在執行的舊品質 Job；有則讓它正常結束，不直接取消共用 ingestion。尚未部署不得稱已節省 GCP 用量。

## 4. 一次功能確認

使用既有受控入口做一次 Controller 處理，確認 runtime definitions 不含 data-quality，舊 pending 為 skipped。確認正常批次仍可用。可利用一次正常 Mart 結果及 Admin 畫面確認品質 artifact／卡片停止新增；不要新增一輪全市場計算只為證明沒有報告。

備份只確認一份實際可讀／可用的新備份，保留清理安全條件；若仍有真實錯誤修該錯誤，不要求等自然 schedule event、不新增探針。既有 GitHub 每日 retention 及正常 Cloud Scheduler 保留。

不要求全歷史來源追溯、逐日 PIT 重建、新20日成熟 cohort、月度報表或六個月觀察才能結案。代表功能一次正常、無具體錯誤即可收尾。

## 5. 回復與回報

若新版使正常收集／推論／備份出錯，回復上一可用映像；程式可 revert 本次 commit，不回寫或刪除真實資料。只記版本、測試結果、部署結果與具體未解錯誤；取消工作記 CANCELLED，不記 PASS。

## 可直接交給其他 AI

> 執行 Janus main 的 `doc/runbook-research-simplification-wi.md`。本次任務是驗證並部署研究精簡版本，不是重新做資料治理。先讀 PROJECT_RULES §0，取消逐來源／全歷史 PIT／精確時間稽核、週月稽核及自然等待。跑本 WI 的受影響測試，修實際問題後沿既有 dev 發布；只做一次功能確認。保留 auth、Owner、必要日期／單位、基本防洩漏、正常收集推論、備份與刪除安全。不要新增付費資源、不大量刪資料、不自動啟用 Risk、不恢復退役 Workflow。回寫唯一 TODO 與 janusChatGPT，報告真實測試／部署結果；未執行不得寫 PASS。
