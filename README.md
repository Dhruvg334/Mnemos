<div align="center">

# Mnemos

### Industrial Knowledge Intelligence for Asset-Centric Operations

**Evidence-grounded operational memory for maintenance, reliability, safety, quality, and compliance teams.**

[![Status](https://img.shields.io/badge/status-in%20development-1f6feb)](#)
[![License](https://img.shields.io/badge/license-TBD-lightgrey)](#)
[![Frontend](https://img.shields.io/badge/frontend-Next.js-black)](#)
[![Backend](https://img.shields.io/badge/backend-FastAPI-009688)](#)
[![Graph](https://img.shields.io/badge/graph-Neo4j-4581C3)](#)

</div>

---

## Overview

Industrial knowledge is rarely absent. It is fragmented across P&IDs, OEM manuals, work orders, shift logs, inspection reports, procedures, incident records, spreadsheets, emails, and the experience of senior personnel.

**Mnemos** converts these disconnected sources into a living, time-aware operational memory centred on industrial assets. It connects assets, events, symptoms, failures, procedures, inspections, requirements, corrective actions, and expert knowledge—then exposes that context through evidence-grounded retrieval and governed workflows.

Mnemos is not a document chatbot or a CMMS replacement. Its primary unit of intelligence is the **asset and its operational history**.

## Core capabilities

- **Heterogeneous ingestion** — native and scanned PDFs, drawings, spreadsheets, work-order exports, inspection records, emails, images, and field notes.
- **Industrial knowledge graph** — asset, component, event, failure, procedure, evidence, requirement, and expert-knowledge relationships.
- **Hybrid retrieval** — semantic retrieval, metadata filtering, graph traversal, structured queries, and reranking.
- **Evidence-grounded copilot** — claim-level citations, confidence, contradictions, missing evidence, and abstention.
- **RCA workspace** — timelines, observed facts, hypotheses, similar failures, rejected causes, diagnostics, and corrective actions.
- **Compliance intelligence** — requirement-to-evidence mapping, validity checks, expiry tracking, contradiction detection, and audit packages.
- **Lessons learned** — recurrence detection across failures, incidents, near misses, non-conformances, and ineffective actions.
- **Field mode** — asset scanning, current procedures, failure history, hazards, open work, and evidence capture.
- **Expert memory** — attributed, reviewable, versioned knowledge cards that cannot silently override approved procedures.

## System architecture

```mermaid
flowchart TB
    A[Documents and Drawings] --> I
    B[CMMS / EAM / QMS] --> I
    C[Shift Logs and Emails] --> I
    D[Expert Notes and Voice] --> I
    E[Historian / SCADA Snapshots] --> I

    I[Ingestion and Document Intelligence]
    I --> P[OCR, Layout and Table Parsing]
    P --> X[Entity and Relation Extraction]
    X --> R[Asset Identity Resolution]
    R --> V[Provenance and Validation]

    V --> O[(Object Storage)]
    V --> SQL[(PostgreSQL)]
    V --> VS[(Vector Index)]
    V --> KG[(Industrial Knowledge Graph)]
    V --> TS[(Time-Series Store)]

    O --> H[Hybrid Retrieval and Evidence Layer]
    SQL --> H
    VS --> H
    KG --> H
    TS --> H

    H --> C1[Asset Copilot]
    H --> C2[RCA Intelligence]
    H --> C3[Compliance Intelligence]
    H --> C4[Lessons Learned]
    H --> C5[Expert Knowledge Workflow]

    C1 --> UI[Desktop and Mobile Experience]
    C2 --> UI
    C3 --> UI
    C4 --> UI
    C5 --> UI
```

## Knowledge model

```mermaid
graph LR
    SITE[Site] -->|CONTAINS| AREA[Area]
    AREA -->|CONTAINS| ASSET[Asset]
    ASSET -->|HAS_COMPONENT| COMPONENT[Component]
    ASSET -->|EXPERIENCED| FAILURE[Failure Event]
    SYMPTOM[Symptom] -->|PRECEDED| FAILURE
    WORK[Work Order] -->|ADDRESSES| FAILURE
    INSPECTION[Inspection] -->|FOUND| OBSERVATION[Observation]
    PROCEDURE[Procedure] -->|APPLIES_TO| ASSET
    REQUIREMENT[Requirement] -->|APPLIES_TO| ASSET
    REQUIREMENT -->|REQUIRES| EVIDENCE[Evidence]
    CLAIM[Claim] -->|SUPPORTED_BY| EVIDENCE
    KNOWLEDGE[Expert Knowledge Card] -->|CONCERNS| ASSET
    ACTION[Corrective Action] -->|RESPONDS_TO| FAILURE
```

Every material fact and relationship carries source provenance, confidence, verification status, temporal validity, and reviewer history.

## How an answer is produced

```mermaid
sequenceDiagram
    participant U as User
    participant O as Orchestrator
    participant R as Hybrid Retriever
    participant G as Knowledge Graph
    participant E as Evidence Verifier
    participant A as Answer Composer

    U->>O: Ask an asset or operational question
    O->>R: Build retrieval plan
    R->>G: Traverse relevant asset relationships
    R->>R: Search documents and structured records
    R-->>E: Candidate claims and evidence regions
    E->>E: Verify support, conflicts, and freshness
    E-->>A: Supported facts, uncertainty, missing evidence
    A-->>U: Grounded answer with citations and next checks
```

## Technology stack

| Layer | Technology |
|---|---|
| Web application | Next.js, TypeScript |
| API services | FastAPI, Python |
| Agent orchestration | LangGraph or equivalent state-machine workflow |
| Relational store | PostgreSQL |
| Vector retrieval | pgvector initially; Qdrant at larger scale |
| Knowledge graph | Neo4j |
| Object storage | MinIO or S3-compatible storage |
| Time-series | TimescaleDB |
| Document processing | Docling, Unstructured, PaddleOCR, custom parsers |
| Background processing | Celery, Dramatiq, or Temporal |
| Graph visualisation | Cytoscape.js or React Flow |
| Deployment | Docker Compose; Kubernetes-ready service boundaries |

## Repository structure

```text
mnemos/
├── src/
│   └── mnemos/
│       ├── agentic/             # AI orchestration — runtime, agents, MCP, retrieval
│       │   ├── agents/          # Retrieval + reasoning agents (11 production agents)
│       │   ├── runtime/         # Pipeline, state, idempotency, checkpoints, OTel
│       │   ├── mcp/             # Internal governed tool dispatch layer
│       │   ├── retrieval/       # Hybrid retrieval engine, reranking, citation
│       │   ├── evaluation/      # Evaluation harness + CI gate tests
│       │   ├── graph/           # Knowledge graph interfaces + Neo4j client
│       │   ├── services/        # LLM service, resource pool, model router
│       │   ├── utils/           # StructuredLogger, config, helpers
│       │   ├── schemas/         # Pydantic models for agents, base, state
│       │   ├── tests/           # Unit + integration tests for agentic layer
│       │   └── runtime/tests/   # Runtime-specific tests
│       ├── core/                # Base config, DB session factory, error types
│       ├── integrations/        # Agent gateway factory (langgraph, http, mock)
│       ├── models/              # SQLAlchemy ORM models
│       ├── schemas/             # API-level pydantic schemas
│       └── services/            # Backend services (query execution, validation)
├── alembic/                    # Database migrations
├── scripts/                    # Utility scripts (seed.py)
├── tests/                      # Project-level tests
├── docker-compose.yml
├── docker-compose.production.yml
├── .env.example
└── README.md
```

## Local setup

### Prerequisites

- Git
- Docker Desktop with Docker Compose
- Node.js 20+
- Python 3.11+
- `pnpm`
- An LLM endpoint configured through environment variables

### Clone and configure

```bash
git clone https://github.com/Dhruvg334/mnemos.git
cd mnemos

cp .env.example .env
```

Configure the required model, database, storage, and authentication values in `.env`.

### Run with Docker Compose

```bash
docker compose up --build
```

Expected local services:

```text
Web application    http://localhost:3000
API documentation  http://localhost:8000/docs
Neo4j browser      http://localhost:7474
MinIO console      http://localhost:9001
```

### Run services separately

Backend:

```bash
cd src
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
uvicorn mnemos.main:app --reload --port 8000
```

### Database migrations

```bash
alembic upgrade head
```

### Load the synthetic demonstration dataset

```bash
python scripts/seed.py
```

### Run tests

```bash
pytest
```

## Evaluation

Mnemos is evaluated against explicit, reproducible criteria:

| Area | Metric |
|---|---|
| Document intelligence | entity and relation extraction precision, recall, and F1 |
| Retrieval | answer relevance, retrieval recall, citation precision |
| Evidence quality | claim-to-source support and contradiction detection |
| Graph quality | identity-resolution accuracy and relationship completeness |
| RCA | chronology quality, evidence coverage, and missing-diagnostic detection |
| Compliance | requirement applicability and evidence-gap detection accuracy |
| Safety | abstention quality and unsupported-claim rate |
| Operational value | time-to-answer compared with manual document search |

## Security and governance

- Role- and site-aware access control before retrieval.
- Tenant and site boundaries on every persisted entity.
- Encryption in transit and at rest.
- Immutable audit records for ingestion, retrieval, agent actions, review, and approval.
- Human approval for RCA closure, compliance decisions, and expert-knowledge validation.
- Private-cloud, on-premise, and local-model deployment paths.
- No autonomous plant control or maintenance approval.

## Implementation status

The table below documents which capabilities are production-ready, which are integrated but need real configuration, and which are scaffolded or planned.

| Capability | Status | Notes |
|---|---|---|
| Backend API (auth, queries, RCA, compliance, documents, audit) | **Implemented & tested** | All routes operational with full lifecycle |
| Query execution pipeline | **Implemented & tested** | Single persistence transaction in `query_execution.py` |
| Agentic orchestrator boundary | **Implemented** | Orchestrator does no persistence; backend owns all writes |
| Canonical workflow (`InvestigationPipeline`) | **Implemented** | 11-stage pipeline with bounded reflection loop — canonical production path |
| Intent-selective agent dispatch | **Implemented** | Query router classifies intent; only relevant agents run |
| Bounded reflection loop | **Implemented** | Max 3 cycles; forces continue on exhaustion |
| Human approval gates | **Implemented & connected** | Raises `_ApprovalPendingError`; never auto-approves; API mounted in FastAPI |
| Durable checkpoints (PostgreSQL) | **Implemented with optimistic concurrency** | `DurableCheckpointManager` with version-based locks (P0 #13) |
| Durable audit log (PostgreSQL) | **Implemented** | `DurableAuditLogger` writes to `runtime_audit_entries` |
| Durable event log (PostgreSQL) | **Implemented** | `DurableEventLog` writes to `runtime_investigation_events` |
| Durable approval queue (PostgreSQL) | **Implemented — fail closed** | DB errors raise; no in-memory fallback for production (P0 #9) |
| Approval REST API | **Implemented & authorized** | Reviewer identity from JWT principal (P0 #8) |
| Error sanitization | **Implemented** | No raw exceptions, SQL, paths, or stack traces in persisted errors |
| Real E2E production-path tests | **Implemented** | `test_real_e2e_pipeline.py` — real gateway, orchestrator, pipeline, agents |
| Dead-letter queue for permanently failed runs | **Implemented** | `DeadLetterQueue` in idempotency.py (P0 #14) |
| Tool layer (12 tools, real backends) | **Implemented** | Governed internal dispatch layer with per-agent allowlists |
| Specialist agents (RCA, compliance, asset intel, etc.) | **Integrated** | Require real LLM API key (`OPENAI_API_KEY` or configured provider) |
| All production agents registered | **Registered** | Registered in `MnemosAIOrchestrator._register_all_agents()` |
| Vector retrieval (pgvector) | **Integrated** | Requires `DATABASE_URL` pointing to a pgvector-enabled PostgreSQL |
| Graph retrieval (Neo4j) | **Integrated** | Requires `NEO4J_URI` and populated graph |
| OpenTelemetry tracing | **Implemented** | OTLP exporter, FastAPI + SQLAlchemy instrumentation (P0 #20, P0 #21) |
| Model routing / fallback / cost budgets | **Implemented** | Routed in `LLMService.call_structured()` via `ModelRouter`; fast/primary tier; fallback on unhealthy |
| CI evaluation gates | **Implemented & tested** | Runs in `backend-ci.yml` as `evaluation-gates` job; 8 threshold gate tests pass |
| Retrieval budget optimiser | **Implemented** | `RetrievalBudgetOptimiser` enforces per-strategy candidate/token budgets in retrieval engine |
| Reproducible evaluation report | **Scaffolded** | Requires real seeded corpus and LLM configuration |
| Frontend–backend integration | **In progress** | Auth forms present; token lifecycle integration ongoing |

### Tool layer note

`MnemosMCPServer` is an **internal governed tool dispatch layer**, not a protocol-compliant Model Context Protocol server. Despite the "MCP" naming (a historical artifact), it does not implement the MCP specification. If protocol-compliant MCP is required, the `mcp` Python SDK and a full transport layer would need to be added in a separate service. See `src/mnemos/agentic/mcp/__init__.py` for the full status.

## Differentiation

```text
Document → Chunk → Answer
```

Mnemos follows:

```text
Asset → Event → Evidence → Relationship → Operational Decision
```

Its defensibility comes from the validated operational memory accumulated over time: plant-specific ontology, resolved asset identities, reviewed relationships, failure patterns, requirement-evidence mappings, and governed expert knowledge.

## Status

Mnemos is under active development for the ET AI Hackathon 2026 problem statement on Industrial Knowledge Intelligence.

---

<div align="center">

**Mnemos — operational memory built around the asset, grounded in evidence.**

</div>
