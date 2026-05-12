from __future__ import annotations

from datetime import UTC, datetime
import json
import urllib.error
import urllib.request

import pytest
from confluent_kafka import Consumer

from demo.contracts import QuestionnaireReceived, make_event_id
from demo.kafka_io import MAGIC_BYTE, consume_events, kafka_client_config, produce_event


def _runtime_available() -> bool:
    try:
        with urllib.request.urlopen("http://localhost:8081/subjects", timeout=2) as response:
            json.loads(response.read().decode("utf-8"))
        return True
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return False


@pytest.mark.skipif(not _runtime_available(), reason="Confluent runtime is not running")
def test_produce_and_consume_schema_governed_event():
    run_id = "run-kafka-io-test"
    event = QuestionnaireReceived(
        event_id=make_event_id(),
        run_id=run_id,
        occurred_at=datetime.now(UTC),
        producer="svc-ingest",
        schema_version=1,
        questionnaire_id="DEMO-QUESTIONNAIRE-001",
        title="Security Questionnaire",
        questions=[{"question_id": "Q-001", "text": "Do you encrypt data?"}],
    )

    produce_event("questionnaire.received.v1", event)
    events = consume_events("questionnaire.received.v1", run_id=run_id, timeout_seconds=10)

    assert any(item.event_id == event.event_id for item in events)


@pytest.mark.skipif(not _runtime_available(), reason="Confluent runtime is not running")
def test_produced_payload_is_avro_binary_not_json():
    run_id = "run-kafka-avro-wire-test"
    topic = "questionnaire.received.v1"
    event = QuestionnaireReceived(
        event_id=make_event_id(),
        run_id=run_id,
        occurred_at=datetime.now(UTC),
        producer="svc-ingest",
        schema_version=1,
        questionnaire_id="DEMO-QUESTIONNAIRE-001",
        title="Security Questionnaire",
        questions=[
            {
                "question_id": "Q-001",
                "scenario": "happy-path",
                "control_area": "encryption",
                "risk_hint": "low",
                "text": "Do you encrypt data?",
            }
        ],
    )

    produce_event(topic, event)
    raw_value = _consume_raw_value(topic, run_id)

    assert raw_value[:1] == MAGIC_BYTE
    payload = raw_value[5:]
    assert not payload.lstrip().startswith(b"{")
    with pytest.raises((UnicodeDecodeError, json.JSONDecodeError)):
        json.loads(payload.decode("utf-8"))


@pytest.mark.skipif(not _runtime_available(), reason="Confluent runtime is not running")
def test_produce_rejects_wrong_model_for_topic():
    event = QuestionnaireReceived(
        event_id=make_event_id(),
        run_id="run-kafka-io-invalid",
        occurred_at=datetime.now(UTC),
        producer="svc-ingest",
        schema_version=1,
        questionnaire_id="DEMO-QUESTIONNAIRE-001",
        title="Security Questionnaire",
        questions=[],
    )

    with pytest.raises(TypeError):
        produce_event("answer.reviewed.v1", event)


def _consume_raw_value(topic: str, run_id: str) -> bytes:
    config = kafka_client_config()
    config.update(
        {
            "group.id": f"raw-reader-{run_id}",
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
    )
    consumer = Consumer(config)
    consumer.subscribe([topic])
    try:
        for _ in range(60):
            message = consumer.poll(0.2)
            if message is None:
                continue
            if message.error():
                raise RuntimeError(str(message.error()))
            if message.key() == run_id.encode("utf-8"):
                return message.value()
    finally:
        consumer.close()
    raise AssertionError(f"No raw Kafka message found for {run_id}")
