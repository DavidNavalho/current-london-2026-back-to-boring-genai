from fastapi.testclient import TestClient

from demo.api.app import app


client = TestClient(app)


def test_demo_ui_page_loads_with_required_panels():
    response = client.get("/")

    assert response.status_code == 200
    html = response.text
    assert "Scenario Controls" in html
    assert "Workflow Board" in html
    assert "Draft and Evidence" in html
    assert "Authority Boundary" in html
    assert "Audit and Security Timeline" in html


def test_demo_ui_includes_scenario_controls():
    html = client.get("/").text

    for label in [
        "Happy Path",
        "Prompt Injection",
        "Restricted Evidence",
        "Hallucinated Evidence",
        "Malformed Draft",
        "Unsupported Claim",
        "Export Shortcut",
        "Direct AI Write",
    ]:
        assert label in html


def test_demo_ui_exposes_human_review_and_kafka_inspector():
    html = client.get("/").text

    assert "Human Review" in html
    assert "Approve Draft" in html
    assert "Export Response" in html
    assert "Open AKHQ" in html
    assert "http://localhost:8080" in html
