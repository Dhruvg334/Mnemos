# Agent runtime

Signed-in questions travel through the Next.js server proxy to the authenticated FastAPI query endpoint. The backend persists the query, classifies intent, plans retrieval, retrieves tenant- and site-scoped evidence, runs relevant analysis, verifies claims and composes the final response.

Broad questions such as “What can I improve?” are treated as portfolio reviews rather than malformed requests. The runtime examines supported evidence for recurring failures, unresolved investigations, compliance exposure, stale procedures, document gaps, maintenance history, reliability trends and unvalidated knowledge. When evidence is insufficient, the response names the missing source types and offers a productive narrowing path instead of inventing an operational diagnosis.

The final composer receives controlled structured findings, citations, contradictions, missing evidence, actions and confidence. It must answer the user rather than describe internal agents. Provider timeout, rate-limit, credential and malformed-output failures use an evidence-aware deterministic fallback and are recorded in structured logs without raw documents, secrets or session tokens.
