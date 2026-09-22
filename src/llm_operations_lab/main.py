import inspect
from contextlib import asynccontextmanager
from typing import Annotated, Any, AsyncIterator

from fastapi import Depends, FastAPI, Path, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from prometheus_client import CONTENT_TYPE_LATEST

from llm_operations_lab.auth import ApplicationIdentity, Authenticator
from llm_operations_lab.config import Settings, get_settings
from llm_operations_lab.errors import LabError
from llm_operations_lab.observability import (
    LangfuseBridge,
    Metrics,
    configure_logging,
    configure_otel,
    correlation_id_var,
    install_http_observability,
    logger,
)
from llm_operations_lab.orders.adapter import PurchaseOrderAdapter
from llm_operations_lab.orders.mock_api import router as mock_sap_router
from llm_operations_lab.policies import InMemoryAccessController
from llm_operations_lab.prompts import PromptStore
from llm_operations_lab.providers import (
    DeterministicMockProvider,
    OpenAICompatibleProvider,
    Provider,
)
from llm_operations_lab.schemas import (
    ErrorDetail,
    ErrorResponse,
    GenerateRequest,
    GenerateResponse,
    ModelCatalogResponse,
    PurchaseOrderToolResponse,
)
from llm_operations_lab.service import GenerationService

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def create_app(
    *,
    settings: Settings | None = None,
    provider: Provider | None = None,
    purchase_order_adapter: PurchaseOrderAdapter | None = None,
    prompts: PromptStore | None = None,
) -> FastAPI:
    configure_logging()
    settings = settings or get_settings()
    owns_provider = provider is None
    owns_order_adapter = purchase_order_adapter is None
    provider = provider or _build_provider(settings)
    purchase_order_adapter = purchase_order_adapter or PurchaseOrderAdapter(
        base_url=str(settings.purchase_order_base_url)
    )
    metrics = Metrics()
    langfuse = LangfuseBridge(settings)
    access = InMemoryAccessController()
    authenticator = Authenticator(settings.applications)
    service = GenerationService(
        provider=provider,
        access=access,
        prompts=prompts or PromptStore(),
        metrics=metrics,
        langfuse=langfuse,
        pricing=settings.pricing,
        max_retries=settings.provider_max_retries,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        if owns_provider:
            await _maybe_close(provider)
        if owns_order_adapter:
            await purchase_order_adapter.aclose()
        langfuse.flush()
        if otel_provider is not None:
            otel_provider.shutdown()

    app = FastAPI(
        title="LLM Operations Lab",
        version="0.1.0",
        description=(
            "Laboratório independente com dados sintéticos. O modo padrão não chama serviços "
            "externos."
        ),
        lifespan=lifespan,
    )
    install_http_observability(app, metrics)
    otel_provider = configure_otel(app, settings)

    async def current_application(
        request: Request, api_key: str | None = Depends(api_key_header)
    ) -> ApplicationIdentity:
        identity = authenticator.authenticate(api_key)
        request.state.application_id = identity.application_id
        return identity

    @app.exception_handler(LabError)
    async def handle_lab_error(_: Request, exc: LabError) -> JSONResponse:
        payload = ErrorResponse(
            error=ErrorDetail(
                code=exc.code,
                message=exc.message,
                request_id=correlation_id_var.get(),
                retryable=exc.retryable,
            )
        )
        return JSONResponse(status_code=exc.status_code, content=payload.model_dump())

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        del exc
        payload = ErrorResponse(
            error=ErrorDetail(
                code="validation_error",
                message="requisição inválida; consulte o schema OpenAPI",
                request_id=correlation_id_var.get(),
            )
        )
        return JSONResponse(status_code=422, content=payload.model_dump())

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_error", error_type=type(exc).__name__)
        payload = ErrorResponse(
            error=ErrorDetail(
                code="internal_error",
                message="erro interno",
                request_id=correlation_id_var.get(),
            )
        )
        return JSONResponse(status_code=500, content=payload.model_dump())

    @app.get("/healthz", tags=["operations"])
    async def healthz() -> dict[str, str]:
        return {"status": "ok", "provider": provider.name}

    @app.get("/metrics", include_in_schema=False)
    async def prometheus_metrics() -> Response:
        return Response(content=metrics.render(), media_type=CONTENT_TYPE_LATEST)

    @app.get("/v1/models", response_model=ModelCatalogResponse, tags=["llm"])
    async def list_models(
        identity: Annotated[ApplicationIdentity, Depends(current_application)],
    ) -> ModelCatalogResponse:
        return ModelCatalogResponse(
            application_id=identity.application_id,
            allowed_models=sorted(identity.policy.allowed_models),
        )

    @app.post(
        "/v1/generate",
        response_model=GenerateResponse,
        responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
        tags=["llm"],
    )
    async def generate(
        body: GenerateRequest,
        identity: Annotated[ApplicationIdentity, Depends(current_application)],
    ) -> GenerateResponse:
        return await service.generate(identity, body)

    @app.get(
        "/v1/tools/purchase-orders/{purchase_order_id}",
        response_model=PurchaseOrderToolResponse,
        tags=["tools"],
    )
    async def purchase_order_tool(
        purchase_order_id: Annotated[str, Path(pattern=r"^PO-[0-9]{6}$")],
        _: Annotated[ApplicationIdentity, Depends(current_application)],
    ) -> PurchaseOrderToolResponse:
        order = await purchase_order_adapter.get_by_id(purchase_order_id)
        return PurchaseOrderToolResponse(order=order)

    app.include_router(mock_sap_router)
    return app


def _build_provider(settings: Settings) -> Provider:
    if settings.llm_provider == "mock":
        return DeterministicMockProvider()
    if settings.openai_compatible_api_key is None:
        raise RuntimeError("OPENAI_COMPATIBLE_API_KEY é obrigatória para o adapter externo")
    return OpenAICompatibleProvider(
        base_url=str(settings.openai_compatible_base_url),
        api_key=settings.openai_compatible_api_key,
    )


async def _maybe_close(resource: Any) -> None:
    close = getattr(resource, "aclose", None)
    if close is not None:
        result = close()
        if inspect.isawaitable(result):
            await result


app = create_app()
