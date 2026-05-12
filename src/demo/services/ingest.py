from __future__ import annotations

from datetime import UTC, datetime

from demo.contracts import QuestionnaireReceived, make_event_id


def build_questionnaire_received(
    run_id: str, questionnaire_fixture: dict
) -> QuestionnaireReceived:
    return QuestionnaireReceived(
        event_id=make_event_id(),
        run_id=run_id,
        occurred_at=datetime.now(UTC),
        producer="svc-ingest",
        schema_version=1,
        questionnaire_id=questionnaire_fixture["questionnaire_id"],
        title=questionnaire_fixture["title"],
        questions=questionnaire_fixture["questions"],
    )

