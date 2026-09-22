from __future__ import annotations

import re

import httpx
from pydantic import TypeAdapter, ValidationError

from llm_operations_lab.errors import (
    PurchaseOrderAdapterError,
    PurchaseOrderNotFoundError,
)
from llm_operations_lab.schemas import PurchaseOrder


class PurchaseOrderAdapter:
    """Cliente somente leitura; não aceita host, URL ou operação vindos do modelo."""

    def __init__(
        self, *, base_url: str, client: httpx.AsyncClient | None = None
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = client or httpx.AsyncClient(timeout=2.0)
        self._owns_client = client is None
        self._validator = TypeAdapter(PurchaseOrder)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def get_by_id(self, purchase_order_id: str) -> PurchaseOrder:
        if not re.fullmatch(r"PO-[0-9]{6}", purchase_order_id):
            raise ValueError("purchase_order_id deve seguir o formato PO-000000")
        url = f"{self._base_url}/PurchaseOrders('{purchase_order_id}')"
        try:
            response = await self._client.get(url)
        except httpx.TransportError as exc:
            raise PurchaseOrderAdapterError("mock de pedidos indisponível") from exc
        if response.status_code == 404:
            raise PurchaseOrderNotFoundError("pedido fictício não encontrado")
        if response.status_code >= 400:
            raise PurchaseOrderAdapterError(
                f"mock de pedidos retornou status {response.status_code}"
            )
        try:
            return self._validator.validate_python(response.json())
        except (ValidationError, ValueError) as exc:
            raise PurchaseOrderAdapterError("resposta inválida do mock de pedidos") from exc

