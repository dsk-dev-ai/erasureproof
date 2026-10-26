"""Policy-as-code.

Policies map a data category (and optional conditions) to one of five actions:
delete, redact, anonymize, retain, or preserve a tombstone. YAML policies live
in ``policies/``; a GDPR-flavoured default keeps the engine usable out of the box.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ..models.domain import Action, Category, ResourceRef

DIRECT_IDENTIFIERS = ("name", "email", "phone", "email_hash")
STABLE_REFERENCE = "user_id"


@dataclass(frozen=True, slots=True)
class Decision:
    action: Action
    rule_name: str
    redact_fields: tuple[str, ...] = ()
    retain_fields: tuple[str, ...] = ()
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action.value,
            "rule_name": self.rule_name,
            "redact_fields": list(self.redact_fields),
            "retain_fields": list(self.retain_fields),
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class Rule:
    name: str
    action: Action
    when: dict[str, Any] = field(default_factory=dict)
    redact_fields: tuple[str, ...] = ()
    retain_fields: tuple[str, ...] = ()
    reason: str = ""
    priority: int = 0

    def matches(self, resource: ResourceRef) -> bool:
        for key, expected in self.when.items():
            if key == "category":
                values = expected if isinstance(expected, (list, tuple)) else [expected]
                if resource.category.value not in values:
                    return False
            elif key == "system_id":
                values = expected if isinstance(expected, (list, tuple)) else [expected]
                if resource.system_id not in values:
                    return False
            elif key == "resource_prefix":
                if not resource.resource_id.startswith(str(expected)):
                    return False
            elif key == "has_exposed_fields":
                if bool(resource.exposed_fields) is not bool(expected):
                    return False
            elif key.startswith("payload."):
                actual = resource.payload.get(key.split(".", 1)[1])
                if isinstance(expected, (list, tuple)):
                    if actual not in expected:
                        return False
                elif actual != expected:
                    return False
            else:
                return False
        return True

    def to_decision(self) -> Decision:
        return Decision(
            action=self.action,
            rule_name=self.name,
            redact_fields=self.redact_fields,
            retain_fields=self.retain_fields,
            reason=self.reason,
        )


_DEFAULT_CATEGORY_RULES: dict[Category, Decision] = {
    Category.PRIMARY_ACCOUNT: Decision(
        Action.TOMBSTONE,
        "default-primary-account",
        redact_fields=DIRECT_IDENTIFIERS,
        retain_fields=(STABLE_REFERENCE,),
        reason="Replace the account with a tombstone that keeps only the stable reference.",
    ),
    Category.TOMBSTONE: Decision(
        Action.TOMBSTONE,
        "default-tombstone",
        redact_fields=DIRECT_IDENTIFIERS,
        retain_fields=(STABLE_REFERENCE,),
        reason="Keep the tombstone; remove direct identifiers.",
    ),
    Category.AUDIT_TRAIL: Decision(
        Action.RETAIN,
        "default-audit-trail",
        retain_fields=(STABLE_REFERENCE,),
        reason="Audit records are required for accountability and must be retained.",
    ),
    Category.LEGAL_HOLD: Decision(
        Action.RETAIN,
        "default-legal-hold",
        retain_fields=(STABLE_REFERENCE,),
        reason="Records under legal hold must be retained.",
    ),
}

_FALLBACK_DELETE = Decision(
    Action.DELETE,
    "default-delete",
    reason="Derived and operational copies must be removed.",
)


@dataclass
class Policy:
    name: str
    jurisdiction: str
    version: str = "1.0"
    defaults: dict[Category, Decision] = field(default_factory=dict)
    rules: tuple[Rule, ...] = ()

    def decide(self, resource: ResourceRef) -> Decision:
        if resource.payload.get("legal_hold") is True:
            return Decision(
                Action.RETAIN,
                "legal-hold",
                retain_fields=(STABLE_REFERENCE,),
                reason="Record is under legal hold.",
            )
        if resource.payload.get("retention_required") is True:
            return Decision(
                Action.RETAIN,
                "retention-required",
                retain_fields=(STABLE_REFERENCE,),
                reason="Policy requires this record to be retained.",
            )

        for rule in sorted(self.rules, key=lambda r: r.priority, reverse=True):
            if rule.matches(resource):
                return rule.to_decision()

        return self.defaults.get(resource.category, _FALLBACK_DELETE)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "jurisdiction": self.jurisdiction,
            "version": self.version,
            "defaults": {k.value: v.to_dict() for k, v in self.defaults.items()},
            "rules": [
                {
                    "name": r.name,
                    "priority": r.priority,
                    "when": r.when,
                    "action": r.action.value,
                    "redact_fields": list(r.redact_fields),
                    "retain_fields": list(r.retain_fields),
                    "reason": r.reason,
                }
                for r in self.rules
            ],
        }


def _decision_from_dict(data: dict[str, Any], fallback_name: str) -> Decision:
    return Decision(
        action=Action(str(data.get("action", "DELETE")).upper()),
        rule_name=str(data.get("name", fallback_name)),
        redact_fields=tuple(data.get("redact_fields", ())),
        retain_fields=tuple(data.get("retain_fields", ())),
        reason=str(data.get("reason", "")),
    )


def policy_from_dict(data: dict[str, Any]) -> Policy:
    defaults: dict[Category, Decision] = {}
    for category, raw in (data.get("defaults") or {}).items():
        defaults[Category(str(category).upper())] = _decision_from_dict(
            raw, f"default-{str(category).lower()}"
        )

    rules = tuple(
        Rule(
            name=str(raw.get("name", f"rule-{index}")),
            action=Action(str(raw.get("action", "DELETE")).upper()),
            when=dict(raw.get("when") or {}),
            redact_fields=tuple(raw.get("redact_fields", ())),
            retain_fields=tuple(raw.get("retain_fields", ())),
            reason=str(raw.get("reason", "")),
            priority=int(raw.get("priority", 0)),
        )
        for index, raw in enumerate(data.get("rules") or [])
    )

    jurisdiction = str(data.get("jurisdiction", "gdpr")).lower()
    return Policy(
        name=str(data.get("name", f"{jurisdiction.upper()} Erasure Policy")),
        jurisdiction=jurisdiction,
        version=str(data.get("version", "1.0")),
        defaults=defaults or dict(_DEFAULT_CATEGORY_RULES),
        rules=rules,
    )


def default_policy(jurisdiction: str = "gdpr") -> Policy:
    return Policy(
        name="GDPR Erasure Policy",
        jurisdiction=jurisdiction,
        defaults=dict(_DEFAULT_CATEGORY_RULES),
        rules=(
            Rule(
                name="audit-trail-retained",
                action=Action.RETAIN,
                when={"category": Category.AUDIT_TRAIL.value},
                retain_fields=(STABLE_REFERENCE,),
                reason="Statutory audit trail is retained.",
                priority=90,
            ),
            Rule(
                name="legal-hold-retained",
                action=Action.RETAIN,
                when={"payload.legal_hold": True},
                retain_fields=(STABLE_REFERENCE,),
                reason="Record is subject to legal hold.",
                priority=100,
            ),
            Rule(
                name="support-attachments-deleted",
                action=Action.DELETE,
                when={"category": Category.SUPPORT.value},
                reason="Support attachments and ticket bodies are deleted.",
                priority=50,
            ),
        ),
    )


class PolicyRegistry:
    def __init__(self, policies: Iterable[Policy]) -> None:
        self._policies: dict[str, Policy] = {p.jurisdiction: p for p in policies}

    @classmethod
    def load(cls, directory: str | Path) -> PolicyRegistry:
        policies: list[Policy] = []
        path = Path(directory)
        if path.is_dir():
            for file in sorted([*path.glob("*.yaml"), *path.glob("*.yml")]):
                raw = yaml.safe_load(file.read_text(encoding="utf-8")) or {}
                entries = raw.get("policies") if isinstance(raw, dict) else None
                if isinstance(entries, list):
                    policies.extend(policy_from_dict(entry) for entry in entries)
                elif isinstance(raw, dict):
                    policies.append(policy_from_dict(raw))
        if not policies:
            policies.append(default_policy())
        return cls(policies)

    def get(self, jurisdiction: str | None) -> Policy:
        key = (jurisdiction or "gdpr").lower()
        if key in self._policies:
            return self._policies[key]
        if "gdpr" in self._policies:
            return self._policies["gdpr"]
        return next(iter(self._policies.values()))

    def jurisdictions(self) -> list[str]:
        return sorted(self._policies)


def exposed_identifiers(resource: ResourceRef, decision: Decision) -> list[str]:
    if decision.redact_fields:
        return [f for f in resource.exposed_fields if f in decision.redact_fields]
    return list(resource.exposed_fields)


def is_compliant(resource: ResourceRef, decision: Decision) -> bool:
    """Whether an existing record already has the policy-required treatment."""

    if decision.action is Action.DELETE:
        return False
    if decision.action is Action.RETAIN:
        return True
    if decision.action in (Action.REDACT, Action.TOMBSTONE):
        return not exposed_identifiers(resource, decision)
    if decision.action is Action.ANONYMIZE:
        return bool(resource.payload.get("anonymized")) or resource.payload.get("linked") is False
    return False
