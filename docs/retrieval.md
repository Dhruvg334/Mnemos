# Retrieval

Mnemos combines retrieval strategies because industrial questions contain both semantic intent and exact identifiers.

## Candidate generation

- **Vector retrieval** finds semantically related chunks through pgvector.
- **Lexical retrieval** preserves exact equipment tags, part numbers, procedure codes, and terminology.
- **Structured retrieval** applies dates, status, numeric, organisation, site, asset, and document filters.
- **Graph retrieval** follows typed operational relationships when Neo4j is enabled.
- **Multi-hop retrieval** resolves indirect relationships under bounded traversal limits.

## Post-processing

Candidates are deduplicated, merged, reranked, and compressed to a token budget. Verification confirms current document identity and citation provenance before evidence reaches reasoning agents. Contradictions and missing evidence remain explicit outputs.

## Scope and safety

Every retrieval request carries tenant, site, asset, document, and classification constraints. Graph expansion and tool enrichment are bounded. A provider result outside the authorised scope is discarded rather than merely down-ranked.

## Evaluation

Deterministic gates cover routing, retrieval recall, citation precision, grounded-answer rate, abstention, tool recovery, and workflow completion. Provider-backed RAGAS evaluation is supported separately and should only be reported with the exact model, corpus, dataset, and run artefact.

## Uploaded evidence

Authenticated retrieval is expected to use persisted `document_chunks` and `evidence_regions` filtered by organisation and site. Public demonstration records remain synthetic and are never mixed into signed-in query execution. Vector retrieval is conditional on successful embedding; lexical retrieval remains available when embeddings are pending or failed. Neo4j and the reranker enrich ranking when configured but are not the source of truth for citations.
