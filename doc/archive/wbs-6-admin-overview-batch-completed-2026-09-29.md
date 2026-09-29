# WBS-6-ADMIN-OVERVIEW-BATCH 驗收結案（2026-09-29）

## 範圍與結論

`WBS-6-ADMIN-OVERVIEW-BATCH` 已在既有 GCP `dev` parallel-live environment 完成 implementation、widget regression、Flutter CI、canonical GitHub deployment 與 live runtime acceptance。

本 WBS 只結案 Admin actionable overview、batch／retry classification、retryable failed item 與 execution lineage 的 operator workflow；**不代表** `WBS-6-ADMIN-STOCK-WORKBENCH`、Mart AI roles／CIO、Analysis Profile 或 legacy Admin retirement 已完成。

## Implementation boundary

- Overview 改為 actionable-issues-first：只把 `failed`／`partial`／`retrying` execution、非 success 的 source health，以及 blocked／review-required／invalid Mart report 放入「優先處理」；正常 successful execution 不佔首頁主要空間。
- `partial` 明確列為需要處理，不視為 full success。Batch 頁分開顯示「需要處理／執行中／已完成」，並將失敗／partial 排在正常成功之前。
- Overview 與 Batch 共用 execution detail：顯示 `trace_id`、immutable lineage、逐項 `safe_message`、retry count 與 backend 回傳的 `retry_classification`。
- 只有 `retry_classification=retryable` 的 failed item 顯示「重試」並呼叫既有 guarded Admin retry endpoint；non-retryable 項目只顯示「不可重試」。Flutter 不自行放寬 backend retry 規則。
- Operator 因此可在 Admin workspace 直接定位近期 execution／Core source／Mart publication 問題，並對 backend 已允許的 failed item 建立 narrow retry，不需登入 GCP 或直接查 DB。

## Implementation / regression commits

- `187c895b6203f5443ae0e21a489e6ebd6dd633e4`（`Complete Admin overview and batch operator workflow`）：加入 operator workflow 與 `apps/user_app/test/admin_overview_batch_test.dart`。
- 首次 Flutter run `36564380741` 的 analyze 成功，但 widget tests 為 34 passed / 4 failed；失敗來自既有 good-state copy contract 與新測試 viewport／finder 假設，不是 backend retry engine failure。本次沒有把該 run 包裝成成功。
- `9bf00f1fe6bd63ffd284023688a7a803fb13487d`（`Fix Admin overview batch widget regressions`）：保留既有「今日沒有需要處理的事項」文案，並將新測試改為固定大型 viewport、捲動驗證 lineage、允許 policy copy 與 row 同時含「部分完成」。

## Tests / CI

修正版 Flutter workflow `36565040429`（run 51）對 commit `9bf00f1f...` 完成：

- `flutter analyze --no-fatal-infos lib test`：success（既有 non-fatal style infos 不構成 failure）。
- `flutter test`：success；包含既有 Admin shell regression 與新增 Overview／Batch tests。
- web entrypoint／PWA metadata checks：success。
- `flutter build web --base-href /app/` 與 built asset validation：success。

新增 regression 固定：

1. Overview 只顯示需要處理的 execution／Core source／Mart blocked item，healthy successful execution 不出現在 priority list。
2. Overview execution detail 顯示 trace lineage，且只有 retryable failed item 能送出 retry endpoint。
3. Batch 將 partial 與 succeeded 分開分類，partial 不計入完成，且 detail／retry／lineage 可操作。

Canonical dev workflow `36565040400`（run 126）`test-api` success；Mart／ingestion／Private Pipeline 均因無相關 runtime 變更而 skipped。

## Dev deployment / live runtime evidence

Canonical workflow `36565040400`：

- Cloud Build `10b6b6c9-f638-45bd-8187-8e29ccfbf4cd`：`SUCCESS`。
- image tag：`us-central1-docker.pkg.dev/gen-lang-client-0593591102/janusai-poc/api:dev-9bf00f1fe6bd63ffd284023688a7a803fb13487d`。
- immutable image digest：`sha256:2f89421ab200ef9d22e681e76de8d840a2a60d226264788a97914af7dce27d22`。
- Cloud Run latest ready revision：`janus-api-g9bf00f1fe6bd-config`，Ready=`True`，100% traffic。
- live verifier 最終輸出：`janus-api traffic, Flutter user/Admin workspace, Admin auth boundary, legacy Admin rollback surface, web build, high-resolution PNG branding, and PWA metadata match 9bf00f1fe6bd63ffd284023688a7a803fb13487d`。

既有 backend Admin tests／service contract 保持 retry safety boundary：retry 必須是 collection execution、原 execution 為 failed／partial、item 存在且 classification 為 retryable；新 UI 只消費這個受控 contract，未建立 client-side bypass。

## 完成語意與後續

因此可以宣稱：

> **Admin Overview／Batch operator workflow 已完成 dev acceptance；首頁以問題優先呈現 persisted Core／Mart／execution evidence，partial 不作 full success，retry classification 與 lineage 可直接操作，安全重跑仍由 backend policy 決定。**

不得延伸宣稱：

- `WBS-6-ADMIN-STOCK-WORKBENCH` 已完成；它現在是下一個 foreground WBS。
- Mart Fact Pack／五角色／CIO 已完成或可由 Admin 假裝重跑。
- Legacy static Admin 可退休；retirement gate 仍需 Stock Workbench 與其他 parity acceptance。
- 五位分析師已進入每日自動工作。

本次未新增 GCP resource、未啟用新付費 API／模型，也未做 production deployment。