# WBS-6-MARKET-HOME-UI — completed 2026-09-27

- `TodayPage` starts market-home and Daily Brief requests independently. Market baseline renders as soon as its request completes; a pending or missing research summary does not block it.
- Baseline cards retain their own data date, freshness, coverage and localized state. The page no longer implies one shared date when section dates differ. A missing research summary shows `研究摘要尚未就緒`.
- Local Flutter widget tests: `flutter test test/widget_test.dart` — **21 passed**. The added regression test keeps the Daily Brief pending while checking market data, date, coverage and partial status; it checks phone and desktop widths without layout exceptions.
- CI Flutter workflow `36314185316` passed analyze, tests, PWA validation and Web build. Local `flutter analyze --no-pub --no-fatal-infos lib test` passed with 20 existing style infos outside the changed lines. Local `flutter build web --base-href /app/` succeeded.
- Dev deployment workflow `36314185317` and `verify-api` passed. Cloud Build `1f614a4f-803d-4641-8ea3-d91b047632a2` succeeded; image digest `sha256:621e4e35747410aac4ade2600e63f61374ab7cb6d946f76f7baa8d09eebacd72`.
- Ready Cloud Run revision `janus-api-gda3e83a69a73-config` serves 100% canonical traffic. Authenticated Chrome `/app/` acceptance displayed persisted TAIEX data dated `2026-09-25`, TPEx / market activity / institutional data dated `2026-09-24`, and the bounded missing research state. At `390×844` the app used bottom navigation; at `1280×900` it used the desktop rail. Temporary viewport overrides were reset.
- Commit: `da3e83a69a73fa5004badc75602eb9a88642ec3d`. Full runtime evidence: [operations and testing](../spec/operations-and-testing.md).
- No production deployment, new service or paid resource was created. The next foreground task is `WBS-3-LIQUID-500-ROTATION` (suggested model: Sol).
