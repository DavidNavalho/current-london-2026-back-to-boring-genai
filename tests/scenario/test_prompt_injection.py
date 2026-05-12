import pytest

from demo.kafka_io import consume_events
from tests.scenario.helpers import demo, runtime_available


@pytest.mark.skipif(not runtime_available(), reason="Confluent runtime is not running")
def test_prompt_injection_rejected_without_review_or_export():
    run_id = "run-prompt-injection-scenario-test"

    result = demo(["run", "prompt-injection", "--run-id", run_id])

    assert result.returncode == 0, result.stdout
    assert "PROMPT_INJECTION" in result.stdout
    assert "APPROVAL_ATTEMPT" in result.stdout

    rejected = consume_events("answer.draft.rejected.v1", run_id=run_id, timeout_seconds=10)
    assert rejected
    assert "PROMPT_INJECTION" in rejected[-1].reason_codes
    assert consume_events("answer.reviewed.v1", run_id=run_id, timeout_seconds=2) == []
    assert consume_events("questionnaire.response.ready.v1", run_id=run_id, timeout_seconds=2) == []
