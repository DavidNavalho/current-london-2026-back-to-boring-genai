from demo.model.codex_client import _codex_response_schema
from demo.services.agentic_drafter import AgentAction


def test_codex_response_schema_requires_nullable_agent_fields_without_defaults():
    schema = _codex_response_schema(AgentAction.model_json_schema())

    assert set(schema["required"]) == set(schema["properties"])
    assert "default" not in str(schema)
