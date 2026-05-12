from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest
from fastapi.testclient import TestClient

from demo.api.app import app
from demo.api.inspectors import schema_lookup


client = TestClient(app)


def _schema_registry_available() -> bool:
    try:
        with urllib.request.urlopen("http://localhost:8081/subjects", timeout=2) as response:
            json.loads(response.read().decode("utf-8"))
        return True
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return False


@pytest.mark.skipif(not _schema_registry_available(), reason="Schema Registry is not running")
def test_schema_lookup_returns_avro_schema_metadata():
    response = client.get("/demo/schemas/answer.draft.proposed.v1-value")

    assert response.status_code == 200
    payload = response.json()
    assert payload["subject"] == "answer.draft.proposed.v1-value"
    assert payload["version"] == 1
    assert payload["schema_type"] == "AVRO"
    assert payload["schema"]["name"] == "ProposedAnswerValue"
    assert "ProposedAnswerValue" in payload["schema_text"]


def test_schema_lookup_rejects_unknown_subject():
    response = client.get("/demo/schemas/not-a-subject")

    assert response.status_code == 404


def test_schema_lookup_maps_registry_failure_to_503():
    with pytest.raises(ConnectionError):
        schema_lookup("answer.draft.proposed.v1-value", schema_registry_url="http://localhost:1")
