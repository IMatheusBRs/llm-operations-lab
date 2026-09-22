from __future__ import annotations

import httpx
import pytest
from pydantic import SecretStr

from llm_operations_lab.errors import ProviderPermanentError, ProviderTransientError
from llm_operations_lab.providers.openai_compatible import OpenAICompatibleProvider


@pytest.mark.asyncio
async def test_openai_compatible_adapter_reads_provider_reported_usage() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer fake-provider-key"
        return httpx.Response(
            200,
            json={
                "model": "synthetic-model-v1",
                "choices": [{"message": {"content": "resposta do adapter"}}],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 4,
                    "total_tokens": 14,
                },
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleProvider(
        base_url="https://provider.example/v1",
        api_key=SecretStr("fake-provider-key"),
        client=client,
    )
    result = await provider.generate(
        model="synthetic-model-v1",
        system_prompt="sistema",
        user_prompt="entrada",
        max_tokens=20,
        temperature=0.0,
    )
    await client.aclose()
    assert result.output == "resposta do adapter"
    assert result.usage.total_tokens == 14
    assert result.usage.source == "provider_reported"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "exception_type"),
    [(429, ProviderTransientError), (503, ProviderTransientError), (400, ProviderPermanentError)],
)
async def test_openai_compatible_adapter_classifies_retryable_statuses(
    status: int, exception_type: type[Exception]
) -> None:
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(status, json={}))
    )
    provider = OpenAICompatibleProvider(
        base_url="https://provider.example/v1",
        api_key=SecretStr("fake-provider-key"),
        client=client,
    )
    with pytest.raises(exception_type):
        await provider.generate(
            model="synthetic-model-v1",
            system_prompt="sistema",
            user_prompt="entrada",
            max_tokens=20,
            temperature=0.0,
        )
    await client.aclose()

