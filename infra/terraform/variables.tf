variable "project_id" {
  description = "GCP project that owns the CI identity resources."
  type        = string
  default     = "gen-lang-client-0593591102"
}

variable "region" {
  description = "Default GCP region."
  type        = string
  default     = "us-central1"
}

variable "github_repository" {
  description = "GitHub repository allowed to impersonate the CI service account."
  type        = string
  default     = "tommylin15/janus-omniforge"
}

variable "ci_service_account_id" {
  description = "Existing service account ID used by GitHub Actions."
  type        = string
  default     = "janus-ci"
}
