from datetime import UTC, datetime

import pytest

from demo.contracts import AcceptedDraft, make_event_id
from demo.services.review_export import build_response_ready, review_answer


def _accepted() -> AcceptedDraft:
    return AcceptedDraft(
        event_id=make_event_id(),
        run_id="run-review-test",
        occurred_at=datetime.now(UTC),
        producer="svc-policy-guard",
        schema_version=1,
        question_id="Q-001",
        draft_event_id="draft-1",
        evidence_ids=["EVID-ENC-001"],
    )


def test_review_answer_creates_separate_reviewed_event():
    reviewed = review_answer(_accepted(), "reviewer-demo", "approved")

    assert reviewed.event_type == "answer.reviewed"
    assert reviewed.reviewer_id == "reviewer-demo"
    assert reviewed.approved_evidence_ids == ["EVID-ENC-001"]


def test_export_requires_reviewed_answer():
    with pytest.raises(ValueError):
        build_response_ready("run-review-test", [])


def test_export_uses_reviewed_answers():
    reviewed = review_answer(_accepted(), "reviewer-demo", "approved")

    response = build_response_ready("run-review-test", [reviewed])

    assert response.event_type == "questionnaire.response.ready"
    assert response.reviewed_answer_ids == [reviewed.event_id]

