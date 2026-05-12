from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from demo.contracts import AiSafeEvidence, ProposedAnswer
from demo.fixtures import get_question, load_evidence_library
from demo.services.ai_drafter import DraftModelOutput, build_proposed_answer, generate_draft
from demo.services.evidence_gateway import make_ai_safe_evidence, select_evidence
from demo.services.prepare_questions import prepared_question_from_fixture


class RecordingProvider:
    def __init__(self, output: dict):
        self.output = output
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> dict:
        self.prompts.append(prompt)
        return self.output


def _question_and_evidence(question_id: str) -> tuple:
    question = prepared_question_from_fixture("run-drafter-test", get_question(question_id), 1)
    selected = select_evidence(question, load_evidence_library())
    ai_safe = make_ai_safe_evidence(question, selected)
    return question, ai_safe


def _valid_output(**overrides) -> dict:
    payload = {
        "answer_type": "yes_with_evidence",
        "draft_answer": "Yes. Customer data is encrypted at rest using managed encryption controls.",
        "evidence_ids": ["EVID-ENC-001"],
        "confidence": 0.86,
        "risk_level": "low",
        "requires_human_review": True,
        "cannot_answer_reason": None,
    }
    payload.update(overrides)
    return payload


def test_generate_draft_builds_schema_valid_proposed_answer():
    question, ai_safe = _question_and_evidence("Q-001")
    provider = RecordingProvider(_valid_output())

    proposed = generate_draft(question, ai_safe, provider)

    assert isinstance(proposed, ProposedAnswer)
    assert proposed.run_id == question.run_id
    assert proposed.question_id == "Q-001"
    assert proposed.control_area == "encryption"
    assert proposed.requires_human_review is True
    assert "EVID-ENC-001" in provider.prompts[0]


def test_build_proposed_answer_rejects_invalid_model_output():
    question, _ai_safe = _question_and_evidence("Q-001")

    with pytest.raises(ValidationError):
        build_proposed_answer(
            question,
            DraftModelOutput.model_validate(_valid_output(requires_human_review=False)),
        )


def test_generate_draft_rejects_evidence_not_present_in_ai_safe_input():
    question, ai_safe = _question_and_evidence("Q-001")
    provider = RecordingProvider(_valid_output(evidence_ids=["EVID-ADMIN-SECRET"]))

    with pytest.raises(ValueError, match="not present in AI-safe evidence"):
        generate_draft(question, ai_safe, provider)


def test_generate_draft_does_not_prompt_with_restricted_values():
    question, ai_safe = _question_and_evidence("Q-008")
    provider = RecordingProvider(
        _valid_output(
            answer_type="cannot_answer",
            draft_answer="Cannot answer from approved evidence.",
            evidence_ids=[],
            confidence=0.2,
            risk_level="critical",
            cannot_answer_reason="No AI-safe evidence supports the requested administrator list.",
        )
    )

    proposed = generate_draft(question, ai_safe, provider)

    assert proposed.answer_type.value == "cannot_answer"
    assert "EVID-ADMIN-SECRET" not in provider.prompts[0]
    assert "alex.admin@example.test" not in provider.prompts[0]


def test_build_proposed_answer_uses_event_envelope_from_question():
    question, _ai_safe = _question_and_evidence("Q-001")
    output = DraftModelOutput.model_validate(_valid_output())

    proposed = build_proposed_answer(question, output, now=datetime(2026, 1, 2, tzinfo=UTC))

    assert proposed.run_id == question.run_id
    assert proposed.occurred_at.isoformat() == "2026-01-02T00:00:00+00:00"
    assert proposed.producer == "svc-ai-drafter"
