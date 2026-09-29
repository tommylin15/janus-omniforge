# WBS-6-ADMIN-STOCK-WORKBENCH 完成紀錄

日期：2026-09-29
狀態：dev parallel-live acceptance 完成

## 結論

`WBS-6-ADMIN-STOCK-WORKBENCH` 已完成本 WBS 的正式 dev acceptance。這次完成的是 Flutter Admin 個股工作台的 operator flow，不代表 `WBS-6-PORTFOLIO-INTRADAY-QUOTE`、Fact Pack、五角色 AI、CIO、Analysis Profile 或 legacy Admin retirement 已完成。

## 完成範圍

- 代號與中文名稱搜尋使用既有 `/api/v1/admin/stocks` read path；Flutter regression 覆蓋中文名稱查詢。
- 個股 detail 讀 persisted Core status 與 persisted Mart 紀錄，不由 Flutter 自行製造 canonical number。
- Dataset health 顯示 row count、received/requested coverage、gap、latest date 與健康狀態。
- Execution、snapshot、source、provenance 與 freshness 放在「技術追蹤（唯讀）」進階區塊；舊 execution／snapshot 維持 immutable，不提供前端改寫入口。
- Gap repair 不再接受任意 config ID。UI 只會從 `/api/v1/admin/source-catalog?limit=200` 選擇同 dataset、`enabled=true`、`collection_enabled=true`，且 `authorization_status` 為 `official` 或 `approved_fallback` 的既有 config；建立 repair 時只送出目前單一 symbol 的 collection execution。
- 若 dataset 沒有已核准且 enabled 的 collection config，UI fail closed，不自行建立、猜測或繞過來源授權。
- 個股工作台移除會讓使用者誤認五角色／CIO 已可用的 rerun 入口；畫面明確標示 Fact Pack、AI role 與 CIO contracts 完成前不提供 role rerun／historical role 操作。既有 persisted Mart history 僅唯讀展示，不代表 advanced capability 已啟用。

## 實作與修正 commits

1. `7946e953cfd5fa3ced4d21dd51ed006708ce0cee` — `Complete Admin stock workbench operator flow`
   - 完成 bounded repair、唯讀 lineage 與 AI capability boundary。
   - 新增 `apps/user_app/test/admin_stock_workbench_test.dart` regression。
2. `739a64384aa88319c76415e07720e552d30f40a5` — `Fix stock workbench viewport regression`
   - 修正既有 widget test 對可捲動內容的 viewport 假設。
3. `9cceb3d1aa8777543f491393cda2c6fbe941a560` — `Fix stock workbench bounded repair regression`
   - 修正 nested List matcher 的測試比較方式，並讓 lineage regression 先捲動到進階區塊後再操作。

第一版 Flutter workflow 有真實紅燈：run `36568576560` 的 test step 為 38 passed / 2 failed，因此沒有將該 commit 當完成。兩個失敗分別是 nested `List` matcher 的測試身份比較，以及舊測試對「歷史分析」初始 viewport 的假設；修正後才進入完成判定。

## CI evidence

修正版 `9cceb3d1aa8777543f491393cda2c6fbe941a560`：

- Flutter workflow run：`36569491143` — `success`
- `flutter analyze --no-fatal-infos lib test` — success
- `flutter test` — success
- Janus index／PWA metadata validation — success
- `flutter build web --base-href /app/` — success
- built PWA asset validation — success

Canonical dev workflow：`36569491137` — `success`

- `detect` — success
- `test-api` — success
- `test-mart` — skipped
- `test-ingestion` — skipped
- `deploy-mart` — skipped
- `deploy-ingestion` — skipped
- `deploy-private-pipeline` — skipped
- `deploy-api` — success
- `Verify api` — success

這次只需要 API／Flutter runtime acceptance；沒有把未修改的 Mart、ingestion 或 Private Pipeline 誤當成本 WBS 的新驗收成果。

## Dev deployment / runtime evidence

- Cloud Build ID：`6ddfab32-02dd-44b9-b821-efb298ebe164`
- Cloud Build status：`SUCCESS`
- image tag：`us-central1-docker.pkg.dev/gen-lang-client-0593591102/janusai-poc/api:dev-9cceb3d1aa8777543f491393cda2c6fbe941a560`
- immutable digest：`sha256:32517542be77d2c85b25cff35e95f9bd491a377878fb86f4f2d38dcd76cdcd2b`
- Cloud Run service：`janus-api`
- revision：`janus-api-g9cceb3d1aa87-config`
- Ready：`True`
- latestCreatedRevisionName = latestReadyRevisionName = `janus-api-g9cceb3d1aa87-config`
- traffic：latest revision 100%
- canonical service URL：`https://janus-api-2oo7qbkd5q-uc.a.run.app`
- `verify-dev.sh api` 最終訊息確認 Flutter User/Admin workspace、Admin auth boundary、legacy Admin rollback surface、web build、branding、PWA metadata 均匹配 Git SHA `9cceb3d1aa8777543f491393cda2c6fbe941a560`。

GitHub Actions checkout post-job 仍可出現既有 `token-savior` submodule cleanup warning 與 Node deprecation warning；workflow conclusion 與 acceptance steps 均為 success，因此這些 warning 不作本 WBS failure，也不作額外成功證據。

## Governance boundary

- 沒有新增 GCP resource。
- 沒有新增或啟用付費 API、model 或 subscription。
- 沒有 production deployment。
- 沒有把缺值補成假資料。
- 沒有讓 Flutter 成為 canonical number owner。
- 沒有把 persisted historical Mart 紀錄包裝成五角色／CIO capability。
- 沒有退休 legacy static Admin；`WBS-6-ADMIN-LEGACY-RETIREMENT` 仍需依自己的 gate 執行。
- `WBS-6-PORTFOLIO-INTRADAY-QUOTE` 仍因正式行情來源授權而 blocked，不能因本 WBS 完成就把盤後價稱為即時價。

## 後續

依 `five-analyst-daily-operation-gate.md`，本 WBS 完成後，Gate 1 所列七個 Product Completeness prerequisite 已全部完成。`WBS-6-PORTFOLIO-INTRADAY-QUOTE` 仍保留為 blocked 的產品缺口，但不是該 Gate 1 的七項之一；在來源授權未解除前，不應停住其他安全且獨立的工程工作。

五位分析師每日運作鏈路的下一個可執行 WBS 是 `WBS-5-MART-FACT-PACKS`【Sol】；完成它仍只代表建立可重跑、具 PIT／missing-data／provenance／evidence／hash lineage 的事實輸入，尚不能宣稱五位分析師已開始每日工作。
