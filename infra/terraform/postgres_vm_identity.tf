locals {
  postgres_vm_service_account_id = "postgres-vm"

  # The future VM must use this explicit allowlist. In particular, do not use
  # https://www.googleapis.com/auth/cloud-platform.
  postgres_vm_oauth_scopes = toset([
    "https://www.googleapis.com/auth/devstorage.read_only",
    "https://www.googleapis.com/auth/logging.write",
    "https://www.googleapis.com/auth/monitoring.write",
  ])
}

resource "google_service_account" "postgres_vm" {
  project      = var.project_id
  account_id   = local.postgres_vm_service_account_id
  display_name = "PostgreSQL VM runtime"
  description  = "Dedicated least-privilege identity for the Free Tier PostgreSQL VM; no default project roles."
}

output "postgres_vm_service_account_email" {
  description = "Dedicated identity for the PostgreSQL VM."
  value       = google_service_account.postgres_vm.email
}

output "postgres_vm_allowed_oauth_scopes" {
  description = "Explicit OAuth scope allowlist for the future VM attachment."
  value       = local.postgres_vm_oauth_scopes
}
