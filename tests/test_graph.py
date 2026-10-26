from __future__ import annotations

from erasureproof.core.graph import build_step_graph, optimise_plan, plan_from_dict
from erasureproof.models.domain import (
    Category,
    Phase,
    Plan,
    State,
    Step,
)


def _plan() -> Plan:
    return Plan(
        request_id="req_1",
        steps=[
            Step(
                1,
                Phase.FINDING,
                "account_db",
                "customers:1",
                "REPORT_REMAINING_RECORD",
                State.PRESENT,
                "ev_1",
                Category.PRIMARY_ACCOUNT,
            ),
            Step(
                2,
                Phase.REMEDIATION,
                "sync",
                "flow:1",
                "DISABLE_DATA_FLOW",
                State.DISABLED,
                category=Category.REPLICA,
            ),
            Step(
                3,
                Phase.REMEDIATION,
                "account_db",
                "customers:1",
                "DELETE_RECORD",
                State.ABSENT,
                category=Category.PRIMARY_ACCOUNT,
            ),
            Step(
                4,
                Phase.VERIFICATION,
                "account_db",
                "customers:1",
                "VERIFY_RECORD_ABSENT",
                State.ABSENT,
                category=Category.PRIMARY_ACCOUNT,
            ),
        ],
    )


def test_graph_orders_findings_controls_actions_and_verification() -> None:
    graph = build_step_graph(_plan())
    order = [node.operation for node in graph.topological_order()]
    assert order.index("REPORT_REMAINING_RECORD") < order.index("DISABLE_DATA_FLOW")
    assert order.index("DISABLE_DATA_FLOW") < order.index("DELETE_RECORD")
    assert order.index("DELETE_RECORD") < order.index("VERIFY_RECORD_ABSENT")
    assert graph.cycle is False
    assert graph.critical_path


def test_graph_optimises_plan_and_renders() -> None:
    plan = _plan()
    optimised = optimise_plan(plan)
    assert [step.step_no for step in optimised.steps] == [1, 2, 3, 4]
    graph = build_step_graph(optimised)
    assert "flowchart TD" in graph.to_mermaid()
    assert "digraph erasureproof" in graph.to_dot()
    assert graph.to_dict()["counts"]["FINDING"] == 1


def test_plan_from_dict_skips_invalid_steps_and_keeps_categories() -> None:
    plan = _plan()
    data = plan.to_dict()
    data["steps"][1]["category"] = "REPLICA"
    data["steps"].append(
        {
            "step_no": 99,
            "phase": "NOPE",
            "state": "ABSENT",
            "system_id": "x",
            "resource_id": "y",
            "operation": "DELETE_RECORD",
        }
    )
    rebuilt = plan_from_dict(data)
    assert len(rebuilt.steps) == 4
    assert rebuilt.steps[1].category is Category.REPLICA
    assert rebuilt.to_dict() == plan.to_dict()

    full_result = {
        "status": "INCOMPLETE",
        "plan": plan.to_dict(),
        "graph": build_step_graph(plan).to_dict(),
    }
    from_result = plan_from_dict(full_result)
    assert from_result.steps[1].category is Category.REPLICA
