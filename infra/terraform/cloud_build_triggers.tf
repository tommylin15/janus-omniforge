variable "github_owner" {
  description = "GitHub repository owner used by Cloud Build connection."
  type        = string
  default     = "tommylin15"
}

variable "github_repository_name" {
  description = "GitHub repository name used by Cloud Build connection."
  type        = string
  default     = "janus-omniforge"
}

variable "cloud_build_github_connection" {
  description = "Existing Developer Connect GitHub connection ID."
  type        = string
  default     = "github"
}

resource "google_cloudbuild_trigger" "ingestion_core" {
  name            = "janus-ingestion-core"
  description     = "Build ingestion-core changes only."
  location        = var.region
  filename        = "cloudbuild.yaml"
  included_files  = ["jobs/ingestion-core/**", "packages/contracts/**", "packages/observability/**", "cloudbuild.yaml"]
  service_account = "projects/${var.project_id}/serviceAccounts/janus-ci@${var.project_id}.iam.gserviceaccount.com"

  substitutions = {
    _DOCKERFILE    = "jobs/ingestion-core/Dockerfile"
    _IMAGE_NAME    = "ingestion-core"
    _IMAGE_TAG     = "main"
    _DEPLOY_TARGET = "job"
    _RUNTIME_NAME  = "janus-ingestion-core"
  }

  developer_connect_event_config {
    git_repository_link = "projects/${var.project_id}/locations/${var.region}/connections/${var.cloud_build_github_connection}/gitRepositoryLinks/${var.github_owner}-${var.github_repository_name}"
    push {
      branch = "^main$"
    }
  }
}

resource "google_cloudbuild_trigger" "intelligence_mart" {
  name            = "janus-intelligence-mart"
  description     = "Build intelligence-mart changes only."
  location        = var.region
  filename        = "cloudbuild.yaml"
  included_files  = ["jobs/intelligence-mart/**", "packages/contracts/**", "packages/observability/**", "cloudbuild.yaml"]
  service_account = "projects/${var.project_id}/serviceAccounts/janus-ci@${var.project_id}.iam.gserviceaccount.com"

  substitutions = {
    _DOCKERFILE = "jobs/intelligence-mart/Dockerfile"
    _IMAGE_NAME = "intelligence-mart"
  }

  developer_connect_event_config {
    git_repository_link = "projects/${var.project_id}/locations/${var.region}/connections/${var.cloud_build_github_connection}/gitRepositoryLinks/${var.github_owner}-${var.github_repository_name}"
    push {
      branch = "^main$"
    }
  }
}

resource "google_cloudbuild_trigger" "trino" {
  name            = "janus-trino"
  description     = "Build and deploy the pinned Trino image to Cloud Run dev."
  location        = var.region
  filename        = "cloudbuild.yaml"
  included_files  = ["services/trino/**", "cloudbuild.yaml"]
  service_account = "projects/${var.project_id}/serviceAccounts/janus-ci@${var.project_id}.iam.gserviceaccount.com"

  substitutions = {
    _DOCKERFILE    = "services/trino/Dockerfile"
    _IMAGE_NAME    = "trino"
    _IMAGE_TAG     = "main"
    _DEPLOY_TARGET = "service"
    _RUNTIME_NAME  = "janus-trino"
  }

  developer_connect_event_config {
    git_repository_link = "projects/${var.project_id}/locations/${var.region}/connections/${var.cloud_build_github_connection}/gitRepositoryLinks/${var.github_owner}-${var.github_repository_name}"
    push {
      branch = "^main$"
    }
  }
}
