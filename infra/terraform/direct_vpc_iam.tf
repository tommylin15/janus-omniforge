data "google_project" "current" {
  project_id = var.project_id
}

data "google_compute_subnetwork" "direct_vpc" {
  name    = var.direct_vpc_subnetwork_name
  project = var.project_id
  region  = var.region
}

locals {
  # Direct VPC egress attaches Cloud Run revisions directly to this subnet.
  # Keep this list explicit so later services/jobs cannot silently invent tags.
  direct_vpc_workload_tags = {
    ingestion_core    = "janus-ingestion-core"
    intelligence_mart = "janus-intelligence-mart"
    web               = "janus-web"
  }

  direct_vpc_network_users = toset([
    "serviceAccount:service-${data.google_project.current.number}@serverless-robot-prod.iam.gserviceaccount.com",
    "serviceAccount:${var.ci_service_account_id}@${var.project_id}.iam.gserviceaccount.com",
  ])
}

# Subnetwork-scoped access is sufficient for Direct VPC egress and avoids a
# project-wide roles/compute.networkUser grant.
resource "google_compute_subnetwork_iam_member" "direct_vpc_network_user" {
  for_each   = local.direct_vpc_network_users
  project    = var.project_id
  region     = data.google_compute_subnetwork.direct_vpc.region
  subnetwork = data.google_compute_subnetwork.direct_vpc.name
  role       = "roles/compute.networkUser"
  member     = each.value
}

output "direct_vpc_workload_tags" {
  description = "Approved Cloud Run Direct VPC egress network tags."
  value       = local.direct_vpc_workload_tags
}
