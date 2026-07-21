# Release Evidence

## Validation scope

This record describes the deterministic engineering validation performed for the current Mnemos release. It is deliberately separated from provider-backed model evaluation and from claims about accuracy on private industrial data.

## Environment

| Component | Version used for final validation |
|---|---|
| Python | 3.13.5 for repository validation; project target remains Python 3.12 |
| Node.js | 22.16.0 |
| npm | 10.9.2 |
| Next.js | 15.5.20 |
| React | 19.1.1 |

The application runtime targets Python 3.12. The final suite also passed under the available Python 3.13 validation environment, providing an additional compatibility signal but not replacing the declared 3.12 target.

## Commands and results

### Backend quality

```bash
python -m ruff check src tests scripts
python -m compileall -q src tests scripts
python -m pytest -q --strict-markers
```

Result:

```text
Ruff: clean
Compilation: passed
Tests: 902 passed, 2 deselected
Project-level suite: 71 passed, 2 deselected in 14.98 s
Agentic package suite: 831 passed in 14.95 s
```

The two deselected tests are marked integration tests that require live infrastructure, provider credentials, and seeded external services.

### Frontend production validation

```bash
cd frontend
npm ci
npm run build
npm audit --omit=dev
```

Result:

```text
Production build: passed
Static and dynamic routes: 27 generated
Dashboard route bundle: 26.7 kB
Shared first-load JavaScript: 102 kB
Production dependency audit: 0 known vulnerabilities
```

## Codebase scale

Counts exclude generated output, dependency directories, and caches.

| Area | Files | Lines |
|---|---:|---:|
| Python under `src/` | 204 | 47,056 |
| Project-level Python tests | 25 | 1,536 |
| Frontend JavaScript | 61 | 4,492 |
| Alembic migrations | 12 | - |
| API router modules | 11 | - |
| Explicit test functions collected statically | 872 | - |

Parameterized tests explain why the executed test count is higher than the static function count.

## Security review performed

- Repository scan for common API-key and private-key patterns. No live credential was found.
- Production settings reject weak JWT secrets and wildcard CORS.
- Anonymous dashboard access was verified to remain a synthetic, frontend-only read path.
- Mutation endpoints remain protected by backend authentication and authorisation dependencies.
- Approval operations enforce tenant/site scope and separation of duties.
- Runtime tool calls are bounded by allowlists, request scope, timeout, and call budgets.
- Frontend production dependencies reported zero known vulnerabilities through `npm audit --omit=dev`.
- A Python vulnerability-database query was attempted, but the validation environment had no network access. No claim is made that a current external Python advisory scan completed.

## Known limitations

- The public dashboard uses curated synthetic records and is not an anonymous production tenant.
- Live provider, graph, vector, storage, and SMTP behaviour depends on deployment configuration.
- Live-infrastructure integration tests were intentionally excluded from the deterministic release suite.
- Single-process background execution can be interrupted by host suspension or restart; durable worker deployment is recommended for operational workloads.
- Evaluation results from mocked providers must not be presented as live-model accuracy.
