from __future__ import annotations

import struct
import time
from uuid import uuid4

from confluent_kafka import Consumer, Producer

from demo.avro_contracts import decode_avro_event, encode_avro_event
from demo.config import Settings
from demo.contracts import SUBJECT_MODELS, StrictEvent
from demo.schema_registry import SchemaRegistryClient


TOPIC_SUBJECTS: dict[str, str] = {
    subject.removesuffix("-value"): subject for subject in SUBJECT_MODELS
}
MAGIC_BYTE = b"\x00"


class KafkaClientError(RuntimeError):
    """Raised when Kafka rejects a produce, consume, or admin operation."""


def kafka_client_config(
    *,
    settings: Settings | None = None,
    principal: str | None = None,
) -> dict[str, str]:
    resolved_settings = settings or Settings()
    resolved_principal = principal or resolved_settings.kafka_principal
    config = {
        "bootstrap.servers": resolved_settings.kafka_bootstrap_servers,
        "security.protocol": resolved_settings.kafka_security_protocol,
    }
    if resolved_settings.kafka_security_protocol.startswith("SASL"):
        config.update(
            {
                "sasl.mechanism": resolved_settings.kafka_sasl_mechanism,
                "sasl.username": resolved_settings.kafka_sasl_username or resolved_principal,
                "sasl.password": resolved_settings.kafka_sasl_password
                or f"{resolved_principal}-secret",
            }
        )
    return config


def _producer(settings: Settings, principal: str | None = None) -> Producer:
    return Producer(kafka_client_config(settings=settings, principal=principal))


def _consumer(settings: Settings, group_id: str, principal: str | None = None) -> Consumer:
    config = kafka_client_config(settings=settings, principal=principal)
    config.update(
        {
            "group.id": group_id,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
    )
    return Consumer(config)


def _encode_schema_registry_payload(schema_id: int, payload: bytes) -> bytes:
    return MAGIC_BYTE + struct.pack(">I", schema_id) + payload


def _decode_schema_registry_payload(value: bytes) -> tuple[int, bytes]:
    if not value or value[:1] != MAGIC_BYTE:
        raise ValueError("Message is not encoded with Schema Registry framing")
    return struct.unpack(">I", value[1:5])[0], value[5:]


def produce_event(topic: str, event: StrictEvent, *, principal: str | None = None) -> None:
    subject = TOPIC_SUBJECTS[topic]
    expected_model = SUBJECT_MODELS[subject]
    if not isinstance(event, expected_model):
        raise TypeError(f"{topic} expects {expected_model.__name__}, got {type(event).__name__}")

    settings = Settings()
    registry = SchemaRegistryClient(settings.schema_registry_url)
    schema_id = registry.get_latest_schema_id(subject)
    payload = encode_avro_event(subject, event)
    encoded = _encode_schema_registry_payload(schema_id, payload)
    producer = _producer(settings, principal)
    errors: list[str] = []

    def _delivery_callback(error, _message) -> None:
        if error is not None:
            errors.append(str(error))

    producer.produce(
        topic,
        key=event.run_id.encode("utf-8"),
        value=encoded,
        on_delivery=_delivery_callback,
    )
    remaining = producer.flush(10)
    if remaining:
        raise KafkaClientError(f"Timed out producing to {topic}")
    if errors:
        raise KafkaClientError(errors[0])


def consume_events(
    topic: str,
    *,
    run_id: str | None = None,
    timeout_seconds: float = 5,
    idle_seconds_after_match: float = 0.4,
    principal: str | None = None,
) -> list[StrictEvent]:
    subject = TOPIC_SUBJECTS[topic]
    settings = Settings()
    consumer = _consumer(settings, group_id=f"demo-reader-{uuid4()}", principal=principal)
    consumer.subscribe([topic])
    deadline = time.time() + timeout_seconds
    events: list[StrictEvent] = []
    last_match_at: float | None = None
    try:
        while time.time() < deadline:
            msg = consumer.poll(0.2)
            if msg is None:
                if last_match_at is not None and time.time() - last_match_at >= idle_seconds_after_match:
                    break
                continue
            if msg.error():
                raise KafkaClientError(str(msg.error()))
            _schema_id, payload = _decode_schema_registry_payload(msg.value())
            event = decode_avro_event(subject, payload)
            if run_id is None or event.run_id == run_id:
                events.append(event)
                last_match_at = time.time()
    finally:
        consumer.close()
    return events


def consume_one(
    topic: str,
    *,
    run_id: str | None = None,
    timeout_seconds: float = 5,
    principal: str | None = None,
) -> StrictEvent:
    events = consume_events(
        topic,
        run_id=run_id,
        timeout_seconds=timeout_seconds,
        principal=principal,
    )
    if not events:
        raise TimeoutError(f"No event consumed from {topic}")
    return events[0]
