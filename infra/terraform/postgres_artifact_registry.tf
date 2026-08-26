resource "google_artifact_registry_repository" "postgres" {
  project       = var.project_id
  location      = var.region
  repository_id = "janus-postgres"
  description   = "Pinned PostgreSQL runtime image for the private Free Tier VM. Scanning is prohibited."
  format        = "DOCKER"

  cleanup_policy_dry_run = false

  cleanup_policies {
    id     = "delete-untagged-after-3-days"
    action = "DELETE"
    condition {
      tag_state  = "UNTAGGED"
      older_than = "259200s"
    }
  }

  cleanup_policies {
    id     = "keep-three-tagged-versions"
    action = "KEEP"
    most_recent_versions {
      keep_count = 3
    }
  }
}

resource "google_artifact_registry_repository_iam_member" "postgres_vm_reader" {
  project    = var.project_id
  location   = google_artifact_registry_repository.postgres.location
  repository = google_artifact_registry_repository.postgres.name
  role       = "roles/artifactregistry.reader"
  member     = google_service_account.postgres_vm.member
}

