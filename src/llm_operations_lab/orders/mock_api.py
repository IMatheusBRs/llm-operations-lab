from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException, Query

from llm_operations_lab.schemas import ODataPurchaseOrderCollection, PurchaseOrder

router = APIRouter(prefix="/mock-sap/odata/v1", tags=["mock-sap"])

SYNTHETIC_PURCHASE_ORDERS = {
    "PO-100001": PurchaseOrder(
        purchase_order_id="PO-100001",
        supplier="Fornecedor Sintético Alfa",
        currency="BRL",
        net_amount=12_450.0,
        status="OPEN",
        created_at="2026-01-15",
    ),
    "PO-100002": PurchaseOrder(
        purchase_order_id="PO-100002",
        supplier="Fornecedor Sintético Beta",
        currency="BRL",
        net_amount=3_799.9,
        status="DELIVERED",
        created_at="2026-02-03",
    ),
}


@router.get("/PurchaseOrders", response_model=ODataPurchaseOrderCollection)
async def list_purchase_orders(
    filter_expression: str | None = Query(default=None, alias="$filter"),
    top: int = Query(default=20, alias="$top", ge=1, le=100),
) -> ODataPurchaseOrderCollection:
    orders = list(SYNTHETIC_PURCHASE_ORDERS.values())
    if filter_expression:
        match = re.fullmatch(
            r"PurchaseOrderId\s+eq\s+'(PO-[0-9]{6})'", filter_expression
        )
        if not match:
            raise HTTPException(
                status_code=400,
                detail="mock aceita apenas: PurchaseOrderId eq 'PO-000000'",
            )
        order = SYNTHETIC_PURCHASE_ORDERS.get(match.group(1))
        orders = [order] if order else []
    return ODataPurchaseOrderCollection(value=orders[:top])


@router.get("/PurchaseOrders('{purchase_order_id}')", response_model=PurchaseOrder)
async def get_purchase_order(purchase_order_id: str) -> PurchaseOrder:
    if not re.fullmatch(r"PO-[0-9]{6}", purchase_order_id):
        raise HTTPException(status_code=400, detail="identificador inválido")
    order = SYNTHETIC_PURCHASE_ORDERS.get(purchase_order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="pedido não encontrado")
    return order

