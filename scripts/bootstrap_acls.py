from __future__ import annotations

import subprocess


SERVICE_ACLS = {
    "svc-ingest": {
        "read": [],
        "write": ["questionnaire.received.v1", "audit.timeline.v1"],
    },
    "svc-preparer": {
        "read": ["questionnaire.received.v1"],
        "write": ["questionnaire.questions.v1", "audit.timeline.v1"],
    },
    "svc-evidence-gateway": {
        "read": ["questionnaire.questions.v1", "evidence.internal.v1"],
        "write": ["evidence.internal.v1", "evidence.ai_safe.v1", "audit.timeline.v1"],
    },
    "svc-ai-drafter": {
        "read": ["questionnaire.questions.v1", "evidence.ai_safe.v1"],
        "write": ["answer.draft.proposed.v1", "audit.timeline.v1"],
    },
    "svc-policy-guard": {
        "read": ["answer.draft.proposed.v1", "evidence.ai_safe.v1", "answer.draft.rejected.v1"],
        "write": [
            "answer.draft.accepted.v1",
            "answer.draft.rejected.v1",
            "security.alert.v1",
            "audit.timeline.v1",
        ],
    },
    "svc-review-export": {
        "read": [
            "answer.draft.accepted.v1",
            "answer.reviewed.v1",
            "questionnaire.response.ready.v1",
        ],
        "write": ["answer.reviewed.v1", "questionnaire.response.ready.v1", "audit.timeline.v1"],
    },
    "svc-audit-viewer": {
        "read": ["audit.timeline.v1", "security.alert.v1"],
        "write": [],
    },
}


def main() -> int:
    for principal, grants in SERVICE_ACLS.items():
        for topic in grants["read"]:
            for operation in ("Read", "Describe"):
                code = _add_topic_acl(principal, operation, topic)
                if code:
                    return code
        for topic in grants["write"]:
            for operation in ("Write", "Describe"):
                code = _add_topic_acl(principal, operation, topic)
                if code:
                    return code
        if grants["read"]:
            code = _add_group_acl(principal)
            if code:
                return code
    print("ACLs ready")
    return 0


def _add_topic_acl(principal: str, operation: str, topic: str) -> int:
    return _run_acl(
        [
            "--add",
            "--allow-principal",
            f"User:{principal}",
            "--operation",
            operation,
            "--topic",
            topic,
        ]
    )


def _add_group_acl(principal: str) -> int:
    return _run_acl(
        [
            "--add",
            "--allow-principal",
            f"User:{principal}",
            "--operation",
            "Read",
            "--group",
            "*",
        ]
    )


def _run_acl(args: list[str]) -> int:
    result = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "broker",
            "kafka-acls",
            "--bootstrap-server",
            "broker:29092",
            *args,
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if result.returncode != 0:
        print(result.stdout)
        return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
