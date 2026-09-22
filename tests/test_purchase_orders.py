from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from llm_operations_lab.main import create_app
from llm_operations_lab.orders.adapter import PurchaseOrderAdapter
from llm_operations_lab.orders.mock_api import router as mock_sap_router
from llm_operations_lab.prompts import PromptStore
from llm_operations_lab.providers.mock import DeterministicMockProvider

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.asyncio
async def test_read_only_purchase_order_tool_returns_synthetic_record(
    settings_factory,
) -> None:
    mock_app = FastAPI()
    mock_app.include_router(mock_sap_router)
    mock_client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=mock_app), base_url="http://mock"
    )
    adapter = PurchaseOrderAdapter(
        base_url="http://mock/mock-sap/odata/v1", client=mock_client
    )
    app = create_app(
        settings=settings_factory(),
        provider=DeterministicMockProvider(),
        purchase_order_adapter=adapter,
        prompts=PromptStore(PROJECT_ROOT / "prompts"),
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/v1/tools/purchase-orders/PO-100001",
            headers={"X-API-Key": "test-secret-key"},
        )
        invalid = await client.get(
            "/v1/tools/purchase-orders/not-an-order",
            headers={"X-API-Key": "test-secret-key"},
        )
        missing = await client.get(
            "/v1/tools/purchase-orders/PO-999999",
            headers={"X-API-Key": "test-secret-key"},
        )
    await mock_client.aclose()
    assert response.status_code == 200
    assert response.json()["source"] == "synthetic_mock"
    assert response.json()["order"]["purchase_order_id"] == "PO-100001"
    assert invalid.status_code == 422
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_mock_odata_subset_rejects_unsupported_filter() -> None:
    mock_app = FastAPI()
    mock_app.include_router(mock_sap_router)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=mock_app), base_url="http://mock"
    ) as client:
        response = await client.get(
            "/mock-sap/odata/v1/PurchaseOrders",
            params={"$filter": "Supplier eq 'anything'"},
        )
    assert response.status_code == 400

