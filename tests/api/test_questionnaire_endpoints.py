from __future__ import annotations

from fastapi.testclient import TestClient

from demo.api.app import app


client = TestClient(app)


def test_questionnaire_endpoint_returns_fixture_questions_with_scenarios():
    response = client.get("/demo/questionnaire")

    assert response.status_code == 200
    payload = response.json()
    assert payload["questionnaire_id"] == "DEMO-QUESTIONNAIRE-001"
    assert payload["title"] == "Security Questionnaire"
    assert len(payload["questions"]) >= 10
    q001 = next(question for question in payload["questions"] if question["question_id"] == "Q-001")
    assert q001["scenario"] == "happy-path"
    assert q001["control_area"] == "encryption"
    assert q001["risk_hint"] == "low"


def test_question_endpoint_returns_ai_safe_evidence_for_question():
    response = client.get("/demo/question/Q-001")

    assert response.status_code == 200
    payload = response.json()
    assert payload["question_id"] == "Q-001"
    assert payload["scenario"] == "happy-path"
    evidence_ids = {item["evidence_id"] for item in payload["ai_safe_evidence"]}
    assert "EVID-ENC-001" in evidence_ids
    assert all("safe_summary" in item for item in payload["ai_safe_evidence"])


def test_question_endpoint_redacts_withheld_evidence():
    response = client.get("/demo/question/Q-008")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ai_safe_evidence"] == []
    assert payload["withheld_evidence"]
    for item in payload["withheld_evidence"]:
        assert item["classification"] == "restricted"
        assert item["redaction_label"] == "withheld - restricted"
        assert "content" not in item
        assert "safe_summary" not in item


def test_question_endpoint_returns_404_for_unknown_question():
    response = client.get("/demo/question/Q-DOES-NOT-EXIST")

    assert response.status_code == 404
