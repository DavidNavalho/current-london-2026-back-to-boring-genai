from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any


class NoopObservation:
    def update(self, **_fields: Any) -> None:
        return None


class NoopAgentTrace:
    enabled = False
    trace_url: str | None = None

    def __enter__(self) -> NoopAgentTrace:
        return self

    def __exit__(self, *_exc_info) -> None:
        return None

    @contextmanager
    def generation(self, *_args, **_kwargs):
        yield NoopObservation()

    @contextmanager
    def tool(self, *_args, **_kwargs):
        yield NoopObservation()

    def update_output(self, **_fields: Any) -> None:
        return None


class LangfuseAgentTrace:
    def __init__(
        self,
        *,
        run_id: str,
        scenario_id: str,
        question_id: str | None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.enabled = True
        self.run_id = run_id
        self.scenario_id = scenario_id
        self.question_id = question_id
        self.metadata = metadata or {}
        self.trace_url: str | None = None
        self._client = None
        self._root_cm = None
        self._root = None

    def __enter__(self):
        try:
            from langfuse import get_client

            self._client = get_client()
            trace_context = {}
            if hasattr(self._client, "create_trace_id"):
                trace_context["trace_id"] = self._client.create_trace_id(seed=self.run_id)
            kwargs = {
                "as_type": "span",
                "name": "questionnaire-agent-loop",
                "input": {
                    "run_id": self.run_id,
                    "scenario_id": self.scenario_id,
                    "question_id": self.question_id,
                },
                "metadata": self.metadata,
            }
            if trace_context:
                kwargs["trace_context"] = trace_context
            self._root_cm = self._client.start_as_current_observation(**kwargs)
            self._root = self._root_cm.__enter__()
            self.trace_url = self._client.get_trace_url(
                trace_id=self._client.get_current_trace_id()
            )
        except Exception:
            self.enabled = False
            self._client = None
            self._root_cm = None
            self._root = None
            self.trace_url = None
        return self

    def __exit__(self, *exc_info) -> None:
        try:
            if self._root_cm is not None:
                self._root_cm.__exit__(*exc_info)
            if self._client is not None and hasattr(self._client, "flush"):
                self._client.flush()
        except Exception:
            return None

    @contextmanager
    def generation(self, *, turn: int, prompt: str):
        if self._client is None:
            yield NoopObservation()
            return
        try:
            with self._client.start_as_current_observation(
                as_type="generation",
                name=f"codex-agent-turn-{turn}",
                input={"prompt": prompt},
            ) as observation:
                yield observation
        except Exception:
            yield NoopObservation()

    @contextmanager
    def tool(self, *, name: str, input_payload: dict):
        if self._client is None:
            yield NoopObservation()
            return
        try:
            with self._client.start_as_current_observation(
                as_type="span",
                name=name,
                input=input_payload,
            ) as observation:
                yield observation
        except Exception:
            yield NoopObservation()

    def update_output(self, **fields: Any) -> None:
        try:
            if self._root is not None:
                self._root.update(output=fields)
        except Exception:
            return None


def make_agent_trace(
    *,
    run_id: str,
    scenario_id: str,
    question_id: str | None,
    metadata: dict[str, Any] | None = None,
) -> NoopAgentTrace | LangfuseAgentTrace:
    if not _langfuse_configured():
        return NoopAgentTrace()
    try:
        import langfuse  # noqa: F401
    except ImportError:
        return NoopAgentTrace()
    return LangfuseAgentTrace(
        run_id=run_id,
        scenario_id=scenario_id,
        question_id=question_id,
        metadata=metadata,
    )


def _langfuse_configured() -> bool:
    return bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))
