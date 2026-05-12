from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, ClassVar, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def make_event_id() -> str:
    return str(uuid4())


class StrictEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    run_id: str
    event_type: str
    occurred_at: datetime
    producer: str
    schema_version: Literal[1] = 1


class Classification(StrEnum):
    PUBLIC = "public"
    CUSTOMER_SHAREABLE = "customer_shareable"
    INTERNAL = "internal"
    RESTRICTED = "restricted"
    SECRET = "secret"


class AnswerType(StrEnum):
    YES_WITH_EVIDENCE = "yes_with_evidence"
    NO = "no"
    PARTIALLY_IMPLEMENTED = "partially_implemented"
    CANNOT_ANSWER = "cannot_answer"
    NEEDS_REVIEW = "needs_review"


class ReviewDecision(StrEnum):
    APPROVED = "approved"
    EDITED_AND_APPROVED = "edited_and_approved"
    REJECTED = "rejected"
    NEEDS_MORE_EVIDENCE = "needs_more_evidence"
    ESCALATED = "escalated"


class QuestionnaireReceived(StrictEvent):
    event_type: Literal["questionnaire.received"] = "questionnaire.received"
    questionnaire_id: str
    title: str
    questions: list[dict]


class PreparedQuestion(StrictEvent):
    event_type: Literal["questionnaire.question_prepared"] = "questionnaire.question_prepared"
    questionnaire_id: str
    question_id: str
    question_text: str
    ordinal: int
    control_area: str
    scenario_tags: list[str] = Field(default_factory=list)
    risk_hint: str = "normal"


class EvidenceItem(StrictEvent):
    event_type: Literal["evidence.internal"] = "evidence.internal"
    evidence_id: str
    title: str
    source_type: str
    control_area: str
    classification: Classification
    allowed_for_ai: bool
    allowed_for_external_response: bool
    content: str
    safe_summary: str | None = None
    valid_from: str | None = None
    valid_until: str | None = None
    owner: str


class AiSafeEvidence(StrictEvent):
    event_type: Literal["evidence.ai_safe"] = "evidence.ai_safe"
    evidence_id: str
    question_id: str
    title: str
    control_area: str
    classification: Classification
    content: str
    source_evidence_id: str

    @field_validator("classification")
    @classmethod
    def reject_restricted_classifications(cls, value: Classification) -> Classification:
        if value in {Classification.RESTRICTED, Classification.SECRET}:
            raise ValueError("AI-safe evidence cannot be restricted or secret")
        return value


class ProposedAnswer(StrictEvent):
    event_type: Literal["answer.draft.proposed"] = "answer.draft.proposed"
    question_id: str
    control_area: str
    answer_type: AnswerType
    draft_answer: str
    evidence_ids: list[str]
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    risk_level: str
    requires_human_review: Literal[True]
    cannot_answer_reason: str | None = None

    @model_validator(mode="after")
    def require_evidence_unless_cannot_answer(self) -> ProposedAnswer:
        if self.answer_type != AnswerType.CANNOT_ANSWER and not self.evidence_ids:
            raise ValueError("evidence_ids are required unless answer_type is cannot_answer")
        return self


class AcceptedDraft(StrictEvent):
    event_type: Literal["answer.draft.accepted"] = "answer.draft.accepted"
    question_id: str
    draft_event_id: str
    evidence_ids: list[str]
    policy_result: Literal["accepted"] = "accepted"
    requires_human_review: Literal[True] = True


class RejectedDraft(StrictEvent):
    event_type: Literal["answer.draft.rejected"] = "answer.draft.rejected"
    question_id: str
    draft_event_id: str | None = None
    reason_codes: list[str]
    message: str
    evidence_ids: list[str] = Field(default_factory=list)


class ReviewedAnswer(StrictEvent):
    event_type: Literal["answer.reviewed"] = "answer.reviewed"
    question_id: str
    reviewer_id: str
    review_decision: ReviewDecision
    reviewed_answer: str
    approved_evidence_ids: list[str]
    review_notes: str | None = None


class ResponseReady(StrictEvent):
    event_type: Literal["questionnaire.response.ready"] = "questionnaire.response.ready"
    questionnaire_id: str
    reviewed_answer_ids: list[str]
    export_summary: str


class AuditEvent(StrictEvent):
    event_type: Literal["audit.timeline"] = "audit.timeline"
    source_event_id: str
    action: str
    outcome: str
    details: dict = Field(default_factory=dict)


class SecurityAlert(StrictEvent):
    event_type: Literal["security.alert"] = "security.alert"
    severity: Literal["info", "warning", "critical"]
    principal: str
    attempted_operation: str
    resource: str
    reason: str


SUBJECT_MODELS: dict[str, type[StrictEvent]] = {
    "questionnaire.received.v1-value": QuestionnaireReceived,
    "questionnaire.questions.v1-value": PreparedQuestion,
    "evidence.internal.v1-value": EvidenceItem,
    "evidence.ai_safe.v1-value": AiSafeEvidence,
    "answer.draft.proposed.v1-value": ProposedAnswer,
    "answer.draft.accepted.v1-value": AcceptedDraft,
    "answer.draft.rejected.v1-value": RejectedDraft,
    "answer.reviewed.v1-value": ReviewedAnswer,
    "questionnaire.response.ready.v1-value": ResponseReady,
    "audit.timeline.v1-value": AuditEvent,
    "security.alert.v1-value": SecurityAlert,
}

TOPICS: tuple[str, ...] = tuple(subject.removesuffix("-value") for subject in SUBJECT_MODELS)

