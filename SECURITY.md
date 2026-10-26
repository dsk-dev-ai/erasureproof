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

## Data handling

- Evidence snapshots contain personal data by design. Restrict access to the
  evidence directory and apply retention limits to the evidence itself.
- The ledger stores IDs and hashes, not record contents; do not add raw PII to
  ledger payloads.
- Attestations include plan and verification metadata. Treat signed attestations
  as confidential unless a regulator or auditor is the intended recipient.
- The demo seeds fictional people only. Do not point the demo at real data.

## Deployment

- Put the API and console behind authenticated TLS termination. The reference
  API and console have no built-in authentication; add OAuth2/OIDC and
  per-tenant authorization before exposing either one.
- Set `ERASUREPROOF_DEMO_ENABLED=false` outside local development. The demo
  bootstrap creates a workspace and seeds fictional records.
- Use a dedicated database role with the minimum privileges needed by each
  connector.
- Run connectors with read-only credentials until remediation is explicitly
  approved, then use narrowly scoped write credentials.
- Back up the ledger and attestation directory; they are your proof trail.

## Dependencies

Keep dependencies current and review transitive packages regularly. The core
install is intentionally small; `boto3`, `psycopg` and `temporalio` are optional
extras.
