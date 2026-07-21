# Deployment

## Local environment

Docker Compose provisions PostgreSQL with pgvector, Redis, object storage, and optional Neo4j. The API and frontend may run outside containers for faster iteration.

## Backend service

The managed backend uses the repository Dockerfile and explicit entrypoint command. Required configuration includes database, Redis, JWT, frontend origin, and provider settings. Neo4j and object storage may be disabled for a reduced demonstration deployment.

## Frontend service

The Next.js project root is `frontend/`. Server-side routes use `MNEMOS_API_URL`; the browser does not need the private backend base URL embedded in client code. Public demonstration access is enabled independently from private workspace authentication.

## Release checks

1. apply focused backend tests for changed behaviour;
2. build the production frontend;
3. apply migrations in a disposable or staging database;
4. deploy the API and verify liveness/readiness;
5. deploy the frontend and verify guest and authenticated paths;
6. exercise one successful query and one controlled failure path.

Production hostnames, credentials, and customer-specific values must not be committed to documentation.
