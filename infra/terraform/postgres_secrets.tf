locals {
  postgres_role_secrets = {
    bootstrap = {
      secret_id = "janus-postgres-bootstrap-password"
      accessor  = var.postgres_bootstrap_operator
    }
    control = {
      secret_id = "janus-postgres-control-password"
      accessor  = "serviceAccount:ingestion-core@${var.project_id}.iam.gserviceaccount.com"
    }
    catalog = {
      secret_id = "janus-postgres-catalog-password"
      accessor  = "serviceAccount:ingestion-core@${var.project_id}.iam.gserviceaccount.com"
    }
    publication = {
      secret_id = "janus-postgres-publication-password"
      accessor  = "serviceAccount:intelligence-mart@${var.project_id}.iam.gserviceaccount.com"
    }
    audit = {
      secret_id = "janus-postgres-audit-password"
      accessor  = "serviceAccount:web-runtime@${var.project_id}.iam.gserviceaccount.com"
    }
  }
}

resource "google_project_service" "postgres_secret_manager" {
  project            = var.project_id
  service            = "secretmanager.googleapis.com"
  disable_on_destroy = false
}

# Create only empty Secret containers. Password values must be added
# out-of-band and must never be Terraform inputs or resources.
resource "google_secret_manager_secret" "postgres_role" {
  for_each = local.postgres_role_secrets

  project   = var.project_id
  secret_id = each.value.secret_id

  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }

  labels = {
    component = "postgresql"
    db_role   = each.key
    managed   = "terraform-container-only"
  }

  lifecycle {
    prevent_destroy = true
  }

  depends_on = [google_project_service.postgres_secret_manager]
}

# One secret, one workload accessor. Do not replace this with a project-level
# accessor role or a shared credential.
resource "google_secret_manager_secret_iam_member" "postgres_role_accessor" {
  for_each = local.postgres_role_secrets

  project   = var.project_id
  secret_id = google_secret_manager_secret.postgres_role[each.key].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = each.value.accessor
}

resource "google_secret_manager_secret_iam_member" "web_control_accessor" {
  project   = var.project_id
  secret_id = google_secret_manager_secret.postgres_role["control"].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:web-runtime@${var.project_id}.iam.gserviceaccount.com"
}

resource "google_secret_manager_secret_iam_member" "web_catalog_accessor" {
  project   = var.project_id
  secret_id = google_secret_manager_secret.postgres_role["catalog"].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:web-runtime@${var.project_id}.iam.gserviceaccount.com"
}

output "postgres_role_secret_names" {
  description = "Empty PostgreSQL role Secret containers; values are managed out-of-band."
  value = {
    for role, secret in google_secret_manager_secret.postgres_role : role => secret.secret_id
  }
}
