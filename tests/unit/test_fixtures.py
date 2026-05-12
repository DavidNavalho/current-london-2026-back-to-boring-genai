from __future__ import annotations

from demo.fixtures import (
    get_evidence,
    get_question,
    get_scenario,
    load_evidence_library,
    load_questionnaire,
    load_scenarios,
    validate_fixture_consistency,
)


def test_fixture_files_parse_and_validate_consistency():
    validate_fixture_consistency()


def test_question_ids_are_unique_and_stable():
    questionnaire = load_questionnaire()
    question_ids = [item["question_id"] for item in questionnaire["questions"]]

    assert question_ids == [f"Q-{index:03d}" for index in range(1, 11)]
    assert len(question_ids) == len(set(question_ids))


def test_evidence_ids_are_unique_and_stable():
    evidence = load_evidence_library()
    evidence_ids = [item["evidence_id"] for item in evidence["evidence"]]

    assert "EVID-ENC-001" in evidence_ids
    assert "EVID-ADMIN-SECRET" in evidence_ids
    assert len(evidence_ids) == len(set(evidence_ids))


def test_restricted_evidence_is_not_ai_allowed():
    item = get_evidence("EVID-ADMIN-SECRET")

    assert item["classification"] == "restricted"
    assert item["allowed_for_ai"] is False
    assert item["allowed_for_external_response"] is False


def test_customer_shareable_evidence_can_be_external():
    item = get_evidence("EVID-ENC-001")

    assert item["classification"] == "customer_shareable"
    assert item["allowed_for_external_response"] is True


def test_soc2_readiness_fixture_explicitly_not_certified():
    item = get_evidence("EVID-SOC2-001")
    content = (item["content"] + " " + (item["safe_summary"] or "")).lower()

    assert "not certified" in content
    assert "readiness" in content


def test_malicious_evidence_is_instruction_like_but_not_shareable():
    item = get_evidence("EVID-MAL-001")

    assert "ignore" in item["content"].lower()
    assert item["classification"] == "internal"
    assert item["allowed_for_external_response"] is False


def test_scenarios_reference_known_questions():
    questions = {item["question_id"] for item in load_questionnaire()["questions"]}
    scenarios = load_scenarios()["scenarios"]

    for scenario in scenarios:
        assert set(scenario["question_ids"]).issubset(questions)


def test_lookup_helpers_return_expected_items():
    assert get_question("Q-001")["scenario"] == "happy-path"
    assert get_scenario("restricted-evidence")["expected_reason_codes"]

