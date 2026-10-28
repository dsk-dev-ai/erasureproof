"""Small dependency-free client for the ErasureProof REST API."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from typing import Any


class ErasureProofError(Exception):
    """A non-2xx API response."""

    def __init__(self, status_code: int, detail: str, request_id: str | None = None) -> None:
        super().__init__(f"ErasureProof API error {status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail
        self.request_id = request_id


class ErasureProofClient:
    """Tenant-scoped ErasureProof API client.

    The key is only ever sent in the ``Authorization`` header. It is never
    logged or included in an exception message.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        timeout: float = 60.0,
        user_agent: str = "erasureproof-python/1.0",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.user_agent = user_agent

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: Mapping[str, Any] | None = None,
        params: Mapping[str, Any] | None = None,
        authenticated: bool = True,
    ) -> Any:
        url = self.base_url + path
        if params:
            query = urllib.parse.urlencode(
                {key: value for key, value in params.items() if value is not None}
            )
            if query:
                url += "?" + query

        headers = {"Accept": "application/json", "User-Agent": self.user_agent}
        data: bytes | None = None
        if body is not None:
            data = json.dumps(body, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if authenticated:
            if not self.api_key:
                raise ValueError("an API key is required for this operation")
            headers["Authorization"] = f"Bearer {self.api_key}"

        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
                if response.status == 204 or not raw:
                    return None
                return json.loads(raw)
        except urllib.error.HTTPError as error:
            raw = error.read(1_000_000)
            detail = error.reason or "request failed"
            try:
                payload = json.loads(raw)
                if isinstance(payload, dict) and payload.get("detail"):
                    detail = str(payload["detail"])
            except (ValueError, TypeError):
                pass
            raise ErasureProofError(
                error.code,
                detail,
                error.headers.get("X-Request-ID") if error.headers else None,
            ) from None
        except urllib.error.URLError as error:
            raise ErasureProofError(0, f"connection failed: {error.reason}") from None

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/healthz", authenticated=False)

    def create_tenant(self, name: str, jurisdiction: str = "gdpr") -> dict[str, Any]:
        """Create a tenant. Requires a deployment-wide administrator key."""

        return self._request(
            "POST", "/v1/tenants", body={"name": name, "jurisdiction": jurisdiction}
        )

    def create_subject(
        self,
        tenant_id: str,
        user_id: str,
        identifiers: list[Mapping[str, Any]],
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/subjects",
            body={"tenant_id": tenant_id, "user_id": user_id, "identifiers": identifiers},
        )

    def create_connector(
        self,
        tenant_id: str,
        connector_type: str,
        name: str,
        config: Mapping[str, Any],
        *,
        enabled: bool = True,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/connectors",
            body={
                "tenant_id": tenant_id,
                "type": connector_type,
                "name": name,
                "config": dict(config),
                "enabled": enabled,
            },
        )

    def create_request(
        self,
        tenant_id: str,
        email: str,
        request_text: str,
        audit_at: str,
        *,
        jurisdiction: str | None = None,
        requested_at: str | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/requests",
            body={
                "tenant_id": tenant_id,
                "email": email,
                "request_text": request_text,
                "audit_at": audit_at,
                "jurisdiction": jurisdiction,
                "requested_at": requested_at,
            },
        )

    def get_request(self, request_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/requests/{request_id}")

    def run_request(
        self,
        request_id: str,
        *,
        remediate: bool = False,
        force: bool = False,
    ) -> dict[str, Any]:
        """Run an audit. Destructive remediation requires operator privileges."""

        return self._request(
            "POST",
            f"/v1/requests/{request_id}/run",
            params={"remediate": str(remediate).lower(), "force": str(force).lower()},
        )

    def attestation(self, request_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/requests/{request_id}/attestation")

    def graph(self, request_id: str, fmt: str = "json") -> Any:
        return self._request(
            "GET", f"/v1/requests/{request_id}/graph", params={"format": fmt}
        )

    def overview(self, tenant_id: str | None = None) -> dict[str, Any]:
        return self._request("GET", "/v1/overview", params={"tenant_id": tenant_id})

    def audit_events(self, tenant_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        return self._request(
            "GET", "/v1/audit-events", params={"tenant_id": tenant_id, "limit": limit}
        )

    def approve(self, request_id: str, *, reason: str = "") -> dict[str, Any]:
        return self._request(
            "POST",
            f"/v1/requests/{request_id}/approval",
            body={"decision": "APPROVED", "reason": reason},
        )

    def list_api_keys(self, tenant_id: str | None = None) -> list[dict[str, Any]]:
        return self._request("GET", "/v1/api-keys", params={"tenant_id": tenant_id})

    def create_api_key(
        self,
        tenant_id: str | None = None,
        *,
        name: str = "API key",
        role: str = "operator",
        expires_in_days: int | None = 90,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/api-keys",
            body={
                "tenant_id": tenant_id,
                "name": name,
                "role": role,
                "expires_in_days": expires_in_days,
            },
        )

    def rotate_api_key(self, key_id: str) -> dict[str, Any]:
        return self._request("POST", f"/v1/api-keys/{key_id}/rotate")

    def revoke_api_key(self, key_id: str) -> None:
        self._request("DELETE", f"/v1/api-keys/{key_id}")


def create_sandbox(
    base_url: str,
    *,
    workspace_name: str = "Developer sandbox",
    jurisdiction: str = "gdpr",
    timeout: float = 60.0,
) -> tuple[ErasureProofClient, dict[str, Any]]:
    """Provision a free anonymous sandbox and return a ready client plus metadata."""

    anonymous = ErasureProofClient(base_url, api_key="", timeout=timeout)
    sandbox = anonymous._request(
        "POST",
        "/v1/onboarding/sandbox",
        body={"workspace_name": workspace_name, "jurisdiction": jurisdiction},
        authenticated=False,
    )
    return ErasureProofClient(base_url, sandbox["api_key"], timeout=timeout), sandbox
