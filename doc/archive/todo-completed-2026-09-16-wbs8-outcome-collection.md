# WBS-8-PILOT-OUTCOME-COLLECTION — completed 2026-09-16

Implementation was already present in the immutable Mart pipeline and was
verified before advancing the queue:

- `intelligence_mart.outcomes` collects exact 5／20／60 trading-day outcomes,
  TAIEX-relative return, MFE／MAE, pending／valid／excluded state, exclusion
  reason, price／benchmark snapshot IDs, and hashed provenance.
- Mart publication records analysis identity, `analysis_as_of`, scope, Core
  snapshot, membership snapshot hash, and Pilot baseline lineage. Membership
  is carried by the immutable Core ready event／analysis request; outcomes do
  not consult the current watchlist when evaluating historical reports.
- Local targeted verification: `python -m unittest tests.test_pilot_readiness`
  — **4 passed**. Python compile and `git diff --check` passed.
- Existing GCP dev `janus-postgres-dev` (`e2-micro`, private IP) was used only
  for acceptance. Migration `025_pilot_readiness` was recorded; lineage
  columns, outcome／feedback relations, bounded privileges, and baseline
  registration all passed in a transaction that ended with `ROLLBACK`.
- The existing `janus-intelligence-mart` Cloud Run Job was updated to immutable
  image digest `sha256:b497e6ee00792d0caf1f65584674f6bf5fa66ba2ed8facb3b7e392d9c002dd8c`
  by Cloud Build `727f5730-4baa-458f-a33a-655ccc32f329`; bounded queue smoke
  execution `janus-intelligence-mart-k98dm` completed successfully. The queue
  was empty at the time, so dev currently has no baseline-linked reports or
  outcome rows; the next real publishable symbol report will start Day 1
  collection through this path.
- No production deployment, paid resource creation, Artifact Analysis／Scanning
  API call, commit, or push was performed.

Calibration／tuning remains deferred to later WBS work.
