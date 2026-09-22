from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

from llm_operations_lab.config import ApplicationPolicy, Settings
from llm_operations_lab.main import create_app
from llm_operations_lab.prompts import PromptStore
from llm_operations_lab.providers.base import Provider

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def settings_factory() -> Callable[..., Settings]:
    def factory(
        *,
        requests_per_minute: int = 30,
        max_concurrency: int = 2,
        timeout_seconds: float = 2.0,
        provider_max_retries: int = 2,
    ) -> Settings:
        return Settings(
            app_credentials_json={
                "test-app": ApplicationPolicy(
                    api_key=SecretStr("test-secret-key"),
                    allowed_models=frozenset({"mock-echo", "mock-ops"}),
                    requests_per_minute=requests_per_minute,
                    max_concurrency=max_concurrency,
                    timeout_seconds=timeout_seconds,
                )
            },
            provider_max_retries=provider_max_retries,
            otel_enabled=False,
            langfuse_enabled=False,
        )

    return factory


@pytest.fixture
def client_factory() -> Callable[..., AsyncIterator[httpx.AsyncClient]]:
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def factory(
        *, settings: Settings, provider: Provider
    ) -> AsyncIterator[httpx.AsyncClient]:
        app = create_app(
            settings=settings,
            provider=provider,
            prompts=PromptStore(PROJECT_ROOT / "prompts"),
        )
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            yield client

    return factory
