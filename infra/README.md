# Infrastructure

Declarative development infrastructure will live here. Do not run provisioning,
deployment, or destructive commands without explicit user authorization.

## PostgreSQL dev/MVP decision

The development control database is planned as a self-managed PostgreSQL on a
single Compute Engine `e2-micro` VM in `us-central1`. Free Tier mode fixes the
machine type, limits total Standard Persistent Disk to 30 GB, uses no external
IP, and keeps outbound data within 1 GB/month. It uses a private IP and
IAP/OS Login; port 5432 must not be public. Automatic snapshots, backups, HA,
and replicas are disabled in this mode because they are not covered by the
Free Tier target.

The VM and database Terraform resources are not provisioned yet. Cloud SQL is
not part of the selected dev topology.

Free Tier eligibility is a billing-account and region condition. Terraform can
enforce the resource shape but cannot guarantee a zero bill; deployment must
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
