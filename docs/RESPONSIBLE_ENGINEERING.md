# Responsible Engineering and Code Ethics

## Purpose

Mnemos is designed to support evidence review and operational investigation. It must not create an appearance of certainty, authority, or automation beyond what its data, configuration, and approval controls can support.

## Engineering commitments

### Evidence integrity

- Material claims should reference identifiable evidence.
- Superseded, contradictory, or missing evidence must remain visible.
- Confidence is a calibrated signal, not a substitute for provenance.
- Synthetic demonstration records must never be represented as real operating history.

### Human authority

- Safety-critical, compliance, and operational decisions remain with authorised people.
- Approval failures are fail-closed.
- The system does not autonomously operate equipment or certify compliance.
- Separation-of-duties controls must not be bypassed for convenience.

### Data responsibility

- Collect only the data required for the intended workflow.
- Preserve tenant, site, asset, and document boundaries through every layer.
- Do not place private operational records, credentials, or production logs in source control.
- Retention, deletion, and export policies must be defined before production data is onboarded.

### Model and tool behaviour

- Agent reflection, retrieval depth, tool calls, tokens, retries, and execution time are bounded.
- Provider failures are surfaced safely and are not converted into fabricated output.
- Tool trajectories should support diagnosis without recording secrets or unnecessary personal data.
- Provider-backed performance must be measured on the intended corpus before operational use.

### Honest communication

- Documentation distinguishes implemented capabilities from integrations that require configuration.
- Test metrics distinguish deterministic checks from live-provider evaluation.
- Public product demonstrations are labelled read-only and synthetic.
- Known limitations are documented rather than hidden behind interface polish.

## Review checklist for material changes

1. Does the change preserve organisation and site scope?
2. Can it mutate data, trigger a governed action, or expose sensitive information?
3. Is authentication and authorisation enforced by the backend rather than only the UI?
4. Are failure, retry, timeout, and rollback behaviours explicit?
5. Does the change add or update tests at the correct boundary?
6. Does documentation state what is configured, mocked, synthetic, or unavailable?
7. Can logs, traces, prompts, or tool arguments expose secrets or operational data?
8. Is there a safe abstention or human-review path when evidence is insufficient?
