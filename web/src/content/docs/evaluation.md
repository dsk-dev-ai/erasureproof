# Evaluation approach

ErasureProof is evaluated at both the request level and the step level.

## Request-level metrics

- Deletion-status accuracy across `COMPLETE`, `INCOMPLETE`, and `NOT_APPLICABLE`.
- Intent-classification accuracy for non-deletion requests.
- Correct handling of audit cutoffs and later evidence.

## Step-level metrics

- Finding coverage: every policy-relevant violation is reported.
- Evidence grounding: every finding cites a valid visible artifact.
- Operation accuracy.
- State accuracy.
- Sequencing accuracy across `FINDING`, `REMEDIATION`, and `VERIFICATION`.
- Dependency correctness for flow and restore controls.

## Custom evaluation cases

The repository includes custom scenarios for:

1. A deletion workflow reported complete while an analytics replica still contains the email.
2. A non-deletion access request that must return `NOT_APPLICABLE`.
3. An account tombstone that retains `user_id` while removing direct identifiers.
4. A backup restore path that recreates deleted data after remediation.
5. A historical email that appears only in an old support attachment.

## Failure-driven improvements

The evaluation suite is intended to catch:

- Over-trusting `reported_status`.
- Deleting records that policy requires to be retained.
- Remediating a source before its downstream copies.
- Omitting restore blocking.
- Citing evidence captured after the audit cutoff.
- Producing non-deterministic step ordering.
