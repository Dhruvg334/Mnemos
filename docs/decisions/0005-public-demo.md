# 0005: Keep the public product tour read-only

**Status:** Accepted

## Context
The product should be inspectable without registration, while private and destructive operations must remain protected.

## Decision
Expose synthetic dashboard data to guests and enforce authentication and role checks for mutations at the API boundary.

## Consequences
The demonstration is frictionless without treating frontend controls as security mechanisms.
