provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  prefix = "mnemos-${var.environment}"
  labels = {
    application = "mnemos"
    environment = var.environment
    managed_by  = "terraform"
  }
}

resource "google_project_service" "services" {
  for_each = toset([
    "artifactregistry.googleapis.com",
    "compute.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "servicenetworking.googleapis.com",
    "sqladmin.googleapis.com",
    "redis.googleapis.com",
    "vpcaccess.googleapis.com",
  ])
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_artifact_registry_repository" "backend" {
  location      = var.region
  repository_id = var.artifact_repository
  format        = "DOCKER"
  labels        = local.labels
  depends_on    = [google_project_service.services]
}

resource "google_compute_network" "main" {
  name                    = "${local.prefix}-network"
  auto_create_subnetworks = false
  depends_on              = [google_project_service.services]
}

resource "google_compute_subnetwork" "main" {
  name          = "${local.prefix}-subnet"
  region        = var.region
  network       = google_compute_network.main.id
  ip_cidr_range = "10.20.0.0/24"
}

resource "google_compute_global_address" "private_services" {
  name          = "${local.prefix}-private-services"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.main.id
}

resource "google_service_networking_connection" "private_services" {
  network                 = google_compute_network.main.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_services.name]
  depends_on              = [google_project_service.services]
}

resource "google_vpc_access_connector" "serverless" {
  name          = "${local.prefix}-connector"
  region        = var.region
  network       = google_compute_network.main.name
  ip_cidr_range = "10.21.0.0/28"
  min_instances = 2
  max_instances = 3
}

resource "random_password" "database" {
  length  = 32
  special = false
}

resource "google_sql_database_instance" "postgres" {
  name             = "${local.prefix}-postgres"
  region           = var.region
  database_version = "POSTGRES_16"
  settings {
    tier              = var.db_tier
    availability_type = "ZONAL"
    disk_type         = "PD_SSD"
    disk_size         = 20
    disk_autoresize   = true
    user_labels       = local.labels
    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
      start_time                     = "03:00"
    }
    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.main.id
      ssl_mode        = "ENCRYPTED_ONLY"
    }
  }
  deletion_protection = true
  depends_on          = [google_service_networking_connection.private_services]
}

resource "google_sql_database" "mnemos" {
  name     = "mnemos"
  instance = google_sql_database_instance.postgres.name
}

resource "google_sql_user" "mnemos" {
  name     = "mnemos"
  instance = google_sql_database_instance.postgres.name
  password = random_password.database.result
}

resource "google_redis_instance" "cache" {
  name               = "${local.prefix}-redis"
  region             = var.region
  tier               = "BASIC"
  memory_size_gb     = var.redis_memory_size_gb
  redis_version      = "REDIS_7_2"
  authorized_network = google_compute_network.main.id
  connect_mode       = "PRIVATE_SERVICE_ACCESS"
  labels             = local.labels
  depends_on          = [google_service_networking_connection.private_services]
}

resource "google_service_account" "runtime" {
  account_id   = "${local.prefix}-runtime"
  display_name = "Mnemos backend runtime"
}

resource "google_project_iam_member" "runtime_secret_access" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_secret_manager_secret" "secret" {
  for_each = toset([
    "database-url",
    "jwt-secret",
    "s3-access-key",
    "s3-secret-key",
    "agent-service-api-key",
    "ingestion-service-api-key",
  ])
  secret_id = "${local.prefix}-${each.value}"
  replication { auto {} }
  labels     = local.labels
}

resource "google_secret_manager_secret_version" "database_url" {
  secret      = google_secret_manager_secret.secret["database-url"].id
  secret_data = "postgresql+asyncpg://mnemos:${random_password.database.result}@${google_sql_database_instance.postgres.private_ip_address}:5432/mnemos"
}
resource "google_secret_manager_secret_version" "jwt_secret" {
  secret      = google_secret_manager_secret.secret["jwt-secret"].id
  secret_data = var.jwt_secret
}
resource "google_secret_manager_secret_version" "s3_access_key" {
  secret      = google_secret_manager_secret.secret["s3-access-key"].id
  secret_data = var.s3_access_key
}
resource "google_secret_manager_secret_version" "s3_secret_key" {
  secret      = google_secret_manager_secret.secret["s3-secret-key"].id
  secret_data = var.s3_secret_key
}
resource "google_secret_manager_secret_version" "agent_key" {
  secret      = google_secret_manager_secret.secret["agent-service-api-key"].id
  secret_data = var.agent_service_api_key
}
resource "google_secret_manager_secret_version" "ingestion_key" {
  secret      = google_secret_manager_secret.secret["ingestion-service-api-key"].id
  secret_data = var.ingestion_service_api_key
}

resource "google_cloud_run_v2_service" "api" {
  name     = var.service_name
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.runtime.email
    timeout         = "300s"

    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    vpc_access {
      connector = google_vpc_access_connector.serverless.id
      egress    = "PRIVATE_RANGES_ONLY"
    }

    containers {
      image = var.container_image
      args  = ["api"]

      ports { container_port = 8000 }
      resources {
        limits = { cpu = "1", memory = "1Gi" }
        cpu_idle = true
      }

      env { name = "APP_ENV", value = var.environment }
      env { name = "EXPOSE_API_DOCS", value = "false" }
      env { name = "CORS_ORIGINS", value = join(",", var.frontend_origins) }
      env { name = "REDIS_URL", value = "redis://${google_redis_instance.cache.host}:${google_redis_instance.cache.port}/0" }
      env { name = "S3_ENDPOINT_URL", value = var.s3_endpoint_url }
      env { name = "S3_BUCKET", value = var.s3_bucket }
      env { name = "S3_REGION", value = var.s3_region }
      env { name = "AGENT_GATEWAY_MODE", value = var.agent_service_url == "" ? "mock" : "http" }
      env { name = "AGENT_SERVICE_URL", value = var.agent_service_url }
      env { name = "INGESTION_GATEWAY_MODE", value = var.ingestion_service_url == "" ? "mock" : "http" }
      env { name = "INGESTION_SERVICE_URL", value = var.ingestion_service_url }

      dynamic "env" {
        for_each = {
          DATABASE_URL              = google_secret_manager_secret.secret["database-url"].id
          JWT_SECRET                = google_secret_manager_secret.secret["jwt-secret"].id
          S3_ACCESS_KEY             = google_secret_manager_secret.secret["s3-access-key"].id
          S3_SECRET_KEY             = google_secret_manager_secret.secret["s3-secret-key"].id
          AGENT_SERVICE_API_KEY     = google_secret_manager_secret.secret["agent-service-api-key"].id
          INGESTION_SERVICE_API_KEY = google_secret_manager_secret.secret["ingestion-service-api-key"].id
        }
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = env.value
              version = "latest"
            }
          }
        }
      }

      startup_probe {
        failure_threshold     = 20
        initial_delay_seconds = 2
        period_seconds        = 3
        timeout_seconds       = 2
        http_get { path = "/health/live", port = 8000 }
      }
      liveness_probe {
        failure_threshold = 3
        period_seconds    = 30
        timeout_seconds   = 3
        http_get { path = "/health/live", port = 8000 }
      }
    }
  }

  labels = local.labels
  depends_on = [
    google_project_iam_member.runtime_secret_access,
    google_secret_manager_secret_version.database_url,
    google_secret_manager_secret_version.jwt_secret,
    google_secret_manager_secret_version.s3_access_key,
    google_secret_manager_secret_version.s3_secret_key,
  ]
}

resource "google_cloud_run_v2_job" "migrate" {
  name     = var.migration_job_name
  location = var.region

  template {
    template {
      service_account = google_service_account.runtime.email
      timeout         = "600s"
      max_retries     = 1
      vpc_access {
        connector = google_vpc_access_connector.serverless.id
        egress    = "PRIVATE_RANGES_ONLY"
      }
      containers {
        image = var.container_image
        args  = ["migrate"]
        env {
          name = "DATABASE_URL"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.secret["database-url"].id
              version = "latest"
            }
          }
        }
      }
    }
  }
  labels = local.labels
}

resource "google_cloud_run_service_iam_member" "public_api" {
  location = google_cloud_run_v2_service.api.location
  service  = google_cloud_run_v2_service.api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
