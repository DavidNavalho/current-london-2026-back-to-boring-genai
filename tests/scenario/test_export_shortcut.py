import pytest

from demo.kafka_io import consume_events
from tests.scenario.helpers import demo, runtime_available


@pytest.mark.skipif(not runtime_available(), reason="Confluent runtime is not running")
def test_export_shortcut_is_rejected_and_export_requires_review():
    run_id = "run-export-shortcut-scenario-test"

    result = demo(["run", "export-shortcut", "--run-id", run_id])

    assert result.returncode == 0, result.stdout
    assert "EXPORT_ATTEMPT" in result.stdout
    assert "review required" in result.stdout

    rejected = consume_events("answer.draft.rejected.v1", run_id=run_id, timeout_seconds=10)
    assert rejected
    assert "EXPORT_ATTEMPT" in rejected[-1].reason_codes
    assert consume_events("questionnaire.response.ready.v1", run_id=run_id, timeout_seconds=2) == []
