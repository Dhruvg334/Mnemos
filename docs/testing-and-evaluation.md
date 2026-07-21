# Testing and evaluation

## Test taxonomy

The suite is organised around behaviour rather than file counts:

- unit tests for deterministic utilities and scoring;
- service tests for persistence and transaction behaviour;
- contract tests for API and agent request propagation;
- runtime tests for checkpoints, events, audit, approvals, and idempotency;
- security tests for scope isolation and separation of duties;
- end-to-end tests for success, failure, duplicate execution, approval, and degraded providers;
- deterministic evaluation gates for retrieval and agent behaviour;
- frontend production-build validation.

## Deterministic evaluation baseline

The checked-in evaluation dataset runs without a live model or database. It is designed as a reproducible regression baseline, not as a claim about real-world model accuracy.

| Metric | Score |
|---|---:|
| Overall weighted score | 0.8438 |
| Weighted evaluation score | 0.8438 |
| Citation precision | 0.9167 |
| Citation precision | 0.9167 |
| Abstention quality | 0.9375 |
| Abstention quality | 0.9375 |



The baseline uses deterministic synthetic investigation states and the same metric implementation used by CI gates. Scores should be interpreted as pipeline-regression evidence, not production accuracy.

## RAGAS

The repository includes a provider-backed RAGAS adapter for answer relevance, context precision, context recall, and faithfulness. No aggregate RAGAS score is published because a valid result requires a pinned corpus, retrieval configuration, generator model, evaluator model, and retained run artefact.

## Reliability scenarios

Automated tests cover awaited persistence, process-safe idempotency, approval pause/resume, reviewer scope, requester/reviewer separation, duplicate suppression, safe exception handling, optional Neo4j startup, governed-tool budgets, tool-selection policy, and Render/Vercel configuration.
