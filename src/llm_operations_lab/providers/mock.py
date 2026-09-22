from __future__ import annotations

import re

from llm_operations_lab.providers.base import ProviderResult, ProviderUsage


def estimate_tokens(text: str) -> int:
    """Contagem simples e explicitamente estimada; não substitui tokenizer real."""

    return max(1, len(re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE)))


class DeterministicMockProvider:
    name = "mock"

    async def generate(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> ProviderResult:
        del temperature
        normalized = " ".join(user_prompt.split())

        if model == "mock-echo":
            output = f"[mock determinístico] {normalized[: min(300, max_tokens * 4)]}"
        elif model == "mock-ops":
            terms = normalized.lower()
            if "erro" in terms or "falha" in terms or "incidente" in terms:
                output = (
                    "[mock determinístico] Classificação: incidente operacional. "
                    "Próximos passos: verificar correlação, logs e saturação antes de intervir."
                )
            else:
                output = (
                    "[mock determinístico] Classificação: solicitação operacional. "
                    "Resposta simulada sem chamada a modelo externo."
                )
        else:
            output = f"[mock determinístico:{model}] {normalized[: min(300, max_tokens * 4)]}"

        input_tokens = estimate_tokens(f"{system_prompt}\n{user_prompt}")
        output_tokens = estimate_tokens(output)
        return ProviderResult(
            output=output,
            model=model,
            usage=ProviderUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
                source="estimated_local",
            ),
        )

