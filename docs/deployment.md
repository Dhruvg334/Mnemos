# Deployment

## Topology

The production profile separates the browser-facing application from data and model services:

```text
Next.js frontend
    └── server-side API proxy
          └── FastAPI service
                ├── PostgreSQL + pgvector
                ├── Redis
                ├── Neo4j AuraDB (optional)
                ├── S3-compatible object storage
                └── cross-encoder reranker (optional)
```

The frontend receives only the public API base URL. Database, graph, object-storage, JWT, and provider credentials belong on the backend service.

## Backend service

The managed backend uses the repository Dockerfile and the explicit entrypoint:

```text
/app/scripts/container-entrypoint.sh migrate-and-api
```

Migrations run before Uvicorn starts. The liveness probe is `/health/live`; dependency failures are reported separately through readiness and diagnostic endpoints.

### Neo4j AuraDB

Add the Aura credentials to the backend service environment, not to Vercel:

```env
NEO4J_ENABLED=true
NEO4J_STARTUP_REQUIRED=false
NEO4J_REQUIRED_FOR_READINESS=false
NEO4J_URI=neo4j+s://<instance>.databases.neo4j.io
NEO4J_USER=<username from the Aura credential file>
NEO4J_PASSWORD=<password from the Aura credential file>
NEO4J_MAX_CONNECTION_POOL_SIZE=10
```

Use the username and password exactly as supplied when the Aura instance is created. `neo4j+s://` provides an encrypted, certificate-verified connection. Keeping startup and readiness requirements false allows the API to remain available during a temporary graph outage while graph-dependent tools report degradation.

A small pool is recommended for the free API and Aura tiers. Increase it only after observing concurrent graph demand and Aura connection limits.

### Cross-encoder reranker

Set the public Hugging Face Space endpoint on the backend service:

```env
CROSS_ENCODER_URL=https://<space-subdomain>.hf.space

# Live agent runtime
AGENT_GATEWAY_MODE=langgraph
MOCK_AGENT_ENABLED=false
GROQ_API_KEY=<secret>
GROQ_MODEL=llama-3.3-70b-versatile
FAST_LLM_MODEL=llama-3.1-8b-instant
GROQ_API_BASE=https://api.groq.com/openai/v1
```

The reranker is optional. Free Spaces can sleep after inactivity, so the retrieval pipeline must retain its timeout and fallback behaviour. Do not expose this URL as a browser credential or add provider secrets to the frontend environment.

## Frontend service

The Next.js project root is `frontend/`. Required environment:

```env
MNEMOS_API_URL=https://<backend-host>/api/v1
AUTH_REQUIRED=false
AUTH_REFRESH_COOKIE_SECONDS=604800
```

Server-side route handlers call the backend and store session tokens in HttpOnly cookies. The browser does not receive backend secrets.

## Release checks

1. run focused tests for changed behaviour;
2. build the production frontend from a clean install;
3. apply migrations in a disposable or staging database;
4. deploy the API and verify liveness and readiness;
5. verify Neo4j and reranker diagnostics independently;
6. deploy the frontend and test guest and authenticated paths;
7. execute one successful query, one missing-evidence case, and one controlled provider failure.

Production hostnames, credentials, and customer-specific values must not be committed to documentation.
