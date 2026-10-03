# 五分析師長期資料驗收前歷史 checkpoint

## 刪除治理上版前 checkpoint（2026-10-03，尚未 dev 驗收）

- 最新決策與範圍見 [刪除治理契約](retention-governance.md)：Stage／quarantine 7 天，每個股五分析師最新 3 代，OOS 僅留最新仍使用結果；淘汰 execution 拒絕舊 replay。既有 Core／Mart 資料期限及必要快照保護保留；Core manifest 淘汰須提供新鮮有效引用清單。
- 本機 `tests/test_data_retention.py`：13 passed，包含未提交／異常資料到期清理、active execution 保護、名單變動時各股獨立保留 3 代、OOS 淘汰、重跑清理冪等性與 Core manifest 引用保護；五分析師 immutable runtime targeted check 1 passed。此 checkpoint 不代表 dev deployment 或實際刪除已完成。
- GCS 只讀盤點：Core warehouse live 86,442,645 bytes，Mart warehouse live 14,109,734 bytes；包含資料與快照相關檔案，不是舊快照獨立占用量，也不代表全部版本的計費容量。

## 最新：五分析師引擎與舊角色移除（2026-10-03，partial）

- 舊生成式每日五角色的引擎、prompt、compatibility、provider execution 與舊契約已刪除。新五分析師採規則/數學/本機 ML evaluator 與中文模板，沒有 publication/CEO 權限；整體 WBS 尚未完成。契約與缺口見 [specialist engines](specialist-engines.md)。Shared CEO auth/routing 保留，未執行下一個 CEO WBS。
- 本機跨模組 tests 121 passed，Flutter widget tests 21 passed，shell syntax 與 workflow YAML 檢查通過。LightGBM/CatBoost/Linear 的 fixture fit 只驗證演算法與漏資料防護，不能當台灣 OOS evidence。免費 pip-audit 83 個鎖定依賴修正 urllib3 2.8.0 後零已知漏洞，未使用付費 Artifact Analysis。
- Commit `289cbd8` 的 dev CI `37110616356` 全部 success，Mart immutable image `sha256:b4a9ff3760c44c43da3ec149a50de471e64ef578f1180237c0d3b467ba14616c`；後續 source-authorization/security/bounded-read 修正仍由同一 canonical dev workflow 部署。
- 真實 Cloud Run execution `janus-intelligence-mart-6gfgn` succeeded，1 CPU / 1 GiB，程式時間 281.532 秒，peak RSS 501.34 MiB，500 screening / 3 Deep Coverage / 15 specialist / 0 LLM token。成果物 manifest `gs://gen-lang-client-0593591102-dev-mart/executions/9f1aea1f-171b-4dd3-b174-5e3030cf74cb/specialist-manifest.json` 與 15 份 artifact 讀回 SHA-256 相符；10 partial / 5 blocked，沒有升級為完整成功。
- Core fence `sha256:cb5a66d91253699dbc66930a3fbfb6d0f496255ae3b8ef0112398afb73335e09`：500 中只有 5 檔具 5/20/60/120 日報酬歷史，其他如實缺值；254 個財報 evidence 缺 availability time，被 Fundamental/Valuation 排除；一筆 Event future leakage 被排除。既有補資料 runtime 僅支援 1..50 TWSE symbols 與 receipt-based historical availability，不能當已具 500 台股歷史 PIT 母體。
- 真實 OOS execution `janus-intelligence-mart-scdmv` 成功，程式時間 136.182 秒、peak RSS 445.95 MiB，15 份 specialist 全部內容重用。evaluation 讀回 SHA 相符；Linear/LightGBM/CatBoost × 5/20/60/120 日共 12 組均 insufficient_history、0 OOS folds／0 predictions，regime 只有 149 returns，不升格 champion 或補假機率。
- Commit `26467fc` 的 dev CI `37114815184` tests／ingestion deployment／Mart deployment／verify 全部 success。Mart Ready，immutable image `sha256:eada4d2b9ad089a1a95bea7f8ba005c078c4243044b8d0b9a1595ceda5294a35`，讀回仍為 1 CPU / 1 GiB。本次針對 PIT 台北日界線、相同 5 日排名、保留其他 Core table fences 的 targeted tests 75 passed；後續 ingestion tests 25 passed。
- 使用者核准簡單補最近 21 個交易日，既有 ingestion execution `janus-ingestion-core-xx92k` succeeded。真實日期 2026-09-02 至 2026-10-02 共 21 天，處理時間 341.418 秒，來源 failures=0；Core created=22,009、reused=11,260。coverage inventory 與 Core manifest 讀回 SHA 相符：每日合格 OHLCV 498..500／500，最新 498／500（缺失 0.4%）；完整 21 天 496／500（缺口 0.8%），均在使用者 10% 容許內，不追加複雜補資料。未同時補其他 datasets，因此 ingestion overall partial，不代表行情整批失敗。
- 新 Core fence `sha256:e5abb77829b2df23b24054e94974ee772d4f02c93619726bd854e897fff7f80a`，snapshot URI `gs://gen-lang-client-0593591102-dev-core/executions/230c9fe1-c787-4ec5-b343-ebf78c2d3019/core-snapshot.json`。新版五分析師／OOS acceptance `janus-intelligence-mart-vc7tw` succeeded，處理 160.708 秒、peak RSS 471.67 MiB、500 screening／3 deep／15 specialist／0 LLM API token。最新行情 498／500、5 日指標 500／500、20 日指標 496／500 均 accepted；60／120 日只有 5／500，另外標示 discussion_required、auto_fail=false，沒有擴大補資料。
- 最終 specialist manifest `gs://gen-lang-client-0593591102-dev-mart/executions/10e4c524-5f6b-4162-a39a-044831994818/specialist-manifest.json`，SHA `sha256:f48f2a608909c6c89dc7b5bb9297bc78ceb9ee6dddfac4fc7407614953a174eb`。Manifest 與 19 份 references（market membership／deep targets／screening／OOS／15 specialist）全部 raw-byte SHA 讀回相符；10 partial／5 blocked。12 組 Quant evaluator 仍 0 folds／0 predictions，另 1 組 regime insufficient_history，沒有任何 promotion；短期篩選可用不等於完整五模型/OOS WBS 完成。
- Migration 039 已在既有 dev PostgreSQL 真實套用，僅新增去識別化 public-market projection EXECUTE，不授予私人表讀取。Mart 固定 1 CPU / 1 GiB 並限制模型 single thread；目前實測不需增加資源。

補資料前置的歷史最新摘要見 [封存](../archive/data-supplement-evidence-summary-before-specialists-2026-10-03.md)。以下 checkpoint 僅作歷史證據，不是重啟舊入口的指令。
