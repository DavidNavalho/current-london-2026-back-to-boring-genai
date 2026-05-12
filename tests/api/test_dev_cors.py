from __future__ import annotations

from fastapi.testclient import TestClient

from demo.api.app import app


client = TestClient(app)


def test_cors_headers_are_absent_by_default(monkeypatch):
    monkeypatch.delenv("DEMO_ENV", raising=False)

    response = client.get("/health", headers={"Origin": "http://localhost:5173"})

    assert "access-control-allow-origin" not in response.headers


def test_dev_environment_adds_permissive_cors_headers(monkeypatch):
    monkeypatch.setenv("DEMO_ENV", "dev")

    response = client.get("/health", headers={"Origin": "http://localhost:5173"})

    assert response.headers["access-control-allow-origin"] == "*"
    assert response.headers["access-control-allow-methods"] == "*"
    assert response.headers["access-control-allow-headers"] == "*"
