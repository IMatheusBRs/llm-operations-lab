from __future__ import annotations

import contextvars
import time
import uuid
from contextlib import contextmanager
from typing import Any, Iterator

import structlog
from fastapi import FastAPI, Request, Response
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest

from llm_operations_lab.config import Settings

correlation_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default="unknown"
)


def configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


logger = structlog.get_logger()


class Metrics:
    def __init__(self) -> None:
        self.registry = CollectorRegistry(auto_describe=True)
        self.http_requests = Counter(
            "llm_lab_http_requests_total",
            "Requisições HTTP processadas",
            ("method", "route", "status"),
            registry=self.registry,
        )
        self.http_errors = Counter(
            "llm_lab_http_errors_total",
            "Requisições HTTP com status de erro",
            ("route", "status"),
            registry=self.registry,
        )
        self.http_duration = Histogram(
            "llm_lab_http_request_duration_seconds",
            "Duração das requisições HTTP",
            ("method", "route"),
            registry=self.registry,
        )
        self.provider_requests = Counter(
            "llm_lab_provider_requests_total",
            "Chamadas ao provedor de linguagem",
            ("application", "provider", "model", "outcome"),
            registry=self.registry,
        )
        self.provider_duration = Histogram(
            "llm_lab_provider_duration_seconds",
            "Duração das chamadas ao provedor",
            ("provider", "model"),
            registry=self.registry,
        )

    def render(self) -> bytes:
        return generate_latest(self.registry)


def install_http_observability(app: FastAPI, metrics: Metrics) -> None:
    @app.middleware("http")
    async def observability_middleware(request: Request, call_next: Any) -> Response:
        incoming = request.headers.get("x-correlation-id", "")
        correlation_id = incoming if _valid_correlation_id(incoming) else str(uuid.uuid4())
        token = correlation_id_var.set(correlation_id)
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
        started = time.perf_counter()
        status_code = 500
        route = request.url.path
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Correlation-ID"] = correlation_id
            return response
        finally:
            matched_route = request.scope.get("route")
            route = getattr(matched_route, "path", route)
            duration = time.perf_counter() - started
            metrics.http_requests.labels(request.method, route, str(status_code)).inc()
            metrics.http_duration.labels(request.method, route).observe(duration)
            if status_code >= 400:
                metrics.http_errors.labels(route, str(status_code)).inc()
            logger.info(
                "http_request",
                method=request.method,
                route=route,
                status=status_code,
                duration_ms=round(duration * 1000, 3),
                application_id=getattr(request.state, "application_id", None),
            )
            structlog.contextvars.clear_contextvars()
            correlation_id_var.reset(token)


def configure_otel(app: FastAPI, settings: Settings) -> TracerProvider | None:
    if not settings.otel_enabled:
        return None
    provider = TracerProvider(
        resource=Resource.create({"service.name": settings.otel_service_name})
    )
    if settings.otel_exporter_otlp_endpoint:
        exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint)
    else:
        exporter = ConsoleSpanExporter()
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
    return provider


class LangfuseBridge:
    def __init__(self, settings: Settings) -> None:
        self._client: Any | None = None
        if not settings.langfuse_enabled:
            return
        if not (
            settings.langfuse_public_key
            and settings.langfuse_secret_key
            and settings.langfuse_base_url
        ):
            raise RuntimeError("Langfuse habilitado sem credenciais e URL completas")
        try:
            from langfuse import Langfuse
        except ImportError as exc:
            raise RuntimeError(
                "instale o extra langfuse: uv sync --extra langfuse"
            ) from exc
        self._client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key.get_secret_value(),
            base_url=settings.langfuse_base_url,
        )

    @contextmanager
    def generation(
        self, *, model: str, prompt: str, application_id: str
    ) -> Iterator[Any | None]:
        if self._client is None:
            yield None
            return
        with self._client.start_as_current_observation(
            as_type="generation",
            name="llm-generate",
            model=model,
            input={"prompt": prompt},
            metadata={"application_id": application_id},
        ) as observation:
            yield observation

    def flush(self) -> None:
        if self._client is not None:
            self._client.flush()


def _valid_correlation_id(value: str) -> bool:
    return bool(value) and len(value) <= 64 and all(
        character.isalnum() or character in "-_." for character in value
    )

