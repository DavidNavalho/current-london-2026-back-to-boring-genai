from __future__ import annotations

import json
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from demo.contracts import SUBJECT_MODELS


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


def _schema_registry_available() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        with urllib.request.urlopen("http://localhost:8081/subjects", timeout=2) as response:
            json.loads(response.read().decode("utf-8"))
        return True
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return False


@pytest.mark.skipif(not _schema_registry_available(), reason="Schema Registry is not running")
def test_schema_registry_bootstrap_registers_subjects():
    result = _run(["make", "bootstrap-schemas"])

    assert result.returncode == 0, result.stdout

    with urllib.request.urlopen("http://localhost:8081/subjects", timeout=5) as response:
        subjects = set(json.loads(response.read().decode("utf-8")))

    assert set(SUBJECT_MODELS).issubset(subjects)

    for subject in SUBJECT_MODELS:
        with urllib.request.urlopen(
            f"http://localhost:8081/subjects/{subject}/versions/latest", timeout=5
        ) as response:
            metadata = json.loads(response.read().decode("utf-8"))
        assert metadata["schemaType"] == "AVRO"
