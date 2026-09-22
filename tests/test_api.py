from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from llm_operations_lab.config import ModelPrice
from llm_operations_lab.errors import ProviderPermanentError, ProviderTransientError
from llm_operations_lab.providers.base import ProviderResult, ProviderUsage
from llm_operations_lab.providers.mock import DeterministicMockProvider


@dataclass
class SlowProvider:
    delay: float
    name: str = "slow-test"

    async def generate(self, **_: object) -> ProviderResult:
        await asyncio.sleep(self.delay)
        return _result()


class FailingProvider:
    name = "failing-test"

    def __init__(self, *, transient: bool = True) -> None:
        self.calls = 0
        self.transient = transient

    async def generate(self, **_: object) -> ProviderResult:
        self.calls += 1
        if self.transient:
            raise ProviderTransientError("falha temporária sintética")
        raise ProviderPermanentError("falha permanente sintética")


class BlockingProvider:
    name = "blocking-test"

    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def generate(self, **_: object) -> ProviderResult:
        self.started.set()
        await self.release.wait()
        return _result()


class ProviderReportedUsageProvider:
    name = "usage-test"

    async def generate(self, **_: object) -> ProviderResult:
        return ProviderResult(
            output="resposta medida pelo provedor sintético",
            model="mock-echo",
            usage=ProviderUsage(100, 50, 150, "provider_reported"),
        )


def _result() -> ProviderResult:
    return ProviderResult(
        output="resposta sintética",
        model="mock-echo",
        usage=ProviderUsage(2, 2, 4, "estimated_local"),
    )


@pytest.mark.asyncio
async def test_authentication_rejects_missing_key(client_factory, settings_factory) -> None:
    async with client_factory(
        settings=settings_factory(), provider=DeterministicMockProvider()
    ) as client:
        response = await client.post(
            "/v1/generate", json={"model": "mock-echo", "prompt": "teste"}
        )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_api_key"


@pytest.mark.asyncio
async def test_api_key_is_not_written_to_structured_logs(
    client_factory, settings_factory, capsys
) -> None:
    async with client_factory(
        settings=settings_factory(), provider=DeterministicMockProvider()
    ) as client:
        response = await client.post(
            "/v1/generate",
            headers={"X-API-Key": "test-secret-key"},
            json={"model": "mock-echo", "prompt": "teste de log"},
        )
    assert response.status_code == 200
    assert "test-secret-key" not in capsys.readouterr().out


@pytest.mark.asyncio
async def test_model_catalog_is_enforced(client_factory, settings_factory) -> None:
    async with client_factory(
        settings=settings_factory(), provider=DeterministicMockProvider()
    ) as client:
        response = await client.post(
            "/v1/generate",
            headers={"X-API-Key": "test-secret-key"},
            json={"model": "external-model", "prompt": "teste"},
        )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "model_not_allowed"


@pytest.mark.asyncio
async def test_rate_limit_is_per_application_in_memory(
    client_factory, settings_factory
) -> None:
    async with client_factory(
        settings=settings_factory(requests_per_minute=1),
        provider=DeterministicMockProvider(),
    ) as client:
        first = await client.post(
            "/v1/generate",
            headers={"X-API-Key": "test-secret-key"},
            json={"model": "mock-echo", "prompt": "primeira"},
        )
        second = await client.post(
            "/v1/generate",
            headers={"X-API-Key": "test-secret-key"},
            json={"model": "mock-echo", "prompt": "segunda"},
        )
    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["error"]["code"] == "rate_limit_exceeded"


@pytest.mark.asyncio
async def test_concurrency_limit_rejects_excess_work(
    client_factory, settings_factory
) -> None:
    provider = BlockingProvider()
    async with client_factory(
        settings=settings_factory(max_concurrency=1), provider=provider
    ) as client:
        first_task = asyncio.create_task(
            client.post(
                "/v1/generate",
                headers={"X-API-Key": "test-secret-key"},
                json={"model": "mock-echo", "prompt": "bloqueia"},
            )
        )
        await provider.started.wait()
        second = await client.post(
            "/v1/generate",
            headers={"X-API-Key": "test-secret-key"},
            json={"model": "mock-echo", "prompt": "excesso"},
        )
        provider.release.set()
        first = await first_task
    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["error"]["code"] == "concurrency_limit_exceeded"


@pytest.mark.asyncio
async def test_provider_timeout_is_explicit(client_factory, settings_factory) -> None:
    async with client_factory(
        settings=settings_factory(timeout_seconds=0.05), provider=SlowProvider(0.1)
    ) as client:
        response = await client.post(
            "/v1/generate",
            headers={"X-API-Key": "test-secret-key"},
            json={"model": "mock-echo", "prompt": "timeout"},
        )
    assert response.status_code == 504
    assert response.json()["error"]["code"] == "provider_timeout"


@pytest.mark.asyncio
async def test_transient_failure_retries_only_up_to_configured_limit(
    client_factory, settings_factory
) -> None:
    provider = FailingProvider(transient=True)
    async with client_factory(
        settings=settings_factory(provider_max_retries=2), provider=provider
    ) as client:
        response = await client.post(
            "/v1/generate",
            headers={"X-API-Key": "test-secret-key"},
            json={"model": "mock-echo", "prompt": "falha"},
        )
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "provider_transient_error"
    assert provider.calls == 3


@pytest.mark.asyncio
async def test_permanent_failure_is_not_retried(client_factory, settings_factory) -> None:
    provider = FailingProvider(transient=False)
    async with client_factory(
        settings=settings_factory(provider_max_retries=2), provider=provider
    ) as client:
        response = await client.post(
            "/v1/generate",
            headers={"X-API-Key": "test-secret-key"},
            json={"model": "mock-echo", "prompt": "falha"},
        )
    assert response.status_code == 502
    assert provider.calls == 1


@pytest.mark.asyncio
async def test_metrics_expose_requests_errors_and_duration(
    client_factory, settings_factory
) -> None:
    async with client_factory(
        settings=settings_factory(), provider=DeterministicMockProvider()
    ) as client:
        await client.get("/healthz")
        metrics = await client.get("/metrics")
    assert metrics.status_code == 200
    assert "llm_lab_http_requests_total" in metrics.text
    assert "llm_lab_http_errors_total" in metrics.text
    assert "llm_lab_http_request_duration_seconds" in metrics.text


@pytest.mark.asyncio
async def test_cost_is_labeled_as_estimate_only_with_provider_reported_usage(
    client_factory, settings_factory
) -> None:
    settings = settings_factory().model_copy(
        update={
            "model_pricing_json": {
                "mock-echo": ModelPrice(
                    input_usd_per_million=1.0,
                    output_usd_per_million=2.0,
                )
            }
        }
    )
    async with client_factory(
        settings=settings, provider=ProviderReportedUsageProvider()
    ) as client:
        response = await client.post(
            "/v1/generate",
            headers={"X-API-Key": "test-secret-key"},
            json={"model": "mock-echo", "prompt": "custo"},
        )
    assert response.status_code == 200
    assert response.json()["cost"] == {
        "amount_usd": 0.0002,
        "basis": "tokens informados pelo provedor × preços configurados pelo operador",
        "is_estimate": True,
    }
