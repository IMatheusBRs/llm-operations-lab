from __future__ import annotations

from typing import Any

import httpx
from pydantic import SecretStr

from llm_operations_lab.errors import ProviderPermanentError, ProviderTransientError
from llm_operations_lab.providers.base import ProviderResult, ProviderUsage


class OpenAICompatibleProvider:
    """Adapter HTTP restrito ao endpoint Chat Completions configurado."""

    name = "openai_compatible"

    def __init__(
        self,
        *,
        base_url: str,
        api_key: SecretStr,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._api_key = api_key
        self._client = client or httpx.AsyncClient(timeout=None)
        self._owns_client = client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def generate(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> ProviderResult:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }
        try:
            response = await self._client.post(
                self._url,
                headers={
                    "Authorization": f"Bearer {self._api_key.get_secret_value()}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        except httpx.TransportError as exc:
            raise ProviderTransientError("falha de transporte ao chamar o provedor") from exc

        if response.status_code == 429 or response.status_code >= 500:
            raise ProviderTransientError(
                f"provedor indisponível (status {response.status_code})"
            )
        if response.status_code >= 400:
            raise ProviderPermanentError(
                f"provedor rejeitou a requisição (status {response.status_code})"
            )

        try:
            data: dict[str, Any] = response.json()
            output = data["choices"][0]["message"]["content"]
            usage = data.get("usage") or {}
            if not isinstance(output, str):
                raise TypeError("conteúdo da resposta não é texto")
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderPermanentError("resposta incompatível com Chat Completions") from exc

        prompt_tokens = _optional_int(usage.get("prompt_tokens"))
        completion_tokens = _optional_int(usage.get("completion_tokens"))
        total_tokens = _optional_int(usage.get("total_tokens"))
        source = "provider_reported" if total_tokens is not None else "unavailable"
        return ProviderResult(
            output=output,
            model=str(data.get("model") or model),
            usage=ProviderUsage(
                input_tokens=prompt_tokens,
                output_tokens=completion_tokens,
                total_tokens=total_tokens,
                source=source,
            ),
        )


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and value >= 0 else None

