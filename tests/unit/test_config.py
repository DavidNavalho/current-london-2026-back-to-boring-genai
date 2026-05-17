from demo.config import Settings


def test_config_loads_defaults(monkeypatch):
    monkeypatch.delenv("KAFKA_BOOTSTRAP_SERVERS", raising=False)
    monkeypatch.delenv("SCHEMA_REGISTRY_URL", raising=False)
    monkeypatch.delenv("CODEX_PROVIDER_MODE", raising=False)

    settings = Settings()

    assert settings.kafka_bootstrap_servers == "localhost:9092"
    assert settings.schema_registry_url == "http://localhost:8081"
    assert settings.codex_provider_mode == "cli"


def test_config_accepts_env_overrides(monkeypatch):
    monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "broker:29092")
    monkeypatch.setenv("SCHEMA_REGISTRY_URL", "http://schema-registry:8081")
    monkeypatch.setenv("CODEX_PROVIDER_MODE", "sdk")

    settings = Settings()

    assert settings.kafka_bootstrap_servers == "broker:29092"
    assert settings.schema_registry_url == "http://schema-registry:8081"
    assert settings.codex_provider_mode == "sdk"


def test_safe_dump_redacts_secret_like_values(monkeypatch):
    monkeypatch.setenv("CODEX_AUTH_TOKEN", "secret-token")
    settings = Settings()

    dumped = settings.safe_dump()

    assert dumped["codex_auth_token"] == "***"
    assert "secret-token" not in str(dumped)
