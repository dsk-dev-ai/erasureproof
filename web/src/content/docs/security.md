# Security and limits

## Trust model

Workflow statuses, activity logs, and system messages are claims. The audit result is established from evidence at the case’s `audit_at` time.

## Safe defaults

- Exposure collection is disabled unless explicitly enabled.
- Scans require `authorized: true`.
- Remediation requires an applicable request and a policy decision.
- Unsupported connector actions are surfaced, not hidden.
- Evidence is content-addressed and verifiable.

## Scope of authorized testing

This project analyzes local artifacts and passive public sources only. It does not authorize:

- Authentication bypass
- Exploitation
- Credential attacks
- Breach-dump acquisition
- Private or ToS-violating scraping

Use the exposure module only where you have a lawful basis and explicit authorization.

## Secrets

- Read credentials from environment variables.
- Do not paste production secrets into connector configuration in the console.
- Do not commit `.env` files, API keys, tokens, or signing keys.
- Store the attestation signing key separately from the evidence store.

## Data handling

The demo uses fictional identities and records. Real deployments must apply their own access control, encryption, retention, and audit policies.

## Limitations

- OCR quality depends on the source image.
- SQL connector coverage depends on schema configuration.
- Policy YAML must match your legal review.
- Exposure results can contain false positives.
- Verification reflects the connector state visible at the audit cutoff.
