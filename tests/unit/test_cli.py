from datetime import UTC, datetime

from typer.testing import CliRunner

import demo.cli as cli_module
from demo.cli import app
from demo.services.agent_swarm import SwarmQuestionResult, SwarmRunResult


runner = CliRunner()


def test_cli_help_exits_successfully():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Questionnaire AI Demo" in result.output


def test_version_prints_non_empty_version():
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert result.output.strip()


def test_unknown_command_exits_non_zero():
    result = runner.invoke(app, ["not-a-command"])

    assert result.exit_code != 0


def test_happy_path_command_documents_review_pause():
    result = runner.invoke(app, ["run", "happy-path", "--help"])

    assert result.exit_code == 0
    assert "--until" in result.output
    assert "review" in result.output


def test_swarm_command_prints_grouped_summary(monkeypatch):
    now = datetime.now(UTC)
    swarm_result = SwarmRunResult(
        swarm_id="swarm-demo",
        concurrency=2,
        questions=(
            SwarmQuestionResult(
                swarm_id="swarm-demo",
                run_id="swarm-demo-Q-001",
                question_id="Q-001",
                status="accepted",
                answer_type="yes_with_evidence",
                tool_call_count=2,
                trace_url="http://localhost:3000/project/demo/traces/q1",
            ),
            SwarmQuestionResult(
                swarm_id="swarm-demo",
                run_id="swarm-demo-Q-008",
                question_id="Q-008",
                status="rejected",
                reason_codes=["RESTRICTED_EVIDENCE"],
                answer_type="cannot_answer",
                tool_call_count=2,
            ),
        ),
        started_at=now,
        ended_at=now,
    )
    monkeypatch.setattr(cli_module, "run_agent_swarm", lambda **_kwargs: swarm_result)

    result = runner.invoke(app, ["run", "swarm", "--concurrency", "2"])

    assert result.exit_code == 0
    assert "Swarm: swarm-demo" in result.output
    assert "Concurrency: 2" in result.output
    assert "Q-001 accepted, 2 tool calls" in result.output
    assert "Q-008 rejected, 2 tool calls, RESTRICTED_EVIDENCE" in result.output
    assert "Langfuse: session_id=swarm-demo; metadata swarm_id=swarm-demo" in result.output
