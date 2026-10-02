# Legacy Static Admin 退役紀錄（2026-10-02）

## 決策

使用者明確決定 legacy static Admin 不再作為 fallback，也不等待 Flutter Admin parity／rollback gate；目前與未來都不再使用該 static frontend。

Flutter Admin／PWA 與既有 Admin API 保持 active。這次退役只移除 legacy static frontend 與其 runtime packaging，不移除 Admin API 能力。

## Backup／還原來源

Legacy static Admin 原始碼已移到 Docker 不會攜帶的 `doc/archive/legacy-static-admin-2026-10-02/`：

- `admin.html`
- `admin.css`
- `admin.js`

archive 三個檔案直接沿用退役前相同的 immutable Git blobs，不是重新產生的近似副本：

- HTML blob `ebbe4459c5eead6ad65667fa3d43e50df45e6836`
- CSS blob `c201c6f9744d2b58a218c4b78c3ca360c83b5293`
- JS blob `ee24a2cb812dcb4c494ebe5521e4d227c82dc49c`

退役前 `main` commit：`c051cdde2d6b9397649ba93bafbb77b2bf20d1ae`。需要時也可直接由該 commit 還原原路徑。

`doc/` 已由 Docker build context 排除，因此 archive 原始碼不進入 API runtime image。

## Active runtime 邊界

- 舊的 `apps/web/static/admin.css` 與 `admin.js` 已從 active tree 移除。
- `apps/web/static/admin.html` 不再包含 legacy UI；只保留極小 compatibility shim，將舊 `/admin` 與 `/admin/stocks` 入口導向 Flutter `/app/admin`，不載入舊 CSS／JS。
- `.dockerignore` 排除 `apps/web` 的 legacy Python adapter／standalone image files，以及 root static-Admin Node／Playwright／Vitest build files；`private-journal-acceptance.html` 與 `usefulness-feedback-acceptance.html` 仍保留給既有 API acceptance path。
- Flutter Admin／PWA 與 `/api/v1/admin/*` backend API 維持 active；本次不刪除 Admin API。

## 驗收狀態

GitHub implementation 已完成 source/archive 與 runtime packaging 切割；`doc/todo.md` 已移除 `WBS-6-ADMIN-LEGACY-RETIREMENT` active gate，`ui/admin.md` 已改為 Flutter Admin 為唯一 active frontend。

Deployment／dev runtime 是否完成仍以對應 GitHub Actions deploy／verify 與 live evidence 為準；若部署尚在執行，本項保持 implementation-complete／runtime-pending，不以文件或 commit 單獨宣稱 full completion。
