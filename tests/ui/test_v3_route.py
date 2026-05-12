from fastapi.testclient import TestClient

from demo.api.app import app


client = TestClient(app)


def test_v3_ui_route_serves_focused_proof_harness():
    response = client.get("/v3")

    assert response.status_code == 200
    html = response.text
    assert "Focused Kafka Proof Harness" in html
    assert "Run Useful Path" in html
    assert "Approve Draft" in html
    assert "Export Response" in html
    assert "Test AI Direct Write" in html
    assert "Reset View" in html
    assert "pending" in html
    assert "branch-source" in html
    assert "guard-choice" in html
    assert "branch-terminal" in html
    assert "stage-draft_rejected" in html
    assert "Guard rejected is terminal" in html
    assert "Kafka authorization check in progress" in html
    assert "CHECKING" in html
    assert "/demo/stream/" in html
    assert "/demo/authority-boundary" in html
    assert "/demo/topics/" in html
    assert "/demo/schemas/" in html
    assert "target_topic=" in html
    assert "answer.reviewed.v1" in html
    assert "http://localhost:8080" in html


def test_v3_ui_hides_broad_scenario_catalogue():
    html = client.get("/v3").text

    for hidden_label in [
        "Prompt Injection",
        "Restricted Evidence",
        "Hallucinated Evidence",
        "Malformed Draft",
        "Unsupported Claim",
        "Export Shortcut",
    ]:
        assert hidden_label not in html


def test_v1_and_v2_remain_available_as_fallbacks():
    root = client.get("/")
    assert root.status_code == 200
    assert "Scenario Controls" in root.text

    v2 = client.get("/v2")
    assert v2.status_code == 200
    assert "Questionnaire AI Demo" in v2.text
