resource "google_project_iam_member" "cloud_build_cloud_run_admin" {
  project = var.project_id
  role    = "roles/run.admin"
  member  = "serviceAccount:${var.ci_service_account_id}@${var.project_id}.iam.gserviceaccount.com"
}

resource "google_service_account_iam_member" "cloud_build_runtime_act_as" {
  for_each = toset([
    "ingestion-core",
    "intelligence-mart",
    "web-runtime",
  ])

  service_account_id = "projects/${var.project_id}/serviceAccounts/${each.value}@${var.project_id}.iam.gserviceaccount.com"
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${var.ci_service_account_id}@${var.project_id}.iam.gserviceaccount.com"
}
