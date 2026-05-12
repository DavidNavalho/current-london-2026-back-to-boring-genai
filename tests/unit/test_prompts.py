from demo.fixtures import get_question, load_evidence_library
from demo.model.prompts import build_draft_prompt
from demo.services.evidence_gateway import make_ai_safe_evidence, select_evidence
from demo.services.prepare_questions import prepared_question_from_fixture


def _prompt_for(question_id: str) -> str:
    question = prepared_question_from_fixture("run-prompt-test", get_question(question_id), 1)
    selected = select_evidence(question, load_evidence_library())
    ai_safe = make_ai_safe_evidence(question, selected)
    return build_draft_prompt(question, ai_safe)


def test_prompt_for_happy_path_includes_expected_evidence():
    prompt = _prompt_for("Q-001")

    assert "Q-001" in prompt
    assert "EVID-ENC-001" in prompt
    assert "Customer data is encrypted at rest and in transit." in prompt


def test_prompt_excludes_restricted_admin_values():
    prompt = _prompt_for("Q-008")

    assert "EVID-ADMIN-SECRET" not in prompt
    assert "alex.admin@example.test" not in prompt
    assert "riley.root@example.test" not in prompt
    assert "Alex Admin" not in prompt
    assert "Riley Root" not in prompt


def test_prompt_names_allowed_evidence_only():
    prompt = _prompt_for("Q-004")

    assert "EVID-IAM-001" in prompt
    assert "EVID-ADMIN-SECRET" not in prompt


def test_prompt_requires_review_and_fallback_answer_types():
    prompt = _prompt_for("Q-001")

    assert "requires_human_review must be true" in prompt
    assert "cannot_answer" in prompt
    assert "needs_review" in prompt
    assert "Do not approve" in prompt
    assert "Do not export" in prompt
    assert "Do not submit" in prompt
