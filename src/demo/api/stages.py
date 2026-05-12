from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StageDefinition:
    key: str
    topic: str
    principal: str


STAGES: tuple[StageDefinition, ...] = (
    StageDefinition("received", "questionnaire.received.v1", "svc-ingest"),
    StageDefinition("prepared", "questionnaire.questions.v1", "svc-preparer"),
    StageDefinition("ai_safe_evidence", "evidence.ai_safe.v1", "svc-evidence-gateway"),
    StageDefinition("draft_proposed", "answer.draft.proposed.v1", "svc-ai-drafter"),
    StageDefinition("draft_accepted", "answer.draft.accepted.v1", "svc-policy-guard"),
    StageDefinition("draft_rejected", "answer.draft.rejected.v1", "svc-policy-guard"),
    StageDefinition("reviewed", "answer.reviewed.v1", "svc-review-export"),
    StageDefinition("response_ready", "questionnaire.response.ready.v1", "svc-review-export"),
)

STAGE_KEYS: list[str] = [stage.key for stage in STAGES]
PRINCIPAL_BY_STAGE: dict[str, str] = {stage.key: stage.principal for stage in STAGES}
