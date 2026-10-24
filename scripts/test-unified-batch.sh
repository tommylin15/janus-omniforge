#!/usr/bin/env bash
# Execute only in the handoff turn, never during source-only authoring.
set -Eeuo pipefail
export PYTHONPATH=".:jobs/ingestion-core:jobs/intelligence-mart${PYTHONPATH:+:${PYTHONPATH}}"
python -m pytest -q \
  tests/test_unified_batch_flow.py \
  tests/test_batch_controller.py \
  tests/test_admin_batch_dashboard.py \
  tests/test_controller_ledger_backup.py \
  tests/test_ledger_backup_retention.py \
  tests/test_private_ledger_backup_retention.py \
  tests/test_private_pipeline.py \
  tests/test_private_pipeline_scheduler.py \
  tests/test_user_api.py \
  tests/test_public_mart_api.py \
  tests/test_specialist_engines.py
bash -n scripts/gcp/ledger-durability-dev.sh
