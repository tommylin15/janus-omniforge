locals {
  ingestion_job_name        = "janus-ingestion-core"
  ingestion_service_account = "ingestion-core@${var.project_id}.iam.gserviceaccount.com"
  ingestion_image           = "${var.region}-docker.pkg.dev/${var.project_id}/janusai-poc/ingestion-core:main"
}

resource "google_service_account" "ingestion_scheduler" {
  project      = var.project_id
  account_id   = "janus-ingestion-scheduler"
  display_name = "Janus ingestion scheduler"
}

resource "google_cloud_run_v2_job" "ingestion_core" {
  project  = var.project_id
  name     = local.ingestion_job_name
  location = var.region

  lifecycle {
    # Cloud Build updates this field to an immutable digest after each merge.
    ignore_changes = [client, client_version, template[0].template[0].containers[0].image]
  }

  template {
    task_count = 1

    template {
      service_account = local.ingestion_service_account
      timeout         = "900s"
      max_retries     = 1

      vpc_access {
        egress = "PRIVATE_RANGES_ONLY"
        network_interfaces {
          network    = "projects/${var.project_id}/global/networks/janusai-lake-poc"
          subnetwork = data.google_compute_subnetwork.direct_vpc.name
          tags       = [local.direct_vpc_workload_tags.ingestion_core]
        }
      }

      containers {
        image = local.ingestion_image

        resources {
          limits = {
            cpu    = "1"
            memory = "1Gi"
          }
        }

        env {
          name  = "GCP_PROJECT_ID"
          value = var.project_id
        }
        env {
          name  = "STAGE_BUCKET"
          value = google_storage_bucket.data["stage"].name
        }
        env {
          name  = "CORE_BUCKET"
          value = google_storage_bucket.data["core"].name
        }
        env {
          name  = "CONTROL_DB_HOST"
          value = google_compute_instance.postgres.network_interface[0].network_ip
        }
        env {
          name  = "CONTROL_DB_NAME"
          value = "janus_control"
        }
        env {
          name  = "CONTROL_DB_USER"
          value = "janus_control"
        }
        env {
          name = "CONTROL_DB_PASSWORD"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.postgres_role["control"].id
              version = "latest"
            }
          }
        }
        env {
          name  = "CONTROL_COLLECTION_CONFIG"
          value = "first-batch"
        }
        env {
          name  = "CATALOG_DB_HOST"
          value = google_compute_instance.postgres.network_interface[0].network_ip
        }
        env {
          name  = "CATALOG_DB_NAME"
          value = "janus_control"
        }
        env {
          name  = "CATALOG_DB_USER"
          value = "janus_catalog"
        }
        env {
          name = "CATALOG_DB_PASSWORD"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.postgres_role["catalog"].id
              version = "latest"
            }
          }
        }
        env {
          name  = "ICEBERG_WAREHOUSE"
          value = "gs://${google_storage_bucket.data["core"].name}/warehouse"
        }
        env {
          name  = "DUCKDB_MEMORY_LIMIT"
          value = "384MB"
        }
        env {
          name  = "DUCKDB_THREADS"
          value = "1"
        }
        env {
          name  = "DUCKDB_QUERY_TIMEOUT_SECONDS"
          value = "60"
        }
      }
    }
  }

  depends_on = [
    google_compute_subnetwork_iam_member.direct_vpc_network_user,
    google_artifact_registry_repository_iam_member.runtime_ingestion_reader,
  ]
}

resource "google_cloud_run_v2_job_iam_member" "scheduler_ingestion_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_job.ingestion_core.name
  role     = "roles/run.invoker"
  member   = google_service_account.ingestion_scheduler.member
}

resource "google_cloud_scheduler_job" "ingestion_daily" {
  project          = var.project_id
  region           = var.region
  name             = "janus-ingestion-daily"
  description      = "Collect first-batch market sources into Stage before 08:00 Asia/Taipei."
  schedule         = "30 7 * * *"
  time_zone        = "Asia/Taipei"
  paused           = false
  attempt_deadline = "320s"

  retry_config {
    retry_count          = 1
    max_retry_duration   = "600s"
    min_backoff_duration = "30s"
    max_backoff_duration = "120s"
  }

  http_target {
    http_method = "POST"
    uri         = "https://run.googleapis.com/v2/projects/${var.project_id}/locations/${var.region}/jobs/${google_cloud_run_v2_job.ingestion_core.name}:run"

    oauth_token {
      service_account_email = google_service_account.ingestion_scheduler.email
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }

  depends_on = [
    google_project_service.compute_direct_vpc_required["cloudscheduler.googleapis.com"],
    google_cloud_run_v2_job_iam_member.scheduler_ingestion_invoker,
  ]
}

output "ingestion_schedule" {
  value = {
    job       = google_cloud_run_v2_job.ingestion_core.name
    scheduler = google_cloud_scheduler_job.ingestion_daily.name
    cron      = google_cloud_scheduler_job.ingestion_daily.schedule
    time_zone = google_cloud_scheduler_job.ingestion_daily.time_zone
  }
}
