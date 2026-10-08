# Janus CI/CD V2 — 實作與驗收狀態

政策權威為 [PROJECT_RULES §12](../PROJECT_RULES.md#12-cirelease-分離2026-10-08-使用者追加政策)。本工作接續既有四元件改造，目前 **PARTIAL**。

## 目前實作

- `ci-v2.yml` 在 main Push 選擇必要 Python suites／相依 lock；文件-only Push 保留 exact-SHA plan 成功證據但略過程式測試，避免 blocking 後續 manual Release。沒有 GCP credential 或 runtime deployment。
- `janus-dev-v2` 是同一個 `us-central1` manual Repository Source Trigger，沒有 Push event。`cloudbuild-v2.yaml` 預設 shadow；候選與 Release 必須明確指定 mode。
- Release planner 讀既有 regional bucket `v2/published.json` 的成功 SHA，從完整 baseline 計算變更。首次發布建四元件；指定 component 不能縮減正式 Release 範圍。
- Release 必須提供工作包 ID、Ready flag及 exact-SHA CI success。SHA image index 只重用已成功 build receipt，image 以 digest部署；build tag包含 Build ID，避免覆蓋同 SHA 的另一個 build。
- Candidate 只更新 API no-traffic revision；Job及Scheduler只讀。HTTP health、未登入 User／Admin拒絕及Flutter SHA gate不代表 authenticated acceptance。
- Release controller使用 regional object generation mutex、main SHA fence、Job idle fence、設定 snapshot／rollback、Scheduler pause／restore，以及 published state generation CAS。CAS 失敗必須回復 Job image／API traffic，直到 CAS 完成才允許清空 rollback 清單；若 Scheduler restore 失敗保留 mutex，待 runtime 人工 readback。Job更新僅存在 Release分支。
- Release先執行controlled runtime驗收：ingestion讀schema／ACL與固定snapshot的一列Core Parquet；Mart重用固定GCS input驗證五分析師；Private使用既有2-task owner queue canary。升流量前合併同SHA／digest的authenticated owner／OAuth／canonical PnL／MCP evidence；任何必要gate缺失均rollback，保留execution evidence。不得手寫PASS代替驗收。
- 050 migration分 publication／control owner檢查，psycopg SELECT與GRANT分開執行；readiness只查／補缺marker。
- 舊 Push deployment與B3／B5／Portfolio驗收中的部署fallback已移除；舊`deploy-dev.yml`只保留明確人工 recovery。
- Image cleanup目前只有 digest-fenced dry-run；尚未完成全引用盤點與新版 live PASS，沒有刪 image。

## 未完成的必要 evidence

1. main `9e42420` selective CI `37737358620` 已 PASS；最新版本 Push CI 與明確 Release 的四元件完整鏈仍待合併驗收。
2. 四元件 target image的完整真實 dev acceptance，包含 authenticated owner／OAuth／PnL／MCP。
3. canonical promotion／same-SHA重試／baseline readback與failure recovery真實驗收。
4. 所有有效 revision、跨區 runtime、execution及候選 evidence引用集合的清理與容量讀回。

完整 checkpoint見 [V2盤點](../archive/cicd-v2-inventory-2026-10-08.md)。Build SUCCESS或migration成功不等於V2 CLOSED。
