locals {
  postgres_vm_name         = "janus-postgres-dev"
  postgres_vm_machine_type = "e2-micro"
  postgres_vm_zone         = "us-central1-a"
  postgres_boot_disk_gb    = 30
  postgres_network_tag     = "janus-postgres-db"
}

resource "google_compute_firewall" "postgres_iap_ssh" {
  project = var.project_id
  name    = "janus-postgres-iap-ssh"
  network = data.google_compute_subnetwork.direct_vpc.network

  direction     = "INGRESS"
  source_ranges = ["35.235.240.0/20"]
  target_tags   = [local.postgres_network_tag]

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }
}

resource "google_compute_firewall" "postgres_private_clients" {
  project = var.project_id
  name    = "janus-postgres-private-clients"
  network = data.google_compute_subnetwork.direct_vpc.network

  # Cloud Run Direct VPC egress network tags can scope egress rules, but they
  # are not supported as the source selector of an ingress firewall rule.
  # Keep this aligned with the private subnet CIDR allowed by pg_hba.conf.
  direction     = "INGRESS"
  source_ranges = [data.google_compute_subnetwork.direct_vpc.ip_cidr_range]
  target_tags   = [local.postgres_network_tag]

  allow {
    protocol = "tcp"
    ports    = ["5432"]
  }
}

resource "google_compute_instance" "postgres" {
  project      = var.project_id
  name         = local.postgres_vm_name
  zone         = local.postgres_vm_zone
  machine_type = local.postgres_vm_machine_type

  allow_stopping_for_update = false
  can_ip_forward            = false
  deletion_protection       = true

  tags = [local.postgres_network_tag]

  boot_disk {
    auto_delete = true

    initialize_params {
      image = "projects/cos-cloud/global/images/cos-stable-121-18867-528-78"
      size  = local.postgres_boot_disk_gb
      type  = "pd-standard"
    }
  }

  network_interface {
    subnetwork = data.google_compute_subnetwork.direct_vpc.self_link
    # Intentionally no access_config: the VM has no external IP.
  }

  service_account {
    email  = google_service_account.postgres_vm.email
    scopes = local.postgres_vm_oauth_scopes
  }

  metadata = {
    enable-oslogin         = "TRUE"
    block-project-ssh-keys = "TRUE"
  }

  shielded_instance_config {
    enable_secure_boot          = true
    enable_vtpm                 = true
    enable_integrity_monitoring = true
  }

  scheduling {
    automatic_restart   = true
    on_host_maintenance = "MIGRATE"
    preemptible         = false
  }

  lifecycle {
    precondition {
      condition     = local.postgres_vm_machine_type == "e2-micro"
      error_message = "Free Tier PostgreSQL must remain e2-micro."
    }
    precondition {
      condition     = startswith(local.postgres_vm_zone, "us-central1-")
      error_message = "Free Tier PostgreSQL must remain in us-central1."
    }
    precondition {
      condition     = local.postgres_boot_disk_gb <= 30
      error_message = "Total PostgreSQL persistent disk allocation must not exceed 30 GB."
    }
    precondition {
      condition     = !contains(local.postgres_vm_oauth_scopes, "https://www.googleapis.com/auth/cloud-platform")
      error_message = "The PostgreSQL VM must not use the broad cloud-platform OAuth scope."
    }
  }

  depends_on = [
    google_project_service.compute_direct_vpc_required["compute.googleapis.com"],
  ]
}

output "postgres_vm_private_ip" {
  description = "Private-only PostgreSQL endpoint; available after authorized apply."
  value       = google_compute_instance.postgres.network_interface[0].network_ip
}
