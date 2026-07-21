# Security

## Trust boundaries

The browser is untrusted. Frontend prompts and disabled buttons improve usability but are not security controls. The API revalidates identity, membership, role, tenant, site, and resource scope for protected operations.

## Authentication and authorisation

Private workspaces use short-lived access tokens and revocable refresh sessions. Password and destructive account operations require authentication. Organisation and site roles determine access; platform-wide authority is explicit and uncommon.

## Public demonstration

The public dashboard uses synthetic data and is read-only. Guest users may navigate the product surface but cannot upload, delete, approve, change credentials, manage members, or mutate organisation data. Protected API routes remain authoritative even when UI state is manipulated.

## Agent and approval controls

Tool calls inherit the authenticated request scope. Critical decisions use durable approval gates with separation of duties. Approval persistence is fail closed: an unavailable approval store cannot produce an implicit approval.

## Secrets and data handling

Secrets belong in deployment environment stores, not source control. Logs must not include tokens, provider credentials, raw private documents, or unrestricted exception data. Public examples and screenshots should use synthetic organisations, people, and records.

## Residual risks

The free demonstration deployment has cold starts and background-task interruption risk. Optional graph and object-storage integrations may be unavailable. Model output remains advisory and must be reviewed against current authorised evidence.
