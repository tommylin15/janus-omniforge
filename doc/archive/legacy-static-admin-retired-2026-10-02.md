# Legacy Static Admin 退役紀錄（2026-10-02）

## 決策

使用者明確決定 legacy static Admin 不再作為 fallback，也不等待 Flutter Admin parity／rollback gate；目前與未來都不再使用該 static frontend。

Flutter Admin／PWA 與既有 Admin API 保持 active。這次退役只移除 legacy static frontend 與其 runtime packaging，不移除 Admin API 能力。

## Backup／還原來源

為避免把已退役程式碼複製到另一個 active source tree、繼續增加 build context／runtime image，本次以 Git immutable history 作為程式碼 backup，並以本文件保存可稽核還原座標。

退役前 `main` commit：`c051cdde2d6b9397649ba93bafbb77b2bf20d1ae`

Legacy static Admin 檔案：

- `apps/web/static/admin.html` — blob `ebbe4459c5eead6ad65667fa3d43e50df45e6836`
- `apps/web/static/admin.css` — blob `c201c6f9744d2b58a218c4b78c3ca360c83b5293`
- `apps/web/static/admin.js` — blob `ee24a2cb812dcb4c494ebe5521e4d227c82dc49c`

需要人工還原時，可由上述 commit 讀回，例如：

```bash
git show c051cdde2d6b9397649ba93bafbb77b2bf20d1ae:apps/web/static/admin.html
```

`doc/` 已由 Docker build context 排除，因此本退役紀錄本身不進入 API runtime image。

## Runtime 邊界

退役前 `services/api/app.py` 仍保留 `/admin`、`/admin/stocks`、`/assets/admin.css`、`/assets/admin.js` 的 legacy static route；API image 又以 repository root 作 build context。退役工作的目標是讓 legacy static frontend 不再有 active source artifact，也不再需要被 runtime image 攜帶。

`private-journal-acceptance.html` 與 `usefulness-feedback-acceptance.html` 是獨立 acceptance helper，不屬於 legacy Admin，本次不以 legacy Admin 名義刪除。

## 狀態

本文件只保存決策與 backup provenance。實際 retirement 是否完成，仍以 GitHub implementation、CI／deployment 與 dev runtime acceptance 為準；沒有 runtime evidence 時不得只因本文件存在而宣稱完成。
