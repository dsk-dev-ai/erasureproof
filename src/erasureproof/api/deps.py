"""Shared API dependencies."""

from __future__ import annotations

from functools import lru_cache

from ..config import Settings, get_settings
from ..core.attestation import AttestationService
from ..core.policy import PolicyRegistry
from ..evidence.ledger import EvidenceLedger
from ..evidence.store import EvidenceStore
from ..models.db import Database, get_database


def get_db() -> Database:
    return get_database()


def get_app_settings() -> Settings:
    return get_settings()


@lru_cache(maxsize=1)
def get_store() -> EvidenceStore:
    settings = get_settings()
    return EvidenceStore(settings.evidence_dir or settings.data_dir / "evidence")


@lru_cache(maxsize=1)
def get_ledger() -> EvidenceLedger:
    settings = get_settings()
    return EvidenceLedger(settings.ledger_path or settings.data_dir / "ledger.jsonl")


@lru_cache(maxsize=1)
def get_attestations() -> AttestationService:
    settings = get_settings()
    return AttestationService(
        settings.attestation_key,
        settings.attestation_dir or settings.data_dir / "attestations",
    )


@lru_cache(maxsize=1)
def get_policies() -> PolicyRegistry:
    settings = get_settings()
    return PolicyRegistry.load(settings.policy_dir)
