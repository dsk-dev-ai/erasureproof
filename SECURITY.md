# Security policy

ErasureProof touches the most sensitive systems a company runs. Treat every
connector credential and every evidence snapshot as production data.

## Reporting a vulnerability

Do not open a public issue for a security problem. Email the maintainer at
`security@erasureproof.dev` with:

- affected version or commit,
- a description of the issue and impact,
- reproduction steps or a proof of concept,
- any suggested fix.

We will acknowledge receipt within three business days and coordinate disclosure.

## Secrets

- Read credentials from environment variables or a secret manager.
- Never commit `.env`, API keys, tokens, certificates or private keys.
- Connector configuration may contain database URLs; store them encrypted and
  restrict access to the connector service.
- Replace `ERASUREPROOF_ATTESTATION_KEY` with a KMS/Vault-backed signer in any
  environment that matters. The default key is for local development only.
- Use one API key per operator, scope it to a tenant, and rotate it on
  offboarding. Keep wildcard admin keys in a break-glass store.
- Protect signed backup archives: they contain evidence, metadata, and the
  ledger. Never store the signing key beside the archives.

## Data handling

- Evidence snapshots contain personal data by design. Restrict access to the
  evidence directory and apply retention limits to the evidence itself.
- The ledger stores IDs and hashes, not record contents; do not add raw PII to
  ledger payloads.
- Attestations include plan and verification metadata. Treat signed attestations
  as confidential unless a regulator or auditor is the intended recipient.
- The demo seeds fictional people only. Do not point the demo at real data.

## Deployment

- Terminate TLS at a trusted ingress. Enable `ERASUREPROOF_HSTS_SECONDS` and set
  `ERASUREPROOF_TRUST_PROXY_HEADERS=true` only when the ingress is the sole path
  to the API.
- Use `ERASUREPROOF_AUTH_MODE=api_key` or `oidc`. Production startup refuses to
  run with authentication disabled or the default attestation key.
- Scope every API key and OIDC tenant claim to one tenant. Wildcard tenants are
  restricted to administrators.
- Enable `ERASUREPROOF_REQUIRE_REMEDIATION_APPROVAL=true` and keep separation of
  duties so the request creator cannot approve their own destructive run.
- Set `ERASUREPROOF_DEMO_ENABLED=false` outside local development. The demo
  bootstrap creates a workspace and seeds fictional records.
- Set `ERASUREPROOF_METRICS_TOKEN`; otherwise `/metrics` requires an admin
  principal. Scrape it over the cluster network only.
- Export audit events to immutable storage and run signed backups on a schedule.
- Use a dedicated database role with the minimum privileges needed by each
  connector.
- Run connectors with read-only credentials until remediation is explicitly
  approved, then use narrowly scoped write credentials.
- Back up the ledger, attestation directory, evidence, and metadata. Use
  `erasureproof backup create` for the signed archive and your database
  provider's tooling for PostgreSQL. Verify a restore before relying on it.

## Dependencies

Keep dependencies current and review transitive packages regularly. The core
install is intentionally small; `boto3`, `psycopg` and `temporalio` are optional
extras.
