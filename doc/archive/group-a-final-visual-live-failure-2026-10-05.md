# A 組 Final Visual Contract — GCP dev live failure checkpoint — 2026-10-05

## Evidence source

使用者以既有 GCP dev `/app/`、真實 Google authenticated User App、手機寬度約 390px 級畫面進行手動驗收並回傳截圖。

此 checkpoint 只記錄畫面與 GitHub `main` 可直接確認的差異；不保存登入憑證、token 或私人交易正文截圖。

## Live result

判定：**FAIL — implementation gap**。

真實 User App 仍顯示目前 legacy/old Material 3 layout，包括：

- 頂部單純 `Janus` AppBar；
- bottom navigation 為 `今日 / 關注 / 記帳／筆記 / 我的`；
- Today 仍為垂直資料卡 + `研究摘要尚未就緒`；
- Ledger 仍為上方 summary cards + `持股 / 紀錄 / 報表 / 筆記` segmented control + 舊 holdings card hierarchy；
- 畫面資訊密度、section order、spacing、card hierarchy 與 Final Visual Contract reference 並未明顯收斂。

這不是 cache／URL／browser 問題。GitHub `main` 的 `apps/user_app/lib/main.dart` 仍明確實作相同舊版結構：`Workspace` 的四個 destination 仍是 `今日 / 關注 / 記帳／筆記 / 我的`，`JanusApp` 仍使用 Material 3 cyan seeded theme，現有 Today/Ledger widgets 亦對應 live 畫面。

因此 root cause 屬 **current main implementation 尚未完成 Final Visual Contract convergence**，不是單純「程式已完成但 deployment lag」。

## Acceptance consequence

依 `doc/status.md` 既有規則：若真實 authenticated owner 畫面仍明顯像 legacy UI，必須視為 acceptance failure／implementation gap，不得列為 cosmetic polish，也不得因 reference PNG 已存在、widget tests passing、build/deploy success 而宣稱完成。

A 組維持 `partial`。

## Required engineering loop

1. 以 `doc/ui/reference` 四張 approved reference + active UI docs 為準，收斂 Today／Watchlist／Ledger／Stock Detail 的非 AI layout。
2. 保留現有 canonical API/data semantics；loading／empty／error／partial／stale／missing 不得用假 0 或 stale value 補齊。
3. 補/更新 390px widget/golden/layout contract tests，測試 section order、主要 card hierarchy、mobile spacing 與關鍵狀態。
4. `flutter analyze` + `flutter test` 通過後 commit `main`。
5. 重新 build/deploy GCP dev User App；確認 `/app/build-id.txt` 對應新 commit。
6. 使用同一 GCP dev `/app/`、同一 authenticated owner、約 390px viewport 重新做四頁 live screenshot acceptance。

在第 6 步成功前，不得將 Final Visual Contract 標示完成。
