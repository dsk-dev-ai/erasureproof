# Connectors

Connectors separate discovery from remediation. Each connector declares what it supports.

## Built-in types

| Type | Purpose |
|---|---|
| `sql` | SQLite and SQLAlchemy-compatible SQL sources. |
| `postgres` | PostgreSQL sources and replicas. |
| `filesystem` | Exports, attachments, logs, archives, and local snapshots. |
| `control` | Control-plane workflows, sync jobs, and restore switches. |
| `s3` | S3-compatible object storage. |
| `local` | Local object-store emulation for development and demos. |
| `workspace` | Filesystem alias for workspace-style data. |

## Configuration

Every connector receives a JSON configuration. A filesystem connector needs a root:

~~~json
{
  "system_id": "exports",
  "root": "/data/exports",
  "default_category": "EXPORT",
  "categories": {
    "backups/*": "BACKUP",
    "logs/*": "LOG"
  },
  "ocr": true
}
~~~

A SQL connector needs a URL, table, and identifier column:

~~~json
{
  "system_id": "analytics",
  "url": "sqlite:///data/analytics.db",
  "table": "events",
  "id_column": "email",
  "category": "ANALYTICS"
}
~~~

## Safety

- Discovery is read-only.
- Destructive actions run only through a validated plan.
- Connector support is explicit. Unsupported actions are reported, not silently ignored.
- Keep credentials in the runtime environment, not in the console or source repository.
