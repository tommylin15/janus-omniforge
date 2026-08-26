locals {
  # Deliberately excludes containeranalysis.googleapis.com and
  # containerscanning.googleapis.com. Do not add either service here.
  compute_direct_vpc_required_apis = toset([
    "compute.googleapis.com",
    "iam.googleapis.com",
    "iap.googleapis.com",
    "oslogin.googleapis.com",
    "run.googleapis.com",
    "cloudscheduler.googleapis.com",
    "serviceusage.googleapis.com",
  ])
}

resource "google_project_service" "compute_direct_vpc_required" {
  for_each = local.compute_direct_vpc_required_apis

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}
