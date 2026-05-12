from demo.fixtures import load_evidence_library, load_questionnaire
from demo.services.evidence_gateway import make_ai_safe_evidence, select_evidence
from demo.services.ingest import build_questionnaire_received
from demo.services.prepare_questions import prepare_questions


def test_received_to_prepared_to_ai_safe_evidence_transform():
    received = build_questionnaire_received("run-transform-test", load_questionnaire())
    prepared = prepare_questions(received)
    q1 = next(item for item in prepared if item.question_id == "Q-001")

    selected = select_evidence(q1, load_evidence_library())
    ai_safe = make_ai_safe_evidence(q1, selected)

    assert received.event_type == "questionnaire.received"
    assert q1.event_type == "questionnaire.question_prepared"
    assert ai_safe
    assert all(item.event_type == "evidence.ai_safe" for item in ai_safe)

