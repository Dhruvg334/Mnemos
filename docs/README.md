# Mnemos documentation

The documentation is organised by engineering concern rather than by implementation phase.

| Document | Audience | Purpose |
|---|---|---|
| [Architecture](architecture.md) | Engineers and reviewers | System boundaries, request flow, deployment shape, and failure domains |
| [Data model](data-model.md) | Backend and data engineers | Tenancy, asset-centric entities, evidence provenance, and runtime tables |
| [Agent runtime](agent-runtime.md) | AI and platform engineers | Investigation stages, checkpoints, approvals, idempotency, and recovery |
| [Retrieval](retrieval.md) | Retrieval and evaluation engineers | Candidate generation, fusion, reranking, provenance, and quality controls |
| [Security](security.md) | Maintainers and security reviewers | Trust boundaries, access control, public-demo restrictions, and residual risks |
| [Operations](operations.md) | Operators | Health checks, migrations, logging, degradation, and incident handling |
| [Deployment](deployment.md) | Release owners | Local, container, backend, and frontend deployment procedures |
| [Testing and evaluation](testing-and-evaluation.md) | Engineers and reviewers | Test taxonomy, deterministic evaluation results, and metric interpretation |
| [Public demo](public-demo.md) | Product and frontend engineers | Synthetic data, guest permissions, and protected actions |
| [Architecture decisions](decisions/README.md) | Maintainers | Durable decisions and their trade-offs |

Documentation should change in the same pull request as the behaviour it describes. Operational procedures belong in runbooks; design rationale belongs in an ADR; temporary implementation notes do not belong in this directory.
