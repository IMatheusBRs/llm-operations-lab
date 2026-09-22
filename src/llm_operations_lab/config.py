from __future__ import annotations

from functools import lru_cache

from pydantic import BaseModel, Field, HttpUrl, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ApplicationPolicy(BaseModel):
    """Limites e catálogo de modelos de uma aplicação cliente."""

    api_key: SecretStr
    allowed_models: frozenset[str] = Field(min_length=1)
    requests_per_minute: int = Field(default=30, ge=1, le=10_000)
    max_concurrency: int = Field(default=2, ge=1, le=100)
    timeout_seconds: float = Field(default=2.0, ge=0.05, le=120.0)


class ModelPrice(BaseModel):
    input_usd_per_million: float = Field(ge=0)
    output_usd_per_million: float = Field(ge=0)


def default_app_credentials() -> dict[str, ApplicationPolicy]:
    return {
        "demo-app": ApplicationPolicy(
            api_key=SecretStr("demo-key-local-only"),
            allowed_models=frozenset({"mock-echo", "mock-ops"}),
            requests_per_minute=30,
            max_concurrency=2,
            timeout_seconds=2.0,
        )
    }


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "llm-operations-lab"
    app_credentials_json: dict[str, ApplicationPolicy] = Field(
        default_factory=default_app_credentials
    )
    llm_provider: str = "mock"
    provider_max_retries: int = Field(default=2, ge=0, le=3)

    openai_compatible_base_url: HttpUrl = HttpUrl("https://api.example.invalid/v1")
    openai_compatible_api_key: SecretStr | None = None
    model_pricing_json: dict[str, ModelPrice] = Field(default_factory=dict)

    otel_enabled: bool = False
    otel_service_name: str = "llm-operations-lab"
    otel_exporter_otlp_endpoint: str | None = None

    langfuse_enabled: bool = False
    langfuse_public_key: str | None = None
    langfuse_secret_key: SecretStr | None = None
    langfuse_base_url: str = "https://cloud.langfuse.com"

    purchase_order_base_url: HttpUrl = HttpUrl(
        "http://127.0.0.1:8000/mock-sap/odata/v1"
    )

    @field_validator("llm_provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        allowed = {"mock", "openai_compatible"}
        if value not in allowed:
            raise ValueError(f"llm_provider deve ser um de {sorted(allowed)}")
        return value

    @property
    def applications(self) -> dict[str, ApplicationPolicy]:
        return self.app_credentials_json

    @property
    def pricing(self) -> dict[str, ModelPrice]:
        return self.model_pricing_json


@lru_cache
def get_settings() -> Settings:
    return Settings()
