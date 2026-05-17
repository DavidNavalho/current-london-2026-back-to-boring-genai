from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_docker_compose_exposes_akhq_with_schema_registry():
    compose = (ROOT / "docker-compose.yml").read_text()

    assert "name: questionnaire-ai-demo" in compose
    assert "akhq:" in compose
    assert "tchiotludo/akhq:" in compose
    assert '"8080:8080"' in compose
    assert "AKHQ_CONFIGURATION" in compose
    assert 'bootstrap.servers: "broker:29092"' in compose
    assert 'url: "http://schema-registry:8081"' in compose


def test_docker_compose_runs_api_and_bootstrap_in_containers():
    compose = (ROOT / "docker-compose.yml").read_text()

    assert "app:" in compose
    assert "bootstrap:" in compose
    assert "questionnaire-ai-demo-app" in compose
    assert '"${APP_PORT:-8000}:8000"' in compose
    assert "KAFKA_BOOTSTRAP_SERVERS: broker:29094" in compose
    assert "KAFKA_SECURITY_PROTOCOL: SASL_PLAINTEXT" in compose
    assert "SCHEMA_REGISTRY_URL: http://schema-registry:8081" in compose
    assert "python scripts/bootstrap_topics.py" in compose
    assert "python scripts/bootstrap_schemas.py" in compose
    assert "python scripts/bootstrap_acls.py" in compose
    assert "${CODEX_HOME:-${HOME}/.codex}:/root/.codex" in compose


def test_dockerfile_installs_api_and_codex_cli():
    dockerfile = (ROOT / "Dockerfile").read_text()

    assert "python:3.12-slim" in dockerfile
    assert "npm install -g @openai/codex@" in dockerfile
    assert 'pip install --no-cache-dir -e ".[dev,observability]"' in dockerfile
    assert 'CMD ["demo", "--help"]' in dockerfile


def test_bootstrap_scripts_run_inside_app_container_without_docker_cli():
    topics_script = (ROOT / "scripts" / "bootstrap_topics.py").read_text()
    acls_script = (ROOT / "scripts" / "bootstrap_acls.py").read_text()

    assert "AdminClient" in topics_script
    assert "AdminClient" in acls_script
    assert '"docker"' not in topics_script
    assert '"docker"' not in acls_script
    assert '"compose"' not in topics_script
    assert '"compose"' not in acls_script
