from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from demo.kafka_io import consume_events


ROOT = Path(__file__).resolve().parents[2]


def _codex_tests_enabled() -> bool:
    return os.getenv("DEMO_RUN_CODEX_TESTS") == "1"


def _runtime_available() -> bool:
    try:
        with urllib.request.urlopen("http://localhost:8081/subjects", timeout=2) as response:
            json.loads(response.read().decode("utf-8"))
        return True
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return False


def _demo(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(ROOT / ".venv" / "bin" / "demo"), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


@pytest.mark.codex
@pytest.mark.skipif(not _codex_tests_enabled(), reason="Set DEMO_RUN_CODEX_TESTS=1 to run Codex scenario tests")
@pytest.mark.skipif(not _runtime_available(), reason="Confluent runtime is not running")
def test_happy_path_scenario_command_runs_to_export():
    run_id = "run-happy-path-scenario-test"

    result = _demo(["run", "happy-path", "--run-id", run_id])

    assert result.returncode == 0, result.stdout
    assert f"Run: {run_id}" in result.stdout
    assert "Codex draft:" in result.stdout
    assert "Policy guard: accepted" in result.stdout
    assert "Export: questionnaire.response.ready.v1" in result.stdout

    assert consume_events("answer.draft.proposed.v1", run_id=run_id, timeout_seconds=15)
    assert consume_events("answer.draft.accepted.v1", run_id=run_id, timeout_seconds=15)
    assert consume_events("answer.reviewed.v1", run_id=run_id, timeout_seconds=15)
    assert consume_events("questionnaire.response.ready.v1", run_id=run_id, timeout_seconds=15)

    rejected = consume_events("answer.draft.rejected.v1", run_id=run_id, timeout_seconds=2)
    alerts = consume_events("security.alert.v1", run_id=run_id, timeout_seconds=2)
    assert rejected == []
    assert alerts == []
