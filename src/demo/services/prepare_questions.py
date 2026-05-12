from __future__ import annotations

from datetime import UTC, datetime

from demo.contracts import PreparedQuestion, QuestionnaireReceived, make_event_id


def prepared_question_from_fixture(
    run_id: str, question: dict, ordinal: int, questionnaire_id: str = "DEMO-QUESTIONNAIRE-001"
) -> PreparedQuestion:
    return PreparedQuestion(
        event_id=make_event_id(),
        run_id=run_id,
        occurred_at=datetime.now(UTC),
        producer="svc-preparer",
        schema_version=1,
        questionnaire_id=questionnaire_id,
        question_id=question["question_id"],
        question_text=question["text"],
        ordinal=ordinal,
        control_area=question["control_area"],
        scenario_tags=[question["scenario"]],
        risk_hint=question["risk_hint"],
    )


def prepare_questions(received_event: QuestionnaireReceived) -> list[PreparedQuestion]:
    return [
        prepared_question_from_fixture(
            received_event.run_id,
            question,
            ordinal=index,
            questionnaire_id=received_event.questionnaire_id,
        )
        for index, question in enumerate(received_event.questions, start=1)
    ]

