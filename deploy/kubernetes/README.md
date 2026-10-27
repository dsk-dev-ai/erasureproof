# Kubernetes deployment

These manifests run ErasureProof 1.0 on Kubernetes with two or more replicas,
RBAC-enforced API keys, a shared evidence/ledger volume, approval-gated
remediation, probes, autoscaling, and network isolation.

## Before you apply

1. **Use managed PostgreSQL.** Multi-replica SQLite is not supported. The
   database must be reachable from the cluster and backed up independently.
2. **Create the shared volume.** Evidence, attestations, and the hash-chained
   ledger live on one `ReadWriteMany` PVC. Use a shared filesystem class such as
   NFS, CephFS, EFS, or Filestore. Do not use `ReadWriteOnce` with more than one
   replica.
3. **Create the secret.** Copy `secret.example.yaml`, replace every value, and
   apply it without committing plaintext. Generate independent random values:
   - `ERASUREPROOF_ATTESTATION_KEY`: at least 32 random bytes; rotating it
     invalidates existing signature verification.
   - `ERASUREPROOF_API_KEYS`: one key per operator, least-privilege role, and a
     `tenant_id` scope. Keep one wildcard admin key offline for break-glass.
   - `ERASUREPROOF_METRICS_TOKEN`: bearer token for Prometheus.
4. **Set the hostnames.** Replace `erasureproof.example.com` in the ConfigMap
   CORS origins and the Ingress, then provide `erasureproof-tls`.
5. **Adjust the NetworkPolicy.** The egress rule for OIDC port 443 is open by
   design; narrow it to your identity provider. Add egress rules for any
   connectors that call external systems.

## Apply

```bash
kubectl apply -k deploy/kubernetes
kubectl -n erasureproof rollout status deploy/erasureproof
```

Secrets are not listed in `kustomization.yaml`. Create `erasureproof-secrets`
before rolling out, or the pods will fail to start.

## Verify

```bash
curl -fsS https://erasureproof.example.com/livez
curl -fsS https://erasureproof.example.com/readyz
curl -fsS https://erasureproof.example.com/healthz
```

`/readyz` checks the database, required tables, writable evidence/attestation
directories, ledger, policies, and production configuration. A `503` means the
pod should not receive traffic.

## Operations

- **Approvals.** Set `ERASUREPROOF_REQUIRE_REMEDIATION_APPROVAL=true` (default in
  the ConfigMap) and use two different administrators: one creates the request,
  another approves remediation. Approvals are single-use and expire after
  `ERASUREPROOF_APPROVAL_TTL_HOURS`.
- **Audit export.** Administrators can download tenant-scoped CSV events from
  the console Settings page or `GET /v1/audit-events/export`.
- **Backups.** Run the signed backup CLI from a maintenance job or a bastion with
  the same `ERASUREPROOF_ATTESTATION_KEY`:

  ```bash
  erasureproof backup create --output /backups/erasureproof-$(date +%F).zip
  erasureproof backup verify /backups/erasureproof-$(date +%F).zip
  ```

  Back up PostgreSQL with your managed provider's tooling in the same window.
  The signed archive covers the evidence objects, ledger, attestations, and a
  SQLite snapshot only when the metadata store is SQLite.
- **Key rotation.** Rotate API keys by updating the secret and restarting pods.
  API keys are read from the environment, so no request can use a removed key
  after rollout.
- **Metrics.** `/metrics` requires `ERASUREPROOF_METRICS_TOKEN` when set;
  otherwise it requires an admin principal. Scrape it over the cluster network
  only.

## Scaling notes

The application is stateless except for the shared volume and PostgreSQL.
SQLite-backed deployments must stay at one replica. The HPA assumes a Postgres
URL and a shared filesystem.
