from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_docker_compose_exposes_akhq_with_schema_registry():
    compose = (ROOT / "docker-compose.yml").read_text()

    assert "akhq:" in compose
    assert "tchiotludo/akhq:" in compose
    assert '"8080:8080"' in compose
    assert "AKHQ_CONFIGURATION" in compose
    assert 'bootstrap.servers: "broker:29092"' in compose
    assert 'url: "http://schema-registry:8081"' in compose
