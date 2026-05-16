from __future__ import annotations

from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from demo.fixtures import load_questionnaire


DEFAULT_SWARM_CONCURRENCY = 2
MAX_SWARM_CONCURRENCY = 3

SwarmQuestionStatus = Literal["accepted", "rejected", "failed"]


@dataclass(frozen=True)
class SwarmChildPlan:
    swarm_id: str
    run_id: str
    question_id: str


@dataclass(frozen=True)
class SwarmPlan:
    swarm_id: str
    children: tuple[SwarmChildPlan, ...]

    @property
    def question_ids(self) -> list[str]:
        return [child.question_id for child in self.children]


@dataclass(frozen=True)
class SwarmQuestionResult:
    swarm_id: str
    run_id: str
    question_id: str
    status: SwarmQuestionStatus
    reason_codes: list[str] = field(default_factory=list)
    answer_type: str | None = None
    tool_call_count: int = 0
    trace_url: str | None = None
    message: str = ""

    def to_dict(self) -> dict:
        return {
            "swarm_id": self.swarm_id,
            "run_id": self.run_id,
            "question_id": self.question_id,
            "status": self.status,
            "reason_codes": self.reason_codes,
            "answer_type": self.answer_type,
            "tool_call_count": self.tool_call_count,
            "trace_url": self.trace_url,
            "message": self.message,
        }


@dataclass(frozen=True)
class SwarmRunResult:
    swarm_id: str
    concurrency: int
    questions: tuple[SwarmQuestionResult, ...]
    started_at: datetime
    ended_at: datetime

    @property
    def total_count(self) -> int:
        return len(self.questions)

    @property
    def accepted_count(self) -> int:
        return sum(1 for item in self.questions if item.status == "accepted")

    @property
    def rejected_count(self) -> int:
        return sum(1 for item in self.questions if item.status == "rejected")

    @property
    def failed_count(self) -> int:
        return sum(1 for item in self.questions if item.status == "failed")

    @property
    def completed_count(self) -> int:
        return self.accepted_count + self.rejected_count + self.failed_count

    @property
    def duration_ms(self) -> int:
        return int((self.ended_at - self.started_at).total_seconds() * 1000)

    def to_dict(self) -> dict:
        return {
            "swarm_id": self.swarm_id,
            "concurrency": self.concurrency,
            "started_at": self.started_at.isoformat().replace("+00:00", "Z"),
            "ended_at": self.ended_at.isoformat().replace("+00:00", "Z"),
            "duration_ms": self.duration_ms,
            "total_count": self.total_count,
            "completed_count": self.completed_count,
            "accepted_count": self.accepted_count,
            "rejected_count": self.rejected_count,
            "failed_count": self.failed_count,
            "questions": [item.to_dict() for item in self.questions],
        }


SwarmWorker = Callable[[SwarmChildPlan], SwarmQuestionResult]


def new_swarm_id() -> str:
    return f"swarm-{uuid4().hex[:8]}"


def build_swarm_plan(
    *,
    swarm_id: str | None = None,
    question_ids: Sequence[str] | None = None,
) -> SwarmPlan:
    resolved_swarm_id = swarm_id or new_swarm_id()
    resolved_question_ids = tuple(question_ids or _fixture_question_ids())
    children = tuple(
        SwarmChildPlan(
            swarm_id=resolved_swarm_id,
            run_id=f"{resolved_swarm_id}-{question_id}",
            question_id=question_id,
        )
        for question_id in resolved_question_ids
    )
    return SwarmPlan(swarm_id=resolved_swarm_id, children=children)


def validate_swarm_concurrency(value: int | None) -> int:
    if value is None:
        return DEFAULT_SWARM_CONCURRENCY
    if value < 1 or value > MAX_SWARM_CONCURRENCY:
        raise ValueError(f"swarm concurrency must be between 1 and {MAX_SWARM_CONCURRENCY}")
    return value


def run_swarm(
    plan: SwarmPlan,
    *,
    concurrency: int | None,
    worker: SwarmWorker,
) -> SwarmRunResult:
    resolved_concurrency = validate_swarm_concurrency(concurrency)
    started_at = datetime.now(UTC)
    by_index: dict[int, SwarmQuestionResult] = {}

    with ThreadPoolExecutor(max_workers=resolved_concurrency) as executor:
        futures = {
            executor.submit(_run_child, child, worker): index
            for index, child in enumerate(plan.children)
        }
        for future in as_completed(futures):
            by_index[futures[future]] = future.result()

    questions = tuple(by_index[index] for index in range(len(plan.children)))
    return SwarmRunResult(
        swarm_id=plan.swarm_id,
        concurrency=resolved_concurrency,
        questions=questions,
        started_at=started_at,
        ended_at=datetime.now(UTC),
    )


def _run_child(child: SwarmChildPlan, worker: SwarmWorker) -> SwarmQuestionResult:
    try:
        return worker(child)
    except Exception as exc:
        return SwarmQuestionResult(
            swarm_id=child.swarm_id,
            run_id=child.run_id,
            question_id=child.question_id,
            status="failed",
            message=str(exc),
        )


def _fixture_question_ids() -> list[str]:
    return [question["question_id"] for question in load_questionnaire()["questions"]]

