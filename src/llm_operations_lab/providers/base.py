from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ProviderUsage:
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    source: str


@dataclass(frozen=True, slots=True)
class ProviderResult:
    output: str
    model: str
    usage: ProviderUsage


class Provider(Protocol):
    name: str

    async def generate(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> ProviderResult: ...

