# Evidence, ledger, and attestations

## Content-addressed evidence

Each artifact has:

- `evidence_id`
- SHA-256 fingerprint
- source
- capture timestamp
- content type
- size
- optional `request_id`

Evidence is stored once per content hash and can be verified independently of its metadata.

## Supported artifact intelligence

ErasureProof can inspect:

- Plain text, JSON, CSV, and logs
- PDFs, including OCR fallback
- Application screenshots and images
- Office documents
- ZIP, TAR, and nested archives
- SQLite-compatible SQL snapshot exports
- EXIF metadata and printable strings

The filesystem connector matches subject identifiers in content, not just filenames.

## Finding requirements

Every `FINDING` step cites the participant-visible evidence, activity, or audit ID that proves it. A finding cannot cite organizer truth or evidence captured after the audit cutoff.

Remediation steps and future verification steps use an empty `evidence_id` because they describe work that has not happened yet.

## Hash-chained ledger

Each ledger entry commits to the previous entry:

~~~text
entry.hash = SHA256(canonical(entry) + prev_hash)
~~~

`POST /v1/ledger/verify` recomputes the chain and reports the head. Editing, reordering, or deleting an entry breaks verification.

## Signed attestations

An attestation binds:

- Request ID and final status
- Plan steps
- Verification results
- Evidence references
- Ledger head
- Subject stable reference and audit cutoff

The signature uses HMAC-SHA256 with a server-managed key. Store that key securely and rotate it according to your own policy.

## Integrity checks

The console exposes two verification actions:

- **Verify evidence** recomputes the object fingerprint from bytes.
- **Verify ledger** recomputes the full hash chain.
