from __future__ import annotations

import sys
from types import SimpleNamespace

from demo.observability import LangfuseAgentTrace


def test_langfuse_trace_propagates_session_id(monkeypatch):
    calls = {"root_kwargs": None, "session_id": None, "entered": [], "exited": []}

    class FakeRoot:
        def update(self, **_fields):
            return None

    class FakeContext:
        def __init__(self, name):
            self.name = name

        def __enter__(self):
            calls["entered"].append(self.name)
            return FakeRoot()

        def __exit__(self, *_exc_info):
            calls["exited"].append(self.name)
            return None

    class FakeClient:
        def create_trace_id(self, seed):
            return f"trace-{seed}"

        def start_as_current_observation(self, **kwargs):
            calls["root_kwargs"] = kwargs
            return FakeContext("root")

        def get_current_trace_id(self):
            return "trace-run-visible-q1"

        def get_trace_url(self, *, trace_id):
            return f"http://localhost:3000/project/demo/traces/{trace_id}"

        def flush(self):
            calls["flushed"] = True

    def fake_propagate_attributes(**kwargs):
        calls["session_id"] = kwargs["session_id"]
        return FakeContext("attributes")

    fake_langfuse = SimpleNamespace(
        get_client=lambda: FakeClient(),
        propagate_attributes=fake_propagate_attributes,
    )
    monkeypatch.setitem(sys.modules, "langfuse", fake_langfuse)

    with LangfuseAgentTrace(
        run_id="run-visible-q1",
        scenario_id="happy-path",
        question_id="Q-001",
        session_id="run-visible-q1",
    ) as trace:
        assert trace.enabled is True

    assert calls["session_id"] == "run-visible-q1"
    assert calls["root_kwargs"]["trace_context"] == {"trace_id": "trace-run-visible-q1"}
    assert calls["entered"] == ["root", "attributes"]
    assert calls["exited"] == ["attributes", "root"]
    assert calls["flushed"] is True
