from __future__ import annotations

import pytest

from demo.fixtures import get_question, load_evidence_library
from demo.services.agentic_drafter import (
    AgentLoopError,
    inspect_evidence,
    run_agentic_draft,
    search_evidence,
)
from demo.services.prepare_questions import prepared_question_from_fixture


class ScriptedAgentProvider:
    def __init__(self, actions: list[dict]):
        self.actions = list(actions)
        self.prompts: list[str] = []

    def generate_action(self, prompt: str) -> dict:
        self.prompts.append(prompt)
        if not self.actions:
            raise AssertionError("scripted provider was called more times than expected")
        return self.actions.pop(0)


def _question(question_id: str = "Q-001"):
    return prepared_question_from_fixture("run-agent-test", get_question(question_id), 1)


def _finish(**overrides) -> dict:
    payload = {
        "action": "finish_draft",
        "answer_type": "yes_with_evidence",
        "draft_answer": "Yes. Customer data is encrypted at rest and in transit.",
        "evidence_ids": ["EVID-ENC-001"],
        "confidence": 0.86,
        "risk_level": "low",
        "requires_human_review": True,
        "cannot_answer_reason": None,
    }
    payload.update(overrides)
    return payload


def test_search_evidence_returns_metadata_without_evidence_content():
    hits = search_evidence(_question(), load_evidence_library(), "encryption customer data")

    assert [hit.evidence_id for hit in hits[:2]] == ["EVID-ENC-001", "EVID-DP-001"]
    serialized = " ".join(hit.model_dump_json() for hit in hits)
    assert "encrypted at rest using managed encryption controls" not in serialized
    assert "safe_summary" not in serialized


def test_inspect_evidence_returns_only_ai_safe_summaries_and_withholds_restricted_items():
    result = inspect_evidence(_question("Q-008"), load_evidence_library(), ["EVID-ADMIN-SECRET"])

    assert result.ai_safe_evidence == []
    assert result.withheld_evidence_ids == ["EVID-ADMIN-SECRET"]
    assert "alex.admin@example.test" not in result.model_dump_json()


def test_agent_loop_refuses_to_finish_before_two_tool_calls():
    provider = ScriptedAgentProvider(
        [
            _finish(),
            {"action": "search_evidence", "query": "encryption customer data"},
            {"action": "inspect_evidence", "evidence_ids": ["EVID-ENC-001"]},
            _finish(),
        ]
    )

    result = run_agentic_draft(_question(), load_evidence_library(), provider)

    assert result.proposed_answer.evidence_ids == ["EVID-ENC-001"]
    assert [call.tool_name for call in result.tool_calls] == ["search_evidence", "inspect_evidence"]
    assert result.tool_call_count == 2
    assert "at least 2 evidence tool calls" in provider.prompts[1]


def test_agent_loop_does_not_execute_more_than_four_tool_calls():
    provider = ScriptedAgentProvider(
        [
            {"action": "search_evidence", "query": "encryption"},
            {"action": "inspect_evidence", "evidence_ids": ["EVID-ENC-001"]},
            {"action": "search_evidence", "query": "data protection"},
            {"action": "inspect_evidence", "evidence_ids": ["EVID-DP-001"]},
            {"action": "search_evidence", "query": "extra search should be refused"},
            _finish(evidence_ids=["EVID-ENC-001", "EVID-DP-001"]),
        ]
    )

    result = run_agentic_draft(_question(), load_evidence_library(), provider)

    assert result.tool_call_count == 4
    assert [call.tool_name for call in result.tool_calls] == [
        "search_evidence",
        "inspect_evidence",
        "search_evidence",
        "inspect_evidence",
    ]
    assert "extra search should be refused" not in str([call.input for call in result.tool_calls])
    assert result.proposed_answer.evidence_ids == ["EVID-ENC-001", "EVID-DP-001"]


def test_agent_loop_rejects_final_draft_that_cites_uninspected_evidence():
    provider = ScriptedAgentProvider(
        [
            {"action": "search_evidence", "query": "encryption customer data"},
            {"action": "inspect_evidence", "evidence_ids": ["EVID-ENC-001"]},
            _finish(evidence_ids=["EVID-DP-001"]),
        ]
    )

    with pytest.raises(AgentLoopError, match="not inspected"):
        run_agentic_draft(_question(), load_evidence_library(), provider)
