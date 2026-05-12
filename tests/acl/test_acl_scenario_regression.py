from __future__ import annotations

import json
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from demo.config import Settings
from demo.kafka_io import consume_events


ROOT = Path(__file__).resolve().parents[2]


def _runtime_available() -> bool:
    try:
        with urllib.request.urlopen("http://localhost:8081/subjects", timeout=2) as response:
            json.loads(response.read().decode("utf-8"))
        return True
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return False


def _acl_mode() -> bool:
    return Settings().kafka_security_protocol.startswith("SASL")


def _demo(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(ROOT / ".venv" / "bin" / "demo"), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


pytestmark = [
    pytest.mark.skipif(not _runtime_available(), reason="Confluent runtime is not running"),
    pytest.mark.skipif(not _acl_mode(), reason="Kafka ACL mode is not enabled"),
]


def test_acl_mode_still_allows_policy_rejection_scenario():
    run_id = "run-acl-regression-hallucinated"

    result = _demo(["run", "hallucinated-evidence", "--run-id", run_id])

    assert result.returncode == 0, result.stdout
    assert "UNKNOWN_EVIDENCE_ID" in result.stdout


def test_direct_ai_write_attack_is_denied_and_visible():
    run_id = "run-acl-direct-write"

    result = _demo(["attack", "ai-direct-write", "--run-id", run_id])

    assert result.returncode == 0, result.stdout
    assert "Result: DENIED" in result.stdout
    assert "questionnaire.response.ready.v1" in result.stdout
    assert consume_events(
        "questionnaire.response.ready.v1",
        run_id=run_id,
        timeout_seconds=2,
        principal="svc-review-export",
    ) == []
    alerts = consume_events(
        "security.alert.v1",
        run_id=run_id,
        timeout_seconds=10,
        principal="svc-audit-viewer",
    )
    assert alerts
    assert alerts[-1].reason == "ACL_DENIED"
