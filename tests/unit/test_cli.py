from typer.testing import CliRunner

from demo.cli import app


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
