# Terraform development infrastructure

This directory declares the GitHub Actions → GCP Workload Identity Federation
trust boundary. Review the plan before applying it. The referenced
`janus-ci` service account must exist before this configuration can be applied.

No service-account keys are used.

The configuration also declares three isolated dev GCS buckets:
`<project_id>-dev-stage`, `<project_id>-dev-core`, and `<project_id>-dev-mart`.
They use uniform bucket-level access, enforced public access prevention,
versioning, and layer-specific lifecycle retention. Review the lifecycle values
before applying because expiration deletes objects and archived versions.
