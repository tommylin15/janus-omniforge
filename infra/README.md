# Infrastructure

Development infrastructure is managed by idempotent gcloud scripts. Automatic
dev runtime deployment is initiated by path-based GCP Cloud Build Developer
Connect triggers; GitHub Actions is retained as a manual fallback only. Do not
run provisioning, deployment, or destructive commands without explicit user
authorization.

可重現的 dev gcloud bootstrap、PostgreSQL migration 與 Cloud Run 部署流程請見
[`doc/runbook-dev-deploy.md`](../doc/runbook-dev-deploy.md)。

## PostgreSQL dev/MVP decision

The development control database is planned as a self-managed PostgreSQL on a
single Compute Engine `e2-micro` VM in `us-central1`. Free Tier mode fixes the
machine type, limits total Standard Persistent Disk to 30 GB, uses no external
IP, and keeps outbound data within 1 GB/month. It uses a private IP and
IAP/OS Login; port 5432 must not be public. Automatic snapshots, backups, HA,
and replicas are disabled in this mode because they are not covered by the
Free Tier target.

The PostgreSQL VM and database resources are managed by the gcloud bootstrap
guard. Cloud SQL is not part of the selected dev topology.

Free Tier eligibility is a billing-account and region condition. The bootstrap
guard checks the resource shape but cannot guarantee a zero bill; deployment must
still check the account's Free Tier eligibility and billing budget.

Provisioning order is: PostgreSQL VM, PostgreSQL repository/migration and
schema bootstrap first, then Trino JDBC catalog and query service. The VM
definition must hard-limit `e2-micro`,
an eligible `us-central1` zone, no external IP, no more than 30 GB Standard
Persistent Disk, and no automatic snapshots or replicas.

Trino remains a separate Cloud Run service (2 vCPU, 4–8 GiB, min 0, max 1)
using GCS/Iceberg for durable data and the PostgreSQL VM for JDBC catalog and
control metadata. The PostgreSQL `e2-micro` VM must not host Trino; its 1 GiB
RAM is reserved for the low-traffic database workload.

## Artifact Registry cost guard

Artifact Registry usage is limited to image push/pull, immutable digest,
metadata, and cleanup operations. Artifact Analysis API, Container Scanning
API, vulnerability scanning, and occurrence APIs must not be enabled or called.
Any SBOM must be generated locally without those APIs.

Both `janusai-poc` and `janus-postgres` apply
`infra/artifact-registry-cleanup-policy.json`: each image package keeps only its
most recent version, while older tagged and untagged versions are eligible for
deletion after one second. Cleanup dry-run is disabled.

## WBS-7 dev security and FinOps guard

`scripts/gcp/security-finops-dev.sh` is the single operator entry point:

- `configure` applies least-privilege runtime identities, bounded Cloud Run
  scaling, bucket lifecycle rules, and one 320 TWD project budget (the approved
  US$10 equivalent for this TWD billing account) with 10%／50%／100% current-spend
  thresholds. It requires `ALLOW_DEV_SECURITY_FINOPS=true`.
- `verify` checks service-account separation, absence of user-managed keys,
  Secret Manager consumers, prohibited APIs, private PostgreSQL／IAP topology,
  Cloud Run limits, GCS lifecycle, Artifact Registry cleanup, and budget rules.
- `report` prints a bounded monthly resource-exposure report without secret
  values or raw payloads.

The Free Tier dev path intentionally verifies that no persistent-disk snapshot
exists. It does not create a snapshot, backup, HA, replica, or paid BigQuery
billing export; those require separate cost approval.
