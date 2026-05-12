from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest
from fastapi.testclient import TestClient

from demo.api import health as health_module
from demo.api.app import app


client = TestClient(app)


def _runtime_available() -> bool:
    try:
        with urllib.request.urlopen("http://localhost:8081/subjects", timeout=2) as response:
            json.loads(response.read().decode("utf-8"))
        return True
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return False


@pytest.mark.skipif(not _runtime_available(), reason="Confluent runtime is not running")
def test_connection_health_returns_200_when_dependencies_are_up():
    response = client.get("/health/connection")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] in {True, False}
    assert payload["dependencies"]["kafka"]["ok"] is True
    assert payload["dependencies"]["schema_registry"]["ok"] is True
    assert "codex" in payload["dependencies"]


def test_connection_health_reports_dependency_failure_without_500(monkeypatch):
    def fail_kafka():
        raise RuntimeError("metadata probe failed")

    monkeypatch.setattr(health_module, "_probe_kafka", fail_kafka)

    response = client.get("/health/connection")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["dependencies"]["kafka"]["ok"] is False
    assert "metadata probe failed" in payload["dependencies"]["kafka"]["detail"]


def test_codex_preflight_result_is_cached(monkeypatch):
    health_module.reset_codex_cache()
    calls = {"count": 0}

    def fake_preflight():
        calls["count"] += 1
        return {"ok": True, "detail": "cached test"}

    monkeypatch.setattr(health_module, "_run_codex_preflight", fake_preflight)

    first = health_module.connection_health()
    second = health_module.connection_health()

    assert first["dependencies"]["codex"]["ok"] is True
    assert second["dependencies"]["codex"]["ok"] is True
    assert calls["count"] == 1
