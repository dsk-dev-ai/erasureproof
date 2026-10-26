# Request lifecycle

## 1. Intent authorization

The request text is classified before any discovery or remediation. Explicit deletion requests proceed. Access, correction, export, restriction, and marketing opt-out requests become `NOT_APPLICABLE`.

The classifier handles multilingual requests and negation. A request that merely mentions deletion in another context does not automatically authorize erasure.

## 2. Identity reconstruction

The supplied email may be current or historic. ErasureProof joins:

- Current identity snapshot
- Historical identity audit events
- Email hashes
- Phone numbers
- Usernames and external references
- Stable internal `user_id`

The result is a subject graph with validity windows. Evidence captured after the audit cutoff must not change the answer.

## 3. Discovery

Enabled connectors enumerate resources that match the subject. Findings include the evidence or activity that proves them.

Discovery state is reconstructed at the case’s `audit_at` timestamp. Reported workflow results and operation logs are claims until evidence establishes the resulting state.

## 4. Policy application

Each discovered resource receives a category and policy decision. Legal holds, retention obligations, and audit-trail requirements override deletion.

A primary account is normally tombstoned: the stable `user_id` remains while name, email, phone, email hash, and other direct identifiers are removed.

## 5. Planning

The plan has three phases in strict order:

1. `FINDING`
2. `REMEDIATION`
3. `VERIFICATION`

Remediation disables active data flows and blocks unsafe restores before dependent record changes. Downstream copies are processed before their source records when the dependency requires it.

The graph layer detects cycles and produces a critical path.

## 6. Execution

Connectors perform only the actions they support. Unsupported actions are recorded explicitly rather than silently treated as successful.

## 7. Verification

The engine re-discovers state after remediation and checks expected outcomes. A verification is evidence-backed, not inferred from an action’s success flag.

## 8. Attestation

The outcome, plan, and verification results are canonicalized, signed with HMAC-SHA256, and appended to the ledger. The attestation is portable and independently verifiable with the signing key.
