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

variable "direct_vpc_subnetwork_name" {
  description = "Existing private subnet used by Cloud Run Direct VPC egress and the PostgreSQL VM."
  type        = string
  default     = "janusai-lake-poc-uscentral1"

  validation {
    condition     = var.direct_vpc_subnetwork_name == "janusai-lake-poc-uscentral1"
    error_message = "Direct VPC egress must remain on the approved private subnet."
  }
}

variable "postgres_bootstrap_operator" {
  description = "Human operator allowed to retrieve the one-time PostgreSQL bootstrap credential."
  type        = string
  default     = "user:tommylin15@gmail.com"

  validation {
    condition     = startswith(var.postgres_bootstrap_operator, "user:")
    error_message = "The bootstrap accessor must be an explicitly named human user."
  }
}
