import pytest

from tests.scenario.helpers import codex_tests_enabled, demo, runtime_available


@pytest.mark.codex
@pytest.mark.skipif(not codex_tests_enabled(), reason="Set DEMO_RUN_CODEX_TESTS=1 to run Codex scenario suite")
@pytest.mark.skipif(not runtime_available(), reason="Confluent runtime is not running")
def test_scenario_test_command_runs_non_acl_suite():
    result = demo(["scenario", "test"])

    assert result.returncode == 0, result.stdout
    assert "happy-path: passed" in result.stdout
    assert "prompt-injection: passed" in result.stdout
    assert "export-shortcut: passed" in result.stdout
