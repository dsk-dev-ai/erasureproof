# Deploy free on Render with Neon

This is the $0 public demo profile. It runs the API and console in one Docker
service on Render Free and stores relational data in Neon Free PostgreSQL.
Neither service requires a credit card for the free tier.

Neon Free is permanent, not a 30-day trial. The hosted demo migrated from the
temporary Render Postgres database to Neon on **2026-10-29**. The legacy Render
Postgres was deleted after the restore and live application were verified.

## What the free profile does and does not do

- One container serves the React console at `/console`, the API under `/v1`,
  OpenAPI at `/docs`, and the health probes.
- Neon stores tenants, requests, identities, API keys, approvals, and audit
  events. Neon Free includes 100 compute-unit hours, 1 GB of Postgres storage,
  and 5 GB of public egress per project per month. Compute scales to zero after
  five minutes of inactivity.
- The Render container filesystem stores evidence snapshots, the ledger,
  attestations, and sandbox source files. **Render Free services have no
  persistent disk**, so those artifacts disappear on deploy, restart, or host
  migration. Neon does not fix this. Database rows survive, but evidence
  references, ledger continuity, and attestation verification can break.
  `ERASUREPROOF_DATA_DIR=/data` only helps when `/data` is backed by a persistent
  disk.
- Anonymous sandbox creation is limited to 3 per IP per day and 100 globally per
  day. Keys expire after 7 days.
- Render Free sleeps after 15 minutes without traffic; the next request wakes it
  in about a minute. Neon also suspends idle compute. The first request after
  both sleep can be slow, but `/healthz` does not wait for the database.

## What survives a free-tier restart

| Artifact | Free-tier behavior |
| --- | --- |
| Tenants, requests, identities, API keys, approvals, audit events | Stored in Neon; survive Render restarts |
| Evidence snapshots under `ERASUREPROOF_DATA_DIR/evidence` | Lost on deploy, restart, or host migration |
| Ledger at `ERASUREPROOF_DATA_DIR/ledger.jsonl` | Lost; hash-chain continuity is broken |
| Attestations under `ERASUREPROOF_DATA_DIR/attestations` | Lost; previously issued signatures can no longer be served |
| Sandbox connector files | Lost with the container |

A health check can still return `200` after an artifact reset because the API is
running and Neon is connected. Treat missing evidence, a broken ledger, or failed
attestation verification as data-integrity failures, not as a healthy free-tier
quirk.

## Create the Neon database

1. Sign up at <https://neon.com/signup>. The Free plan does not require a credit
   card.
2. Create one project. Choose the AWS region closest to the Render region. For
   Render's default Oregon region, use **AWS US West (Oregon)**.
3. Open **Connect** and copy the **direct** connection string, not the pooled
   one. This deployment runs one Render instance, so the direct connection
   avoids pooler edge cases.
4. Confirm the string starts with `postgresql://` and includes
   `sslmode=require`. Neon includes this by default.
5. Keep the connection string secret. Paste it only into Render's environment
   settings; never commit it.

ErasureProof normalizes `postgresql://` to the Psycopg driver automatically. The
Docker image already installs the `postgres` extra, and the database engine uses
pre-ping so stale connections are discarded after Neon scales to zero.

## Migrate a Render database

The legacy free Render Postgres was deleted on **2026-10-29**; it would have
expired on **2026-11-27**. Keep these steps for a future migration.

Install a PostgreSQL 16 `pg_dump` and `psql`, then:

```bash
export OLD_DATABASE_URL='postgresql://...render.com/...'
export NEON_DATABASE_URL='postgresql://...neon.tech/neondb?sslmode=require'

pg_dump "$OLD_DATABASE_URL" \
  --no-owner --no-acl --clean --if-exists \
  --format=plain -f erasureproof.sql

psql "$NEON_DATABASE_URL" -v ON_ERROR_STOP=1 -f erasureproof.sql
psql "$NEON_DATABASE_URL" -c '\dt'
```

Render Free Postgres does not provide managed backups, so take the dump before
the expiry window. Do not delete the old database or approve a Blueprint sync
that removes it until the Neon restore and the application have been verified.

If the old database has already expired, upgrade it for the grace period just
long enough to dump it, or accept a fresh database.

## Option A: deploy the repository with a Blueprint

1. Push the repository to GitHub.
2. In Render, choose **New → Blueprint** and select the repository.
3. Render reads `render.yaml` and prompts for:
   - `ERASUREPROOF_DATABASE_URL`: paste the Neon direct connection string.
   - `ERASUREPROOF_API_KEYS`: enter a JSON array with one bootstrap key:

     ```json
     [{"key":"replace-with-a-long-random-value","role":"admin","tenant_id":"*","subject":"bootstrap-admin"}]
     ```

     Generate the key locally with `openssl rand -hex 32`. Never reuse a demo key.
4. Apply the Blueprint and wait for `/healthz` to pass.
5. Open `https://<service>.onrender.com/console`.

The Blueprint no longer creates a Render database. `ERASUREPROOF_ATTESTATION_KEY`
is generated by Render and stored as a service secret.

## Option B: update the existing Render service

1. Open the service in Render and go to **Environment**.
2. Keep the current `ERASUREPROOF_DATABASE_URL` until the Neon migration is
   verified.
3. Change `ERASUREPROOF_DATABASE_URL` to the Neon direct connection string.
4. Save and redeploy. If the service is currently asleep, the first request may
   take about a minute.
5. Verify the deployment with the commands below. Only then remove the old
   Render database.

If you later re-sync a Blueprint that omits the old Render database, Render may
propose deleting it. Review the diff and do not approve that deletion until the
Neon database is proven good.

## Option C: deploy the Docker image manually

Create a Render **Web Service** with:

| Setting | Value |
|---|---|
| Environment | Docker |
| Region | Oregon (or nearest) |
| Plan | Free |
| Health check path | `/healthz` |
| Dockerfile | `Dockerfile` at repository root |

Environment variables:

```text
ERASUREPROOF_ENVIRONMENT=production
ERASUREPROOF_AUTH_MODE=api_key
ERASUREPROOF_DATABASE_URL=<Neon direct connection string>
ERASUREPROOF_DATA_DIR=/data
ERASUREPROOF_POLICY_DIR=/app/policies
ERASUREPROOF_WEB_DIR=/app/web/dist
ERASUREPROOF_ATTESTATION_KEY=<openssl rand -hex 32>
ERASUREPROOF_API_KEYS=[{"key":"<long random bootstrap key>","role":"admin","tenant_id":"*","subject":"bootstrap-admin"}]
ERASUREPROOF_DEMO_ENABLED=false
ERASUREPROOF_SELF_SERVE_ENABLED=true
ERASUREPROOF_SANDBOX_TTL_HOURS=168
ERASUREPROOF_SANDBOX_DAILY_LIMIT=100
ERASUREPROOF_SANDBOX_PER_IP_DAILY_LIMIT=3
ERASUREPROOF_REQUIRE_REMEDIATION_APPROVAL=false
ERASUREPROOF_RATE_LIMIT_PER_MINUTE=300
ERASUREPROOF_TRUST_PROXY_HEADERS=true
ERASUREPROOF_HSTS_SECONDS=31536000
ERASUREPROOF_EXPOSURE_ENABLED=false
```

Do not set `ERASUREPROOF_AUTH_MODE=disabled` or leave the default attestation key
in production. Startup validation rejects both. The Docker command honors
Render's `$PORT`.

## Verify the deployment

```bash
curl -s https://<service>.onrender.com/healthz
curl -s https://<service>.onrender.com/readyz
curl -s https://<service>.onrender.com/version

SANDBOX=$(curl -s -X POST https://<service>.onrender.com/v1/onboarding/sandbox \
  -H 'content-type: application/json' \
  -d '{"workspace_name":"Deploy check"}')
echo "$SANDBOX" | python3 -c 'import json,sys; print(json.load(sys.stdin)["sample_request_id"])'
```

`/readyz` checks the database connection. Then open the console from the
generated link, paste the sandbox key into Settings → API access, and run the
seeded request. Attestations should be available immediately, and the API keys
page should show the sandbox key with a revoke action.

## Cost controls and limits

- The documented setup costs **$0/month**.
- Render Free includes 750 instance hours per month and sleeps after 15 idle
  minutes. It has 512 MB RAM, 0.1 CPU, and no persistent disk.
- Neon Free includes 100 compute-unit hours, 1 GB of Postgres storage, and 5 GB
  of egress per project per month. Compute suspends after idle and after the
  compute allowance is exhausted.
- Exceeding Neon's storage cap blocks writes; it does not delete data. Reaching
  the compute or egress cap suspends compute until the next billing period.
- Render Free has included bandwidth. If it is exhausted and no payment method
  is attached, Render suspends the free service rather than charging a card.
- Move to a paid Render instance with a persistent disk and a paid database
  before onboarding real customers or storing evidence you need to keep.

## Rotate or recover

- If the bootstrap key leaks, create a scoped admin key first, add it to
  `ERASUREPROOF_API_KEYS`, deploy, then remove the old entry. Static keys are only
  read from the environment.
- Database-backed tenant keys can be rotated and revoked from the console or
  `POST /v1/api-keys/{id}/rotate`.
- If the Neon password leaks, reset the role password in Neon and update
  `ERASUREPROOF_DATABASE_URL` in Render.
- Changing `ERASUREPROOF_ATTESTATION_KEY` invalidates verification of existing
  attestations and backups. Keep old keys for verification if you rotate them.
