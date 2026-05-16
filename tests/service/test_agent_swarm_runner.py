from __future__ import annotations

from datetime import UTC, datetime

from demo.api.pacing import Pacing
from demo.contracts import AcceptedDraft, ProposedAnswer, make_event_id
from demo.fixtures import get_question
from demo.scenario_runner import AgentDraftRunResult, run_agent_swarm
import demo.scenario_runner as scenario_runner
from demo.services.agent_swarm import SwarmChildPlan, SwarmQuestionResult
from demo.services.agentic_drafter import ToolCallRecord
from demo.services.prepare_questions import prepared_question_from_fixture


def test_run_agent_swarm_uses_child_runs_and_preserves_question_order():
    seen: list[SwarmChildPlan] = []

    def fake_question_runner(child: SwarmChildPlan) -> SwarmQuestionResult:
        seen.append(child)
        return SwarmQuestionResult(
            swarm_id=child.swarm_id,
            run_id=child.run_id,
            question_id=child.question_id,
            status="accepted",
            answer_type="yes_with_evidence",
            tool_call_count=2,
        )

    result = run_agent_swarm(
        swarm_id="swarm-demo",
        question_ids=["Q-001", "Q-002"],
        concurrency=2,
        question_runner=fake_question_runner,
    )

    assert result.swarm_id == "swarm-demo"
    assert [child.run_id for child in seen] == ["swarm-demo-Q-001", "swarm-demo-Q-002"]
    assert [item.question_id for item in result.questions] == ["Q-001", "Q-002"]
    assert result.accepted_count == 2


def test_swarm_question_runner_stops_before_review_and_export(monkeypatch):
    child = SwarmChildPlan(
        swarm_id="swarm-demo",
        run_id="swarm-demo-Q-001",
        question_id="Q-001",
    )
    prepared = prepared_question_from_fixture(child.run_id, get_question("Q-001"), 1)
    proposed = ProposedAnswer(
        event_id=make_event_id(),
        run_id=child.run_id,
        occurred_at=datetime.now(UTC),
        producer="svc-ai-drafter",
        schema_version=1,
        question_id="Q-001",
        control_area=prepared.control_area,
        answer_type="yes_with_evidence",
        draft_answer="Yes. Customer data is encrypted at rest and in transit.",
        evidence_ids=["EVID-ENC-001"],
        confidence=0.9,
        risk_level="low",
        requires_human_review=True,
        cannot_answer_reason=None,
    )
    accepted = AcceptedDraft(
        event_id=make_event_id(),
        run_id=child.run_id,
        occurred_at=datetime.now(UTC),
        producer="svc-policy-guard",
        schema_version=1,
        question_id="Q-001",
        draft_event_id=proposed.event_id,
        evidence_ids=["EVID-ENC-001"],
    )
    tool_calls = [
        ToolCallRecord(
            turn=1,
            tool_index=1,
            tool_name="search_evidence",
            input={"query": "encryption"},
            observation={"hits": []},
        ),
        ToolCallRecord(
            turn=2,
            tool_index=2,
            tool_name="inspect_evidence",
            input={"evidence_ids": ["EVID-ENC-001"]},
            observation={"ai_safe_evidence_ids": ["EVID-ENC-001"]},
        ),
    ]

    monkeypatch.setattr(scenario_runner, "seed_evidence_events", lambda *_args, **_kwargs: 1)
    monkeypatch.setattr(scenario_runner, "ingest_questionnaire_event", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(scenario_runner, "prepare_questions_for_run", lambda *_args, **_kwargs: [prepared])
    monkeypatch.setattr(
        scenario_runner,
        "draft_answer_agentically_for_question",
        lambda *_args, **_kwargs: AgentDraftRunResult(
            proposed_answer=proposed,
            ai_safe_evidence=[],
            tool_calls=tool_calls,
            trace_url="http://localhost:3000/project/demo-project/traces/q1",
        ),
    )
    monkeypatch.setattr(scenario_runner, "guard_draft_for_question", lambda *_args, **_kwargs: accepted)
    monkeypatch.setattr(
        scenario_runner,
        "review_accepted_answer",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("review should not run")),
    )
    monkeypatch.setattr(
        scenario_runner,
        "export_reviewed_response",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("export should not run")),
    )

    result = scenario_runner._run_agent_swarm_question(
        child,
        provider_factory=lambda: object(),
        pacing=Pacing(name="realtime", delay_ms=0),
    )

    assert result.status == "accepted"
    assert result.run_id == "swarm-demo-Q-001"
    assert result.tool_call_count == 2
    assert result.trace_url.endswith("/q1")


def test_swarm_child_context_carries_langfuse_grouping_metadata(monkeypatch):
    child = SwarmChildPlan(
        swarm_id="swarm-demo",
        run_id="swarm-demo-Q-001",
        question_id="Q-001",
    )
    prepared = prepared_question_from_fixture(child.run_id, get_question("Q-001"), 1)
    proposed = ProposedAnswer(
        event_id=make_event_id(),
        run_id=child.run_id,
        occurred_at=datetime.now(UTC),
        producer="svc-ai-drafter",
        schema_version=1,
        question_id="Q-001",
        control_area=prepared.control_area,
        answer_type="yes_with_evidence",
        draft_answer="Yes. Customer data is encrypted at rest and in transit.",
        evidence_ids=["EVID-ENC-001"],
        confidence=0.9,
        risk_level="low",
        requires_human_review=True,
        cannot_answer_reason=None,
    )
    accepted = AcceptedDraft(
        event_id=make_event_id(),
        run_id=child.run_id,
        occurred_at=datetime.now(UTC),
        producer="svc-policy-guard",
        schema_version=1,
        question_id="Q-001",
        draft_event_id=proposed.event_id,
        evidence_ids=["EVID-ENC-001"],
    )
    captured_metadata = {}
    captured_session = {}

    def fake_draft(_run_id, _question_id, _provider, *, context=None):
        captured_metadata.update(context.metadata)
        captured_session["session_id"] = context.session_id
        return AgentDraftRunResult(
            proposed_answer=proposed,
            ai_safe_evidence=[],
            tool_calls=[],
            trace_url=None,
        )

    monkeypatch.setattr(scenario_runner, "seed_evidence_events", lambda *_args, **_kwargs: 1)
    monkeypatch.setattr(scenario_runner, "ingest_questionnaire_event", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(scenario_runner, "prepare_questions_for_run", lambda *_args, **_kwargs: [prepared])
    monkeypatch.setattr(scenario_runner, "draft_answer_agentically_for_question", fake_draft)
    monkeypatch.setattr(scenario_runner, "guard_draft_for_question", lambda *_args, **_kwargs: accepted)

    scenario_runner._run_agent_swarm_question(
        child,
        provider_factory=lambda: object(),
        pacing=Pacing(name="realtime", delay_ms=0),
        session_id="run-visible-q1",
    )

    assert captured_session["session_id"] == "run-visible-q1"
    assert captured_metadata["swarm_id"] == "swarm-demo"
    assert captured_metadata["main_run_id"] == "run-visible-q1"
    assert captured_metadata["child_run_id"] == "swarm-demo-Q-001"
    assert captured_metadata["question_id"] == "Q-001"
    assert captured_metadata["concurrency_limit"] == 2
