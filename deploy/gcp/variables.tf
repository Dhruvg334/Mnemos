variable "project_id" { type = string }
variable "region" { type = string, default = "asia-south1" }
variable "environment" { type = string, default = "production" }
variable "service_name" { type = string, default = "mnemos-api" }
variable "migration_job_name" { type = string, default = "mnemos-migrate" }
variable "artifact_repository" { type = string, default = "mnemos" }
variable "container_image" { type = string }
variable "frontend_origins" { type = list(string), default = [] }
variable "agent_service_url" { type = string, default = "" }
variable "ingestion_service_url" { type = string, default = "" }
variable "s3_endpoint_url" { type = string }
variable "s3_bucket" { type = string, default = "mnemos-documents" }
variable "s3_region" { type = string, default = "auto" }
variable "s3_access_key" { type = string, sensitive = true }
variable "s3_secret_key" { type = string, sensitive = true }
variable "jwt_secret" { type = string, sensitive = true }
variable "agent_service_api_key" { type = string, sensitive = true, default = "" }
variable "ingestion_service_api_key" { type = string, sensitive = true, default = "" }
variable "db_tier" { type = string, default = "db-custom-1-3840" }
variable "redis_memory_size_gb" { type = number, default = 1 }
variable "min_instances" { type = number, default = 0 }
variable "max_instances" { type = number, default = 5 }
