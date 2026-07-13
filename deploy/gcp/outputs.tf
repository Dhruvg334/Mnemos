output "api_url" { value = google_cloud_run_v2_service.api.uri }
output "artifact_repository" { value = google_artifact_registry_repository.backend.name }
output "migration_job_name" { value = google_cloud_run_v2_job.migrate.name }
output "runtime_service_account" { value = google_service_account.runtime.email }
output "database_private_ip" {
  value = google_sql_database_instance.postgres.private_ip_address
  sensitive = true
}
output "redis_host" {
  value = google_redis_instance.cache.host
  sensitive = true
}
