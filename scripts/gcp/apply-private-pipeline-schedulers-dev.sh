#!/usr/bin/env bash
set -Eeuo pipefail

cat >&2 <<'EOF'
Retired: direct janus-private-pipeline Cloud Scheduler jobs are no longer the
effective dev trigger.

Since the 2026-10-02 batch-controller cutover, Private Pipeline is dispatched
by janus-batch-controller from the canonical BATCHES definition in
jobs/ingestion-core/ingestion_core/batch_controller.py.

Do not recreate janus-private-pipeline-0740/1100/1400/2130 here. Re-enabling
those schedulers would create a second trigger path and can duplicate work.
EOF
exit 1
