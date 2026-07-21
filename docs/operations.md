# Operations

## Health endpoints

- `/health/live` verifies that the API process can serve requests.
- `/health/ready` reports required and optional dependency state.
- `/health/agent-tools` reports governed-tool latency and failure health.
- graph and vector probes diagnose their respective integrations.

Liveness should not depend on optional providers. Readiness may report degraded operation without restarting the service.

## Startup and migrations

The container entrypoint applies Alembic migrations before starting Uvicorn. Migration failures stop deployment. Neo4j initialisation is bounded by a timeout and is non-fatal unless configured as required.

## Logging

Structured logs include request IDs, route, status, duration, and controlled runtime events. Exception details remain server-side. Operators should correlate query IDs, run IDs, approval request IDs, and request IDs when investigating failures.

## Common incidents

- **Queries remain queued:** verify dispatch mode and service availability.
- **Database migration failure:** inspect the first Alembic exception; do not create tables manually.
- **Graph unavailable:** confirm URI, TLS scheme, credentials, and feature flags.
- **Repeated provider failures:** inspect tool-health categories and latency before increasing retries.
- **Cross-origin failure:** validate the exact frontend origin and JSON/list environment parsing.

## Recovery

Retry only idempotent operations. Approval resume must use the stored snapshot. Roll back application releases independently from schema migrations where the migration is not backward compatible.
