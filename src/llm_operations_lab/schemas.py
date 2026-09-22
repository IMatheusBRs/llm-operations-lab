from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    model: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9._:-]+$")
    prompt: str = Field(min_length=1, max_length=4_000)
    prompt_version: str = Field(default="v1", pattern=r"^v[1-9][0-9]*$")
    max_tokens: int = Field(default=256, ge=1, le=512)
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)


class TokenUsage(BaseModel):
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    source: Literal["provider_reported", "estimated_local", "unavailable"]


class CostEstimate(BaseModel):
    amount_usd: float = Field(ge=0)
    basis: str
    is_estimate: Literal[True] = True


class GenerateResponse(BaseModel):
    request_id: str
    application_id: str
    provider: str
    model: str
    prompt_version: str
    output: str
    usage: TokenUsage
    cost: CostEstimate | None = None


class ModelCatalogResponse(BaseModel):
    application_id: str
    allowed_models: list[str]


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str
    retryable: bool = False


class ErrorResponse(BaseModel):
    error: ErrorDetail


class PurchaseOrder(BaseModel):
    purchase_order_id: str = Field(pattern=r"^PO-[0-9]{6}$")
    supplier: str
    currency: str = Field(min_length=3, max_length=3)
    net_amount: float = Field(ge=0)
    status: Literal["OPEN", "RELEASED", "DELIVERED", "CANCELLED"]
    created_at: str


class ODataPurchaseOrderCollection(BaseModel):
    value: list[PurchaseOrder]


class PurchaseOrderToolResponse(BaseModel):
    source: Literal["synthetic_mock"] = "synthetic_mock"
    order: PurchaseOrder

