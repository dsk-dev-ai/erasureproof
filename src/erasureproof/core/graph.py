"""Step dependency graph.

The planner already emits a safe order. The graph makes that order inspectable,
machine-checkable and optimisable:

* findings are roots;
* flow and restore controls run before record changes;
* downstream categories (exports, search, analytics, logs, support, replicas,
  archives) run before primary accounts and tombstones;
* every verification depends on the action that produced the state it checks.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from typing import Any

from ..models.domain import Category, Phase, Plan, RemediationOperation, State, Step
from .planner import CATEGORY_ORDER

PHASE_ORDER = {
    Phase.FINDING: 0,
    Phase.REMEDIATION: 1,
    Phase.VERIFICATION: 2,
}

_CONTROL_OPERATIONS = {
    RemediationOperation.DISABLE_DATA_FLOW.value,
    RemediationOperation.BLOCK_RESTORE.value,
}

_RECORD_OPERATIONS = {
    RemediationOperation.DELETE_RECORD.value,
    RemediationOperation.REDACT_RECORD.value,
    RemediationOperation.ANONYMIZE_RECORD.value,
}


@dataclass(slots=True)
class GraphNode:
    id: str
    step_no: int
    phase: Phase
    system_id: str
    resource_id: str
    operation: str
    state: str
    category: str | None = None
    depends_on: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        return f"#{self.step_no} {self.operation}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "step_no": self.step_no,
            "phase": self.phase.value,
            "system_id": self.system_id,
            "resource_id": self.resource_id,
            "operation": self.operation,
            "state": self.state,
            "category": self.category,
            "label": self.label,
            "depends_on": list(self.depends_on),
        }


@dataclass(slots=True)
class StepGraph:
    request_id: str
    nodes: list[GraphNode]
    edges: list[tuple[str, str]]
    cycle: bool = False
    critical_path: list[str] = field(default_factory=list)

    def by_id(self) -> dict[str, GraphNode]:
        return {node.id: node for node in self.nodes}

    def _kahn(self) -> list[GraphNode]:
        by_id = self.by_id()
        incoming = {node.id: set(node.depends_on) for node in self.nodes}
        children: dict[str, list[str]] = {node.id: [] for node in self.nodes}
        for node in self.nodes:
            for dependency in node.depends_on:
                if dependency in by_id:
                    children[dependency].append(node.id)
        heap: list[tuple[int, str]] = [
            (by_id[node_id].step_no, node_id)
            for node_id, deps in incoming.items()
            if not deps
        ]
        heapq.heapify(heap)
        ordered: list[GraphNode] = []
        while heap:
            _, node_id = heapq.heappop(heap)
            ordered.append(by_id[node_id])
            for child in sorted(children[node_id], key=lambda item: by_id[item].step_no):
                incoming[child].discard(node_id)
                if not incoming[child]:
                    heapq.heappush(heap, (by_id[child].step_no, child))
        if len(ordered) != len(self.nodes):
            return sorted(self.nodes, key=lambda node: node.step_no)
        return ordered

    def topological_order(self) -> list[GraphNode]:
        """Dependency-valid order, stabilised into FINDING→REMEDIATION→VERIFICATION."""

        order = self._kahn()
        indexed = {node.id: index for index, node in enumerate(order)}
        return sorted(
            order,
            key=lambda node: (PHASE_ORDER.get(node.phase, 99), indexed[node.id]),
        )

    def _critical_path(self, order: list[GraphNode]) -> list[str]:
        distance: dict[str, int] = {}
        previous: dict[str, str | None] = {}
        for node in order:
            distance[node.id] = 1 + max(
                (distance.get(dep, 0) for dep in node.depends_on), default=0
            )
            previous[node.id] = max(
                node.depends_on, key=lambda dep: distance.get(dep, 0), default=None
            )
        if not distance:
            return []
        order_index = {node.id: index for index, node in enumerate(order)}
        end = max(distance, key=lambda node_id: (distance[node_id], -order_index[node_id]))
        path: list[str] = []
        cursor: str | None = end
        while cursor:
            path.append(cursor)
            cursor = previous.get(cursor)
        return list(reversed(path))

    def optimise(self, plan: Plan) -> Plan:
        order = self.topological_order()
        by_step = {step.step_no: step for step in plan.steps}
        steps = [by_step[node.step_no] for node in order if node.step_no in by_step]
        if len(steps) == len(plan.steps):
            plan.steps = steps
            plan.renumber()
        return plan

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "cycle": self.cycle,
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [{"from": source, "to": target} for source, target in self.edges],
            "order": [node.id for node in self.topological_order()],
            "critical_path": list(self.critical_path),
            "counts": {
                phase.value: sum(1 for node in self.nodes if node.phase is phase)
                for phase in Phase
            },
        }

    def to_mermaid(self) -> str:
        lines = ["flowchart TD"]
        for phase in Phase:
            phase_nodes = [node for node in self.nodes if node.phase is phase]
            if not phase_nodes:
                continue
            lines.append(f'  subgraph {phase.value.lower()}["{phase.value}"]')
            for node in phase_nodes:
                label = (
                    f"#{node.step_no} {node.operation}<br/>"
                    f"{node.system_id}:{node.resource_id}"
                )
                lines.append(f'    n{node.step_no}["{_escape(label)}"]')
            lines.append("  end")
        for source, target in self.edges:
            source_no = source.lstrip("n")
            target_no = target.lstrip("n")
            lines.append(f"  n{source_no} --> n{target_no}")
        lines.extend(
            [
                "  classDef finding fill:#fff4d6,stroke:#c58a00,color:#3d2b00",
                "  classDef remediation fill:#e8f4ff,stroke:#2277cc,color:#0b2e4f",
                "  classDef verification fill:#e9f8ee,stroke:#2b8a4b,color:#103d22",
            ]
        )
        for phase, style in (
            (Phase.FINDING, "finding"),
            (Phase.REMEDIATION, "remediation"),
            (Phase.VERIFICATION, "verification"),
        ):
            ids = [f"n{node.step_no}" for node in self.nodes if node.phase is phase]
            if ids:
                lines.append(f"  class {','.join(ids)} {style}")
        return "\n".join(lines) + "\n"

    def to_dot(self) -> str:
        lines = [
            "digraph erasureproof {",
            "  rankdir=LR;",
            '  node [shape=box, style="rounded,filled", fontname="Helvetica"];',
        ]
        colors = {
            Phase.FINDING: "#fff4d6",
            Phase.REMEDIATION: "#e8f4ff",
            Phase.VERIFICATION: "#e9f8ee",
        }
        for node in self.nodes:
            label = (
                f"#{node.step_no} {node.operation}\\n{node.system_id}:{node.resource_id}"
            ).replace('"', '\\"')
            color = colors.get(node.phase, "#ffffff")
            lines.append(f'  n{node.step_no} [label="{label}", fillcolor="{color}"];')
        for source, target in self.edges:
            source_no = source.lstrip("n")
            target_no = target.lstrip("n")
            lines.append(f"  n{source_no} -> n{target_no};")
        lines.append("}")
        return "\n".join(lines) + "\n"


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def build_step_graph(plan: Plan) -> StepGraph:
    steps = sorted(plan.steps, key=lambda step: step.step_no)
    nodes = [
        GraphNode(
            id=f"n{step.step_no}",
            step_no=step.step_no,
            phase=step.phase,
            system_id=step.system_id,
            resource_id=step.resource_id,
            operation=step.operation,
            state=step.state.value,
            category=step.category.value if step.category else None,
        )
        for step in steps
    ]
    by_id = {node.id: node for node in nodes}

    finding: dict[str, str] = {}
    remediation: dict[str, str] = {}
    control_ids: list[str] = []
    record_ids: list[str] = []
    record_by_category: dict[str, list[str]] = {}
    verification: dict[str, list[str]] = {}

    for step in steps:
        key = f"{step.system_id}:{step.resource_id}"
        node_id = f"n{step.step_no}"
        if step.phase is Phase.FINDING:
            finding.setdefault(key, node_id)
        elif step.phase is Phase.REMEDIATION:
            remediation.setdefault(key, node_id)
            if step.operation in _CONTROL_OPERATIONS:
                control_ids.append(node_id)
            elif step.operation in _RECORD_OPERATIONS:
                record_ids.append(node_id)
                category = step.category.value if step.category else "UNKNOWN"
                record_by_category.setdefault(category, []).append(node_id)
        elif step.phase is Phase.VERIFICATION:
            verification.setdefault(key, []).append(node_id)

    # Category barrier: each category waits for the immediately lower category.
    ranked_categories = sorted(record_by_category, key=lambda item: CATEGORY_ORDER.get(
        _category(item), 99
    ))
    previous_ids: list[str] = []
    for category in ranked_categories:
        for node_id in record_by_category[category]:
            by_id[node_id].depends_on.extend(previous_ids)
        previous_ids = record_by_category[category]

    for step in steps:
        key = f"{step.system_id}:{step.resource_id}"
        node = by_id[f"n{step.step_no}"]
        if step.phase is Phase.FINDING:
            continue
        if step.phase is Phase.REMEDIATION:
            if key in finding:
                node.depends_on.append(finding[key])
            if step.operation in _CONTROL_OPERATIONS:
                continue
            node.depends_on.extend(control_ids)
        else:
            dependency = remediation.get(key) or finding.get(key)
            if dependency:
                node.depends_on.append(dependency)
            else:
                node.depends_on = []

    # Depends-on lists must be deterministic and free of duplicates.
    for node in nodes:
        node.depends_on = sorted(
            set(node.depends_on),
            key=lambda item: int(item.lstrip("n")) if item.lstrip("n").isdigit() else 0,
        )

    edges = [
        (dependency, node.id)
        for node in nodes
        for dependency in node.depends_on
        if dependency in by_id
    ]
    graph = StepGraph(request_id=plan.request_id, nodes=nodes, edges=edges)
    order = graph._kahn()
    graph.cycle = len(order) != len(nodes)
    graph.critical_path = graph._critical_path(order)
    return graph


def _category(value: str):
    from ..models.domain import Category

    try:
        return Category(value)
    except ValueError:
        return Category.EXPORT


def optimise_plan(plan: Plan) -> Plan:
    """Return the plan in dependency order. Cycles leave the original order."""

    graph = build_step_graph(plan)
    if graph.cycle:
        return plan
    return graph.optimise(plan)


def plan_from_dict(data: dict[str, Any]) -> Plan:
    """Rebuild a plan from stored JSON (API responses, attestations, exports)."""

    graph_data = data.get("graph")
    if isinstance(data.get("plan"), dict):
        data = data["plan"]
    categories: dict[int, Category] = {}
    if isinstance(graph_data, dict):
        for node in graph_data.get("nodes", []):
            raw_category = node.get("category")
            raw_step = node.get("step_no")
            if raw_category and str(raw_step).isdigit():
                try:
                    categories[int(raw_step)] = Category(str(raw_category))
                except ValueError:
                    continue

    steps: list[Step] = []
    for index, item in enumerate(data.get("steps", []), start=1):
        try:
            phase = Phase(str(item.get("phase")))
            state = State(str(item.get("state")))
        except ValueError:
            continue
        category_value = item.get("category")
        category = categories.get(int(item.get("step_no", index)))
        if category is None and category_value:
            try:
                category = Category(str(category_value))
            except ValueError:
                category = None
        steps.append(
            Step(
                step_no=int(item.get("step_no", index)),
                phase=phase,
                system_id=str(item.get("system_id", "")),
                resource_id=str(item.get("resource_id", "")),
                operation=str(item.get("operation", "")),
                state=state,
                evidence_id=str(item.get("evidence_id", "")),
                category=category,
            )
        )
    return Plan(
        request_id=str(data.get("request_id", "")),
        steps=steps,
        status=str(data.get("status", "PLANNED")),
    )
