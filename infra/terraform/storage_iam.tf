locals {
  ingestion_core_service_account    = "ingestion-core@${var.project_id}.iam.gserviceaccount.com"
  intelligence_mart_service_account = "intelligence-mart@${var.project_id}.iam.gserviceaccount.com"
  trino_runtime_service_account     = "trino-runtime@${var.project_id}.iam.gserviceaccount.com"
}

resource "google_storage_bucket_iam_member" "stage_ingestion_writer" {
  bucket = google_storage_bucket.data["stage"].name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${local.ingestion_core_service_account}"
}

resource "google_storage_bucket_iam_member" "core_ingestion_writer" {
  bucket = google_storage_bucket.data["core"].name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${local.ingestion_core_service_account}"
}

resource "google_storage_bucket_iam_member" "core_trino_writer" {
  bucket = google_storage_bucket.data["core"].name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${local.trino_runtime_service_account}"
}

resource "google_storage_bucket_iam_member" "core_mart_reader" {
  bucket = google_storage_bucket.data["core"].name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${local.intelligence_mart_service_account}"
}
