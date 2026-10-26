from __future__ import annotations

from pathlib import Path

from erasureproof.core.policy import (
    DIRECT_IDENTIFIERS,
    PolicyRegistry,
    default_policy,
    is_compliant,
)
from erasureproof.models.domain import Action, Category, ResourceRef


def test_default_actions_by_category() -> None:
    policy = default_policy()

    account = ResourceRef("db", "account:1", Category.PRIMARY_ACCOUNT)
    search = ResourceRef("db", "search:1", Category.SEARCH_INDEX)
    audit = ResourceRef("db", "audit:1", Category.AUDIT_TRAIL)

    assert policy.decide(account).action is Action.TOMBSTONE
    assert policy.decide(search).action is Action.DELETE
    assert policy.decide(audit).action is Action.RETAIN


def test_legal_hold_overrides_defaults() -> None:
    policy = default_policy()
    record = ResourceRef(
        "db",
        "orders:1",
        Category.PRIMARY_ACCOUNT,
        payload={"legal_hold": True},
    )
    decision = policy.decide(record)
    assert decision.action is Action.RETAIN
    assert decision.rule_name == "legal-hold"


def test_redaction_compliance() -> None:
    policy = default_policy()
    record = ResourceRef(
        "db",
        "account:1",
        Category.PRIMARY_ACCOUNT,
        exposed_fields=["name", "email"],
    )
    decision = policy.decide(record)
    assert not is_compliant(record, decision)

    record.exposed_fields = []
    assert is_compliant(record, decision)

    assert set(decision.redact_fields) == set(DIRECT_IDENTIFIERS)
    assert "user_id" in decision.retain_fields


def test_yaml_policy_registry_loads_shipped_policies() -> None:
    directory = Path(__file__).resolve().parents[1] / "policies"
    registry = PolicyRegistry.load(directory)

    assert {"ccpa", "gdpr"} <= set(registry.jurisdictions())
    gdpr = registry.get("gdpr")
    assert gdpr.name == "GDPR Erasure Policy"
    assert gdpr.decide(ResourceRef("db", "x", Category.ANALYTICS)).action is Action.DELETE
    assert registry.get("unknown").jurisdiction == "gdpr"
