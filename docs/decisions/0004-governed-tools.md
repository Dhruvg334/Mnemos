# 0004: Route agent actions through governed tools

**Status:** Accepted

## Context
Direct agent access to databases and external systems would bypass authorisation and reduce auditability.

## Decision
Use typed, scoped, allowlisted tool dispatch with budgets, timeouts, trajectories, and policy evaluation.

## Consequences
Agents are more predictable, but tool contracts become part of the platform API surface.
