# ErasureProof Python SDK

A dependency-free client for the ErasureProof deletion-audit API. It uses only
the Python standard library and never logs or embeds the API key.

```bash
pip install erasureproof-sdk
```

For development from the repository:

```bash
pip install -e sdk/python
```

## Create a sandbox and run an audit

```python
from erasureproof_sdk import create_sandbox

client, sandbox = create_sandbox("https://erasureproof.onrender.com")

run = client.run_request(sandbox["sample_request_id"], remediate=False)
print(run["status"])
print(run["plan"]["steps"])

proof = client.attestation(sandbox["sample_request_id"])
print(proof["signature"])
print(proof["payload"]["status"])
```

The sandbox response includes a one-time administrator key scoped to the new
tenant. Store it in a secret manager for later use.

## Bring your own key

```python
from erasureproof_sdk import ErasureProofClient

client = ErasureProofClient("https://erasureproof.onrender.com", api_key=key)
print(client.health())
print(client.overview(tenant_id="ten_..."))
```

Errors raise `ErasureProofError` with `status_code`, `detail`, and `request_id`.
A `request_id` is useful when contacting support or correlating access logs.

## Manage keys

```python
created = client.create_api_key(tenant_id, name="CI", role="operator", expires_in_days=90)
print(created["api_key"])  # shown once
client.rotate_api_key(created["id"])
client.revoke_api_key(created["id"])
```

Key administration requires an administrator key scoped to the tenant. Use a
deployment-wide administrator key only for tenant creation.
