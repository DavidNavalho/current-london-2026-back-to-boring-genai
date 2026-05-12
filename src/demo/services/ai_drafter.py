from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from demo.contracts import AiSafeEvidence, AnswerType, PreparedQuestion, ProposedAnswer, make_event_id
from demo.model.prompts import build_draft_prompt


class DraftModelOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer_type: AnswerType
    draft_answer: str
    evidence_ids: list[str]
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    risk_level: str
    requires_human_review: Literal[True]
    cannot_answer_reason: str | None


class DraftProvider(Protocol):
    def generate(self, prompt: str) -> DraftModelOutput | dict:
        """Generate draft answer content from a prompt."""


def build_proposed_answer(
    prepared_question: PreparedQuestion,
    model_output: DraftModelOutput,
    *,
    now: datetime | None = None,
) -> ProposedAnswer:
    occurred_at = now or datetime.now(UTC)
    return ProposedAnswer(
        event_id=make_event_id(),
        run_id=prepared_question.run_id,
        occurred_at=occurred_at,
        producer="svc-ai-drafter",
        schema_version=1,
        question_id=prepared_question.question_id,
        control_area=prepared_question.control_area,
        answer_type=model_output.answer_type,
        draft_answer=model_output.draft_answer,
        evidence_ids=model_output.evidence_ids,
        confidence=model_output.confidence,
        risk_level=model_output.risk_level,
        requires_human_review=model_output.requires_human_review,
        cannot_answer_reason=model_output.cannot_answer_reason,
    )


def generate_draft(
    prepared_question: PreparedQuestion,
    ai_safe_evidence: list[AiSafeEvidence],
    provider: DraftProvider,
) -> ProposedAnswer:
    prompt = build_draft_prompt(prepared_question, ai_safe_evidence)
    raw_output = provider.generate(prompt)
    model_output = (
        raw_output
        if isinstance(raw_output, DraftModelOutput)
        else DraftModelOutput.model_validate(raw_output)
    )

    allowed_evidence_ids = {
        item.evidence_id for item in ai_safe_evidence
    } | {item.source_evidence_id for item in ai_safe_evidence}
    unknown_evidence_ids = set(model_output.evidence_ids) - allowed_evidence_ids
    if unknown_evidence_ids:
        formatted = ", ".join(sorted(unknown_evidence_ids))
        raise ValueError(f"Model output referenced evidence not present in AI-safe evidence: {formatted}")

    return build_proposed_answer(prepared_question, model_output)
