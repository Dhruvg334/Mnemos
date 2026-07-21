# 0002: Persist investigation runtime state

**Status:** Accepted

## Context
Long-running investigations and human approvals cannot depend on one process lifetime.

## Decision
Persist checkpoints, events, audit records, approval requests, and idempotency markers in PostgreSQL and await durability-critical writes.

## Consequences
Recovery is reliable, at the cost of explicit transaction boundaries and schema maintenance.
