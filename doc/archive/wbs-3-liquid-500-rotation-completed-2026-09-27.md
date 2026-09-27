# WBS-3-LIQUID-500-ROTATION completed (2026-09-27)

The weekly liquid-500 source, ranking, fail-closed guards, deployment, dev
rotation, and live Admin manual adjustment acceptance are complete. Earlier
source, test, deployment, and rotation evidence is recorded in the
[operations ledger](../spec/operations-and-testing.md).

Live Admin acceptance used the effective version 1 list as the baseline. The
Admin UI confirmed 500 members ranked 1–500, `2330` (`台積電`) at rank 58, and
that `9911` (`櫻花`) was an enabled listed stock outside the 500. The operator
removed `2330`, added `9911` with a reason, verified version 2 still had 500
members and marked the replacement as manual, then reversed the swap with a
restoration reason.

Version 3 restored the original roster: read-only PostgreSQL checks confirmed
500 members, ranks 1–500, and zero symmetric difference from version 1. Audit
records 22 and 23 correspond to the two UI changes and preserve their reasons
and authenticated Admin actor. No production deployment or new cloud resource
was created.
