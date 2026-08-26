# Terraform development infrastructure

This directory declares the GitHub Actions → GCP Workload Identity Federation
trust boundary. Review the plan before applying it. The referenced
`janus-ci` service account must exist before this configuration can be applied.

No service-account keys are used.

The planned dev control-plane database is a self-managed PostgreSQL on a
Compute Engine `e2-micro` VM in `us-central1`, with a private address, no
external IP, at most 30 GB total Standard Persistent Disk, and IAP/OS Login.
Free Tier mode does not create scheduled snapshots, backups, HA, or replicas.
Terraform for that VM,
its disk, firewall, service-account attachment, and snapshot policy remains a pending
infrastructure task; reviewing this document does not authorize provisioning.

The dedicated `postgres-vm` service account is managed separately from the VM
and has no project-level roles by default. The future VM attachment must use
the exported logging/monitoring OAuth scope allowlist and must not use the
default Compute Engine service account or the `cloud-platform` scope. Secret
access is granted later per secret, never as a project-wide role.

PostgreSQL bootstrap, control, catalog, publication, and audit credentials use
five separate regional Secret Manager containers. Terraform manages only their
names and one workload-specific accessor per secret; it never manages a secret
version or credential value. Credential values must not be passed through
Terraform variables, state, metadata, or VM startup scripts.
The bootstrap secret is restricted to the named human bootstrap operator;
`postgres-vm` does not receive Secret Manager access because its OAuth scopes
deliberately exclude `cloud-platform`.

The Free Tier boundary is one eligible `e2-micro` in `us-central1`, up to 30 GB
Standard Persistent Disk and 1 GB/month outbound data. These are billing-account
conditions, not a guaranteed zero-cost contract.

The provisioning dependency is PostgreSQL VM → control/catalog schema bootstrap
→ Trino JDBC catalog. The PostgreSQL VM must be planned and validated before
any Trino Cloud Run deployment is applied.

Trino is not colocated on the PostgreSQL VM. Its planned runtime remains a
separate Cloud Run service with 2 vCPU and 4–8 GiB memory, min 0 and max 1.

Artifact Registry is subject to the repository cost guard: do not enable or
call Artifact Analysis API, Container Scanning API, vulnerability scanning, or
occurrence APIs. Terraform changes must not add those APIs or related triggers.

Cloud Run uses Direct VPC egress through the existing
`janusai-lake-poc-uscentral1` subnet. The Cloud Run service agent and `janus-ci`
deployer receive subnet-scoped `roles/compute.networkUser`; no project-wide
network grant or Serverless VPC Access connector is created. Approved revision
network tags are exported by Terraform for ingestion, mart, Trino, and web.

The configuration also declares three isolated dev GCS buckets:
`<project_id>-dev-stage`, `<project_id>-dev-core`, and `<project_id>-dev-mart`.
They use uniform bucket-level access, enforced public access prevention,
versioning, and layer-specific lifecycle retention. Review the lifecycle values
before applying because expiration deletes objects and archived versions.
