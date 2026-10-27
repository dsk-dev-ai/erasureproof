# Security and limits

## Trust model

Workflow statuses, activity logs, and system messages are claims. The audit result is established from evidence at the case's `audit_at` time.

## Access control

- Authentication is `disabled` only for local development. Production startup
  refuses to run with authentication disabled or with the default attestation
  key.
- API keys and OIDC identities resolve to `viewer`, `operator`, or `admin`.
- Every request is tenant-scoped server-side. A scoped principal receives `404`
  for another tenant's request, subject, connector, evidence, ledger entry, or
  approval.
- Tenant creation requires a wildcard deployment administrator.
- Destructive remediation can require a single-use approval from a different
  administrator. The approval is time-limited and consumed atomically.
- Administrative events are recorded in `audit_events` and exportable as CSV.

## Safe defaults

- Exposure collection is disabled unless explicitly enabled.
- Scans require `authorized: true`.
- Remediation requires an applicable request and a policy decision.
- Demo seed is disabled in production.
- CORS uses exact configured origins, never `*`.
- Unsupported connector actions are surfaced, not hidden.
- Connector configurations are redacted for secret-bearing keys in API output.
- Evidence is content-addressed and verifiable.

## Edge controls

- Request IDs are accepted only in a narrow safe format, otherwise generated.
- Per-IP rate limiting applies to `/v1`; keep gateway limits as the primary
  control. Rate limits are per process, not global.
- Security headers include `nosniff`, `DENY` framing, no-referrer, a restrictive
  permissions policy, and a console CSP. HSTS is enabled when configured.
- `/metrics` requires `ERASUREPROOF_METRICS_TOKEN`, or an admin principal when
  authentication is enabled.
- `/readyz` reports database, schema, storage, ledger, policy, and configuration
  failures without exposing secrets.

## Scope of authorized testing

This project analyzes local artifacts and passive public sources only. It does not authorize:

- Authentication bypass
- Exploitation
- Credential attacks
- Breach-dump acquisition
- Private or ToS-violating scraping

Use the exposure module only where you have a lawful basis and explicit authorization.

## Secrets

- Read credentials from environment variables or a managed secret store.
- Do not paste production secrets into connector configuration in the console.
- Do not commit `.env` files, API keys, tokens, or signing keys.
- Store the attestation signing key separately from the evidence store.
- Use one API key per operator, scope it to a tenant, and rotate on offboarding.
- The attestation key also signs backup manifests. Rotation invalidates
  verification of older archives, so retain the old key only for verification.
- Protect the backup destination and encrypt it at rest; archives contain
  evidence and metadata.

## Data handling

The demo uses fictional identities and records. Real deployments must apply their own access control, encryption, retention, and audit policies. Evidence downloads are authenticated; files are served inline from the private evidence store.

## Limitations

- OCR quality depends on the source image.
- SQL connector coverage depends on schema configuration.
- Policy YAML must match your legal review.
- Exposure results can contain false positives.
- Verification reflects the connector state visible at the audit cutoff.
- In-process rate limiting and approvals are backed by the metadata store; use a
  gateway and managed PostgreSQL for multi-replica deployments.
