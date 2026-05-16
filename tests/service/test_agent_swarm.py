from __future__ import annotations

import pytest

from demo.services.agent_swarm import (
    SwarmQuestionResult,
    build_swarm_plan,
    run_swarm,
    validate_swarm_concurrency,
)


def test_swarm_plan_creates_isolated_child_runs_for_questions():
    plan = build_swarm_plan(
        swarm_id="swarm-demo",
        question_ids=["Q-001", "Q-002"],
    )

    assert plan.swarm_id == "swarm-demo"
    assert [child.question_id for child in plan.children] == ["Q-001", "Q-002"]
    assert [child.run_id for child in plan.children] == [
        "swarm-demo-Q-001",
        "swarm-demo-Q-002",
    ]


def test_swarm_plan_defaults_to_all_fixture_questions():
    plan = build_swarm_plan(swarm_id="swarm-demo")

    assert len(plan.children) == 10
    assert plan.children[0].question_id == "Q-001"
    assert plan.children[-1].question_id == "Q-010"


@pytest.mark.parametrize("value", [0, -1, 4])
def test_swarm_concurrency_rejects_values_outside_demo_bounds(value):
    with pytest.raises(ValueError, match="concurrency"):
        validate_swarm_concurrency(value)


def test_swarm_concurrency_defaults_to_two_and_allows_three():
    assert validate_swarm_concurrency(None) == 2
    assert validate_swarm_concurrency(3) == 3


def test_run_swarm_preserves_question_order_and_reports_partial_failures():
    plan = build_swarm_plan(swarm_id="swarm-demo", question_ids=["Q-001", "Q-002"])

    def worker(child):
        if child.question_id == "Q-002":
            raise RuntimeError("provider failed")
        return SwarmQuestionResult(
            swarm_id=child.swarm_id,
            run_id=child.run_id,
            question_id=child.question_id,
            status="accepted",
            answer_type="yes_with_evidence",
            tool_call_count=2,
            trace_url="http://localhost:3000/project/demo/traces/q1",
        )

    result = run_swarm(plan, concurrency=2, worker=worker)

    assert [item.question_id for item in result.questions] == ["Q-001", "Q-002"]
    assert [item.status for item in result.questions] == ["accepted", "failed"]
    assert result.accepted_count == 1
    assert result.rejected_count == 0
    assert result.failed_count == 1
    assert result.completed_count == 2
    assert "provider failed" in result.questions[1].message

