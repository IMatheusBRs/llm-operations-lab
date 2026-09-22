from __future__ import annotations

import pytest

from llm_operations_lab.providers.mock import DeterministicMockProvider


@pytest.mark.asyncio
async def test_mock_provider_is_deterministic_and_marks_usage_as_estimated() -> None:
    provider = DeterministicMockProvider()
    arguments = {
        "model": "mock-ops",
        "system_prompt": "sistema",
        "user_prompt": "Falha sintética no serviço",
        "max_tokens": 100,
        "temperature": 0.0,
    }
    first = await provider.generate(**arguments)
    second = await provider.generate(**arguments)
    assert first == second
    assert first.usage.source == "estimated_local"
    assert "incidente operacional" in first.output

