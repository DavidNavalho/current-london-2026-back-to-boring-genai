from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from demo.api.app import app


client = TestClient(app)
ROOT = Path(__file__).resolve().parents[2]


def test_v2_ui_route_serves_v2_shell():
    if not (ROOT / "web" / "v2" / "index.html").exists():
        pytest.skip("UI v2 shell has not been generated yet")

    response = client.get("/v2")

    assert response.status_code == 200
    html = response.text
    assert "Questionnaire AI Demo" in html
    assert "/demo/stream/" in html
    assert "/health/connection" in html
