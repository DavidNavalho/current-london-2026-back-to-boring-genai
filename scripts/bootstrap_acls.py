from __future__ import annotations

from confluent_kafka import KafkaError, KafkaException
from confluent_kafka.admin import (
    AclBinding,
    AclOperation,
    AclPermissionType,
    AdminClient,
    ResourcePatternType,
    ResourceType,
)

from demo.kafka_io import kafka_client_config


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
    admin = AdminClient(kafka_client_config())
    acl_bindings: list[AclBinding] = []
    for principal, grants in SERVICE_ACLS.items():
        for topic in grants["read"]:
            for operation in ("Read", "Describe"):
                acl_bindings.append(_topic_acl(principal, operation, topic))
        for topic in grants["write"]:
            for operation in ("Write", "Describe"):
                acl_bindings.append(_topic_acl(principal, operation, topic))
        if grants["read"]:
            acl_bindings.append(_group_acl(principal))

    acl_bindings = list(dict.fromkeys(acl_bindings))
    futures = admin.create_acls(
        acl_bindings,
        request_timeout=15,
    )
    for acl, future in futures.items():
        try:
            future.result()
        except KafkaException as exc:
            error = exc.args[0]
            if error.code() != KafkaError.DUPLICATE_RESOURCE:
                print(f"ACL bootstrap failed for {acl}: {error}")
                return 1
    print("ACLs ready")
    return 0


def _topic_acl(principal: str, operation: str, topic: str) -> AclBinding:
    return AclBinding(
        ResourceType.TOPIC,
        topic,
        ResourcePatternType.LITERAL,
        f"User:{principal}",
        "*",
        _operation(operation),
        AclPermissionType.ALLOW,
    )


def _group_acl(principal: str) -> AclBinding:
    return AclBinding(
        ResourceType.GROUP,
        "*",
        ResourcePatternType.LITERAL,
        f"User:{principal}",
        "*",
        AclOperation.READ,
        AclPermissionType.ALLOW,
    )


def _operation(operation: str) -> AclOperation:
    return {
        "Read": AclOperation.READ,
        "Write": AclOperation.WRITE,
        "Describe": AclOperation.DESCRIBE,
    }[operation]


if __name__ == "__main__":
    raise SystemExit(main())
