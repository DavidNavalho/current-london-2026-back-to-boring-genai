from demo.fixtures import load_questionnaire
from demo.services.ingest import build_questionnaire_received
from demo.services.prepare_questions import prepare_questions


def test_prepare_questions_preserves_question_ids_and_tags():
    received = build_questionnaire_received("run-service-test", load_questionnaire())

    prepared = prepare_questions(received)

    assert [item.question_id for item in prepared] == [f"Q-{index:03d}" for index in range(1, 11)]
    assert prepared[0].control_area == "encryption"
    assert "happy-path" in prepared[0].scenario_tags
    assert prepared[7].risk_hint == "critical"

