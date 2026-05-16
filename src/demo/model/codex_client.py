from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel
from pydantic import ValidationError

from demo.services.agentic_drafter import AgentAction
from demo.services.ai_drafter import DraftModelOutput


StructuredOutput = TypeVar("StructuredOutput", bound=BaseModel)


class CodexUnavailable(RuntimeError):
    """Raised when Codex CLI is not installed or not authenticated."""


class CodexExecutionError(RuntimeError):
    """Raised when Codex CLI fails to produce valid structured output."""


@dataclass
class CodexCliClient:
    command: str = "codex"
    model: str | None = None
    timeout_seconds: int = 180
    workspace: Path | None = None

    def preflight(self) -> DraftModelOutput:
        self._assert_available_and_authenticated()
        output = self.generate(
            "\n".join(
                [
                    "Return a minimal questionnaire draft object for a preflight check.",
                    "Use answer_type yes_with_evidence, evidence_ids [\"EVID-PREFLIGHT-001\"],",
                    "requires_human_review true, and a short draft answer.",
                ]
            )
        )
        if not isinstance(output, DraftModelOutput):
            return DraftModelOutput.model_validate(output)
        return output

    def generate(self, prompt: str) -> DraftModelOutput:
        return self.generate_structured(prompt, DraftModelOutput)

    def generate_action(self, prompt: str) -> AgentAction:
        return self.generate_structured(prompt, AgentAction)

    def generate_structured(
        self,
        prompt: str,
        output_model: type[StructuredOutput],
    ) -> StructuredOutput:
        self._assert_available_and_authenticated()
        with tempfile.TemporaryDirectory(prefix="questionnaire-codex-") as tmpdir:
            tmp_path = Path(tmpdir)
            schema_path = tmp_path / "draft-output.schema.json"
            output_path = tmp_path / "last-message.json"
            schema_path.write_text(
                json.dumps(
                    _codex_response_schema(output_model.model_json_schema()),
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            cmd = [
                self._resolved_command(),
                "exec",
                "--skip-git-repo-check",
                "--ephemeral",
                "--sandbox",
                "read-only",
                "--output-schema",
                str(schema_path),
                "--output-last-message",
                str(output_path),
                "--color",
                "never",
                "-C",
                str(self.workspace or Path.cwd()),
            ]
            if self.model:
                cmd.extend(["--model", self.model])
            cmd.append("-")

            result = subprocess.run(
                cmd,
                input=prompt,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=self.timeout_seconds,
                check=False,
            )
            if result.returncode != 0:
                raise CodexExecutionError(_format_failure("Codex execution failed", result.stdout))

            raw_response = output_path.read_text(encoding="utf-8") if output_path.exists() else result.stdout
            try:
                payload = _parse_json_object(raw_response)
                return output_model.model_validate(payload)
            except (json.JSONDecodeError, ValidationError, ValueError) as exc:
                raise CodexExecutionError(
                    _format_failure(f"Codex returned invalid structured output: {exc}", raw_response)
                ) from exc

    def _assert_available_and_authenticated(self) -> None:
        if not self._resolved_command():
            raise CodexUnavailable("Codex CLI is not installed. Install Codex and run `codex login`.")

        result = subprocess.run(
            [self._resolved_command(), "login", "status"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=15,
            check=False,
        )
        if result.returncode != 0:
            raise CodexUnavailable(
                _format_failure(
                    "Codex CLI is not authenticated. Run `codex login` and choose ChatGPT login.",
                    result.stdout,
                )
            )

    def _resolved_command(self) -> str:
        return shutil.which(self.command) or ""


def _parse_json_object(raw: str) -> dict:
    stripped = raw.strip()
    if not stripped:
        raise ValueError("empty response")
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        stripped = "\n".join(line for line in lines if not line.startswith("```")).strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(stripped[start : end + 1])


def _codex_response_schema(schema: dict) -> dict:
    normalized = deepcopy(schema)
    _normalize_object_schema(normalized)
    return normalized


def _normalize_object_schema(node) -> None:
    if isinstance(node, dict):
        node.pop("default", None)
        properties = node.get("properties")
        if isinstance(properties, dict):
            node["required"] = list(properties)
        for value in node.values():
            _normalize_object_schema(value)
    elif isinstance(node, list):
        for item in node:
            _normalize_object_schema(item)


def _format_failure(message: str, output: str) -> str:
    excerpt = output.strip()
    if len(excerpt) > 2000:
        excerpt = excerpt[:2000] + "\n..."
    return f"{message}\n{excerpt}" if excerpt else message
