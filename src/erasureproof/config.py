"""Application configuration.

Every setting can be overridden with an ``ERASUREPROOF_``-prefixed environment
variable or a ``.env`` file. Safe local defaults mean the demo runs with no
external services.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


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
    attestation_key: str = "dev-insecure-change-me"

    # Policy
    policy_dir: Path = Path("./policies")
    default_jurisdiction: str = "gdpr"

    # The console can create a safe, non-destructive demo tenant. Disable this
    # for any deployment that exposes the API outside a trusted environment.
    demo_enabled: bool = True

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
    exposure_user_agent: str = (
        "ErasureProof/0.2 (+https://github.com/dsk-dev-ai/erasureproof)"
    )
    serper_api_key: str | None = None
    brave_api_key: str | None = None
    github_token: str | None = None
    hibp_api_key: str | None = None

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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide settings singleton."""

    return Settings()
