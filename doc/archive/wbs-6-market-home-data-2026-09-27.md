# WBS-6-MARKET-HOME-DATA — completed 2026-09-27

- The deterministic `/api/v1/public/market-home` contract reads persisted Core benchmark, market-activity and institutional sections without a Daily Brief dependency.
- Each section reports its own date, freshness, status, coverage and provenance. Mixed dates produce a null top-level `as_of`; aggregate provenance retains source, execution and provenance ID lists.
- Missing section metrics remain missing, dataset read failures stay local to that section, and public output does not expose backend exception details.
- Local targeted tests: `python -m pytest tests/test_market_home.py -q` — **4 passed**. GitHub API CI passed, but its selected test command does not include `tests/test_market_home.py`.
- GCP dev persisted-data acceptance passed on Ready revision `janus-api-g6d6b53d8c4ec-config`, serving 100% traffic. Public unauthenticated endpoint returned 200 with TAIEX `2026-09-25` and TPEx, market-activity and institutional `2026-09-24`; unauthenticated Admin endpoint returned 401.
- Commit: `6d6b53d8c4ec6de87f54e58f73509e1f22e6cca8`. Deployment evidence: [operations and testing](../spec/operations-and-testing.md).
- No production deployment, new service or paid resource was created.
- The next active slice is `WBS-6-MARKET-HOME-UI`.
