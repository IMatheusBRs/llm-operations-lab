from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator

from llm_operations_lab.auth import ApplicationIdentity
from llm_operations_lab.errors import (
    ConcurrencyLimitError,
    ModelNotAllowedError,
    RateLimitError,
)


@dataclass(slots=True)
class _RuntimeState:
    active: int = 0


class InMemoryAccessController:
    """Limites por processo; não representa quota distribuída entre réplicas."""

    def __init__(self) -> None:
        self._timestamps: dict[str, deque[float]] = defaultdict(deque)
        self._state: dict[str, _RuntimeState] = defaultdict(_RuntimeState)
        self._lock = asyncio.Lock()

    async def check_rate_limit(self, identity: ApplicationIdentity) -> None:
        now = time.monotonic()
        cutoff = now - 60.0
        async with self._lock:
            bucket = self._timestamps[identity.application_id]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= identity.policy.requests_per_minute:
                raise RateLimitError(
                    "limite de "
                    f"{identity.policy.requests_per_minute} requisições por minuto excedido"
                )
            bucket.append(now)

    def check_model(self, identity: ApplicationIdentity, model: str) -> None:
        if model not in identity.policy.allowed_models:
            raise ModelNotAllowedError(f"modelo {model!r} não autorizado para a aplicação")

    @asynccontextmanager
    async def concurrency_slot(
        self, identity: ApplicationIdentity
    ) -> AsyncIterator[None]:
        async with self._lock:
            state = self._state[identity.application_id]
            if state.active >= identity.policy.max_concurrency:
                raise ConcurrencyLimitError(
                    f"limite de {identity.policy.max_concurrency} requisições simultâneas excedido"
                )
            state.active += 1
        try:
            yield
        finally:
            async with self._lock:
                self._state[identity.application_id].active -= 1
