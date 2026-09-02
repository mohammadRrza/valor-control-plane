"""Centralized, environment-driven configuration."""

from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class ApplicationSettings(BaseModel):
    name: str = "VALOR"
    environment: Literal["local", "test", "staging", "production"] = "local"
    debug: bool = False


class DatabaseSettings(BaseModel):
    url: PostgresDsn
    pool_size: int = Field(default=5, ge=1, le=50)
    max_overflow: int = Field(default=10, ge=0, le=100)
    pool_timeout_seconds: float = Field(default=30, gt=0)


class ObservabilitySettings(BaseModel):
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_json: bool = True


class Settings(BaseSettings):
    """VALOR settings loaded once at the composition root."""

    model_config = SettingsConfigDict(
        env_prefix="VALOR_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    application: ApplicationSettings = ApplicationSettings()
    database: DatabaseSettings
    observability: ObservabilitySettings = ObservabilitySettings()


@lru_cache
def get_settings() -> Settings:
    return Settings()
