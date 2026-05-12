from __future__ import annotations

import re
from datetime import UTC, datetime

from demo.contracts import AcceptedDraft, AiSafeEvidence, ProposedAnswer, RejectedDraft, make_event_id


EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}\b")


def evaluate_draft(
    proposed_answer: ProposedAnswer,
    ai_safe_evidence: list[AiSafeEvidence],
    scenario_context: dict | None = None,
) -> AcceptedDraft | RejectedDraft:
    reason_codes: list[str] = []
    known_evidence_ids = {item.evidence_id for item in ai_safe_evidence} | {
        item.source_evidence_id for item in ai_safe_evidence
    }
    text = proposed_answer.draft_answer.lower()

    if proposed_answer.answer_type.value != "cannot_answer" and not proposed_answer.evidence_ids:
        reason_codes.append("MISSING_EVIDENCE")

    unknown = set(proposed_answer.evidence_ids) - known_evidence_ids
    if unknown:
        reason_codes.append("UNKNOWN_EVIDENCE_ID")

    if "approved" in text or "approval" in text:
        reason_codes.append("APPROVAL_ATTEMPT")
    if "submitted" in text or "submit" in text:
        reason_codes.append("EXPORT_ATTEMPT")

    if EMAIL_RE.search(proposed_answer.draft_answer):
        reason_codes.append("SENSITIVE_DATA")

    if "ignore previous" in text or "ignore all prior" in text:
        reason_codes.append("PROMPT_INJECTION")

    if proposed_answer.question_id == "Q-008" and not ai_safe_evidence:
        reason_codes.append("RESTRICTED_EVIDENCE")

    if (
        proposed_answer.control_area == "certification"
        and proposed_answer.answer_type.value == "yes_with_evidence"
        and "certified" in text
    ):
        reason_codes.append("UNSUPPORTED_CLAIM")

    if reason_codes:
        deduped = list(dict.fromkeys(reason_codes))
        return RejectedDraft(
            event_id=make_event_id(),
            run_id=proposed_answer.run_id,
            occurred_at=datetime.now(UTC),
            producer="svc-policy-guard",
            schema_version=1,
            question_id=proposed_answer.question_id,
            draft_event_id=proposed_answer.event_id,
            reason_codes=deduped,
            message="Draft failed policy guard checks.",
            evidence_ids=proposed_answer.evidence_ids,
        )

    return AcceptedDraft(
        event_id=make_event_id(),
        run_id=proposed_answer.run_id,
        occurred_at=datetime.now(UTC),
        producer="svc-policy-guard",
        schema_version=1,
        question_id=proposed_answer.question_id,
        draft_event_id=proposed_answer.event_id,
        evidence_ids=proposed_answer.evidence_ids,
    )
