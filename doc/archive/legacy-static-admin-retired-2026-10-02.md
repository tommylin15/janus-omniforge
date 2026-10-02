# Legacy Static Admin 退役紀錄（2026-10-02）

## 決策

使用者明確決定 legacy static Admin 不再作為 fallback，也不等待 Flutter Admin parity／rollback gate；目前與未來都不再使用該 static frontend。

Flutter Admin／PWA 與既有 Admin API 保持 active。這次退役只移除 legacy static frontend 與其專用 adapter／build／test tooling，不移除 Admin API 能力。

## Backup／還原來源

Legacy static Admin 原始碼與專用工具已移到 Docker 不會攜帶的 `doc/archive/legacy-static-admin-2026-10-02/`：

- UI：`admin.html`、`admin.css`、`admin.js`
- legacy adapter：`adapter/`
- Node／Playwright／Vitest build/test tooling：`tooling/`
- legacy UI tests：`tests/`

archive 檔案直接沿用退役前相同的 immutable Git blobs，不是重新產生的近似副本。主要 UI blobs：

- HTML `ebbe4459c5eead6ad65667fa3d43e50df45e6836`
- CSS `c201c6f9744d2b58a218c4b78c3ca360c83b5293`
- JS `ee24a2cb812dcb4c494ebe5521e4d227c82dc49c`

退役前 `main` commit：`c051cdde2d6b9397649ba93bafbb77b2bf20d1ae`。需要時也可直接由該 commit 還原原路徑。

`doc/` 已由 Docker build context 排除，因此 archive 原始碼不進入 API runtime image。

## Active tree／runtime 邊界

- `apps/web/static/admin.css` 與 `admin.js` 已從 active tree 移除。
- `apps/web/static/admin.html` 不再包含 legacy UI；只保留 206-byte compatibility shim，將舊 `/admin` 與 `/admin/stocks` 入口導向 Flutter `/app/admin`，不載入舊 CSS／JS。
- `apps/web` 的 legacy Python adapter／Dockerfile／README 已移到 archive；active `apps/web` 只保留 `static/` 中仍被 API 使用的 compatibility／acceptance HTML。
- Root `package.json`／lock、ESLint／TypeScript、Playwright／Vitest config、`scripts/build-web.mjs` 及舊 Admin frontend/e2e tests 已移到 archive，不再形成 active Node/static-Admin build/test surface。
- `private-journal-acceptance.html` 與 `usefulness-feedback-acceptance.html` 是獨立 acceptance helper，仍保留給既有 API acceptance path。
- Flutter Admin／PWA 與 `/api/v1/admin/*` backend API 維持 active；本次不刪除 Admin API。

## TODO／UI 決策同步

- `doc/todo.md` 已移除 `WBS-6-ADMIN-LEGACY-RETIREMENT` active gate。
- `ui/admin.md` 已改為 Flutter Admin 是唯一 active Admin frontend。
- 舊 WBS／archive 中若仍描述 migration-era parity gate，屬歷史設計，不得覆蓋本次使用者決策與 active TODO／UI contract。

## 驗收狀態

GitHub implementation 已完成 legacy static Admin source、adapter、build tooling、tests 與 runtime packaging 的 active/archive 切割。Deployment／dev runtime 是否完成仍以對應 GitHub Actions deploy／verify 與 live evidence 為準；沒有 runtime evidence 時不得只因文件或 commit 存在而宣稱 full completion。
