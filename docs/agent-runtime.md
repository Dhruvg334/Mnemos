# Agent runtime

## Canonical pipeline

The investigation runtime has one production construction root and eleven ordered stages:

1. supervisor initialisation;
2. query routing;
3. retrieval planning;
4. evidence retrieval;
5. evidence verification;
6. bounded reflection;
7. specialist reasoning;
8. report composition;
9. human approval when required;
10. final response;
11. completion and checkpoint.

Reflection is bounded to prevent unproductive loops. Tool execution is also bounded by per-agent call limits and timeouts.

## Durability

Checkpoint, event, audit, and idempotency writes are awaited. The runtime does not rely on fire-and-forget persistence for correctness. Approval pause state is serialised before the request is exposed to reviewers, and resume reconstructs the stored state rather than rerunning evidence collection.

## Human approval

Approval requests retain organisation, site, requester, gate type, and state snapshot. Reviewers must have an approval-capable role within scope. A requester cannot approve their own governed action. Out-of-scope identifiers return not-found semantics to limit enumeration.

## Tool governance

Agents do not receive unrestricted database access. Tool calls preserve principal and resource scope, enforce allowlists, record trajectories, categorise failures, and fail closed on scope violations. Tool enrichment may improve an answer but must not replace verified evidence.

## Recovery

Retries use idempotency markers to avoid duplicate node effects. Provider and optional-service failures are surfaced as controlled failures or degraded enrichment. Permanently failed runs retain enough state for diagnosis rather than being silently discarded.
