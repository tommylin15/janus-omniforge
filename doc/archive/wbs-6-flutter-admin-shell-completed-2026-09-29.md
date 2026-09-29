# WBS-6-FLUTTER-ADMIN-SHELL 驗收結案（2026-09-29）

## 範圍與結論

`WBS-6-FLUTTER-ADMIN-SHELL` 已在既有 GCP `dev` parallel-live environment 完成 implementation、targeted tests、Flutter CI、canonical GitHub deployment 與 live runtime acceptance。

本 WBS 只結案 Admin workspace shell、responsive 中文主導覽、Admin backend auth／token audience boundary 與 legacy static Admin 保留／rollback surface；**不代表** `WBS-6-ADMIN-OVERVIEW-BATCH`、`WBS-6-ADMIN-STOCK-WORKBENCH`、Mart AI roles／CIO 或 legacy retirement 已完成。

## Implementation boundary

- 單一 `apps/user_app` Flutter codebase 同時承載 User 與 Admin workspace。`/app/admin` 或明確 `JANUS_WORKSPACE=admin` 才選擇 Admin workspace；一般 `/app` 保持 User workspace。
- Admin shell 使用中文主導覽：`總覽`、`批次`、`個股`、`市場資訊`、`AI 分析`、`進階管理`。寬版使用 `NavigationRail`，390×844 級窄版切換為 `NavigationDrawer`。
- User／Admin OAuth client audience 分離；Flutter 只負責選擇登入 client 與顯示 workspace，不把隱藏控制當 security boundary。`/api/v1/admin/*` 與 legacy `/api/v1/core/*` 仍由 FastAPI `GoogleAdminAuthenticator` 在 backend 驗證 Admin audience／allowed email。
- Legacy static Admin 仍保留在 `/admin`、`/admin/stocks` 與 `/assets/admin.*`。本 WBS 沒有刪除或改寫 rollback surface；`WBS-6-ADMIN-LEGACY-RETIREMENT` 仍需等待 foreground Admin parity 與其自身 acceptance。

## 驗收變更

Commit `2c1b2babdd1548cb79373f7fd8c46739a4073923`（`Accept Flutter Admin shell in dev`）：

- 新增 `apps/user_app/test/admin_shell_test.dart`，固定 explicit Admin route/build mode、1280×900 desktop rail、390×844 mobile drawer 與六個中文主導覽 regression。
- 強化 `scripts/gcp/verify-dev.sh api`，在 canonical dev deployment 後額外要求：
  1. `/app/admin` 必須回傳當次 Git SHA 的同一 Flutter web build；
  2. 未帶 Admin token 呼叫 `/api/v1/admin/source-health?limit=1` 必須回 `401`；
  3. `/admin/stocks` 必須仍是 legacy static Admin，含 `Janus 管理介面 · 資料營運` 與 `/assets/admin.js`，且不得解析成 Flutter bootstrap。

## Tests / CI

- Flutter workflow `36561885167`（run 49）對 commit `2c1b2bab...` 完成 `flutter analyze --no-fatal-infos lib test`、`flutter test`、PWA metadata validation、`flutter build web --base-href /app/` 與 built asset validation，全部 `success`。
- Dev deployment workflow `36561885101`（run 124）`test-api` success。既有 auth negative coverage 同時確認：無 token 的 Admin API 為 `401`、User audience token 不可進 Admin API、正確 Admin audience 但不在 allowed email 為 `403`、合法 Admin token 才可讀 Admin Core route；User auth 亦拒絕 Admin audience／expired／untrusted issuer。
- 因 `verify-dev.sh` 是 API／Private Pipeline 共用 deployment script dependency，本次 path detection 也重新部署並 verify `janus-private-pipeline`；該 job success。Mart／ingestion 未被重跑。

## Dev deployment / live runtime evidence

Canonical workflow `36561885101`：

- Cloud Build `c021e812-f61a-4ade-a9b2-cb5b8b6fed48`：`SUCCESS`。
- image tag：`us-central1-docker.pkg.dev/gen-lang-client-0593591102/janusai-poc/api:dev-2c1b2babdd1548cb79373f7fd8c46739a4073923`。
- immutable image digest：`sha256:9b1a2eb392f6ba348f1cf55ee8fce8f988f31da5512d0603fa922c96c0f408dd`。
- Cloud Run latest ready revision：`janus-api-g2c1b2babdd15-config`，Ready=`True`，100% traffic。
- live verifier 最終輸出：`janus-api traffic, Flutter user/Admin workspace, Admin auth boundary, legacy Admin rollback surface, web build, high-resolution PNG branding, and PWA metadata match 2c1b2babdd1548cb79373f7fd8c46739a4073923`。

GitHub Actions 在 post-job checkout cleanup 出現既有 `token-savior` submodule path warning，但 workflow conclusion 為 `success`，且所有本 WBS tests／deploy／live verify steps 均已成功；本結案不把該非驗收 cleanup warning 當成功證據，也不把它解讀成 Admin runtime failure。

## 完成語意與後續

因此可以宣稱：

> **Flutter Admin shell 已完成 dev acceptance；single-codebase Admin workspace、responsive 中文導覽與 backend Admin auth boundary 已成立，legacy static Admin rollback surface 仍保留。**

不得延伸宣稱：

- Overview／Batch operator workflow 已完成；下一個 foreground WBS 仍是 `WBS-6-ADMIN-OVERVIEW-BATCH`。
- Stock Workbench 已完成；其正式 acceptance 仍由 `WBS-6-ADMIN-STOCK-WORKBENCH` 負責。
- Legacy static Admin 可刪除；retirement gate 尚未成立。
- 五位分析師／CIO／Mart advanced capability 已可用。

本次未新增 GCP resource、未啟用新付費 API／模型，也未做 production deployment。
