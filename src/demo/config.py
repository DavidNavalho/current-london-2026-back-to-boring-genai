from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    kafka_bootstrap_servers: str = Field(default="localhost:9092")
    schema_registry_url: str = Field(default="http://localhost:8081")
    kafka_security_protocol: str = Field(default="SASL_PLAINTEXT")
    kafka_sasl_mechanism: str = Field(default="PLAIN")
    kafka_principal: str = Field(default="svc-admin")
    kafka_sasl_username: str | None = Field(default=None)
    kafka_sasl_password: str | None = Field(default=None)
    codex_provider_mode: str = Field(default="cli")
    codex_auth_token: str | None = Field(default=None)
    demo_pacing: str = Field(default="realtime")
    demo_env: str = Field(default="demo")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def safe_dump(self) -> dict[str, object]:
        values = self.model_dump()
        redacted = {}
        for key, value in values.items():
            if value and any(marker in key.lower() for marker in ("token", "key", "secret", "password")):
                redacted[key] = "***"
            else:
                redacted[key] = value
        return redacted
