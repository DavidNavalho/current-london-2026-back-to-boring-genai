from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4


MAX_RUNS = 50


@dataclass
class RunRecord:
    run_id: str
    scenario_id: str
    pacing: str
    started_at: datetime
    ended_at: datetime | None = None
    final_status: str = "allocated"
    reason_codes: list[str] = field(default_factory=list)
    denied: bool | None = None
    question_id: str | None = None
    telemetry: dict[str, int | float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        duration_ms = None
        if self.ended_at is not None:
            duration_ms = int((self.ended_at - self.started_at).total_seconds() * 1000)
        return {
            "run_id": self.run_id,
            "scenario_id": self.scenario_id,
            "pacing": self.pacing,
            "started_at": self.started_at.isoformat().replace("+00:00", "Z"),
            "ended_at": self.ended_at.isoformat().replace("+00:00", "Z") if self.ended_at else None,
            "duration_ms": duration_ms,
            "final_status": self.final_status,
            "reason_codes": self.reason_codes,
            "denied": self.denied,
            "question_id": self.question_id,
            "telemetry": self.telemetry,
        }


_RUNS: dict[str, RunRecord] = {}


def allocate_run(scenario_id: str, pacing: str) -> RunRecord:
    run_id = f"run-{scenario_id}-{uuid4()}"
    record = RunRecord(
        run_id=run_id,
        scenario_id=scenario_id,
        pacing=pacing,
        started_at=datetime.now(UTC),
    )
    _RUNS[run_id] = record
    _trim()
    return record


def mark_started(
    run_id: str,
    *,
    scenario_id: str,
    pacing: str,
    started_at: datetime | None = None,
) -> RunRecord:
    record = _RUNS.get(run_id)
    if record is None:
        record = RunRecord(
            run_id=run_id,
            scenario_id=scenario_id,
            pacing=pacing,
            started_at=started_at or datetime.now(UTC),
            final_status="running",
        )
        _RUNS[run_id] = record
    else:
        record.scenario_id = scenario_id
        record.pacing = pacing
        record.started_at = started_at or datetime.now(UTC)
        record.ended_at = None
        record.final_status = "running"
        record.reason_codes = []
        record.denied = None
    _trim()
    return record


def mark_completed(
    run_id: str,
    *,
    scenario_id: str,
    pacing: str,
    final_status: str,
    reason_codes: list[str] | None = None,
    denied: bool | None = None,
    question_id: str | None = None,
    telemetry: dict[str, int | float] | None = None,
    started_at: datetime | None = None,
) -> RunRecord:
    record = _RUNS.get(run_id)
    if record is None:
        record = RunRecord(
            run_id=run_id,
            scenario_id=scenario_id,
            pacing=pacing,
            started_at=started_at or datetime.now(UTC),
        )
        _RUNS[run_id] = record
    record.scenario_id = scenario_id
    record.pacing = pacing
    if started_at is not None:
        record.started_at = started_at
    record.ended_at = datetime.now(UTC)
    record.final_status = final_status
    record.reason_codes = reason_codes or []
    record.denied = denied
    record.question_id = question_id
    if telemetry:
        record.telemetry.update(telemetry)
    _trim()
    return record


def list_runs() -> list[dict]:
    return [
        record.to_dict()
        for record in sorted(_RUNS.values(), key=lambda item: item.started_at, reverse=True)[:MAX_RUNS]
    ]


def get_run(run_id: str) -> RunRecord | None:
    return _RUNS.get(run_id)


def reset_runs() -> int:
    count = len(_RUNS)
    _RUNS.clear()
    return count


def _trim() -> None:
    if len(_RUNS) <= MAX_RUNS:
        return
    keep = {
        record.run_id
        for record in sorted(_RUNS.values(), key=lambda item: item.started_at, reverse=True)[:MAX_RUNS]
    }
    for run_id in list(_RUNS):
        if run_id not in keep:
            del _RUNS[run_id]
