locals {
  web_service_name = "janus-web"
  web_image        = "${var.region}-docker.pkg.dev/${var.project_id}/janusai-poc/web:main"
}

resource "google_cloud_run_v2_service" "web" {
  project  = var.project_id
  name     = local.web_service_name
  location = var.region

  template {
    service_account = "web-runtime@${var.project_id}.iam.gserviceaccount.com"
    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }
    timeout = "60s"
    vpc_access {
      egress = "PRIVATE_RANGES_ONLY"
      network_interfaces {
        network    = "projects/${var.project_id}/global/networks/janusai-lake-poc"
        subnetwork = data.google_compute_subnetwork.direct_vpc.name
        tags       = [local.direct_vpc_workload_tags.web]
      }
    }
    containers {
      image = local.web_image
      resources {
        limits = { cpu = "1", memory = "1Gi" }
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
        name  = "ICEBERG_WAREHOUSE"
        value = "gs://${google_storage_bucket.data["core"].name}/warehouse"
      }
      env {
        name  = "WEB_QUERY_MAX_ROWS"
        value = "200"
      }
    }
  }
  lifecycle {
    ignore_changes = [client, client_version, template[0].containers[0].image]
  }
  depends_on = [
    google_compute_subnetwork_iam_member.direct_vpc_network_user,
    google_secret_manager_secret_iam_member.web_control_accessor,
    google_secret_manager_secret_iam_member.web_catalog_accessor,
  ]
}

resource "google_cloud_run_service_iam_member" "web_invoker" {
  project  = var.project_id
  location = var.region
  service  = google_cloud_run_v2_service.web.name
  role     = "roles/run.invoker"
  member   = "user:tommylin15@gmail.com"
}
