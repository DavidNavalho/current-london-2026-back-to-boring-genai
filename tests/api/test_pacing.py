from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from demo.api.app import app
from demo.api.pacing import parse_pacing


client = TestClient(app)


@pytest.mark.parametrize(
    ("value", "expected_ms"),
    [
        ("realtime", 0),
        ("demo", 600),
        ("slow", 1500),
        ("250", 250),
    ],
)
def test_pacing_presets_and_integer_values(value: str, expected_ms: int):
    pacing = parse_pacing(value)

    assert pacing.delay_ms == expected_ms


@pytest.mark.parametrize("value", ["", "warp", "-1", "5001", "1.5"])
def test_invalid_pacing_values_are_rejected(value: str):
    with pytest.raises(ValueError):
        parse_pacing(value)


def test_allocate_rejects_invalid_pacing():
    response = client.post(
        "/demo/runs/allocate",
        json={"scenario_id": "hallucinated-evidence", "pacing": "warp"},
    )

    assert response.status_code == 422


def test_run_rejects_invalid_pacing_before_launch():
    response = client.post("/demo/run/hallucinated-evidence?pacing=warp")

    assert response.status_code == 422
