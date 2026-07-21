# Contributing

Contributions are welcome through issues and pull requests. Before starting a substantial change, open an issue so the problem, scope, and compatibility implications can be agreed.

## Working agreement

- Keep changes focused and explain the operational problem being solved.
- Add or update tests for behavioural changes.
- Preserve tenant, site, asset, and document boundaries.
- Do not weaken approval gates, auditability, provenance, or public-demo write protection.
- Never commit credentials, production exports, customer records, or proprietary source documents.
- Use clear commit messages that describe the specific change.

## Local checks

```bash
python -m ruff check src tests scripts
python -m pytest -q <affected tests>
cd frontend && npm run build
```

By submitting a contribution, you agree that it is licensed under the repository's Apache License 2.0 and may be modified, accepted, or declined by the maintainers. The repository owner retains final authority over roadmap, architecture, releases, and project governance.
