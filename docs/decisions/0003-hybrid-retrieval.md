# 0003: Use hybrid retrieval instead of vector-only search

**Status:** Accepted

## Context
Industrial queries combine semantic meaning with exact identifiers, revisions, dates, and relationships.

## Decision
Fuse vector, lexical, structured, graph, and bounded multi-hop retrieval before reranking and verification.

## Consequences
Coverage improves, while evaluation and failure diagnosis must remain strategy-aware.
