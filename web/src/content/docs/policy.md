# Policy engine

Policies are code. They map resource categories and conditions to a required action.

## Actions

| Action | Meaning |
|---|---|
| `DELETE` | Remove the entire record. |
| `REDACT` | Keep the record but remove required identifying fields. |
| `ANONYMIZE` | Irreversibly unlink the record from the subject. |
| `RETAIN` | Keep the record because policy requires it. |
| `TOMBSTONE` | Preserve a stable reference while removing direct identifiers. |

## Default categories

Typical defaults:

- Primary account → `TOMBSTONE`
- Derived operational copies → `DELETE`
- Analytics records → `DELETE` or `ANONYMIZE`
- Audit trail → `RETAIN`
- Legal hold → `RETAIN`

## Overrides

Legal holds and explicit retention obligations are evaluated before ordinary rules. Conditional rules can match:

- Category
- `system_id`
- Resource prefix
- Presence of exposed fields
- Arbitrary payload fields

## Tombstones

An account tombstone preserves `user_id` and removes direct identifiers such as:

- Name
- Email
- Phone
- Email hash

The stable reference is the only permitted link back to the subject.

## Policy configuration

Policies live as YAML under the server’s policy directory. The API returns the active registry at:

~~~bash
curl http://localhost:8000/v1/policies
~~~

The web console’s **Policy matrix** page renders defaults and conditional rules for each jurisdiction.

## Verification

Every policy decision produces a verification expectation. A retained record must remain present; a redacted record must prove the direct identifiers are gone; an anonymized record must prove it can no longer be linked.
