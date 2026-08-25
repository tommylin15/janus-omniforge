locals {
  storage_buckets = {
    stage = {
      name          = "${var.project_id}-dev-stage"
      delete_after  = 30
      storage_class = "STANDARD"
    }
    core = {
      name          = "${var.project_id}-dev-core"
      delete_after  = 365
      storage_class = "STANDARD"
    }
    mart = {
      name          = "${var.project_id}-dev-mart"
      delete_after  = 365
      storage_class = "STANDARD"
    }
  }
}

resource "google_storage_bucket" "data" {
  for_each = local.storage_buckets

  name                        = each.value.name
  location                    = var.region
  project                     = var.project_id
  storage_class               = each.value.storage_class
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  labels = {
    environment = "dev"
    layer       = each.key
    managed_by  = "terraform"
  }

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      age = each.value.delete_after
    }
    action {
      type = "Delete"
    }
  }

  lifecycle_rule {
    condition {
      num_newer_versions = 3
      with_state         = "ARCHIVED"
    }
    action {
      type = "Delete"
    }
  }
}

output "dev_data_bucket_names" {
  description = "GCS buckets for the dev Stage, Core, and Mart layers."
  value       = { for layer, bucket in google_storage_bucket.data : layer => bucket.name }
}
