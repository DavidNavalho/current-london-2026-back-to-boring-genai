from __future__ import annotations

import json
import shutil
import subprocess
import urllib.request
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def _runtime_available() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        with urllib.request.urlopen("http://localhost:8081/subjects", timeout=2) as response:
            json.loads(response.read().decode("utf-8"))
        return True
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return False


@pytest.mark.skipif(not _runtime_available(), reason="Confluent runtime is not running")
def test_confluent_runtime_health_targets():
    health = _run(["make", "runtime-health"])
    assert health.returncode == 0, health.stdout

    with urllib.request.urlopen("http://localhost:8081/subjects", timeout=5) as response:
        subjects = json.loads(response.read().decode("utf-8"))
    assert isinstance(subjects, list)

    topics = _run(["make", "bootstrap-topics"])
    assert topics.returncode == 0, topics.stdout
    assert "Topic ready:" in topics.stdout

    schemas = _run(["make", "bootstrap-schemas"])
    assert schemas.returncode == 0, schemas.stdout
    assert "Schema ready:" in schemas.stdout
