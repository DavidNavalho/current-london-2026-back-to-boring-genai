from demo.fixtures import get_question, load_evidence_library
from demo.services.evidence_gateway import make_ai_safe_evidence, select_evidence
from demo.services.prepare_questions import prepared_question_from_fixture


def test_happy_path_selects_encryption_evidence():
    question = prepared_question_from_fixture("run-evidence-test", get_question("Q-001"), 1)

    selected = select_evidence(question, load_evidence_library())

    assert {item.evidence_id for item in selected} >= {"EVID-ENC-001", "EVID-DP-001"}


def test_restricted_evidence_is_excluded_from_ai_safe_output():
    question = prepared_question_from_fixture("run-evidence-test", get_question("Q-008"), 8)
    selected = select_evidence(question, load_evidence_library())

    ai_safe = make_ai_safe_evidence(question, selected)

    assert "EVID-ADMIN-SECRET" in {item.evidence_id for item in selected}
    assert "EVID-ADMIN-SECRET" not in {item.source_evidence_id for item in ai_safe}
    assert all(item.classification.value != "restricted" for item in ai_safe)

