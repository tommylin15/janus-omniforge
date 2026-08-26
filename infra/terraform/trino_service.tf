locals {
  trino_service_name = "janus-trino"
  trino_service_account = "trino-runtime@${var.project_id}.iam.gserviceaccount.com"
  trino_image_digest = "us-central1-docker.pkg.dev/${var.project_id}/janusai-poc/trino@sha256:e6376bfd8b4315fe70ebdba0d2d683881ac80e112099cbc09528388c6af10a61"
}

resource "google_cloud_run_v2_service" "trino" {
  project  = var.project_id
  name     = local.trino_service_name
  location = var.region
  ingress  = "INGRESS_TRAFFIC_INTERNAL_ONLY"

  template {
    service_account = local.trino_service_account
    timeout         = "900s"

    scaling {
      min_instance_count = 0
      max_instance_count = 1
    }

    vpc_access {
      egress = "PRIVATE_RANGES_ONLY"
      network_interfaces {
        network    = data.google_compute_subnetwork.direct_vpc.network
        subnetwork = data.google_compute_subnetwork.direct_vpc.name
        tags       = [local.direct_vpc_workload_tags.trino]
      }
    }

    containers {
      image = local.trino_image_digest

      resources {
        limits = {
          cpu    = "2"
          memory = "4Gi"
        }
        cpu_idle = false
      }

      ports {
        container_port = 8080
      }

      env {
        name  = "TRINO_ENVIRONMENT"
        value = "dev"
      }
      env {
        name  = "TRINO_NODE_ID"
        value = "${local.trino_service_name}-coordinator"
      }
      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "CORE_BUCKET"
        value = google_storage_bucket.data["core"].name
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
    }
  }

  depends_on = [
    google_compute_subnetwork_iam_member.direct_vpc_network_user,
    google_secret_manager_secret_iam_member.postgres_role_accessor,
  ]
}

# No public invoker is granted. Callers must be explicitly listed workload
# identities and Cloud Run still enforces internal ingress.
resource "google_cloud_run_v2_service_iam_member" "trino_ingestion_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.trino.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:ingestion-core@${var.project_id}.iam.gserviceaccount.com"
}

resource "google_cloud_run_v2_service_iam_member" "trino_mart_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.trino.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:intelligence-mart@${var.project_id}.iam.gserviceaccount.com"
}

output "trino_service_name" {
  value = google_cloud_run_v2_service.trino.name
}
