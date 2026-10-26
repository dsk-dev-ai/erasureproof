# ErasureProof overview

ErasureProof is a **deletion audit control plane**. It answers a narrower and much harder question than “did the workflow close the ticket?”:

> At the audit timestamp, what copies of this person’s data still exist, what is their required treatment, and what proves the result?

It is designed for privacy engineering, security, and compliance teams operating across databases, warehouses, logs, support systems, archives, exports, object storage, and backups.

## What it does

- Classifies the request intent before taking action.
- Resolves current and historical identifiers into one subject graph.
- Discovers records, active copy paths, and restorable backups.
- Applies a jurisdiction-aware policy to every discovered resource.
- Produces a safe, dependency-ordered remediation plan.
- Executes supported actions and re-discovers the resulting state.
- Verifies every expected outcome rather than trusting action flags.
- Issues a signed attestation and appends events to a hash-chained ledger.

## What “complete” means

A request is `COMPLETE` only when:

1. Every relevant copy has the policy-required treatment.
2. Every policy-required retained record is present and correctly redacted.
3. No active sync, import, export, or restore path can recreate prohibited data.
4. Every required verification check passes at the audit cutoff.

A workflow’s reported status is treated as a claim, never as evidence.

## Decision states

| Status | Meaning |
|---|---|
| `COMPLETE` | Required state is proven by evidence at the audit cutoff. |
| `INCOMPLETE` | At least one prohibited copy, exposure, active flow, or restore risk remains. |
| `NOT_APPLICABLE` | The request does not authorize deletion. No remediation is required. |
| `PENDING` | The request is authorized but has not been audited yet. |

## Non-goals

ErasureProof does not:

- Bypass authentication or authorization.
- Exploit services or attempt credential attacks.
- Download breach dumps.
- Scrape private or ToS-restricted sources.
- Replace legal advice or an organization’s records-retention review.

The exposure module is passive, opt-in, and disabled by default.
