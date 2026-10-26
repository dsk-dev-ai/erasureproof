# Exposure intelligence

The exposure module checks whether a subject’s identifiers remain publicly reachable after an erasure.

## Collectors

- Direct URL checks
- Wayback archives
- Search-index snippets
- Breach metadata lookup
- Public GitHub references
- Gravatar profiles
- Username sweeps

## Guardrails

A scan is permitted only when:

1. The caller sets `authorized: true`.
2. The server sets `ERASUREPROOF_EXPOSURE_ENABLED=true`.
3. A supported collector and target are supplied.

The module is passive by design. It does not:

- Attempt authentication bypass.
- Exploit vulnerabilities.
- Perform credential attacks.
- Download breach dumps.
- Scrape private or restricted sources.

## Output

Each report contains:

- `scanned_at`
- `authorized`
- `risk_score`
- `severity`
- `hits`
- `errors`
- `collectors`
- `report_evidence_id`

Each hit includes collector provenance, confidence, matched identifiers, severity, and a URL. The report itself is written to the evidence store and recorded in the ledger.

## Operational guidance

- Respect rate limits and robots directives.
- Use a dedicated egress identity.
- Log authorization decisions.
- Review false positives before contacting a host or taking further action.
