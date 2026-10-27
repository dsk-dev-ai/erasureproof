"""Application configuration.

Every setting can be overridden with an ``ERASUREPROOF_``-prefixed environment
variable or a ``.env`` file. Safe local defaults mean the demo runs with no
external services.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

LOGGER = logging.getLogger("erasureproof.config")
DEFAULT_ATTESTATION_KEY = "dev-insecure-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ERASUREPROOF_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "ErasureProof"
    environment: str = "development"

    # Storage
    database_url: str = "sqlite:///./.erasureproof/erasureproof.db"
    data_dir: Path = Path("./.erasureproof")
    evidence_dir: Path | None = None
    ledger_path: Path | None = None
    attestation_dir: Path | None = None
    web_dir: Path = Path("./web/dist")

    # Attestation signing. Use a real secret (KMS/Vault) outside local dev.
    attestation_key: str = DEFAULT_ATTESTATION_KEY

    # Policy
    policy_dir: Path = Path("./policies")
    default_jurisdiction: str = "gdpr"

    # The console can create a safe, non-destructive demo tenant. Disable this
    # for any deployment that exposes the API outside a trusted environment.
    demo_enabled: bool = True

    # Authentication and authorization. ``disabled`` is for local development
    # only; production deployments should use ``api_key`` or ``oidc``.
    auth_mode: str = "disabled"
    api_keys: str = ""
    oidc_issuer: str | None = None
    oidc_audience: str | None = None
    oidc_jwks_url: str | None = None
    oidc_algorithms: str = "RS256"
    oidc_role_claim: str = "roles"
    oidc_tenant_claim: str = "tenant_id"
    oidc_default_role: str = "viewer"
    oidc_clock_skew_seconds: int = 60
    oidc_jwks_cache_seconds: int = 300

    # Destructive remediation can require an explicit, time-limited approval
    # recorded by a second administrator.
    require_remediation_approval: bool = False
    approval_requires_separate_user: bool = True
    approval_ttl_hours: int = 24

    # Edge controls. Keep rate limiting at the gateway too; these per-process
    # limits protect a single deployment from accidental request bursts.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    rate_limit_per_minute: int = 0
    trust_proxy_headers: bool = False
    security_headers_enabled: bool = True
    hsts_seconds: int = 0
    metrics_enabled: bool = True
    metrics_token: str | None = None
    access_log_enabled: bool = True

    # Optional Temporal address. When unset the in-process orchestrator is used.
    temporal_address: str | None = None

    # Timeouts for connector operations (seconds).
    connector_timeout_seconds: int = 30

    # Passive exposure discovery. Network collectors are disabled by default and
    # require both this switch and explicit per-scan authorization.
    exposure_enabled: bool = False
    exposure_timeout_seconds: int = 15
    exposure_max_bytes: int = 2_000_000
    exposure_rate_limit_seconds: float = 1.0
    exposure_max_queries: int = 6
    exposure_user_agent: str = "ErasureProof/1.0 (+https://github.com/dsk-dev-ai/erasureproof)"
    serper_api_key: str | None = None
    brave_api_key: str | None = None
    github_token: str | None = None
    hibp_api_key: str | None = None

    @property
    def is_production(self) -> bool:
        return self.environment.strip().lower() in {"production", "prod"}

    def model_post_init(self, __context: object) -> None:
        self.data_dir = Path(self.data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        if self.evidence_dir is None:
            self.evidence_dir = self.data_dir / "evidence"
        if self.ledger_path is None:
            self.ledger_path = self.data_dir / "ledger.jsonl"
        if self.attestation_dir is None:
            self.attestation_dir = self.data_dir / "attestations"

        for directory in (self.evidence_dir, self.attestation_dir):
            Path(directory).mkdir(parents=True, exist_ok=True)
        Path(self.ledger_path).parent.mkdir(parents=True, exist_ok=True)

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


def _api_key_errors(raw: str) -> list[str]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return ["ERASUREPROOF_API_KEYS must be valid JSON"]
    if not isinstance(parsed, list) or not parsed:
        return ["ERASUREPROOF_API_KEYS must be a non-empty JSON list"]
    errors = []
    for index, item in enumerate(parsed):
        if not isinstance(item, dict) or not item.get("key"):
            errors.append(f"API key entry {index} is missing key")
            continue
        role = str(item.get("role", "viewer")).lower()
        if role not in {"viewer", "operator", "admin"}:
            errors.append(f"API key entry {index} has an invalid role")
        tenant = item.get("tenant_id", item.get("tenant"))
        if tenant in {None, ""}:
            errors.append(f"API key entry {index} is missing tenant")
        elif tenant == "*" and role != "admin":
            errors.append(f"API key entry {index} uses a wildcard tenant without admin role")
    return errors


def validate_runtime_settings(settings: Settings) -> list[str]:
    """Reject unusable security configuration and return non-fatal warnings."""

    mode = settings.auth_mode.strip().lower()
    errors: list[str] = []
    if mode not in {"disabled", "api_key", "oidc"}:
        errors.append("ERASUREPROOF_AUTH_MODE must be disabled, api_key, or oidc")
    elif mode == "api_key":
        errors.extend(_api_key_errors(settings.api_keys))
    elif mode == "oidc":
        missing = [
            name
            for name, value in (
                ("ERASUREPROOF_OIDC_ISSUER", settings.oidc_issuer),
                ("ERASUREPROOF_OIDC_AUDIENCE", settings.oidc_audience),
                ("ERASUREPROOF_OIDC_JWKS_URL", settings.oidc_jwks_url),
            )
            if not value
        ]
        if missing:
            errors.append("OIDC requires " + ", ".join(missing))
        algorithms = {
            item.strip().upper() for item in settings.oidc_algorithms.split(",") if item.strip()
        }
        if not algorithms or not algorithms <= {"RS256", "RS384", "RS512"}:
            errors.append("OIDC algorithms must be a subset of RS256, RS384, RS512")

    if settings.is_production and mode == "disabled":
        errors.append("authentication cannot be disabled when ENVIRONMENT=production")
    if settings.is_production and settings.attestation_key == DEFAULT_ATTESTATION_KEY:
        errors.append("ERASUREPROOF_ATTESTATION_KEY must be changed in production")
    if settings.approval_ttl_hours < 1:
        errors.append("ERASUREPROOF_APPROVAL_TTL_HOURS must be at least 1")

    warnings: list[str] = []
    if settings.is_production and settings.demo_enabled:
        warnings.append("demo bootstrap is enabled in production")
    if settings.is_production and not settings.require_remediation_approval:
        warnings.append("remediation approval is disabled in production")
    if settings.is_production and settings.hsts_seconds <= 0:
        warnings.append("HSTS is disabled in production")
    if settings.metrics_enabled and not settings.metrics_token and mode != "disabled":
        warnings.append("/metrics falls back to admin authentication because no token is set")
    if settings.is_production and settings.rate_limit_per_minute <= 0:
        warnings.append("local rate limiting is disabled in production")
    if settings.is_production and settings.trust_proxy_headers:
        warnings.append("proxy headers are trusted; ensure only the ingress can reach the API")

    if errors:
        raise ValueError("; ".join(errors))
    for warning in warnings:
        LOGGER.warning("configuration: %s", warning)
    return warnings


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide settings singleton."""

    return Settings()
