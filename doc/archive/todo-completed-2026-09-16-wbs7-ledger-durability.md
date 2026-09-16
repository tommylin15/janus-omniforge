# WBS-7-PILOT-LEDGER-DURABILITY 完成紀錄

- PostgreSQL `janus_control` whole-database custom-format `pg_dump` 已由既有 `janus-postgres-dev` 每日 systemd timer 執行；VM 維持 `e2-micro`／private IP，僅將已核准的 OAuth scope 改為 `devstorage.read_write`，未建立新 VM、disk、snapshot、Cloud SQL 或 replica。
- Backup bucket：既有 `gen-lang-client-0593591102-dev-private`；`pilot-ledger-backups/` managed folder 綁定 VM `roles/storage.objectAdmin` 與 Cloud Build default service account `roles/storage.objectViewer`，daily retention 14、monthly checkpoint retention 6。
- Backup evidence（2026-09-16 UTC）：owners=2、ledger_events=0、bytes=161278、projected_retention_bytes=3225560；daily／monthly 各 1 個 object。
- Isolated restore：Cloud Build `b12d64a5-dab9-4aef-9853-f06324a015d3` SUCCESS；pinned PostgreSQL image、`--network none`、tmpfs restore；`restore_checks=t`，owners=2、ledger_events=0、owner_boundary_valid=true、latest_versions_valid=true、correction_links_valid=true、credential_columns=0。
- 本機驗證：shell `bash -n`、YAML parse、`tests/test_pilot_readiness.py` 4 passed、`git diff --check`。
