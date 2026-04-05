"""Ingest service config."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    postgres_user: str = "factory"
    postgres_password: str = "factory_dev_password"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "factory_pulse"

    redis_host: str = "localhost"
    redis_port: int = 6379

    opcua_endpoint: str = "opc.tcp://localhost:4840"
    opcua_namespace: str = "urn:factory-pulse:simulator"

    batch_max_size: int = 100
    batch_max_age_seconds: float = 1.0
    batch_overflow_limit: int = 10000

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/0"


settings = Settings()
