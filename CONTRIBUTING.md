# Contributing

Thanks for helping make deletion provable.

## Setup

```bash
uv venv .venv
uv pip install --python .venv/bin/python -e ".[dev]"
.venv/bin/pytest
.venv/bin/ruff check .
```

## Project layout

```text
src/erasureproof/
├── api/           FastAPI schemas, dependencies and routes
├── connectors/    Connector SDK and built-in SQL/object/control connectors
├── core/          Identity, policy, planner, verifier, attestation, intent
├── evidence/      Content-addressed store and hash-chained ledger
├── models/        Domain types and SQLAlchemy persistence
├── orchestrator/  In-process run loop (Temporal-ready)
├── config.py      Environment-driven settings
├── demo.py        Seeded end-to-end scenario
└── cli.py         `erasureproof` command
```

## Adding a connector

1. Subclass `BaseConnector` in `src/erasureproof/connectors/`.
2. Set a unique `type` and the capability flags you support.
3. Implement `discover`, plus `remediate`, `discover_flows`,
   `discover_backups` or `verify` where applicable.
4. Record evidence for every discovered resource using `_record_evidence`.
5. Register the class in `connectors/registry.py`.
6. Add tests with a temporary local datastore; never call real customer systems.

Rules:

- Discovery must be read-only.
- Match records through normalized identifiers, not only the request email.
- Respect the `as_of` cutoff: evidence captured after the audit time must not
  affect the result.
- Never trust a delete return code; implement `verify` by re-reading state when
  possible.
- Do not log identifiers, credentials or record contents.

## Adding a policy

Add a YAML file under `policies/` with a unique `jurisdiction`. Use only the five
actions (`DELETE`, `REDACT`, `ANONYMIZE`, `RETAIN`, `TOMBSTONE`). Rules with a
higher `priority` win. Legal holds and `retention_required` are always evaluated
before category rules.

## Tests

- Unit tests for pure logic (intent, policy, planner, verifier).
- Connector tests against temporary SQLite/object-store fixtures.
- Ledger and attestation tamper tests.
- API tests via `fastapi.testclient`.
- The demo test must end in `COMPLETE` with every verification passing.

## Pull requests

- Keep changes focused and deterministic.
- Run `pytest` and `ruff check .` before opening a PR.
- Explain the policy or evidence implications of connector changes.
- Do not include real personal data, customer credentials or golden labels.
