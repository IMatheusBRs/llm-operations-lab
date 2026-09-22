from __future__ import annotations

import asyncio
import time

from opentelemetry import trace

from llm_operations_lab.auth import ApplicationIdentity
from llm_operations_lab.config import ModelPrice
from llm_operations_lab.errors import ProviderTimeoutError, ProviderTransientError
from llm_operations_lab.observability import LangfuseBridge, Metrics, correlation_id_var
from llm_operations_lab.policies import InMemoryAccessController
from llm_operations_lab.prompts import PromptStore
from llm_operations_lab.providers.base import Provider, ProviderResult
from llm_operations_lab.schemas import (
    CostEstimate,
    GenerateRequest,
    GenerateResponse,
    TokenUsage,
)


class GenerationService:
    def __init__(
        self,
        *,
        provider: Provider,
        access: InMemoryAccessController,
        prompts: PromptStore,
        metrics: Metrics,
        langfuse: LangfuseBridge,
        pricing: dict[str, ModelPrice],
        max_retries: int,
    ) -> None:
        self._provider = provider
        self._access = access
        self._prompts = prompts
        self._metrics = metrics
        self._langfuse = langfuse
        self._pricing = pricing
        self._max_retries = max_retries
        self._tracer = trace.get_tracer("llm_operations_lab.generation")

    async def generate(
        self, identity: ApplicationIdentity, request: GenerateRequest
    ) -> GenerateResponse:
        self._access.check_model(identity, request.model)
        await self._access.check_rate_limit(identity)
        system_prompt = self._prompts.system_prompt(request.prompt_version)
        started = time.perf_counter()
        outcome = "error"
        try:
            async with self._access.concurrency_slot(identity):
                try:
                    async with asyncio.timeout(identity.policy.timeout_seconds):
                        with self._tracer.start_as_current_span("provider.generate") as span:
                            span.set_attribute("gen_ai.system", self._provider.name)
                            span.set_attribute("gen_ai.request.model", request.model)
                            span.set_attribute(
                                "llm.application_id", identity.application_id
                            )
                            with self._langfuse.generation(
                                model=request.model,
                                prompt=request.prompt,
                                application_id=identity.application_id,
                            ) as observation:
                                result = await self._call_with_retries(
                                    model=request.model,
                                    system_prompt=system_prompt,
                                    request=request,
                                )
                                if observation is not None:
                                    observation.update(
                                        output=result.output,
                                        usage_details={
                                            "input_tokens": result.usage.input_tokens,
                                            "output_tokens": result.usage.output_tokens,
                                            "total_tokens": result.usage.total_tokens,
                                        },
                                    )
                except TimeoutError as exc:
                    raise ProviderTimeoutError(
                        f"provedor excedeu {identity.policy.timeout_seconds:.2f}s"
                    ) from exc
            outcome = "success"
            return self._response(identity, request, result)
        finally:
            duration = time.perf_counter() - started
            self._metrics.provider_requests.labels(
                identity.application_id,
                self._provider.name,
                request.model,
                outcome,
            ).inc()
            self._metrics.provider_duration.labels(
                self._provider.name, request.model
            ).observe(duration)

    async def _call_with_retries(
        self, *, model: str, system_prompt: str, request: GenerateRequest
    ) -> ProviderResult:
        for attempt in range(self._max_retries + 1):
            try:
                return await self._provider.generate(
                    model=model,
                    system_prompt=system_prompt,
                    user_prompt=request.prompt,
                    max_tokens=request.max_tokens,
                    temperature=request.temperature,
                )
            except ProviderTransientError:
                if attempt >= self._max_retries:
                    raise
                await asyncio.sleep(min(0.05 * (2**attempt), 0.2))
        raise AssertionError("loop de retry terminou sem resultado")

    def _response(
        self,
        identity: ApplicationIdentity,
        request: GenerateRequest,
        result: ProviderResult,
    ) -> GenerateResponse:
        return GenerateResponse(
            request_id=correlation_id_var.get(),
            application_id=identity.application_id,
            provider=self._provider.name,
            model=result.model,
            prompt_version=request.prompt_version,
            output=result.output,
            usage=TokenUsage(
                input_tokens=result.usage.input_tokens,
                output_tokens=result.usage.output_tokens,
                total_tokens=result.usage.total_tokens,
                source=result.usage.source,
            ),
            cost=self._estimate_cost(result),
        )

    def _estimate_cost(self, result: ProviderResult) -> CostEstimate | None:
        price = self._pricing.get(result.model)
        usage = result.usage
        if (
            price is None
            or usage.source != "provider_reported"
            or usage.input_tokens is None
            or usage.output_tokens is None
        ):
            return None
        amount = (
            usage.input_tokens * price.input_usd_per_million
            + usage.output_tokens * price.output_usd_per_million
        ) / 1_000_000
        return CostEstimate(
            amount_usd=round(amount, 8),
            basis="tokens informados pelo provedor × preços configurados pelo operador",
            is_estimate=True,
        )
