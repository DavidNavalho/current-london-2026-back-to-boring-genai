from __future__ import annotations

import json

import typer

from demo import __version__
from demo.config import Settings
from demo.model.codex_client import CodexCliClient, CodexExecutionError, CodexUnavailable
from demo.scenario_runner import (
    collect_audit_events,
    draft_answer_for_question,
    export_reviewed_response,
    guard_draft_for_question,
    ingest_questionnaire_event,
    prepare_questions_for_run,
    produce_ai_safe_evidence_for_question,
    render_audit_for_run,
    review_accepted_answer,
    run_ai_direct_write_attack,
    run_agent_swarm,
    run_happy_path,
    run_happy_path_until_review,
    run_export_shortcut,
    run_hallucinated_evidence,
    run_malformed_draft,
    run_non_acl_scenarios,
    run_prompt_injection,
    run_restricted_evidence,
    run_unsupported_claim,
    seed_evidence_events,
)


app = typer.Typer(help="Questionnaire AI Demo")
attack_app = typer.Typer(help="Attack demo commands")
config_app = typer.Typer(help="Configuration commands")
codex_app = typer.Typer(help="Codex model commands")
run_app = typer.Typer(help="Run demo scenarios")
scenario_app = typer.Typer(help="Scenario suite commands")
seed_app = typer.Typer(help="Seed fixture data")
ingest_app = typer.Typer(help="Ingest questionnaires")
worker_app = typer.Typer(help="Run one-shot workflow workers")
review_app = typer.Typer(help="Human review commands")
app.add_typer(attack_app, name="attack")
app.add_typer(config_app, name="config")
app.add_typer(codex_app, name="codex")
app.add_typer(run_app, name="run")
app.add_typer(scenario_app, name="scenario")
app.add_typer(seed_app, name="seed")
app.add_typer(ingest_app, name="ingest")
app.add_typer(worker_app, name="worker")
app.add_typer(review_app, name="review")


@app.command()
def version() -> None:
    """Print the demo CLI version."""
    typer.echo(__version__)


@config_app.command("show")
def config_show() -> None:
    """Print non-secret configuration values."""
    settings = Settings()
    typer.echo(json.dumps(settings.safe_dump(), indent=2, sort_keys=True))


@codex_app.command("preflight")
def codex_preflight() -> None:
    """Verify Codex CLI auth and structured output."""
    try:
        result = CodexCliClient().preflight()
    except (CodexUnavailable, CodexExecutionError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    typer.echo(f"Codex preflight passed: {result.answer_type.value}")


@seed_app.command("evidence")
def seed_evidence(run_id: str = typer.Option(..., help="Workflow run ID")) -> None:
    """Produce synthetic evidence fixture events."""
    count = seed_evidence_events(run_id)
    typer.echo(f"Seeded {count} evidence event(s) for {run_id}")


@ingest_app.command("questionnaire")
def ingest_questionnaire(run_id: str = typer.Option(..., help="Workflow run ID")) -> None:
    """Produce the questionnaire received event."""
    ingest_questionnaire_event(run_id)
    typer.echo(f"Ingested questionnaire for {run_id}")


@worker_app.command("prepare")
def worker_prepare(run_id: str = typer.Option(..., help="Workflow run ID")) -> None:
    """Prepare questions from a questionnaire received event."""
    try:
        prepared = prepare_questions_for_run(run_id)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"Prepared {len(prepared)} question event(s) for {run_id}")


@worker_app.command("evidence")
def worker_evidence(
    run_id: str = typer.Option(..., help="Workflow run ID"),
    question_id: str = typer.Option(..., help="Question ID"),
) -> None:
    """Select and redact evidence for one prepared question."""
    try:
        ai_safe = produce_ai_safe_evidence_for_question(run_id, question_id)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"Produced {len(ai_safe)} AI-safe evidence event(s) for {question_id}")


@worker_app.command("draft")
def worker_draft(
    run_id: str = typer.Option(..., help="Workflow run ID"),
    question_id: str = typer.Option(..., help="Question ID"),
) -> None:
    """Draft one answer through Codex and publish a proposed-answer event."""
    try:
        draft_answer_for_question(run_id, question_id, CodexCliClient())
    except (CodexUnavailable, CodexExecutionError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    typer.echo(f"Published draft answer for {question_id}")


@worker_app.command("guard")
def worker_guard(
    run_id: str = typer.Option(..., help="Workflow run ID"),
    question_id: str = typer.Option(..., help="Question ID"),
) -> None:
    """Apply policy guard checks to a proposed draft."""
    try:
        result = guard_draft_for_question(run_id, question_id)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if result.event_type == "answer.draft.accepted":
        typer.echo(f"Policy guard accepted {question_id}")
    else:
        typer.echo(f"Policy guard rejected {question_id}: {', '.join(result.reason_codes)}")


@review_app.command("approve")
def review_approve(
    question_id: str = typer.Argument(..., help="Question ID"),
    run_id: str = typer.Option(..., help="Workflow run ID"),
    reviewer_id: str = typer.Option("reviewer-demo", help="Reviewer ID"),
) -> None:
    """Approve an accepted draft as a human reviewer."""
    try:
        reviewed = review_accepted_answer(
            run_id,
            question_id,
            reviewer_id=reviewer_id,
            decision="approved",
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"Review approved {reviewed.question_id} by {reviewed.reviewer_id}")


@app.command("export")
def export_response(run_id: str = typer.Option(..., help="Workflow run ID")) -> None:
    """Create an export-ready response after human review."""
    try:
        response = export_reviewed_response(run_id)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    typer.echo(f"Export: questionnaire.response.ready.v1 ({response.export_summary})")


@app.command("audit")
def audit_timeline(run_id: str = typer.Option(..., help="Workflow run ID")) -> None:
    """Print a readable audit timeline."""
    typer.echo(render_audit_for_run(run_id))


@run_app.command("happy-path")
def run_happy_path_command(
    run_id: str | None = typer.Option(None, help="Workflow run ID"),
    until: str | None = typer.Option(
        None,
        help="Stop at a workflow stage. Supported value: review.",
    ),
) -> None:
    """Run the happy-path scenario, optionally pausing for human review."""
    try:
        if until == "review":
            result = run_happy_path_until_review(run_id)
            evidence_ids = ", ".join(event.evidence_id for event in result.ai_safe_evidence) or "none"
            typer.echo(f"Run: {result.run_id}")
            typer.echo(f"Q-001 prepared: {result.prepared_question.control_area}")
            typer.echo(f"Evidence safe for AI: {evidence_ids}")
            typer.echo(f"Agent tool calls: {len(result.agent_tool_calls)}")
            typer.echo(
                "Codex draft: "
                f"{result.proposed_answer.answer_type.value}, confidence {result.proposed_answer.confidence:.2f}"
            )
            typer.echo("Policy guard: accepted")
            typer.echo("Human Review: required")
            typer.echo("Export: locked until review")
            typer.echo(f"Audit: {len(result.audit_events)} events")
            return
        if until is not None:
            raise typer.BadParameter("--until supports only 'review'")
        result = run_happy_path(run_id)
    except (CodexUnavailable, CodexExecutionError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    evidence_ids = ", ".join(event.evidence_id for event in result.ai_safe_evidence) or "none"
    typer.echo(f"Run: {result.run_id}")
    typer.echo(f"Q-001 prepared: {result.prepared_question.control_area}")
    typer.echo(f"Evidence safe for AI: {evidence_ids}")
    typer.echo(f"Agent tool calls: {len(result.agent_tool_calls)}")
    typer.echo(
        "Codex draft: "
        f"{result.proposed_answer.answer_type.value}, confidence {result.proposed_answer.confidence:.2f}"
    )
    typer.echo("Policy guard: accepted, human review required")
    typer.echo(f"Review: approved by {result.reviewed_answer.reviewer_id}")
    typer.echo("Export: questionnaire.response.ready.v1")
    typer.echo(f"Audit: {len(collect_audit_events(result.run_id))} events")


@run_app.command("swarm")
def run_swarm_command(
    swarm_id: str | None = typer.Option(None, help="Swarm ID for Langfuse grouping"),
    concurrency: int | None = typer.Option(None, help="Concurrent Codex agents. Default: 2, max: 3"),
) -> None:
    """Run the agent swarm across all questionnaire questions."""
    try:
        result = run_agent_swarm(swarm_id=swarm_id, concurrency=concurrency)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"Swarm: {result.swarm_id}")
    typer.echo(f"Concurrency: {result.concurrency}")
    typer.echo(
        "Summary: "
        f"{result.accepted_count} accepted, "
        f"{result.rejected_count} rejected, "
        f"{result.failed_count} failed"
    )
    for item in result.questions:
        details = ", ".join(item.reason_codes)
        suffix = f", {details}" if details else ""
        typer.echo(
            f"{item.question_id} {item.status}, "
            f"{item.tool_call_count} tool calls"
            f"{suffix}"
        )
    typer.echo(f"Langfuse: session_id={result.swarm_id}; metadata swarm_id={result.swarm_id}")


@run_app.command("prompt-injection")
def run_prompt_injection_command(run_id: str | None = typer.Option(None, help="Workflow run ID")) -> None:
    """Run the prompt-injection rejection scenario."""
    _print_scenario_result(run_prompt_injection(run_id))


@run_app.command("restricted-evidence")
def run_restricted_evidence_command(run_id: str | None = typer.Option(None, help="Workflow run ID")) -> None:
    """Run the restricted-evidence rejection scenario."""
    _print_scenario_result(run_restricted_evidence(run_id))


@run_app.command("hallucinated-evidence")
def run_hallucinated_evidence_command(run_id: str | None = typer.Option(None, help="Workflow run ID")) -> None:
    """Run the hallucinated-evidence rejection scenario."""
    _print_scenario_result(run_hallucinated_evidence(run_id))


@run_app.command("malformed-draft")
def run_malformed_draft_command(run_id: str | None = typer.Option(None, help="Workflow run ID")) -> None:
    """Run the malformed-draft rejection scenario."""
    _print_scenario_result(run_malformed_draft(run_id))


@run_app.command("unsupported-claim")
def run_unsupported_claim_command(run_id: str | None = typer.Option(None, help="Workflow run ID")) -> None:
    """Run the unsupported-claim rejection scenario."""
    _print_scenario_result(run_unsupported_claim(run_id))


@run_app.command("export-shortcut")
def run_export_shortcut_command(run_id: str | None = typer.Option(None, help="Workflow run ID")) -> None:
    """Run the export-shortcut rejection scenario."""
    _print_scenario_result(run_export_shortcut(run_id))


@scenario_app.command("test")
def scenario_test() -> None:
    """Run the non-ACL scenario suite."""
    results = run_non_acl_scenarios()
    failed = False
    for scenario_id, passed, message in results:
        status = "passed" if passed else "failed"
        suffix = f": {message}" if message else ""
        typer.echo(f"{scenario_id}: {status}{suffix}")
        failed = failed or not passed
    if failed:
        raise typer.Exit(1)


@attack_app.command("ai-direct-write")
def attack_ai_direct_write(run_id: str | None = typer.Option(None, help="Workflow run ID")) -> None:
    """Attempt an unauthorized AI drafter write to export-ready output."""
    result = run_ai_direct_write_attack(run_id)
    typer.echo(f"Attack: svc-ai-drafter -> {result.target_topic}")
    typer.echo(f"Result: {'DENIED' if result.denied else 'ALLOWED'}")
    typer.echo(f"Reason: {result.reason}")
    typer.echo("Audit: no export-ready event created" if result.denied else "Audit: unexpected write")


def _print_scenario_result(result) -> None:
    reason_codes = ", ".join(result.reason_codes) or "none"
    typer.echo(f"Run: {result.run_id}")
    typer.echo(f"Scenario: {result.scenario_id}")
    typer.echo(f"Question: {result.question_id}")
    typer.echo(f"Status: {result.status}")
    typer.echo(f"Reason codes: {reason_codes}")
    if result.message:
        typer.echo(result.message)
    typer.echo(f"Audit: {len(result.audit_events)} events")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
