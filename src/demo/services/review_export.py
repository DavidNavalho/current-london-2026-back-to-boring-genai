from __future__ import annotations

from datetime import UTC, datetime

from demo.contracts import AcceptedDraft, ResponseReady, ReviewedAnswer, ReviewDecision, make_event_id


def review_answer(
    accepted_draft: AcceptedDraft,
    reviewer_id: str,
    decision: str,
    edited_answer: str | None = None,
) -> ReviewedAnswer:
    review_decision = ReviewDecision(decision)
    answer = edited_answer or f"Reviewed answer for {accepted_draft.question_id}."
    return ReviewedAnswer(
        event_id=make_event_id(),
        run_id=accepted_draft.run_id,
        occurred_at=datetime.now(UTC),
        producer="svc-review-export",
        schema_version=1,
        question_id=accepted_draft.question_id,
        reviewer_id=reviewer_id,
        review_decision=review_decision,
        reviewed_answer=answer,
        approved_evidence_ids=accepted_draft.evidence_ids,
        review_notes=None,
    )


def build_response_ready(run_id: str, reviewed_answers: list[ReviewedAnswer]) -> ResponseReady:
    exportable = [
        answer
        for answer in reviewed_answers
        if answer.review_decision
        in {ReviewDecision.APPROVED, ReviewDecision.EDITED_AND_APPROVED}
    ]
    if not exportable:
        raise ValueError("At least one reviewed approved answer is required before export")

    return ResponseReady(
        event_id=make_event_id(),
        run_id=run_id,
        occurred_at=datetime.now(UTC),
        producer="svc-review-export",
        schema_version=1,
        questionnaire_id="DEMO-QUESTIONNAIRE-001",
        reviewed_answer_ids=[answer.event_id for answer in exportable],
        export_summary=f"{len(exportable)} reviewed answer(s) ready for export.",
    )

